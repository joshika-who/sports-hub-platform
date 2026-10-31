from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Event, Match, Registration, User
from app.schemas import (
    MatchResponse,
    SchedulerGenerateRequest,
    SchedulerGenerateResponse,
)
from app.security import require_role
from app.services.notifications.dispatcher import NotificationDispatcher
from app.services.scheduler.solver import solve_tournament_schedule

router = APIRouter(prefix="/api/v1/scheduler", tags=["AI Tournament Scheduler"])


@router.post("/generate", response_model=SchedulerGenerateResponse)
def generate_schedule(payload: SchedulerGenerateRequest):
    return solve_tournament_schedule(payload)


@router.post(
    "/generate/{event_id}/commit",
    response_model=List[MatchResponse],
    status_code=status.HTTP_201_CREATED,
)
def generate_and_commit_schedule(
    event_id: str,
    payload: SchedulerGenerateRequest,
    organizer: User = Depends(require_role("organizer")),
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")

    solved = solve_tournament_schedule(payload)

    # Replace existing scheduled matches for this tournament
    db.query(Match).filter(
        Match.tournament_id == event.id,
        Match.status == "SCHEDULED",
    ).delete()

    created_matches: List[Match] = []
    for item in solved.timetable:
        m = Match(
            tournament_id=event.id,
            team_a=item.team_a,
            team_b=item.team_b,
            court_number=item.court_number,
            start_time=item.start_time,
            score_a=0,
            score_b=0,
            status="SCHEDULED",
        )
        db.add(m)
        created_matches.append(m)

    db.commit()
    for m in created_matches:
        db.refresh(m)

    # Notify confirmed/registered athletes + organizer of MATCH_SCHEDULE_UPDATED
    regs = (
        db.query(Registration)
        .filter(Registration.event_id == event.id)
        .all()
    )
    recipient_ids = {r.user_id for r in regs} | {organizer.id}
    for uid in recipient_ids:
        NotificationDispatcher.dispatch(
            db=db,
            user_id=uid,
            title="Match Schedule Published",
            body=f"Conflict-free schedule ({len(created_matches)} matches) committed for '{event.title}'.",
            kind="MATCH_SCHEDULE_UPDATED",
        )

    return [
        MatchResponse(
            id=m.id,
            tournament_id=m.tournament_id,
            event_title=event.title,
            sport_name=event.sport_name,
            team_a=m.team_a,
            team_b=m.team_b,
            court_number=m.court_number,
            start_time=m.start_time,
            score_a=m.score_a,
            score_b=m.score_b,
            status=m.status,
        )
        for m in created_matches
    ]

