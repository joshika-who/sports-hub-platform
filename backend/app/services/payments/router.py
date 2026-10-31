from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.cache import cache
from app.config import settings
from app.db import get_db
from app.models import Booking, Court, Event, Payment, Registration, User
from app.schemas import (
    PaymentIntentRequest,
    PaymentIntentResponse,
    PaymentStatusResponse,
)
from app.security import get_current_user
from app.services.bookings.router import build_court_lock_key
from app.services.notifications.dispatcher import NotificationDispatcher
from app.services.payments.base import PaymentGateway
from app.services.payments.mock_gw import MockGateway
from app.services.payments.phonepe_gw import PhonePeGateway
from app.services.payments.razorpay_gw import RazorpayGateway
from app.services.payments.stripe_gw import StripeGateway

router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


def get_gateway_adapter(gateway_name: str, for_webhook: bool = False) -> PaymentGateway:
    gw = gateway_name.lower().strip()
    if settings.PAYMENT_MODE.lower() != "live" and not for_webhook:
        return MockGateway(label=gw)

    if gw == "stripe":
        return StripeGateway()
    if gw == "razorpay":
        return RazorpayGateway()
    if gw == "phonepe":
        return PhonePeGateway()
    return MockGateway(label=gw)


def on_payment_success(db: Session, payment: Payment) -> PaymentStatusResponse:
    """
    Idempotently marks a Payment as SUCCESS, updates the linked Booking or Registration
    to CONFIRMED, releases court lock if applicable, and dispatches a push notification.
    """
    if payment.status == "SUCCESS":
        return PaymentStatusResponse(
            payment_id=payment.id,
            status=payment.status,
            purpose=payment.purpose,
            ref_id=payment.ref_id,
            gateway_order_id=payment.gateway_order_id,
        )

    payment.status = "SUCCESS"
    db.add(payment)

    if payment.purpose == "REGISTRATION":
        reg = db.query(Registration).filter(Registration.id == payment.ref_id).first()
        if reg:
            reg.status = "CONFIRMED"
            reg.payment_id = payment.id
            db.add(reg)
            event = db.query(Event).filter(Event.id == reg.event_id).first()
            event_title = event.title if event else "Tournament Event"
            NotificationDispatcher.dispatch(
                db=db,
                user_id=payment.user_id,
                title="Event Registration Confirmed",
                body=f"Payment of ₹{payment.amount / 100:.2f} received. Your spot in '{event_title}' is confirmed!",
                kind="REGISTRATION_CONFIRMED",
            )

    elif payment.purpose == "BOOKING":
        booking = db.query(Booking).filter(Booking.id == payment.ref_id).first()
        if booking:
            booking.payment_status = "CONFIRMED"
            db.add(booking)
            # Release the temporary Redis/in-memory lock now that DB booking is confirmed
            lock_key = build_court_lock_key(booking.court_id, booking.slot_start)
            cache.delete(lock_key)

            court = db.query(Court).filter(Court.id == booking.court_id).first()
            court_name = court.name if court else "Court"
            NotificationDispatcher.dispatch(
                db=db,
                user_id=payment.user_id,
                title="Court Booking Confirmed",
                body=f"Your booking for {court_name} on {booking.slot_start.strftime('%Y-%m-%d %H:%M')} is confirmed!",
                kind="BOOKING_CONFIRMED",
            )

    db.commit()
    db.refresh(payment)
    return PaymentStatusResponse(
        payment_id=payment.id,
        status=payment.status,
        purpose=payment.purpose,
        ref_id=payment.ref_id,
        gateway_order_id=payment.gateway_order_id,
    )


@router.post("/create-intent", response_model=PaymentIntentResponse, status_code=status.HTTP_201_CREATED)
def create_payment_intent(
    payload: PaymentIntentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    amount = 0
    currency = "INR"

    if payload.purpose == "REGISTRATION":
        reg = db.query(Registration).filter(Registration.id == payload.ref_id).first()
        if not reg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registration not found.")
        event = db.query(Event).filter(Event.id == reg.event_id).first()
        amount = event.entry_fee if event and event.entry_fee > 0 else 50000
    elif payload.purpose == "BOOKING":
        booking = db.query(Booking).filter(Booking.id == payload.ref_id).first()
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
        court = db.query(Court).filter(Court.id == booking.court_id).first()
        amount = court.hourly_price if court and court.hourly_price > 0 else 50000

    adapter = get_gateway_adapter(payload.gateway, for_webhook=False)
    order_res = adapter.create_order(
        amount=amount,
        currency=currency,
        purpose=payload.purpose,
        ref_id=payload.ref_id,
    )

    payment = Payment(
        user_id=current_user.id,
        purpose=payload.purpose,
        ref_id=payload.ref_id,
        gateway=payload.gateway.lower(),
        amount=amount,
        currency=currency,
        gateway_order_id=order_res.gateway_order_id,
        status="PENDING",
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    return PaymentIntentResponse(
        payment_id=payment.id,
        gateway=payment.gateway,
        order_id=payment.gateway_order_id,
        amount=payment.amount,
        currency=payment.currency,
        mode=settings.PAYMENT_MODE.lower(),
        checkout_url_or_token=order_res.checkout_url_or_token,
    )


@router.post("/mock/complete/{payment_id}", response_model=PaymentStatusResponse)
def mock_complete_payment(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if settings.PAYMENT_MODE.lower() != "mock":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mock payment completion is only enabled when PAYMENT_MODE=mock.",
        )

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment record not found.")

    return on_payment_success(db, payment)


@router.post("/webhook/{gateway}", response_model=PaymentStatusResponse)
async def payment_webhook(
    gateway: str,
    request: Request,
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    gw = gateway.lower().strip()
    # If signature headers are present for stripe/razorpay/phonepe, verify with real adapter;
    # otherwise if PAYMENT_MODE=mock and gateway=='mock', use MockGateway.
    if gw in ("stripe", "razorpay", "phonepe") and (
        "stripe-signature" in headers
        or "x-razorpay-signature" in headers
        or "x-verify" in headers
        or settings.PAYMENT_MODE.lower() == "live"
    ):
        adapter = get_gateway_adapter(gw, for_webhook=True)
    else:
        adapter = MockGateway(label=gw)

    try:
        gateway_order_id = adapter.verify_webhook(headers, raw_body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    payment = db.query(Payment).filter(Payment.gateway_order_id == gateway_order_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with gateway_order_id '{gateway_order_id}' not found.",
        )

    return on_payment_success(db, payment)

