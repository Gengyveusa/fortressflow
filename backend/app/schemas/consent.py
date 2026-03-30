from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ConsentCreate(BaseModel):
    lead_id: UUID
    channel: str = Field(..., pattern="^(email|sms|linkedin)$")
    method: str = Field(..., pattern="^(meeting_card|web_form|import_verified)$")
    proof: dict[str, Any] = Field(..., description="Proof object containing timestamp, source, and IP")


class ConsentResponse(BaseModel):
    id: UUID
    lead_id: UUID
    channel: str
    method: str
    proof: dict[str, Any]
    granted_at: datetime
    revoked_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConsentRevoke(BaseModel):
    lead_id: UUID
    channel: str = Field(..., pattern="^(email|sms|linkedin)$")
