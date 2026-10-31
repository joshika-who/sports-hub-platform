import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import Court, Document, Event, Match, Notification, User
from app.security import hash_password

logger = logging.getLogger("sportshub.seed")

DEMO_PASSWORD = "Passw0rd!"


def seed_database(db: Session) -> None:
    """
    Idempotent seed routine creating demo users, documents, events, courts,
    live/finished matches, and welcome notifications.
    """
    existing_athlete = db.query(User).filter(User.email == "athlete@demo.com").first()
    if existing_athlete:
        logger.info("Seed data already present; skipping seed.")
        return

    logger.info("Seeding Sports Hub Platform demo data...")
    pw_hash = hash_password(DEMO_PASSWORD)

    # 1. Users
    athlete1 = User(
        name="Aarav Sharma (Athlete)",
        email="athlete@demo.com",
        password_hash=pw_hash,
        role="athlete",
        profile_metrics={"height": 178, "weight": 72, "age": 22, "fitness_score": 86},
        device_token="fcm:demo_athlete1_token",
    )
    athlete2 = User(
        name="Diya Patel (Pro Athlete)",
        email="athlete2@demo.com",
        password_hash=pw_hash,
        role="athlete",
        profile_metrics={"height": 168, "weight": 61, "age": 24, "fitness_score": 92},
        device_token="apns:demo_athlete2_token",
    )
    organizer = User(
        name="Vikram Rao (Organizer)",
        email="organizer@demo.com",
        password_hash=pw_hash,
        role="organizer",
        profile_metrics={"height": 180, "weight": 78, "age": 34, "fitness_score": 80},
    )
    referee = User(
        name="Kabir Sen (Head Referee)",
        email="referee@demo.com",
        password_hash=pw_hash,
        role="referee",
        profile_metrics={"height": 176, "weight": 74, "age": 31, "fitness_score": 85},
    )

    db.add_all([athlete1, athlete2, organizer, referee])
    db.flush()

    # 2. Documents
    # athlete@demo.com has ONLY verified ID (missing MEDICAL & WAIVER for strict events)
    docs = [
        Document(
            user_id=athlete1.id,
            doc_type="ID",
            storage_url="uploads/seed_athlete1_id.pdf",
            is_verified=True,
        ),
        # athlete2@demo.com has all 3 documents verified
        Document(
            user_id=athlete2.id,
            doc_type="ID",
            storage_url="uploads/seed_athlete2_id.pdf",
            is_verified=True,
        ),
        Document(
            user_id=athlete2.id,
            doc_type="MEDICAL",
            storage_url="uploads/seed_athlete2_medical.pdf",
            is_verified=True,
        ),
        Document(
            user_id=athlete2.id,
            doc_type="WAIVER",
            storage_url="uploads/seed_athlete2_waiver.pdf",
            is_verified=True,
        ),
    ]
    db.add_all(docs)

    # 3. Events (6 events across football, badminton, tennis, basketball)
    now = datetime.now(timezone.utc).replace(tzinfo=None, minute=0, second=0, microsecond=0)
    events = [
        Event(
            sport_name="Badminton",
            title="City Open Badminton Championship 2026",
            venue="Smash Arena Indoor Stadium, Court Complex A",
            organizer_id=organizer.id,
            date_time=now + timedelta(days=5, hours=4),
            entry_fee=49900,  # ₹499.00
            capacity=32,
            mandatory_requirements=["MIN_AGE:16", "ID", "MEDICAL"],
        ),
        Event(
            sport_name="Football",
            title="Metro 7v7 Floodlit Football Cup",
            venue="Greenfield Turf Park, Main Pitch",
            organizer_id=organizer.id,
            date_time=now + timedelta(days=7, hours=6),
            entry_fee=75000,  # ₹750.00
            capacity=16,
            mandatory_requirements=["MIN_AGE:18", "ID"],
        ),
        Event(
            sport_name="Tennis",
            title="Grand Slam Hardcourt Challengers Series",
            venue="Ace Tennis Academy, Center Court",
            organizer_id=organizer.id,
            date_time=now + timedelta(days=10, hours=3),
            entry_fee=99900,  # ₹999.00
            capacity=24,
            mandatory_requirements=["MIN_AGE:18", "ID", "MEDICAL", "WAIVER"],
        ),
        Event(
            sport_name="Basketball",
            title="3x3 Streetball Pro-Am Showdown",
            venue="Skyline Hoops Dome",
            organizer_id=organizer.id,
            date_time=now + timedelta(days=3, hours=5),
            entry_fee=0,  # Free community tournament (instant confirmation!)
            capacity=20,
            mandatory_requirements=["MIN_AGE:16", "ID"],
        ),
        Event(
            sport_name="Badminton",
            title="Masters Senior Badminton Invitational (25+)",
            venue="Smash Arena Indoor Stadium, Hall B",
            organizer_id=organizer.id,
            date_time=now + timedelta(days=12, hours=2),
            entry_fee=59900,  # ₹599.00
            capacity=16,
            mandatory_requirements=["MIN_AGE:25", "ID", "MEDICAL"],
        ),
        Event(
            sport_name="Football",
            title="Elite Premier Futsal League Qualifiers",
            venue="Apex Indoor Arena",
            organizer_id=organizer.id,
            date_time=now + timedelta(days=14, hours=7),
            entry_fee=65000,  # ₹650.00
            capacity=16,
            mandatory_requirements=["MIN_AGE:18", "ID", "WAIVER"],
        ),
    ]
    db.add_all(events)
    db.flush()

    # 4. Courts (5 courts across sports)
    courts = [
        Court(
            name="Pro Synthetic Court 1 (BWF Grade)",
            sport_name="Badminton",
            venue="Smash Arena Indoor Stadium",
            hourly_price=40000,  # ₹400/hr
        ),
        Court(
            name="Pro Synthetic Court 2 (BWF Grade)",
            sport_name="Badminton",
            venue="Smash Arena Indoor Stadium",
            hourly_price=40000,
        ),
        Court(
            name="Championship Acrylic Hard Court 1",
            sport_name="Tennis",
            venue="Ace Tennis Academy",
            hourly_price=60000,  # ₹600/hr
        ),
        Court(
            name="FIFA Quality Pro 5v5 Turf Pitch",
            sport_name="Football",
            venue="Greenfield Turf Park",
            hourly_price=120000,  # ₹1200/hr
        ),
        Court(
            name="FIBA Maple Hardwood Full Court",
            sport_name="Basketball",
            venue="Skyline Hoops Dome",
            hourly_price=90000,  # ₹900/hr
        ),
    ]
    db.add_all(courts)
    db.flush()

    # 5. Live & Finished Matches
    matches = [
        Match(
            tournament_id=events[0].id,
            team_a="Bangalore Smashers",
            team_b="Hyderabad Falcons",
            court_number=1,
            start_time=now - timedelta(minutes=25),
            score_a=18,
            score_b=16,
            status="LIVE",
        ),
        Match(
            tournament_id=events[1].id,
            team_a="Westside United FC",
            team_b="Deccan Strikers",
            court_number=2,
            start_time=now - timedelta(minutes=40),
            score_a=2,
            score_b=2,
            status="LIVE",
        ),
        Match(
            tournament_id=events[3].id,
            team_a="Metro Ballers",
            team_b="Thunder Hoops",
            court_number=1,
            start_time=now - timedelta(hours=3),
            score_a=21,
            score_b=17,
            status="FINISHED",
        ),
    ]
    db.add_all(matches)

    # 6. Welcome Notification for demo athlete
    welcome_notif = Notification(
        user_id=athlete1.id,
        title="Welcome to Sports Hub Platform!",
        body="Your Government ID is verified. Upload your Medical Certificate in the Document Vault to unlock Championship tournaments.",
        kind="SYSTEM_WELCOME",
        read=False,
    )
    db.add(welcome_notif)

    db.commit()
    logger.info("Seed data successfully initialized.")


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_database(session)

