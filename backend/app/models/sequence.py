import uuid
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SequenceStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    archived = "archived"


class StepType(str, enum.Enum):
    email = "email"
    linkedin = "linkedin"
    sms = "sms"
    wait = "wait"


class EnrollmentStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    paused = "paused"
    bounced = "bounced"
    unsubscribed = "unsubscribed"


class Sequence(Base):
    __tablename__ = "sequences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[SequenceStatus] = mapped_column(
        Enum(SequenceStatus, name="sequence_status"),
        nullable=False,
        default=SequenceStatus.draft,
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

    steps: Mapped[list["SequenceStep"]] = relationship(
        back_populates="sequence", lazy="selectin", order_by="SequenceStep.position"
    )
    enrollments: Mapped[list["SequenceEnrollment"]] = relationship(
        back_populates="sequence", lazy="selectin"
    )


class SequenceStep(Base):
    __tablename__ = "sequence_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sequence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sequences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_type: Mapped[StepType] = mapped_column(
        Enum(StepType, name="step_type"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    delay_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sequence: Mapped["Sequence"] = relationship(back_populates="steps")


class SequenceEnrollment(Base):
    __tablename__ = "sequence_enrollments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sequence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sequences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[EnrollmentStatus] = mapped_column(
        Enum(EnrollmentStatus, name="enrollment_status"),
        nullable=False,
        default=EnrollmentStatus.active,
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sequence: Mapped["Sequence"] = relationship(back_populates="enrollments")
    lead: Mapped["Lead"] = relationship()  # noqa: F821
