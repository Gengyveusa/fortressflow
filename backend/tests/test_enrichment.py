"""
Tests for enrichment services (ZoomInfo, Apollo, orchestrator).

All tests use mocked HTTP clients — no real external API calls.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.email_validator import (
    is_disposable_email,
    is_role_based_email,
    validate_email_full,
)


# ── Email Validation Tests ────────────────────────────────────────────


def test_disposable_email_detected():
    """Disposable email domains should be detected."""
    assert is_disposable_email("user@mailinator.com") is True
    assert is_disposable_email("user@guerrillamail.com") is True
    assert is_disposable_email("user@yopmail.com") is True


def test_normal_email_not_disposable():
    """Normal email domains should not be flagged as disposable."""
    assert is_disposable_email("user@example.com") is False
    assert is_disposable_email("user@gmail.com") is False
    assert is_disposable_email("user@company.io") is False


def test_role_based_email_detected():
    """Role-based email prefixes should be detected."""
    assert is_role_based_email("info@company.com") is True
    assert is_role_based_email("support@company.com") is True
    assert is_role_based_email("noreply@company.com") is True
    assert is_role_based_email("admin@company.com") is True


def test_personal_email_not_role_based():
    """Personal email addresses should not be flagged as role-based."""
    assert is_role_based_email("john@company.com") is False
    assert is_role_based_email("alice.smith@company.com") is False


def test_validate_email_full_valid():
    """Valid non-disposable non-role email passes full validation."""
    is_valid, reason = validate_email_full("john@example.com")
    assert is_valid is True
    assert reason == "valid"


def test_validate_email_full_disposable():
    """Disposable email fails full validation."""
    is_valid, reason = validate_email_full("test@mailinator.com")
    assert is_valid is False
    assert reason == "disposable_email_domain"


def test_validate_email_full_role_based():
    """Role-based email fails full validation."""
    is_valid, reason = validate_email_full("info@company.com")
    assert is_valid is False
    assert reason == "role_based_email"


def test_validate_email_full_invalid_format():
    """Invalid email format fails full validation."""
    is_valid, reason = validate_email_full("not-an-email")
    assert is_valid is False
    assert reason == "invalid_email_format"


# ── ZoomInfo Service Tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_zoominfo_enrich_person_success():
    """ZoomInfo enrichment returns data on success."""
    from app.services.zoominfo_service import ZoomInfoService

    mock_response = httpx.Response(
        200,
        json={
            "result": {
                "data": [
                    {
                        "firstName": "Jane",
                        "lastName": "Doe",
                        "jobTitle": "CTO",
                        "companyName": "ACME",
                        "phone": "+14155550001",
                        "email": "jane@acme.com",
                        "linkedInUrl": "https://linkedin.com/in/janedoe",
                        "companyDomain": "acme.com",
                    }
                ]
            }
        },
        request=httpx.Request("POST", "https://api.zoominfo.com/search/contact"),
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.services.zoominfo_service.settings") as mock_settings:
        mock_settings.ZOOMINFO_API_KEY = "test-key"
        mock_settings.ZOOMINFO_CLIENT_ID = ""
        mock_settings.ZOOMINFO_CLIENT_SECRET = ""
        mock_settings.ZOOMINFO_RATE_LIMIT = 25

        svc = ZoomInfoService(http_client=mock_client)
        result = await svc.enrich_person("jane@acme.com")

    assert result.get("source") == "zoominfo"
    assert result["data"]["first_name"] == "Jane"
    assert result["data"]["company_name"] == "ACME"


@pytest.mark.asyncio
async def test_zoominfo_enrich_person_no_results():
    """ZoomInfo returns empty dict when no results found."""
    from app.services.zoominfo_service import ZoomInfoService

    mock_response = httpx.Response(
        200,
        json={"result": {"data": []}},
        request=httpx.Request("POST", "https://api.zoominfo.com/search/contact"),
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.services.zoominfo_service.settings") as mock_settings:
        mock_settings.ZOOMINFO_API_KEY = "test-key"
        mock_settings.ZOOMINFO_CLIENT_ID = ""
        mock_settings.ZOOMINFO_CLIENT_SECRET = ""
        mock_settings.ZOOMINFO_RATE_LIMIT = 25

        svc = ZoomInfoService(http_client=mock_client)
        result = await svc.enrich_person("nobody@example.com")

    assert result == {}


# ── Apollo Service Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apollo_enrich_person_success():
    """Apollo enrichment returns data on success."""
    from app.services.apollo_service import ApolloService

    mock_response = httpx.Response(
        200,
        json={
            "person": {
                "first_name": "Bob",
                "last_name": "Smith",
                "email": "bob@company.io",
                "phone_number": "+14155550002",
                "title": "VP Sales",
                "organization": {"name": "CompanyCo"},
                "linkedin_url": "https://linkedin.com/in/bobsmith",
            }
        },
        request=httpx.Request("POST", "https://api.apollo.io/v1/people/match"),
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.services.apollo_service.settings") as mock_settings:
        mock_settings.APOLLO_API_KEY = "test-key"
        mock_settings.APOLLO_RATE_LIMIT = 50

        svc = ApolloService(http_client=mock_client)
        result = await svc.enrich_person("bob@company.io")

    assert result.get("source") == "apollo"
    assert result["data"]["first_name"] == "Bob"
    assert result["data"]["organization_name"] == "CompanyCo"


@pytest.mark.asyncio
async def test_apollo_enrich_person_not_configured():
    """Apollo returns empty dict when API key not configured."""
    from app.services.apollo_service import ApolloService

    with patch("app.services.apollo_service.settings") as mock_settings:
        mock_settings.APOLLO_API_KEY = ""
        mock_settings.APOLLO_RATE_LIMIT = 50

        svc = ApolloService()
        result = await svc.enrich_person("test@example.com")

    assert result == {}


# ── Enrichment Orchestrator Tests ─────────────────────────────────────


@pytest.mark.asyncio
async def test_enrichment_waterfall_zoominfo_success():
    """Enrichment uses ZoomInfo when it returns complete data."""
    from app.services.enrichment import EnrichmentService

    mock_lead = MagicMock()
    mock_lead.id = uuid.uuid4()
    mock_lead.email = "test@example.com"
    mock_lead.company = "ACME"
    mock_lead.meeting_verified = True
    mock_lead.enriched_data = None
    mock_lead.last_enriched_at = None
    mock_lead.meeting_proof = None
    mock_lead.consents = []

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_lead
    db.execute = AsyncMock(return_value=result_mock)
    db.flush = AsyncMock()

    zoominfo_data = {
        "source": "zoominfo",
        "data": {
            "email": "test@example.com",
            "phone": "+14155550001",
            "job_title": "CTO",
            "company_name": "ACME",
        },
        "enriched_at": datetime.now(UTC).isoformat(),
    }

    mock_zoominfo = AsyncMock()
    mock_zoominfo.enrich_person = AsyncMock(return_value=zoominfo_data)
    mock_apollo = AsyncMock()
    mock_apollo.enrich_person = AsyncMock(return_value={})

    svc = EnrichmentService(zoominfo=mock_zoominfo, apollo=mock_apollo)
    result = await svc.enrich_lead(mock_lead.id, db)

    assert result["success"] is True
    assert "zoominfo" in result["source"]
    mock_zoominfo.enrich_person.assert_called_once()


@pytest.mark.asyncio
async def test_enrichment_waterfall_apollo_fallback():
    """Enrichment falls back to Apollo when ZoomInfo returns empty."""
    from app.services.enrichment import EnrichmentService

    mock_lead = MagicMock()
    mock_lead.id = uuid.uuid4()
    mock_lead.email = "test@example.com"
    mock_lead.company = "ACME"
    mock_lead.meeting_verified = True
    mock_lead.enriched_data = None
    mock_lead.last_enriched_at = None
    mock_lead.meeting_proof = None
    mock_lead.consents = []

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_lead
    db.execute = AsyncMock(return_value=result_mock)
    db.flush = AsyncMock()

    apollo_data = {
        "source": "apollo",
        "data": {
            "email": "test@example.com",
            "phone": "+14155550002",
            "title": "VP Sales",
            "organization_name": "ACME",
        },
        "enriched_at": datetime.now(UTC).isoformat(),
    }

    mock_zoominfo = AsyncMock()
    mock_zoominfo.enrich_person = AsyncMock(return_value={})
    mock_apollo = AsyncMock()
    mock_apollo.enrich_person = AsyncMock(return_value=apollo_data)

    svc = EnrichmentService(zoominfo=mock_zoominfo, apollo=mock_apollo)
    result = await svc.enrich_lead(mock_lead.id, db)

    assert result["success"] is True
    assert result["source"] == "apollo"
    mock_apollo.enrich_person.assert_called_once()


@pytest.mark.asyncio
async def test_enrichment_cache_fresh_skips_enrich():
    """Enrichment skips API calls when cache is still fresh."""
    from app.services.enrichment import EnrichmentService

    mock_lead = MagicMock()
    mock_lead.id = uuid.uuid4()
    mock_lead.email = "cached@example.com"
    mock_lead.company = "ACME"
    mock_lead.meeting_verified = True
    mock_lead.enriched_data = {
        "source": "zoominfo",
        "data": {"email": "cached@example.com"},
        "enriched_at": datetime.now(UTC).isoformat(),
    }
    mock_lead.last_enriched_at = datetime.now(UTC) - timedelta(days=30)  # Only 30 days old
    mock_lead.meeting_proof = None
    mock_lead.consents = []

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_lead
    db.execute = AsyncMock(return_value=result_mock)

    mock_zoominfo = AsyncMock()
    mock_apollo = AsyncMock()

    svc = EnrichmentService(zoominfo=mock_zoominfo, apollo=mock_apollo)
    result = await svc.enrich_lead(mock_lead.id, db)

    assert result["success"] is True
    # Should NOT call external APIs
    mock_zoominfo.enrich_person.assert_not_called()
    mock_apollo.enrich_person.assert_not_called()


@pytest.mark.asyncio
async def test_enrichment_90_day_re_verification():
    """Enrichment re-runs when cache is older than 90 days."""
    from app.services.enrichment import EnrichmentService

    mock_lead = MagicMock()
    mock_lead.id = uuid.uuid4()
    mock_lead.email = "stale@example.com"
    mock_lead.company = "ACME"
    mock_lead.meeting_verified = True
    mock_lead.enriched_data = {"source": "zoominfo", "data": {"email": "stale@example.com"}}
    mock_lead.last_enriched_at = datetime.now(UTC) - timedelta(days=100)  # Over 90 days
    mock_lead.meeting_proof = None
    mock_lead.consents = []

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_lead
    db.execute = AsyncMock(return_value=result_mock)
    db.flush = AsyncMock()

    new_data = {
        "source": "zoominfo",
        "data": {"email": "stale@example.com", "phone": "+14155550001"},
        "enriched_at": datetime.now(UTC).isoformat(),
    }

    mock_zoominfo = AsyncMock()
    mock_zoominfo.enrich_person = AsyncMock(return_value=new_data)
    mock_apollo = AsyncMock()

    svc = EnrichmentService(zoominfo=mock_zoominfo, apollo=mock_apollo)
    result = await svc.enrich_lead(mock_lead.id, db)

    assert result["success"] is True
    # Should call ZoomInfo since cache is stale
    mock_zoominfo.enrich_person.assert_called_once()


@pytest.mark.asyncio
async def test_enrichment_lead_not_found():
    """Enrichment returns error when lead not found."""
    from app.services.enrichment import EnrichmentService

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    svc = EnrichmentService()
    result = await svc.enrich_lead(uuid.uuid4(), db)

    assert result["success"] is False
    assert "lead_not_found" in result["errors"]
