import uuid
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TemplateChannel(str, enum.Enum):
    email = "email"
    sms = "sms"
    linkedin = "linkedin"


class TemplateCategory(str, enum.Enum):
    cold_outreach = "cold_outreach"
    follow_up = "follow_up"
    re_engagement = "re_engagement"
    custom = "custom"


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[TemplateChannel] = mapped_column(Enum(TemplateChannel, name="template_channel"), nullable=False)
    category: Mapped[TemplateCategory] = mapped_column(
        Enum(TemplateCategory, name="template_category"),
        nullable=False,
        default=TemplateCategory.custom,
    )
    # Email-specific
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Universal plain text body (SMS uses this, email fallback)
    plain_body: Mapped[str] = mapped_column(Text, nullable=False)
    # LinkedIn-specific
    linkedin_action: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # "connection_request", "inmail", "message"
    # Template variables metadata (e.g. ["first_name", "company", "title"])
    variables: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # A/B testing
    variant_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    variant_label: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "A", "B", etc.
    # Flags
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
