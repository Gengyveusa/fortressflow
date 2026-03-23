"""
Tests for lead import endpoints (CSV and HubSpot).

All tests use in-memory mocks — no real database or external APIs required.
"""

import io
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models.user import UserRole


def _make_lead(email: str = "test@example.com", **kwargs) -> MagicMock:
    lead = MagicMock()
    lead.id = uuid.uuid4()
    lead.email = email
    lead.phone = "+14155552671"
    lead.first_name = "Jane"
    lead.last_name = "Doe"
    lead.company = "ACME Inc."
    lead.title = "CTO"
    lead.source = "test"
    lead.meeting_verified = False
    lead.proof_data = None
    lead.meeting_proof = None
    lead.enriched_data = None
    lead.last_enriched_at = None
    lead.created_at = datetime.now(UTC)
    lead.updated_at = datetime.now(UTC)
    for k, v in kwargs.items():
        setattr(lead, k, v)
    return lead


def _mock_current_user():
    """Create a mock user for auth override."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "testuser@fortressflow.io"
    user.full_name = "Test User"
    user.role = UserRole.user
    user.is_active = True
    return user


def _csv_content(rows: list[dict]) -> bytes:
    """Build a CSV file as bytes from a list of row dicts."""
    if not rows:
        return b""
    headers = list(rows[0].keys())
    lines = [",".join(headers)]
    for row in rows:
        lines.append(",".join(str(row.get(h, "")) for h in headers))
    return "\n".join(lines).encode("utf-8")


# ── CSV Import Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_csv_import_valid():
    """CSV import with valid data creates leads and returns summary."""
    csv_data = _csv_content([
        {"email": "alice@example.com", "first_name": "Alice", "last_name": "Smith"},
        {"email": "bob@example.com", "first_name": "Bob", "last_name": "Jones"},
    ])

    async def override_db():
        db = AsyncMock()
        # Each email dedupe check returns None (no existing lead)
        result_none = MagicMock()
        result_none.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_none)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        db.close = AsyncMock()
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: _mock_current_user()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": "Bearer test-csrf-bypass"}) as ac:
            resp = await ac.post(
                "/api/v1/leads/import/csv",
                files={"file": ("leads.csv", io.BytesIO(csv_data), "text/csv")},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_rows"] == 2
        assert body["imported"] == 2
        assert body["skipped_dupes"] == 0
        assert body["errors"] == []
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_csv_import_duplicate_handling():
    """CSV import skips existing leads (duplicate by email)."""
    csv_data = _csv_content([
        {"email": "existing@example.com", "first_name": "Existing", "last_name": "User"},
        {"email": "new@example.com", "first_name": "New", "last_name": "User"},
    ])

    existing_lead = _make_lead(email="existing@example.com")
    call_count = 0

    async def override_db():
        db = AsyncMock()

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            # First call: check for existing@example.com → found
            # Second call: check for new@example.com → not found
            if call_count == 1:
                result.scalar_one_or_none.return_value = existing_lead
            else:
                result.scalar_one_or_none.return_value = None
            return result

        db.execute = AsyncMock(side_effect=execute_side_effect)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        db.close = AsyncMock()
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: _mock_current_user()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": "Bearer test-csrf-bypass"}) as ac:
            resp = await ac.post(
                "/api/v1/leads/import/csv",
                files={"file": ("leads.csv", io.BytesIO(csv_data), "text/csv")},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_rows"] == 2
        assert body["imported"] == 1
        assert body["skipped_dupes"] == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_csv_import_invalid_format():
    """CSV import rejects non-CSV files."""
    async def override_db():
        db = AsyncMock()
        db.rollback = AsyncMock()
        db.close = AsyncMock()
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: _mock_current_user()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": "Bearer test-csrf-bypass"}) as ac:
            resp = await ac.post(
                "/api/v1/leads/import/csv",
                files={"file": ("leads.txt", io.BytesIO(b"not csv"), "text/plain")},
            )
        assert resp.status_code == 400
        assert "CSV" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_csv_import_missing_required_columns():
    """CSV import rejects files missing required columns."""
    csv_data = b"email,company\nalice@example.com,ACME"

    async def override_db():
        db = AsyncMock()
        db.rollback = AsyncMock()
        db.close = AsyncMock()
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: _mock_current_user()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": "Bearer test-csrf-bypass"}) as ac:
            resp = await ac.post(
                "/api/v1/leads/import/csv",
                files={"file": ("leads.csv", io.BytesIO(csv_data), "text/csv")},
            )
        assert resp.status_code == 400
        assert "missing required columns" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


# ── HubSpot Sync Import Tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_hubspot_sync_import():
    """HubSpot import syncs contacts from HubSpot API (mocked)."""
    mock_contacts = [
        {
            "email": "hs_user@example.com",
            "firstname": "HS",
            "lastname": "User",
            "company": "HubCo",
            "jobtitle": "VP Sales",
            "phone": "+14155550001",
        },
    ]

    async def override_db():
        db = AsyncMock()
        result_none = MagicMock()
        result_none.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_none)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        db.close = AsyncMock()
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: _mock_current_user()
    try:
        with patch("app.services.hubspot.HubSpotService") as MockHS:
            instance = MockHS.return_value
            instance.pull_contacts_from_hubspot = AsyncMock(return_value=mock_contacts)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": "Bearer test-csrf-bypass"}) as ac:
                resp = await ac.post("/api/v1/leads/import/hubspot")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_contacts"] == 1
            assert body["synced"] == 1
            assert body["skipped"] == 0
    finally:
        app.dependency_overrides.clear()
