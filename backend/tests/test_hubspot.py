"""
Tests for HubSpot integration service.

All tests use mocked HTTP clients — no real HubSpot API calls.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ── Push Lead Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_push_lead_to_hubspot_success():
    """Push a lead to HubSpot creates a contact and returns ID."""
    from app.services.hubspot import HubSpotService

    mock_response = httpx.Response(
        201,
        json={"id": "12345"},
        request=httpx.Request("POST", "https://api.hubapi.com/crm/v3/objects/contacts"),
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.request = AsyncMock(return_value=mock_response)

    lead = MagicMock()
    lead.id = uuid.uuid4()
    lead.email = "test@example.com"
    lead.first_name = "Jane"
    lead.last_name = "Doe"
    lead.company = "ACME"
    lead.title = "CTO"
    lead.phone = "+14155550001"

    with patch("app.services.hubspot.settings") as mock_settings:
        mock_settings.HUBSPOT_API_KEY = "test-hubspot-key"

        svc = HubSpotService(http_client=mock_client)
        hs_id = await svc.push_lead_to_hubspot(lead)

    assert hs_id == "12345"


@pytest.mark.asyncio
async def test_push_lead_no_api_key():
    """Push returns empty string when HUBSPOT_API_KEY is not set."""
    from app.services.hubspot import HubSpotService

    lead = MagicMock()
    lead.email = "test@example.com"

    with patch("app.services.hubspot.settings") as mock_settings:
        mock_settings.HUBSPOT_API_KEY = ""

        svc = HubSpotService()
        hs_id = await svc.push_lead_to_hubspot(lead)

    assert hs_id == ""


@pytest.mark.asyncio
async def test_push_lead_conflict_fetches_existing():
    """Push handles 409 conflict by fetching existing contact."""
    from app.services.hubspot import HubSpotService

    conflict_resp = httpx.Response(
        409,
        json={"message": "Contact already exists"},
        request=httpx.Request("POST", "https://api.hubapi.com/crm/v3/objects/contacts"),
    )
    get_resp = httpx.Response(
        200,
        json={"id": "67890"},
        request=httpx.Request("GET", "https://api.hubapi.com/crm/v3/objects/contacts/test@example.com"),
    )

    call_count = 0

    async def mock_request(method, url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.HTTPStatusError("409", request=conflict_resp.request, response=conflict_resp)
        return get_resp

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.request = AsyncMock(side_effect=mock_request)

    lead = MagicMock()
    lead.id = uuid.uuid4()
    lead.email = "test@example.com"
    lead.first_name = "Jane"
    lead.last_name = "Doe"
    lead.company = "ACME"
    lead.title = "CTO"
    lead.phone = "+14155550001"

    with patch("app.services.hubspot.settings") as mock_settings:
        mock_settings.HUBSPOT_API_KEY = "test-hubspot-key"

        svc = HubSpotService(http_client=mock_client)
        hs_id = await svc.push_lead_to_hubspot(lead)

    assert hs_id == "67890"


# ── Pull Contacts Tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pull_contacts_from_hubspot():
    """Pull contacts returns parsed contact properties."""
    from app.services.hubspot import HubSpotService

    mock_response = httpx.Response(
        200,
        json={
            "results": [
                {
                    "id": "100",
                    "properties": {
                        "email": "hs_user@example.com",
                        "firstname": "HubSpot",
                        "lastname": "User",
                        "company": "HubCo",
                        "jobtitle": "VP Sales",
                        "phone": "+14155550001",
                    },
                }
            ],
            "paging": {},
        },
        request=httpx.Request("POST", "https://api.hubapi.com/crm/v3/objects/contacts/search"),
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.request = AsyncMock(return_value=mock_response)

    with patch("app.services.hubspot.settings") as mock_settings:
        mock_settings.HUBSPOT_API_KEY = "test-hubspot-key"

        svc = HubSpotService(http_client=mock_client)
        contacts = await svc.pull_contacts_from_hubspot()

    assert len(contacts) == 1
    assert contacts[0]["email"] == "hs_user@example.com"
    assert contacts[0]["hs_object_id"] == "100"


@pytest.mark.asyncio
async def test_pull_contacts_no_api_key():
    """Pull returns empty list when API key not set."""
    from app.services.hubspot import HubSpotService

    with patch("app.services.hubspot.settings") as mock_settings:
        mock_settings.HUBSPOT_API_KEY = ""

        svc = HubSpotService()
        contacts = await svc.pull_contacts_from_hubspot()

    assert contacts == []


@pytest.mark.asyncio
async def test_pull_contacts_with_since_filter():
    """Pull contacts respects the since datetime filter."""
    from app.services.hubspot import HubSpotService

    mock_response = httpx.Response(
        200,
        json={"results": [], "paging": {}},
        request=httpx.Request("POST", "https://api.hubapi.com/crm/v3/objects/contacts/search"),
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.request = AsyncMock(return_value=mock_response)

    since = datetime(2024, 1, 1, tzinfo=UTC)

    with patch("app.services.hubspot.settings") as mock_settings:
        mock_settings.HUBSPOT_API_KEY = "test-hubspot-key"

        svc = HubSpotService(http_client=mock_client)
        contacts = await svc.pull_contacts_from_hubspot(since=since)

    assert contacts == []
    # Verify the search API was called
    mock_client.request.assert_called_once()
    call_kwargs = mock_client.request.call_args
    assert call_kwargs[0][0] == "POST"


# ── Note Creation Tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_enrichment_note():
    """Create enrichment note calls HubSpot notes API."""
    from app.services.hubspot import HubSpotService

    mock_response = httpx.Response(
        201,
        json={"id": "note-1"},
        request=httpx.Request("POST", "https://api.hubapi.com/crm/v3/objects/notes"),
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.request = AsyncMock(return_value=mock_response)

    with patch("app.services.hubspot.settings") as mock_settings:
        mock_settings.HUBSPOT_API_KEY = "test-hubspot-key"

        svc = HubSpotService(http_client=mock_client)
        await svc.create_enrichment_note("12345", "Enriched via ZoomInfo at 2024-01-01")

    mock_client.request.assert_called_once()
    call_args = mock_client.request.call_args
    assert call_args[0][0] == "POST"
    assert "notes" in call_args[0][1]


@pytest.mark.asyncio
async def test_create_enrichment_note_no_contact_id():
    """Note creation is skipped when no contact ID provided."""
    from app.services.hubspot import HubSpotService

    mock_client = AsyncMock(spec=httpx.AsyncClient)

    with patch("app.services.hubspot.settings") as mock_settings:
        mock_settings.HUBSPOT_API_KEY = "test-hubspot-key"

        svc = HubSpotService(http_client=mock_client)
        await svc.create_enrichment_note("", "Some details")

    mock_client.request.assert_not_called()
