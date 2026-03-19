from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Domain schemas ─────────────────────────────────────────────────────

class DomainCreate(BaseModel):
    domain: str = Field(..., min_length=1, max_length=255)


class DomainResponse(BaseModel):
    id: UUID
    domain: str
    health_score: float
    warmup_progress: float
    total_sent: int
    total_bounced: int
    spf_verified: bool = False
    dkim_verified: bool = False
    dmarc_verified: bool = False
    bimi_verified: bool = False
    dedicated_ip_pool: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DomainDNSInstructions(BaseModel):
    domain: str
    records: list[dict]


# ── Inbox schemas ──────────────────────────────────────────────────────

class InboxCreate(BaseModel):
    email_address: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    domain: str = Field(..., min_length=1, max_length=255)


class InboxResponse(BaseModel):
    id: UUID
    email_address: str
    display_name: str
    domain: str
    status: str
    ses_verified: bool
    dkim_verified: bool
    warmup_day: int
    daily_sent: int
    daily_limit: int
    health_score: float
    bounce_rate_7d: float
    spam_rate_7d: float
    open_rate_7d: float
    reply_rate_7d: float
    total_sent: int
    total_bounced: int
    total_complaints: int
    ai_sender_reputation_score: float | None = None
    ai_optimal_send_hour: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Warmup schemas ─────────────────────────────────────────────────────

class WarmupStatus(BaseModel):
    inbox_id: str
    date: str
    emails_sent: int
    emails_target: int
    bounce_rate: float
    spam_rate: float
    open_rate: float
    reply_rate: float = 0.0
    status: str
    seed_selection_method: str | None = None


class WarmupConfigCreate(BaseModel):
    inbox_id: UUID
    ramp_duration_weeks: int = Field(default=6, ge=2, le=12)
    initial_daily_volume: int = Field(default=5, ge=1, le=20)
    target_daily_volume: int = Field(default=50, ge=10, le=200)
    ramp_multiplier: float = Field(default=1.15, ge=1.05, le=1.5)
    max_bounce_rate: float = Field(default=0.05, ge=0.01, le=0.10)
    max_spam_rate: float = Field(default=0.001, ge=0.0005, le=0.01)
    min_open_rate: float = Field(default=0.15, ge=0.05, le=0.50)


class WarmupConfigResponse(BaseModel):
    id: UUID
    inbox_id: UUID
    ramp_duration_weeks: int
    initial_daily_volume: int
    target_daily_volume: int
    ramp_multiplier: float
    ai_tuned: bool
    max_bounce_rate: float
    max_spam_rate: float
    min_open_rate: float
    is_active: bool
    paused_reason: str | None = None
    last_ai_review: datetime | None = None

    model_config = {"from_attributes": True}


class RampScheduleEntry(BaseModel):
    day: int
    week: int
    daily_volume: int


# ── Dashboard schema ───────────────────────────────────────────────────

class DeliverabilityDashboard(BaseModel):
    summary: dict
    inboxes: list[dict]
    domains: list[dict]
