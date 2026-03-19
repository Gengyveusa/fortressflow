from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SequenceStepCreate(BaseModel):
    step_type: str = Field(..., pattern="^(email|linkedin|sms|wait)$")
    position: int = Field(0, ge=0)
    config: dict[str, Any] | None = None
    delay_hours: float = Field(0, ge=0)


class SequenceStepResponse(BaseModel):
    id: UUID
    sequence_id: UUID
    step_type: str
    position: int
    config: dict[str, Any] | None
    delay_hours: float
    created_at: datetime

    model_config = {"from_attributes": True}


class SequenceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    status: str = Field("draft", pattern="^(draft|active|paused|archived)$")


class SequenceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(None, pattern="^(draft|active|paused|archived)$")


class SequenceResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    steps: list[SequenceStepResponse] = []
    enrolled_count: int = 0

    model_config = {"from_attributes": True}


class SequenceListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SequenceResponse]


class EnrollRequest(BaseModel):
    lead_ids: list[UUID]


class EnrollmentResponse(BaseModel):
    id: UUID
    sequence_id: UUID
    lead_id: UUID
    current_step: int
    status: str
    enrolled_at: datetime

    model_config = {"from_attributes": True}


class StepAnalytics(BaseModel):
    step_position: int
    step_type: str
    sent: int = 0
    opened: int = 0
    replied: int = 0
    bounced: int = 0


class SequenceAnalyticsResponse(BaseModel):
    sequence_id: UUID
    total_enrolled: int
    active: int
    completed: int
    steps: list[StepAnalytics]
