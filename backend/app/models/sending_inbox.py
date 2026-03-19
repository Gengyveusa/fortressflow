"""
Sending identity model for round-robin rotation.

Each inbox represents one verified sending identity (e.g. outreach1@mail.gengyveusa.com).
FortressFlow rotates across 5-10 identities to spread reputation load and
stay under per-identity daily limits.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InboxStatus(StrEnum):
    warming = "warming"
    active = "active"
    paused = "paused"
    suspended = "suspended"


class SendingInbox(Base):
    __tablename__ = "sending_inboxes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email_address: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # SES verification
    ses_identity_arn: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ses_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dkim_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dmarc_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Status and warmup
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=InboxStatus.warming
    )
    warmup_day: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warmup_start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Daily counters (reset each day by scheduler)
    daily_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    daily_limit: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # Reputation metrics (rolling)
    bounce_rate_7d: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    spam_rate_7d: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    open_rate_7d: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reply_rate_7d: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    health_score: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)

    # Total lifetime counters
    total_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_bounced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_complaints: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_opens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_replies: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # AI scores from platform integrations
    ai_sender_reputation_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # From HubSpot Breeze / ZoomInfo Copilot
    ai_optimal_send_hour: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # AI-recommended send hour (0-23 UTC)
    ai_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # Additional AI insights

    # Notes / config
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
