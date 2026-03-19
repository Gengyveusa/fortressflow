"""
Sequence schemas — enhanced for Phase 4 visual builder, AI generation,
conditional branching, and A/B testing.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Step Schemas ──────────────────────────────────────────────────────


class SequenceStepCreate(BaseModel):
    step_type: str = Field(
        ...,
        pattern="^(email|linkedin|sms|wait|conditional|ab_split|end)$",
    )
    position: int = Field(0, ge=0)
    config: dict[str, Any] | None = None
    delay_hours: float = Field(0, ge=0)

    # Phase 4: Conditional branching
    condition: dict[str, Any] | None = None
    true_next_position: int | None = None
    false_next_position: int | None = None

    # Phase 4: A/B testing
    ab_variants: dict[str, Any] | None = None
    is_ab_test: bool = False

    # Phase 4: React Flow node ID
    node_id: str | None = None


class SequenceStepResponse(BaseModel):
    id: UUID
    sequence_id: UUID
    step_type: str
    position: int
    config: dict[str, Any] | None
    delay_hours: float

    # Phase 4 fields
    condition: dict[str, Any] | None = None
    true_next_position: int | None = None
    false_next_position: int | None = None
    ab_variants: dict[str, Any] | None = None
    is_ab_test: bool = False
    node_id: str | None = None

    created_at: datetime

    model_config = {"from_attributes": True}


# ── Sequence Schemas ──────────────────────────────────────────────────


class SequenceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    status: str = Field("draft", pattern="^(draft|active|paused|archived)$")

    # Phase 4: Visual builder config
    visual_config: dict[str, Any] | None = None

    # Phase 4: AI generation metadata
    ai_generated: bool = False
    ai_generation_prompt: str | None = None
    ai_generation_metadata: dict[str, Any] | None = None


class SequenceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(None, pattern="^(draft|active|paused|archived)$")

    # Phase 4: Visual builder config
    visual_config: dict[str, Any] | None = None


class SequenceResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    steps: list[SequenceStepResponse] = []
    enrolled_count: int = 0

    # Phase 4 fields
    visual_config: dict[str, Any] | None = None
    ai_generated: bool = False
    ai_generation_prompt: str | None = None
    ai_generation_metadata: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class SequenceListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SequenceResponse]


# ── Enrollment Schemas ────────────────────────────────────────────────


class EnrollRequest(BaseModel):
    lead_ids: list[UUID]


class EnrollmentResponse(BaseModel):
    id: UUID
    sequence_id: UUID
    lead_id: UUID
    current_step: int
    status: str
    enrolled_at: datetime

    # Phase 4 fields
    last_touch_at: datetime | None = None
    last_state_change_at: datetime | None = None
    ab_variant_assignments: dict[str, Any] | None = None
    hole_filler_triggered: bool = False
    escalation_channel: str | None = None
    last_dispatch_id: str | None = None

    model_config = {"from_attributes": True}


# ── Analytics Schemas ─────────────────────────────────────────────────


class StepAnalytics(BaseModel):
    step_position: int
    step_type: str
    sent: int = 0
    opened: int = 0
    replied: int = 0
    bounced: int = 0


class ABVariantAnalytics(BaseModel):
    step_position: int
    variant: str
    sent: int = 0
    opened: int = 0
    replied: int = 0
    bounced: int = 0
    open_rate: float = 0.0
    reply_rate: float = 0.0


class SequenceAnalyticsResponse(BaseModel):
    sequence_id: UUID
    total_enrolled: int
    active: int
    completed: int
    steps: list[StepAnalytics]
    ab_results: list[ABVariantAnalytics] = []


# ── AI Generation Schemas ────────────────────────────────────────────


class SequenceGenerateRequest(BaseModel):
    """Request body for POST /sequences/generate."""

    prompt: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Natural language description of the desired sequence",
    )
    target_industry: str = Field(
        "dental",
        description="Target industry for context",
    )
    num_steps: int | None = Field(
        None,
        ge=3,
        le=20,
        description="Override number of steps (AI decides if omitted)",
    )
    channels: list[str] | None = Field(
        None,
        description="Channels to include: email, linkedin, sms",
    )
    include_ab_test: bool = Field(
        True,
        description="Include A/B split nodes",
    )
    include_conditionals: bool = Field(
        True,
        description="Include conditional branch nodes",
    )


class SequenceGenerateResponse(BaseModel):
    """Response from POST /sequences/generate."""

    success: bool
    sequence_id: UUID | None = None
    sequence_name: str | None = None
    steps_generated: int = 0
    channels_used: list[str] = []
    ai_platforms_consulted: list[str] = []
    visual_config: dict[str, Any] | None = None
    error: str | None = None


# ── Visual Builder Schemas ────────────────────────────────────────────


class VisualConfigSaveRequest(BaseModel):
    """Save the React Flow visual builder config for a sequence."""

    visual_config: dict[str, Any] = Field(
        ...,
        description="React Flow nodes, edges, and viewport config",
    )
    steps: list[SequenceStepCreate] | None = Field(
        None,
        description="Optionally sync steps from the visual config",
    )


class VisualConfigResponse(BaseModel):
    """Response with the visual builder config."""

    sequence_id: UUID
    visual_config: dict[str, Any] | None = None
    steps: list[SequenceStepResponse] = []
