"""
Shared pytest fixtures.

All fixtures use in-memory mocks — no real database required.
"""
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def lead_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_lead(lead_id):
    lead = MagicMock()
    lead.id = lead_id
    lead.email = "test@example.com"
    lead.phone = "+14155552671"
    return lead


@pytest.fixture
def mock_consent(lead_id):
    consent = MagicMock()
    consent.id = uuid.uuid4()
    consent.lead_id = lead_id
    consent.channel = "email"
    consent.method = "web_form"
    consent.proof = {"timestamp": datetime.now(UTC).isoformat(), "source": "test", "ip": "127.0.0.1"}
    consent.granted_at = datetime.now(UTC)
    consent.revoked_at = None
    consent.created_at = datetime.now(UTC)
    return consent


@pytest.fixture
def mock_db():
    """Return a fully-mocked AsyncSession."""
    db = AsyncMock(spec=AsyncSession)
    return db
