from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Event, Registration, User
from app.schemas import (
    EligibilityResponse,
    EventCreateRequest,
    EventResponse,
    RegistrationResponse,
)
from app.security import get_current_user, get_optional_user, require_role
from app.services.events.eligibility import evaluate_event_eligibility
from app.services.notifications.dispatcher import NotificationDispatcher

router = APIRouter(prefix="/api/v1/events", tags=["Events & Eligibility"])


def _enrich_event(
    db: Session,
    event: Event,
    current_user: Optional[User] = None,
) -> EventResponse:
    reg_count = (
        db.query(func.count(Registration.id))
        .filter(
            Registration.event_id == event.id,
            Registration.status.in_(["PENDING_PAYMENT", "CONFIRMED"]),
        )
        .scalar()
        or 0
    )
    eligible_flag: Optional[bool] = None
    if current_user is not None:
        eligible_flag = evaluate_event_eligibility(db, current_user, event).eligible

    return EventResponse(
        id=event.id,
        sport_name=event.sport_name,
        title=event.title,
        venue=event.venue,
        organizer_id=event.organizer_id,
        date_time=event.date_time,
        entry_fee=event.entry_fee,
        capacity=event.capacity,
        mandatory_requirements=list(event.mandatory_requirements or []),
        registered_count=reg_count,
        eligible=eligible_flag,
    )


@router.get("", response_model=List[EventResponse])
def list_events(
    sport: Optional[str] = Query(None, description="Filter by sport_name"),
    date_from: Optional[datetime] = Query(None, description="Start of date range"),
    date_to: Optional[datetime] = Query(None, description="End of date range"),
    search: Optional[str] = Query(None, description="Search title, sport, or venue"),
    eligible_only: bool = Query(False, description="Only return events the logged-in user is eligible for"),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    query = db.query(Event)
    if sport:
        query = query.filter(func.lower(Event.sport_name) == sport.strip().lower())
    if date_from:
        query = query.filter(Event.date_time >= date_from)
    if date_to:
        query = query.filter(Event.date_time <= date_to)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            (Event.title.ilike(pattern))
            | (Event.venue.ilike(pattern))
            | (Event.sport_name.ilike(pattern))
        )

    events = query.order_by(Event.date_time.asc()).all()

    if eligible_only and current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required when filtering with eligible_only=true.",
        )

    results: List[EventResponse] = []
    for ev in events:
        enriched = _enrich_event(db, ev, current_user)
        if eligible_only and not enriched.eligible:
            continue
        results.append(enriched)
    return results


@router.get("/registrations/me", response_model=List[RegistrationResponse])
def list_my_registrations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    regs = (
        db.query(Registration)
        .filter(Registration.user_id == current_user.id)
        .all()
    )
    return [RegistrationResponse.model_validate(r) for r in regs]


@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")
    return _enrich_event(db, event, current_user)


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreateRequest,
    organizer: User = Depends(require_role("organizer")),
    db: Session = Depends(get_db),
):
    event = Event(
        sport_name=payload.sport_name.strip(),
        title=payload.title.strip(),
        venue=payload.venue.strip(),
        organizer_id=organizer.id,
        date_time=payload.date_time,
        entry_fee=payload.entry_fee,
        capacity=payload.capacity,
        mandatory_requirements=payload.mandatory_requirements,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return _enrich_event(db, event, organizer)


@router.get("/{event_id}/eligibility", response_model=EligibilityResponse)
def check_eligibility(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")
    return evaluate_event_eligibility(db, current_user, event)


@router.post("/{event_id}/register", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
def register_for_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")

    eligibility = evaluate_event_eligibility(db, current_user, event)
    if not eligibility.eligible:
        failed_msgs = [c.message for c in eligibility.checks if not c.passed]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Not eligible for this event: " + "; ".join(failed_msgs),
                "eligible": False,
                "checks": [c.model_dump() for c in eligibility.checks],
            },
        )

    existing = (
        db.query(Registration)
        .filter(
            Registration.event_id == event.id,
            Registration.user_id == current_user.id,
            Registration.status.in_(["PENDING_PAYMENT", "CONFIRMED"]),
        )
        .first()
    )
    if existing:
        return RegistrationResponse.model_validate(existing)

    active_count = (
        db.query(func.count(Registration.id))
        .filter(
            Registration.event_id == event.id,
            Registration.status.in_(["PENDING_PAYMENT", "CONFIRMED"]),
        )
        .scalar()
        or 0
    )
    if active_count >= event.capacity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Event has reached maximum capacity.",
        )

    initial_status = "CONFIRMED" if event.entry_fee == 0 else "PENDING_PAYMENT"
    reg = Registration(
        event_id=event.id,
        user_id=current_user.id,
        status=initial_status,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)

    if initial_status == "CONFIRMED":
        NotificationDispatcher.dispatch(
            db=db,
            user_id=current_user.id,
            title="Registration Confirmed",
            body=f"You are confirmed for {event.title} at {event.venue}!",
            kind="REGISTRATION_CONFIRMED",
        )

    return RegistrationResponse.model_validate(reg)

