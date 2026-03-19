from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator
import phonenumbers


class LeadCreate(BaseModel):
    email: EmailStr
    phone: str | None = None
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    company: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=1, max_length=255)
    source: str = Field(..., min_length=1, max_length=100)
    meeting_verified: bool = False
    proof_data: dict[str, Any] | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            parsed = phonenumbers.parse(v, None)
            if not phonenumbers.is_valid_number(parsed):
                raise ValueError("Invalid phone number")
        except phonenumbers.NumberParseException:
            raise ValueError("Invalid phone number format")
        return v


class LeadUpdate(BaseModel):
    phone: str | None = None
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    company: str | None = Field(None, min_length=1, max_length=255)
    title: str | None = Field(None, min_length=1, max_length=255)
    meeting_verified: bool | None = None
    proof_data: dict[str, Any] | None = None


class LeadResponse(BaseModel):
    id: UUID
    email: str
    phone: str | None
    first_name: str
    last_name: str
    company: str
    title: str
    source: str
    meeting_verified: bool
    proof_data: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LeadListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[LeadResponse]


class TouchLogCreate(BaseModel):
    channel: str = Field(..., pattern="^(email|sms|linkedin)$")
    action: str = Field(..., pattern="^(sent|delivered|opened|replied|bounced|complained|unsubscribed)$")
    sequence_id: UUID | None = None
    step_number: int | None = None
    extra_metadata: dict[str, Any] | None = None


class TouchLogResponse(BaseModel):
    id: UUID
    lead_id: UUID
    channel: str
    action: str
    sequence_id: UUID | None
    step_number: int | None
    extra_metadata: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}
