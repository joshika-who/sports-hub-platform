import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Event, Match, User
from app.schemas import MatchResponse, ScoreUpdateRequest
from app.security import require_role

logger = logging.getLogger("sportshub.live")

router = APIRouter(tags=["Live Scores"])


class LiveConnectionManager:
    """Manages active WebSocket connections and broadcasts real-time score updates safely."""

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        stale: List[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)
        for dead in stale:
            self.disconnect(dead)


manager = LiveConnectionManager()


def _enrich_match(db: Session, match: Match) -> MatchResponse:
    event = db.query(Event).filter(Event.id == match.tournament_id).first()
    return MatchResponse(
        id=match.id,
        tournament_id=match.tournament_id,
        event_title=event.title if event else "Championship Match",
        sport_name=event.sport_name if event else "Sports",
        team_a=match.team_a,
        team_b=match.team_b,
        court_number=match.court_number,
        start_time=match.start_time,
        score_a=match.score_a,
        score_b=match.score_b,
        status=match.status,
    )


@router.get("/api/v1/live/matches", response_model=List[MatchResponse])
def list_live_matches(
    tournament_id: Optional[str] = Query(None, description="Optional tournament/event ID filter"),
    status_filter: Optional[str] = Query(None, alias="status", description="Optional status filter"),
    db: Session = Depends(get_db),
):
    q = db.query(Match)
    if tournament_id:
        q = q.filter(Match.tournament_id == tournament_id)
    if status_filter:
        q = q.filter(Match.status == status_filter.upper())
    matches = q.order_by(Match.start_time.asc()).all()
    return [_enrich_match(db, m) for m in matches]


@router.put("/api/v1/live/matches/{match_id}/score", response_model=MatchResponse)
async def update_match_score(
    match_id: str,
    payload: ScoreUpdateRequest,
    _official: User = Depends(require_role("referee", "organizer")),
    db: Session = Depends(get_db),
):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )

    match.score_a = payload.score_a
    match.score_b = payload.score_b
    if payload.status:
        match.status = payload.status
    db.add(match)
    db.commit()
    db.refresh(match)

    enriched = _enrich_match(db, match)
    broadcast_payload = {
        "type": "SCORE_UPDATE",
        "match": enriched.model_dump(mode="json"),
    }
    await manager.broadcast(broadcast_payload)
    return enriched


@router.websocket("/ws/live")
@router.websocket("/api/v1/live/ws")
async def websocket_live_scores(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({"type": "CONNECTED", "message": "Subscribed to live score stream"})
        while True:
            # Keep connection alive and handle optional ping messages from client
            msg = await websocket.receive_text()
            if msg.strip().lower() == "ping":
                await websocket.send_json({"type": "PONG"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

