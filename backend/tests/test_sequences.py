"""Tests for sequences API endpoints."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _apply_mock_fields(target, source):
    """Copy mock fields to target object to simulate db.refresh()."""
    target.id = source.id
    target.name = source.name
    target.description = source.description
    target.status = source.status
    target.created_at = source.created_at
    target.updated_at = source.updated_at
    target.steps = source.steps
    target.enrollments = source.enrollments


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_sequence():
    return MagicMock(
        id=uuid.uuid4(),
        name="Test Sequence",
        description="A test sequence",
        status=MagicMock(value="draft"),
        created_at="2024-01-01T00:00:00+00:00",
        updated_at="2024-01-01T00:00:00+00:00",
        steps=[],
        enrollments=[],
    )


class TestSequencesCRUD:
    """Test sequence CRUD operations."""

    def test_create_sequence(self, client):
        """POST /api/v1/sequences/ should create a new sequence."""
        from datetime import datetime, timezone

        from app.models.sequence import SequenceStatus

        mock_db = AsyncMock()
        seq_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        mock_seq = MagicMock()
        mock_seq.id = seq_id
        mock_seq.name = "Outreach Campaign"
        mock_seq.description = "Email outreach"
        mock_seq.status = SequenceStatus.draft
        mock_seq.created_at = now
        mock_seq.updated_at = now
        mock_seq.steps = []
        mock_seq.enrollments = []

        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock(side_effect=lambda obj: _apply_mock_fields(obj, mock_seq))
        mock_db.add = MagicMock()

        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.post(
            "/api/v1/sequences/",
            json={"name": "Outreach Campaign", "description": "Email outreach"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Outreach Campaign"
        assert data["status"] == "draft"
        app.dependency_overrides.clear()

    def test_get_sequence_not_found(self, client):
        """GET /api/v1/sequences/{id} should return 404 for missing sequence."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.get(f"/api/v1/sequences/{uuid.uuid4()}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Sequence not found"
        app.dependency_overrides.clear()

    def test_delete_sequence_not_found(self, client):
        """DELETE /api/v1/sequences/{id} should return 404 for missing sequence."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.delete(f"/api/v1/sequences/{uuid.uuid4()}")
        assert response.status_code == 404
        app.dependency_overrides.clear()

    def test_list_sequences(self, client):
        """GET /api/v1/sequences/ should list sequences."""
        mock_db = AsyncMock()

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0

        # Mock list query
        mock_list_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.return_value = mock_scalars
        mock_scalars.all.return_value = []
        mock_list_result.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_list_result])

        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.get("/api/v1/sequences/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []
        app.dependency_overrides.clear()


class TestSequenceSteps:
    """Test adding steps to sequences."""

    def test_add_step_sequence_not_found(self, client):
        """POST /api/v1/sequences/{id}/steps should return 404 for missing sequence."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.post(
            f"/api/v1/sequences/{uuid.uuid4()}/steps",
            json={"step_type": "email", "position": 0},
        )
        assert response.status_code == 404
        app.dependency_overrides.clear()


class TestSequenceEnrollment:
    """Test enrolling leads into sequences."""

    def test_enroll_sequence_not_found(self, client):
        """POST /api/v1/sequences/{id}/enroll should return 404 for missing sequence."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.post(
            f"/api/v1/sequences/{uuid.uuid4()}/enroll",
            json={"lead_ids": [str(uuid.uuid4())]},
        )
        assert response.status_code == 404
        app.dependency_overrides.clear()


class TestSequenceAnalytics:
    """Test sequence analytics endpoint."""

    def test_analytics_sequence_not_found(self, client):
        """GET /api/v1/sequences/{id}/analytics should return 404 for missing sequence."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.get(f"/api/v1/sequences/{uuid.uuid4()}/analytics")
        assert response.status_code == 404
        app.dependency_overrides.clear()
