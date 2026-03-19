from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    channel: str = Field(..., pattern="^(email|sms|linkedin)$")
    category: str = Field("custom", pattern="^(cold_outreach|follow_up|re_engagement|custom)$")
    subject: str | None = None
    html_body: str | None = None
    plain_body: str = Field(..., min_length=1)
    linkedin_action: str | None = Field(None, pattern="^(connection_request|inmail|message)$")
    variables: list[str] | None = None
    variant_group: str | None = None
    variant_label: str | None = None


class TemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    channel: str | None = Field(None, pattern="^(email|sms|linkedin)$")
    category: str | None = Field(None, pattern="^(cold_outreach|follow_up|re_engagement|custom)$")
    subject: str | None = None
    html_body: str | None = None
    plain_body: str | None = None
    linkedin_action: str | None = Field(None, pattern="^(connection_request|inmail|message)$")
    variables: list[str] | None = None
    variant_group: str | None = None
    variant_label: str | None = None
    is_active: bool | None = None


class TemplateResponse(BaseModel):
    id: UUID
    name: str
    channel: str
    category: str
    subject: str | None
    html_body: str | None
    plain_body: str
    linkedin_action: str | None
    variables: list[str] | None
    variant_group: str | None
    variant_label: str | None
    is_system: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TemplateResponse]


class TemplatePreviewRequest(BaseModel):
    template_id: UUID | None = None
    plain_body: str | None = None
    html_body: str | None = None
    subject: str | None = None
    context: dict[str, str] = Field(
        default_factory=lambda: {
            "first_name": "Sarah",
            "last_name": "Chen",
            "company": "SmileCare Dental Group",
            "title": "Office Manager",
            "sender_name": "Dr. Thad",
            "sender_company": "Gengyve USA",
        }
    )


class TemplatePreviewResponse(BaseModel):
    rendered_subject: str | None = None
    rendered_plain_body: str
    rendered_html_body: str | None = None
    variables_used: list[str]
    warnings: list[str]


class SequencePreset(BaseModel):
    """A pre-built sequence with steps and templates."""
    name: str
    description: str
    category: str
    steps: list[dict[str, Any]]
