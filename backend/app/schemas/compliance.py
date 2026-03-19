from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ComplianceCheckRequest(BaseModel):
    lead_id: UUID
    channel: str = Field(..., pattern="^(email|sms|linkedin)$")


class ComplianceCheckResponse(BaseModel):
    can_send: bool
    reason: str


class ConsentGrantRequest(BaseModel):
    lead_id: UUID
    channel: str = Field(..., pattern="^(email|sms|linkedin)$")
    method: str = Field(..., pattern="^(meeting_card|web_form|import_verified)$")
    proof: dict[str, Any]


class ConsentGrantResponse(BaseModel):
    consent_id: UUID
    granted_at: datetime


class ConsentRevokeRequest(BaseModel):
    lead_id: UUID
    channel: str = Field(..., pattern="^(email|sms|linkedin)$")


class ConsentRevokeResponse(BaseModel):
    revoked: bool


class DNCAddRequest(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=255)
    channel: str = Field(..., pattern="^(email|sms|linkedin)$")
    reason: str = Field(..., min_length=1, max_length=500)
    source: str = Field(..., min_length=1, max_length=100)


class AuditTrailResponse(BaseModel):
    lead_id: UUID
    consents: list[dict[str, Any]]
    touch_logs: list[dict[str, Any]]
    dnc_records: list[dict[str, Any]]


class UnsubscribeResponse(BaseModel):
    unsubscribed: bool
    message: str
