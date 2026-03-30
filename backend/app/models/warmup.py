"""
Warmup models for AI-powered inbox warmup.

WarmupQueue: daily per-inbox warmup tracking (enhanced from Phase 1 shell).
WarmupConfig: per-inbox warmup configuration with AI-tuned parameters.
WarmupSeedLog: tracks which seeds were selected and outcomes for learning loops.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WarmupQueue(Base):
    """Daily warmup record — one per inbox per day."""

    __tablename__ = "warmup_queue"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inbox_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sending_inboxes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    emails_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    emails_target: Mapped[int] = mapped_column(Integer, nullable=False)
    bounce_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    spam_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    open_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reply_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")

    # AI-selected seed details
    seed_selection_method: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # "hubspot_breeze", "zoominfo_copilot", "apollo_ai", "manual"
    seed_criteria: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # AI criteria used for seed selection
    seed_lead_ids: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # List of lead UUIDs used as seeds

    # Health check result
    health_check_passed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    health_check_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class WarmupConfig(Base):
    """Per-inbox warmup configuration with AI-tuned ramp schedule."""

    __tablename__ = "warmup_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inbox_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sending_inboxes.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Ramp schedule
    ramp_duration_weeks: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    initial_daily_volume: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    target_daily_volume: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    ramp_multiplier: Mapped[float] = mapped_column(Float, default=1.15, nullable=False)  # 15% daily increase

    # AI tuning
    ai_tuned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_ramp_adjustments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # AI-recommended adjustments
    ai_seed_profile: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Ideal seed characteristics from AI

    # Safety thresholds
    max_bounce_rate: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)  # Pause at 5%
    max_spam_rate: Mapped[float] = mapped_column(Float, default=0.001, nullable=False)  # Pause at 0.1%
    min_open_rate: Mapped[float] = mapped_column(Float, default=0.15, nullable=False)  # Alert below 15%

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    paused_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_ai_review: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class WarmupSeedLog(Base):
    """Tracks seed selection and outcomes for bi-directional AI learning loops."""

    __tablename__ = "warmup_seed_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inbox_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sending_inboxes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    warmup_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Selection metadata
    selected_by: Mapped[str] = mapped_column(String(100), nullable=False)  # Platform that selected this seed
    selection_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    selection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Outcome tracking
    opened: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    replied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bounced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    complained: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Feedback to AI platforms
    feedback_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    feedback_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
