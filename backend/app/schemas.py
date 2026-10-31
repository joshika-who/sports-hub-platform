from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Auth & User Schemas ---
class ProfileMetrics(BaseModel):
    height: Optional[float] = 175
    weight: Optional[float] = 70
    age: int = 22
    fitness_score: Optional[int] = 80


class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: Literal["athlete", "coach", "organizer", "referee"] = "athlete"
    profile_metrics: Optional[ProfileMetrics] = None


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class DeviceTokenRequest(BaseModel):
    device_token: str = Field(..., min_length=4, max_length=512)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    role: str
    profile_metrics: Dict[str, Any]
    device_token: Optional[str] = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# --- Document Vault Schemas ---
class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    doc_type: str
    storage_url: str
    is_verified: bool
    uploaded_at: datetime


# --- Event & Eligibility Schemas ---
class EventCreateRequest(BaseModel):
    sport_name: str = Field(..., min_length=2, max_length=64)
    title: str = Field(..., min_length=3, max_length=200)
    venue: str = Field(..., min_length=2, max_length=200)
    date_time: datetime
    entry_fee: int = Field(0, ge=0, description="Entry fee in paise/cents (e.g. 50000 = 500.00)")
    capacity: int = Field(32, ge=2)
    mandatory_requirements: List[str] = Field(default_factory=list)


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sport_name: str
    title: str
    venue: str
    organizer_id: str
    date_time: datetime
    entry_fee: int
    capacity: int
    mandatory_requirements: List[str]
    registered_count: int = 0
    eligible: Optional[bool] = None


class EligibilityCheckItem(BaseModel):
    requirement: str
    passed: bool
    message: str


class EligibilityResponse(BaseModel):
    eligible: bool
    checks: List[EligibilityCheckItem]


class RegistrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    user_id: str
    status: str
    payment_id: Optional[str] = None


# --- Court & Booking Schemas ---
class CourtResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    sport_name: str
    venue: str
    hourly_price: int


class SlotAvailabilityItem(BaseModel):
    slot_start: datetime
    slot_end: datetime
    label: str
    available: bool
    status: str  # AVAILABLE | LOCKED | BOOKED


class BookingCreateRequest(BaseModel):
    court_id: str
    slot_start: datetime
    slot_end: Optional[datetime] = None


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    court_id: str
    court_name: Optional[str] = None
    venue: Optional[str] = None
    hourly_price: Optional[int] = None
    slot_start: datetime
    slot_end: datetime
    payment_status: str
    created_at: datetime


# --- Payment Schemas ---
class PaymentIntentRequest(BaseModel):
    purpose: Literal["BOOKING", "REGISTRATION"]
    ref_id: str
    gateway: Literal["stripe", "razorpay", "phonepe", "mock"] = "stripe"


class PaymentIntentResponse(BaseModel):
    payment_id: str
    gateway: str
    order_id: str
    amount: int
    currency: str
    mode: str
    checkout_url_or_token: str


class PaymentStatusResponse(BaseModel):
    payment_id: str
    status: str
    purpose: str
    ref_id: str
    gateway_order_id: str


# --- Notification Schemas ---
class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    body: str
    kind: str
    sent_at: datetime
    read: bool


# --- Injury AI Schemas ---
class InjuryQueryRequest(BaseModel):
    question: Optional[str] = Field(None, max_length=2000)
    query: Optional[str] = Field(None, max_length=2000)
    user_query: Optional[str] = Field(None, max_length=2000)
    sport: Optional[str] = None
    history: Optional[str] = None

    def resolved_query(self) -> str:
        base = (self.question or self.query or self.user_query or "").strip()
        parts = [p for p in [self.sport, base, self.history] if p]
        return " | ".join(parts) if parts else base


# --- Scheduler Schemas ---
class SchedulerGenerateRequest(BaseModel):
    teams: List[str] = Field(..., min_length=2)
    num_courts: int = Field(2, ge=1, le=20)
    match_duration_minutes: int = Field(60, ge=15, le=240)
    start_time: datetime
    min_rest_slots: int = Field(1, ge=0, le=10)
    format: Literal["round_robin", "single_elimination"] = "round_robin"


class ScheduledMatchItem(BaseModel):
    match_index: int
    team_a: str
    team_b: str
    court_number: int
    slot_index: int
    start_time: datetime
    end_time: datetime


class SchedulerGenerateResponse(BaseModel):
    format: str
    total_matches: int
    makespan_slots: int
    solver_status: str
    timetable: List[ScheduledMatchItem]


# --- Live Scores Schemas ---
class MatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tournament_id: str
    event_title: Optional[str] = None
    sport_name: Optional[str] = None
    team_a: str
    team_b: str
    court_number: int
    start_time: datetime
    score_a: int
    score_b: int
    status: str


class ScoreUpdateRequest(BaseModel):
    score_a: int = Field(..., ge=0)
    score_b: int = Field(..., ge=0)
    status: Optional[Literal["SCHEDULED", "LIVE", "FINISHED"]] = "LIVE"

