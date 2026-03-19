"""
Sending domain model with full DNS authentication tracking.

Supports SPF, DKIM, DMARC, and BIMI verification status for each domain.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SendingDomain(Base):
    __tablename__ = "sending_domains"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    domain: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    # DNS verification statuses
    spf_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dkim_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dmarc_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bimi_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # SES domain identity
    ses_domain_arn: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ses_dkim_tokens: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # DKIM CNAME records from SES

    # Health metrics
    health_score: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    warmup_progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_bounced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_complaints: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Dedicated IP pool
    dedicated_ip_pool: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dedicated_ips: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # List of IPs in the pool

    # DMARC policy
    dmarc_policy: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # "none", "quarantine", "reject"
    dmarc_rua: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # Aggregate report email
    dmarc_ruf: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # Forensic report email

    # BIMI
    bimi_svg_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    bimi_vmc_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Notes
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
