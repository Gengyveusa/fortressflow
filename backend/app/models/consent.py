import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

import enum


class ConsentChannel(str, enum.Enum):
    email = "email"
    sms = "sms"
    linkedin = "linkedin"


class ConsentMethod(str, enum.Enum):
    meeting_card = "meeting_card"
    web_form = "web_form"
    import_verified = "import_verified"


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[ConsentChannel] = mapped_column(Enum(ConsentChannel, name="consent_channel"), nullable=False)
    method: Mapped[ConsentMethod] = mapped_column(Enum(ConsentMethod, name="consent_method"), nullable=False)
    proof: Mapped[dict] = mapped_column(JSONB, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    lead: Mapped["Lead"] = relationship(back_populates="consents")  # noqa: F821
