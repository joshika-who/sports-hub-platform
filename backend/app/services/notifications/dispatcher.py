import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Match, Notification, Registration, User
from app.services.notifications.apns import send_apns_push
from app.services.notifications.fcm import send_fcm_push

logger = logging.getLogger("sportshub.notifications")


class NotificationDispatcher:
    """
    Dispatches notifications to the `notifications` table and (in live mode)
    routes to FCM HTTP v1 or APNs depending on user device_token prefix.
    """

    @staticmethod
    def dispatch(
        db: Session,
        user_id: str,
        title: str,
        body: str,
        kind: str,
    ) -> Notification:
        notif = Notification(
            user_id=user_id,
            title=title,
            body=body,
            kind=kind,
            read=False,
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)

        user = db.query(User).filter(User.id == user_id).first()
        token = user.device_token if user else None

        if settings.NOTIFY_MODE.lower() == "live" and token:
            if token.startswith(("apns:", "ios:")):
                send_apns_push(token, title, body, {"kind": kind, "notification_id": notif.id})
            else:
                send_fcm_push(token, title, body, {"kind": kind, "notification_id": notif.id})
        else:
            logger.info(
                "[MOCK PUSH] user=%s kind=%s title=%r body=%r",
                user_id,
                kind,
                title,
                body,
            )

        return notif


def check_and_send_match_reminders(db: Session) -> int:
    """
    Checks for scheduled matches starting within the next 60 minutes and dispatches
    a MATCH_REMINDER notification to confirmed participants of that tournament.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    one_hour_later = now + timedelta(hours=1)

    upcoming_matches = (
        db.query(Match)
        .filter(
            Match.status == "SCHEDULED",
            Match.start_time >= now,
            Match.start_time <= one_hour_later,
        )
        .all()
    )

    sent_count = 0
    for match in upcoming_matches:
        regs = (
            db.query(Registration)
            .filter(
                Registration.event_id == match.tournament_id,
                Registration.status == "CONFIRMED",
            )
            .all()
        )
        for reg in regs:
            marker_title = f"Upcoming Match Reminder: {match.team_a} vs {match.team_b}"
            already_sent = (
                db.query(Notification)
                .filter(
                    Notification.user_id == reg.user_id,
                    Notification.kind == "MATCH_REMINDER",
                    Notification.title == marker_title,
                )
                .first()
            )
            if not already_sent:
                NotificationDispatcher.dispatch(
                    db=db,
                    user_id=reg.user_id,
                    title=marker_title,
                    body=(
                        f"Your tournament match ({match.team_a} vs {match.team_b}) starts at "
                        f"{match.start_time.strftime('%H:%M')} on Court {match.court_number}."
                    ),
                    kind="MATCH_REMINDER",
                )
                sent_count += 1
    return sent_count


async def match_reminder_background_task() -> None:
    """Background loop triggered in FastAPI lifespan that checks every 60s for 1-hour match reminders."""
    while True:
        try:
            with SessionLocal() as db:
                check_and_send_match_reminders(db)
        except Exception as exc:
            logger.warning("Match reminder background check error: %s", exc)
        await asyncio.sleep(60)

