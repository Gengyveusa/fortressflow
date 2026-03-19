from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DomainCreate(BaseModel):
    domain: str = Field(..., min_length=1, max_length=255)


class DomainResponse(BaseModel):
    id: UUID
    domain: str
    health_score: float
    warmup_progress: float
    total_sent: int
    total_bounced: int
    created_at: datetime

    model_config = {"from_attributes": True}


class WarmupStatus(BaseModel):
    inbox_id: str
    date: str
    emails_sent: int
    emails_target: int
    bounce_rate: float
    spam_rate: float
    open_rate: float
    status: str
