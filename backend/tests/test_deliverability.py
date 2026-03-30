"""Tests for deliverability API endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.main import app


@pytest.fixture
def client(mock_user, auth_token):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    c = TestClient(app, headers={"Authorization": f"Bearer {auth_token}"})
    yield c
    app.dependency_overrides.clear()


class TestDomains:
    """Test domain management endpoints."""

    def test_list_domains_empty(self, client):
        """GET /api/v1/deliverability/domains should return empty list."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.get("/api/v1/deliverability/domains")
        assert response.status_code == 200
        assert response.json() == []

    def test_add_domain_conflict(self, client):
        """POST /api/v1/deliverability/domains should return 409 for duplicate domain."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()  # domain exists
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.post(
            "/api/v1/deliverability/domains",
            json={"domain": "example.com"},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "Domain already exists"


class TestWarmup:
    """Test warmup status endpoint."""

    def test_warmup_status_empty(self, client):
        """GET /api/v1/deliverability/warmup should return empty list."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.get("/api/v1/deliverability/warmup")
        assert response.status_code == 200
        assert response.json() == []
