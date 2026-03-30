"""
Lead API unit tests.

All tests use in-memory mocks — no real database required.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.main import app
from app.database import get_db


def _make_lead(email: str = "test@example.com") -> MagicMock:
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
    lead.created_at = datetime.now(UTC)
    lead.updated_at = datetime.now(UTC)
    return lead


def _mock_db_with_lead(lead):
    db = AsyncMock()
    result = AsyncMock()
    result.scalar_one_or_none.return_value = None  # email not taken
    result2 = AsyncMock()
    result2.scalar_one_or_none.return_value = lead
    db.execute.side_effect = [result, result2]
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    return db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.asyncio
async def test_create_lead_duplicate_email(mock_user):
    """Creating a lead with a duplicate email returns 409."""
    existing_lead = _make_lead()

    async def override_db():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = existing_lead
        db.execute.return_value = result
        db.rollback = AsyncMock()
        db.close = AsyncMock()
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    from httpx import AsyncClient, ASGITransport

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer test-csrf-bypass"},
        ) as ac:
            resp = await ac.post(
                "/api/v1/leads/",
                json={
                    "email": "test@example.com",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "company": "ACME",
                    "title": "CTO",
                    "source": "test",
                },
            )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_lead_not_found(mock_user):
    """Getting a non-existent lead returns 404."""

    async def override_db():
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result
        db.rollback = AsyncMock()
        db.close = AsyncMock()
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    from httpx import AsyncClient, ASGITransport

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/api/v1/leads/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_health_check():
    """Health endpoint returns 200."""
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
