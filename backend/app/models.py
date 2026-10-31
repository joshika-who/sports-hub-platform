import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False, default="athlete")  # athlete|coach|organizer|referee
    profile_metrics = Column(
        JSON,
        nullable=False,
        default=lambda: {"height": 175, "weight": 70, "age": 22, "fitness_score": 80},
    )
    device_token = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    doc_type = Column(String(32), nullable=False)  # ID|MEDICAL|WAIVER
    storage_url = Column(String(512), nullable=False)
    is_verified = Column(Boolean, nullable=False, default=False)
    uploaded_at = Column(DateTime, nullable=False, default=utc_now)

    user = relationship("User", back_populates="documents")


class Event(Base):
    __tablename__ = "events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    sport_name = Column(String(64), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    venue = Column(String(200), nullable=False)
    organizer_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    date_time = Column(DateTime, nullable=False, index=True)
    entry_fee = Column(Integer, nullable=False, default=0)  # Stored in integer paise/cents (e.g. 50000 = ₹500.00)
    capacity = Column(Integer, nullable=False, default=32)
    mandatory_requirements = Column(JSON, nullable=False, default=list)


class Registration(Base):
    __tablename__ = "registrations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="PENDING_PAYMENT")  # PENDING_PAYMENT|CONFIRMED|CANCELLED
    payment_id = Column(String(36), nullable=True)


class Court(Base):
    __tablename__ = "courts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(120), nullable=False)
    sport_name = Column(String(64), nullable=False, index=True)
    venue = Column(String(200), nullable=False)
    hourly_price = Column(Integer, nullable=False, default=50000)  # integer paise


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint("court_id", "slot_start", name="uq_booking_court_slot_start"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    court_id = Column(String(36), ForeignKey("courts.id", ondelete="CASCADE"), nullable=False, index=True)
    slot_start = Column(DateTime, nullable=False, index=True)
    slot_end = Column(DateTime, nullable=False)
    payment_status = Column(String(32), nullable=False, default="PENDING")  # PENDING|CONFIRMED|FAILED
    created_at = Column(DateTime, nullable=False, default=utc_now)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(String(32), nullable=False)  # BOOKING|REGISTRATION
    ref_id = Column(String(36), nullable=False, index=True)
    gateway = Column(String(32), nullable=False)  # stripe|razorpay|phonepe|mock
    amount = Column(Integer, nullable=False)
    currency = Column(String(16), nullable=False, default="INR")
    gateway_order_id = Column(String(128), unique=True, index=True, nullable=False)
    status = Column(String(32), nullable=False, default="PENDING")  # PENDING|SUCCESS|FAILED
    created_at = Column(DateTime, nullable=False, default=utc_now)


class Match(Base):
    __tablename__ = "matches"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tournament_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    team_a = Column(String(120), nullable=False)
    team_b = Column(String(120), nullable=False)
    court_number = Column(Integer, nullable=False, default=1)
    start_time = Column(DateTime, nullable=False, index=True)
    score_a = Column(Integer, nullable=False, default=0)
    score_b = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="SCHEDULED")  # SCHEDULED|LIVE|FINISHED


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    body = Column(String(1000), nullable=False)
    kind = Column(String(64), nullable=False)
    sent_at = Column(DateTime, nullable=False, default=utc_now)
    read = Column(Boolean, nullable=False, default=False)

