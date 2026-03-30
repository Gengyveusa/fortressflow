"""
Sequence models — enhanced for Phase 4 visual builder, state machine,
A/B testing, and conditional branching.
"""

import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
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
    conditional = "conditional"  # Phase 4: if/else branch
    ab_split = "ab_split"  # Phase 4: A/B test node
    end = "end"  # Phase 4: explicit end node


class EnrollmentStatus(str, enum.Enum):
    # Phase 1-3 legacy states
    active = "active"
    completed = "completed"
    paused = "paused"
    bounced = "bounced"
    unsubscribed = "unsubscribed"
    # Phase 4 FSM states
    pending = "pending"
    sent = "sent"
    opened = "opened"
    replied = "replied"
    escalated = "escalated"
    failed = "failed"


class Sequence(Base):
    __tablename__ = "sequences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[SequenceStatus] = mapped_column(
        Enum(SequenceStatus, name="sequence_status", create_type=False),
        nullable=False,
        default=SequenceStatus.draft,
    )

    # Phase 4: Visual builder config (React Flow nodes/edges)
    visual_config: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # {nodes: [...], edges: [...], viewport: {...}}

    # Phase 4: AI generation metadata
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_generation_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_generation_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # Which platforms contributed, scores, etc.

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    steps: Mapped[list["SequenceStep"]] = relationship(
        back_populates="sequence", lazy="selectin", order_by="SequenceStep.position"
    )
    enrollments: Mapped[list["SequenceEnrollment"]] = relationship(back_populates="sequence", lazy="selectin")


class SequenceStep(Base):
    __tablename__ = "sequence_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sequence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sequences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_type: Mapped[StepType] = mapped_column(Enum(StepType, name="step_type", create_type=False), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    delay_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    # Phase 4: Conditional branching
    condition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # {"type": "opened", "within_hours": 48}
    true_next_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    false_next_position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Phase 4: A/B testing
    ab_variants: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # {"A": {"template_id": "...", "weight": 50}, "B": {"template_id": "...", "weight": 50}}
    is_ab_test: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Phase 4: React Flow node ID (for visual builder mapping)
    node_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    sequence: Mapped["Sequence"] = relationship(back_populates="steps")


class SequenceEnrollment(Base):
    __tablename__ = "sequence_enrollments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
        Enum(EnrollmentStatus, name="enrollment_status", create_type=False),
        nullable=False,
        default=EnrollmentStatus.pending,
    )

    # Phase 4: FSM tracking
    last_touch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_state_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Phase 4: A/B variant tracking
    ab_variant_assignments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # {step_position: "A" or "B"}

    # Phase 4: Hole-filler tracking
    hole_filler_triggered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    escalation_channel: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "linkedin", "sms"

    # Phase 4: Idempotency
    last_dispatch_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )  # UUID of last dispatched touch (prevent double-send)

    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    sequence: Mapped["Sequence"] = relationship(back_populates="enrollments")
    lead: Mapped["Lead"] = relationship()  # noqa: F821
