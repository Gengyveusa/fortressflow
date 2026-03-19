import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_email_lower", func.lower("email"), unique=True),
        Index("ix_leads_last_enriched_at", "last_enriched_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    meeting_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    meeting_proof: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    proof_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    enriched_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_enriched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    consents: Mapped[list["Consent"]] = relationship(back_populates="lead", lazy="selectin")  # noqa: F821
    touch_logs: Mapped[list["TouchLog"]] = relationship(back_populates="lead", lazy="selectin")  # noqa: F821
