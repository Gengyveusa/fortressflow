"""
Enrichment orchestrator — ZoomInfo (primary) + Apollo (fallback).

Results are cached in the leads.enriched_data JSONB column with a configurable TTL.
Validates emails (disposable/role-based) and phones before storing.
Retries 3x on transient errors.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.lead import Lead
from app.services.apollo_service import ApolloService
from app.services.email_validator import (
    is_valid_phone,
    validate_email_full,
)
from app.services.zoominfo_service import ZoomInfoService

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_TRANSIENT_EXCEPTIONS = (httpx.TimeoutException,)
_TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503})


def _is_transient_error(exc: Exception) -> bool:
    """Return True if the exception is a transient/retryable error."""
    if isinstance(exc, _TRANSIENT_EXCEPTIONS):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _TRANSIENT_STATUS_CODES
    return False


def _has_key_fields(data: dict) -> bool:
    """Return True if enrichment data has the key fields we need."""
    inner = data.get("data", {})
    return all(inner.get(field) for field in ("email", "phone"))


class EnrichmentService:
    """Orchestrates ZoomInfo + Apollo enrichment with validation and caching."""

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        zoominfo: ZoomInfoService | None = None,
        apollo: ApolloService | None = None,
    ) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=30)
        self._zoominfo = zoominfo or ZoomInfoService(http_client=self._client)
        self._apollo = apollo or ApolloService(http_client=self._client)

    async def enrich_lead(self, lead_id: UUID, db: AsyncSession) -> dict:
        """Enrich a lead using the waterfall strategy.

        1. Check cache freshness
        2. ZoomInfo first
        3. Apollo fallback if key fields missing
        4. Validate enriched email/phone
        5. Update lead record

        Returns enrichment result dict.
        """
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if lead is None:
            logger.warning("enrich_lead: lead %s not found", lead_id)
            return {"success": False, "errors": ["lead_not_found"]}

        # Check if cache is still fresh
        if self._is_cache_fresh(lead.enriched_data, lead.last_enriched_at):
            logger.info("enrich_lead: cache still fresh for %s", lead_id)
            return {
                "success": True,
                "enriched_fields": lead.enriched_data or {},
                "source": (lead.enriched_data or {}).get("source", "cache"),
                "timestamp": (lead.last_enriched_at or datetime.now(UTC)).isoformat(),
            }

        # Only enrich if source allows (meeting_verified or has consent)
        if not lead.meeting_verified:
            consent_count = len([c for c in lead.consents if c.revoked_at is None])
            if consent_count == 0:
                logger.info(
                    "enrich_lead: lead %s not meeting_verified and no active consent",
                    lead_id,
                )
                return {
                    "success": False,
                    "errors": ["not_meeting_verified_and_no_consent"],
                }

        errors: list[str] = []

        # Waterfall: ZoomInfo first
        data = await self._try_enrich_with_retry(self._zoominfo.enrich_person, lead.email, lead.company)

        # Fallback to Apollo if ZoomInfo misses key fields
        if not data or not _has_key_fields(data):
            if data:
                logger.info(
                    "ZoomInfo result missing key fields for %s, trying Apollo",
                    lead.email,
                )
            apollo_data = await self._try_enrich_with_retry(self._apollo.enrich_person, lead.email)
            if apollo_data:
                if data:
                    data = self._merge_enrichment_data(data, apollo_data)
                else:
                    data = apollo_data

        if not data:
            logger.warning("No enrichment data found for lead %s", lead_id)
            return {"success": False, "errors": ["no_enrichment_data"]}

        # Validate enriched data
        inner = data.get("data", {})
        enriched_email = inner.get("email", "")
        if enriched_email:
            email_valid, email_reason = validate_email_full(enriched_email)
            if not email_valid:
                errors.append(f"enriched_email_invalid: {email_reason}")
                inner["email_validation"] = email_reason

        enriched_phone = inner.get("phone", "")
        if enriched_phone and not is_valid_phone(enriched_phone):
            errors.append("enriched_phone_invalid")
            inner["phone_validation"] = "invalid_format"

        # Update lead record
        now = datetime.now(UTC)
        lead.enriched_data = data
        lead.last_enriched_at = now
        if lead.meeting_proof is None:
            lead.meeting_proof = {}
        lead.meeting_proof = {
            **lead.meeting_proof,
            "last_enrichment": {
                "source": data.get("source", "unknown"),
                "timestamp": now.isoformat(),
                "fields_enriched": list(inner.keys()),
            },
        }
        await db.flush()

        logger.info("Enriched lead %s via %s", lead_id, data.get("source", "unknown"))
        return {
            "success": True,
            "enriched_fields": data,
            "source": data.get("source", "unknown"),
            "timestamp": now.isoformat(),
            "errors": errors,
        }

    async def _try_enrich_with_retry(self, func, *args) -> dict:
        """Call enrichment function with up to _MAX_RETRIES on transient errors."""
        for attempt in range(_MAX_RETRIES):
            try:
                return await func(*args)
            except Exception as exc:
                if _is_transient_error(exc) and attempt < _MAX_RETRIES - 1:
                    logger.warning(
                        "Transient error on attempt %d: %s, retrying",
                        attempt + 1,
                        exc,
                    )
                    continue
                if _is_transient_error(exc):
                    logger.error(
                        "Transient error after %d attempts: %s",
                        _MAX_RETRIES,
                        exc,
                    )
                    return {}
                # Non-transient error — don't retry
                logger.error("Non-transient enrichment error: %s", exc)
                return {}
        return {}

    def _is_cache_fresh(self, enriched_data: dict | None, last_enriched_at: datetime | None) -> bool:
        """Return True if cached enrichment data is within TTL."""
        if not enriched_data or not last_enriched_at:
            return False
        if last_enriched_at.tzinfo is None:
            last_enriched_at = last_enriched_at.replace(tzinfo=UTC)
        return datetime.now(UTC) - last_enriched_at < timedelta(days=settings.ENRICHMENT_TTL_DAYS)

    @staticmethod
    def _merge_enrichment_data(primary: dict, fallback: dict) -> dict:
        """Merge enrichment data from two sources, preferring primary non-empty values."""
        primary_inner = primary.get("data", {})
        fallback_inner = fallback.get("data", {})
        merged = {
            **fallback_inner,
            **{k: v for k, v in primary_inner.items() if v},
        }
        return {
            "source": "zoominfo+apollo",
            "data": merged,
            "enriched_at": datetime.now(UTC).isoformat(),
        }

    async def validate_email(self, email: str) -> bool:
        """Validate email using local validator (no external call)."""
        from app.services.email_validator import is_valid_email

        return is_valid_email(email)

    async def validate_phone(self, phone: str) -> bool:
        """Validate phone using phonenumbers library."""
        return is_valid_phone(phone)
