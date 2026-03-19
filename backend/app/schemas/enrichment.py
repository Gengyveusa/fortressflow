"""Pydantic schemas for enrichment payloads."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EnrichmentRequest(BaseModel):
    """Request to enrich a single lead."""

    lead_id: UUID
    force_refresh: bool = False


class ZoomInfoPersonResponse(BaseModel):
    """ZoomInfo person enrichment result."""

    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    job_title: str | None = None
    company_name: str | None = None
    company_domain: str | None = None
    linkedin_url: str | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)


class ApolloPersonResponse(BaseModel):
    """Apollo person enrichment result."""

    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    title: str | None = None
    organization_name: str | None = None
    linkedin_url: str | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)


class EnrichmentResult(BaseModel):
    """Enrichment result for a lead."""

    enriched_fields: dict[str, Any] = Field(default_factory=dict)
    source: str = ""  # "zoominfo" or "apollo"
    timestamp: datetime | None = None
    success: bool = False
    errors: list[str] = Field(default_factory=list)
