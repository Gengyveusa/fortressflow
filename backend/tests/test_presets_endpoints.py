"""
Tests for preset API endpoints.

Covers:
- GET /presets/ returns available presets
- POST /presets/{index}/deploy deploys a preset correctly
- Invalid preset index returns 404
- Auth required
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


_BEARER = {"Authorization": "Bearer test-token"}


@pytest.fixture
def client():
    return TestClient(app)


def _override_db(mock_db):
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db


def _override_auth():
    from app.auth import get_current_user
    mock_user = MagicMock()
    mock_user.id = "00000000-0000-0000-0000-000000000001"
    mock_user.email = "test@test.com"
    mock_user.role = MagicMock()
    mock_user.role.value = "user"
    app.dependency_overrides[get_current_user] = lambda: mock_user


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()


class TestListPresets:
    def test_list_presets_returns_array(self, client):
        _override_auth()
        response = client.get("/api/v1/presets/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_list_presets_structure(self, client):
        _override_auth()
        response = client.get("/api/v1/presets/")
        data = response.json()
        preset = data[0]
        assert "name" in preset
        assert "description" in preset
        assert "category" in preset
        assert "steps" in preset
        assert isinstance(preset["steps"], list)

    def test_list_presets_step_structure(self, client):
        _override_auth()
        response = client.get("/api/v1/presets/")
        data = response.json()
        # Find first preset with steps
        for preset in data:
            if preset["steps"]:
                step = preset["steps"][0]
                assert "step_type" in step
                assert "position" in step
                assert "delay_hours" in step
                assert "has_template" in step
                break

    def test_list_presets_requires_auth(self, client):
        response = client.get("/api/v1/presets/")
        assert response.status_code in (401, 403)


class TestDeployPreset:
    def test_deploy_preset_success(self, client):
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        # Mock db.refresh to set ID on the sequence object
        import uuid

        async def mock_refresh(obj):
            if not hasattr(obj, '_refreshed'):
                obj.id = uuid.uuid4()
                obj._refreshed = True

        mock_db.refresh = AsyncMock(side_effect=mock_refresh)
        _override_db(mock_db)
        _override_auth()

        response = client.post("/api/v1/presets/0/deploy", headers=_BEARER)
        assert response.status_code == 201
        data = response.json()
        assert "sequence_id" in data
        assert "sequence_name" in data
        assert "templates_created" in data
        assert "steps_created" in data
        assert data["status"] == "deployed_as_draft"

    def test_deploy_invalid_preset_index(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)
        _override_auth()

        response = client.post("/api/v1/presets/999/deploy", headers=_BEARER)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_deploy_negative_index(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)
        _override_auth()

        response = client.post("/api/v1/presets/-1/deploy", headers=_BEARER)
        assert response.status_code == 404

    def test_deploy_requires_auth(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)
        response = client.post("/api/v1/presets/0/deploy", headers=_BEARER)
        assert response.status_code in (401, 403)
