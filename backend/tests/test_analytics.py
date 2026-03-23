"""Tests for analytics API endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.main import app


@pytest.fixture
def client(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestDashboardAnalytics:
    """Test dashboard analytics endpoint."""

    def test_dashboard_stats(self, client):
        """GET /api/v1/analytics/dashboard should return aggregate stats."""
        mock_db = AsyncMock()

        # Mock 4 count queries: leads, consents, touches_sent, replies
        results = []
        for val in [10, 5, 100, 15]:
            mock_result = MagicMock()
            mock_result.scalar_one.return_value = val
            results.append(mock_result)

        mock_db.execute = AsyncMock(side_effect=results)

        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.get("/api/v1/analytics/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "total_leads" in data
        assert "active_consents" in data
        assert "touches_sent" in data
        assert "response_rate" in data
        assert data["total_leads"] == 10
        assert data["active_consents"] == 5
        assert data["touches_sent"] == 100
        assert data["response_rate"] == 15.0  # 15/100*100

    def test_dashboard_stats_zero_touches(self, client):
        """Dashboard should handle zero touches gracefully (no division by zero)."""
        mock_db = AsyncMock()

        results = []
        for val in [0, 0, 0, 0]:
            mock_result = MagicMock()
            mock_result.scalar_one.return_value = val
            results.append(mock_result)

        mock_db.execute = AsyncMock(side_effect=results)

        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.get("/api/v1/analytics/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["response_rate"] == 0.0


class TestDeliverabilityAnalytics:
    """Test deliverability analytics endpoint."""

    def test_deliverability_stats(self, client):
        """GET /api/v1/analytics/deliverability should return bounce/spam stats."""
        mock_db = AsyncMock()

        # Mocks: sent, bounced, spam, warmup_active, warmup_completed
        results = []
        for val in [200, 10, 2, 3, 7]:
            mock_result = MagicMock()
            mock_result.scalar_one.return_value = val
            results.append(mock_result)

        mock_db.execute = AsyncMock(side_effect=results)

        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.get("/api/v1/analytics/deliverability")
        assert response.status_code == 200
        data = response.json()
        assert data["total_sent"] == 200
        assert data["total_bounced"] == 10
        assert data["bounce_rate"] == 5.0
        assert data["spam_complaints"] == 2
        assert data["warmup_active"] == 3
        assert data["warmup_completed"] == 7


class TestSequencesAnalytics:
    """Test sequences analytics endpoint."""

    def test_sequences_analytics_empty(self, client):
        """GET /api/v1/analytics/sequences should return empty list when no sequences."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.return_value = mock_scalars
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.get("/api/v1/analytics/sequences")
        assert response.status_code == 200
        data = response.json()
        assert data["sequences"] == []
