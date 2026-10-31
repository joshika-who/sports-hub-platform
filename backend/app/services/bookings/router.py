from datetime import date, datetime, time as dt_time, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cache import cache
from app.db import get_db
from app.models import Booking, Court, User
from app.schemas import (
    BookingCreateRequest,
    BookingResponse,
    CourtResponse,
    SlotAvailabilityItem,
)
from app.security import get_current_user

router = APIRouter(prefix="/api/v1", tags=["Court Bookings"])

LOCK_TTL_SECONDS = 300  # 5 minutes


def normalize_slot_dt(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(minute=0, second=0, microsecond=0)


def build_court_lock_key(court_id: str, slot_start: datetime) -> str:
    norm = normalize_slot_dt(slot_start)
    return f"lock:court:{court_id}:{norm.strftime('%Y-%m-%dT%H:%M:%S')}"


def _enrich_booking(db: Session, booking: Booking) -> BookingResponse:
    court = db.query(Court).filter(Court.id == booking.court_id).first()
    return BookingResponse(
        id=booking.id,
        user_id=booking.user_id,
        court_id=booking.court_id,
        court_name=court.name if court else None,
        venue=court.venue if court else None,
        hourly_price=court.hourly_price if court else None,
        slot_start=booking.slot_start,
        slot_end=booking.slot_end,
        payment_status=booking.payment_status,
        created_at=booking.created_at,
    )


@router.get("/courts", response_model=List[CourtResponse])
@router.get("/bookings/courts", response_model=List[CourtResponse], include_in_schema=False)
def list_courts(
    sport: Optional[str] = Query(None, description="Optional sport filter"),
    db: Session = Depends(get_db),
):
    q = db.query(Court)
    if sport:
        q = q.filter(Court.sport_name.ilike(sport.strip()))
    courts = q.order_by(Court.name.asc()).all()
    return [CourtResponse.model_validate(c) for c in courts]


@router.get("/courts/{court_id}/availability", response_model=List[SlotAvailabilityItem])
@router.get("/bookings/courts/{court_id}/availability", response_model=List[SlotAvailabilityItem], include_in_schema=False)
def get_court_availability(
    court_id: str,
    date_str: str = Query(..., alias="date", description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_db),
):
    court = db.query(Court).filter(Court.id == court_id).first()
    if not court:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Court not found.")

    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid date format. Expected YYYY-MM-DD.",
        )

    day_start = datetime.combine(target_date, dt_time(0, 0, 0))
    day_end = day_start + timedelta(days=1)

    existing_bookings = (
        db.query(Booking)
        .filter(
            Booking.court_id == court_id,
            Booking.slot_start >= day_start,
            Booking.slot_start < day_end,
            Booking.payment_status.in_(["PENDING", "CONFIRMED"]),
        )
        .all()
    )
    booked_map = {normalize_slot_dt(b.slot_start): b.payment_status for b in existing_bookings}

    slots: List[SlotAvailabilityItem] = []
    for hour in range(6, 22):  # 06:00 to 22:00 hourly slots
        s_start = datetime.combine(target_date, dt_time(hour, 0, 0))
        s_end = s_start + timedelta(hours=1)
        lock_key = build_court_lock_key(court_id, s_start)
        locked = cache.get(lock_key) is not None

        if s_start in booked_map:
            b_status = booked_map[s_start]
            slot_status = "BOOKED" if b_status == "CONFIRMED" else "LOCKED"
            available = False
        elif locked:
            slot_status = "LOCKED"
            available = False
        else:
            slot_status = "AVAILABLE"
            available = True

        slots.append(
            SlotAvailabilityItem(
                slot_start=s_start,
                slot_end=s_end,
                label=f"{s_start.strftime('%H:%M')} - {s_end.strftime('%H:%M')}",
                available=available,
                status=slot_status,
            )
        )
    return slots


@router.post("/bookings", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    court = db.query(Court).filter(Court.id == payload.court_id).first()
    if not court:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Court not found.")

    slot_start = normalize_slot_dt(payload.slot_start)
    slot_end = (
        normalize_slot_dt(payload.slot_end)
        if payload.slot_end
        else slot_start + timedelta(hours=1)
    )

    lock_key = build_court_lock_key(court.id, slot_start)

    # 1. Acquire atomic lock with 5-minute TTL (SETNX)
    lock_acquired = cache.setnx(lock_key, current_user.id, ex=LOCK_TTL_SECONDS)
    if not lock_acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This court slot is currently locked or already booked.",
        )

    # 2. Check DB for existing active booking on this slot
    existing = (
        db.query(Booking)
        .filter(
            Booking.court_id == court.id,
            Booking.slot_start == slot_start,
        )
        .first()
    )
    if existing and existing.payment_status in ("PENDING", "CONFIRMED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Court slot is already booked.",
        )

    try:
        if existing and existing.payment_status == "FAILED":
            existing.user_id = current_user.id
            existing.slot_end = slot_end
            existing.payment_status = "PENDING"
            booking = existing
        else:
            booking = Booking(
                user_id=current_user.id,
                court_id=court.id,
                slot_start=slot_start,
                slot_end=slot_end,
                payment_status="PENDING",
            )
            db.add(booking)
        db.commit()
        db.refresh(booking)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Double booking detected for this court and slot.",
        )

    return _enrich_booking(db, booking)


@router.get("/bookings/me", response_model=List[BookingResponse])
def list_my_bookings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bookings = (
        db.query(Booking)
        .filter(Booking.user_id == current_user.id)
        .order_by(Booking.slot_start.desc())
        .all()
    )
    return [_enrich_booking(db, b) for b in bookings]

