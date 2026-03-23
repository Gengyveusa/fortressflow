"""
Tests for DNC (Do-Not-Contact) API endpoints.

Covers:
- CRUD operations
- Admin-only delete
- Pagination and search
- Auth required
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import UserRole

_BEARER = {"Authorization": "Bearer test-token"}


@pytest.fixture
def client():
    return TestClient(app)


def _override_db(mock_db):
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db


def _override_auth(role="user"):
    from app.auth import get_current_user, require_role
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.email = "test@test.com"
    mock_user.full_name = "Test User"
    mock_user.role = UserRole.admin if role == "admin" else UserRole.user
    mock_user.is_active = True
    app.dependency_overrides[get_current_user] = lambda: mock_user
    if role == "admin":
        app.dependency_overrides[require_role(UserRole.admin)] = lambda: mock_user
    return mock_user


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()


# ── List DNC ─────────────────────────────────────────────────────────────


class TestListDNC:
    def test_list_dnc_empty(self, client):
        mock_db = AsyncMock()
        # Count query
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        # List query
        list_scalars = MagicMock()
        list_scalars.all.return_value = []
        list_result = MagicMock()
        list_result.scalars.return_value = list_scalars

        mock_db.execute = AsyncMock(side_effect=[count_result, list_result])
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/compliance/dnc")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    def test_list_dnc_with_data(self, client):
        mock_db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar_one.return_value = 2

        dnc1 = MagicMock()
        dnc1.id = uuid.uuid4()
        dnc1.identifier = "bad@email.com"
        dnc1.channel = "email"
        dnc1.reason = "hard_bounce"
        dnc1.source = "ses_webhook"
        dnc1.blocked_at = datetime.now(UTC)
        dnc1.created_at = datetime.now(UTC)

        dnc2 = MagicMock()
        dnc2.id = uuid.uuid4()
        dnc2.identifier = "+14155551234"
        dnc2.channel = "sms"
        dnc2.reason = "stop_requested"
        dnc2.source = "twilio"
        dnc2.blocked_at = datetime.now(UTC)
        dnc2.created_at = datetime.now(UTC)

        list_scalars = MagicMock()
        list_scalars.all.return_value = [dnc1, dnc2]
        list_result = MagicMock()
        list_result.scalars.return_value = list_scalars

        mock_db.execute = AsyncMock(side_effect=[count_result, list_result])
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/compliance/dnc")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["identifier"] == "bad@email.com"

    def test_list_dnc_with_search(self, client):
        mock_db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1

        dnc = MagicMock()
        dnc.id = uuid.uuid4()
        dnc.identifier = "searched@email.com"
        dnc.channel = "email"
        dnc.reason = "manual"
        dnc.source = "admin"
        dnc.blocked_at = datetime.now(UTC)
        dnc.created_at = datetime.now(UTC)

        list_scalars = MagicMock()
        list_scalars.all.return_value = [dnc]
        list_result = MagicMock()
        list_result.scalars.return_value = list_scalars

        mock_db.execute = AsyncMock(side_effect=[count_result, list_result])
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/compliance/dnc?search=searched")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    def test_list_dnc_pagination(self, client):
        mock_db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar_one.return_value = 100

        list_scalars = MagicMock()
        list_scalars.all.return_value = []
        list_result = MagicMock()
        list_result.scalars.return_value = list_scalars

        mock_db.execute = AsyncMock(side_effect=[count_result, list_result])
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/compliance/dnc?page=3&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 3
        assert data["page_size"] == 10
        assert data["total"] == 100

    def test_list_dnc_requires_auth(self, client):
        response = client.get("/api/v1/compliance/dnc")
        assert response.status_code in (401, 403)


# ── Add DNC ──────────────────────────────────────────────────────────────


class TestAddDNC:
    def test_add_dnc_success(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)
        _override_auth()

        from app.services import compliance as compliance_svc

        mock_block = MagicMock()
        mock_block.id = uuid.uuid4()
        mock_block.identifier = "block@email.com"
        mock_block.channel = "email"
        mock_block.reason = "manual_block"
        mock_block.source = "admin_ui"
        mock_block.blocked_at = datetime.now(UTC)

        with MagicMock() as mock_svc:
            compliance_svc.add_to_dnc = AsyncMock(return_value=mock_block)

            response = client.post(
                "/api/v1/compliance/dnc",
                json={
                    "identifier": "block@email.com",
                    "channel": "email",
                    "reason": "manual_block",
                    "source": "admin_ui",
                },
                headers=_BEARER,
            )
            assert response.status_code == 201
            data = response.json()
            assert data["identifier"] == "block@email.com"
            assert data["channel"] == "email"

    def test_add_dnc_requires_auth(self, client):
        response = client.post(
            "/api/v1/compliance/dnc",
            json={
                "identifier": "block@email.com",
                "channel": "email",
                "reason": "test",
                "source": "test",
            },
            headers=_BEARER,
        )
        assert response.status_code in (401, 403)


# ── Delete DNC (Admin only) ─────────────────────────────────────────────


class TestDeleteDNC:
    def test_delete_dnc_success(self, client):
        mock_db = AsyncMock()
        mock_db.delete = AsyncMock()
        mock_db.flush = AsyncMock()

        dnc = MagicMock()
        dnc.id = uuid.uuid4()
        result = MagicMock()
        result.scalar_one_or_none.return_value = dnc
        mock_db.execute = AsyncMock(return_value=result)
        _override_db(mock_db)

        # Override admin role
        from app.auth import get_current_user, require_role
        admin_user = MagicMock()
        admin_user.id = uuid.uuid4()
        admin_user.role = UserRole.admin
        admin_user.is_active = True
        app.dependency_overrides[get_current_user] = lambda: admin_user
        # Also override the require_role dependency
        app.dependency_overrides[require_role(UserRole.admin)] = lambda: admin_user

        response = client.delete(f"/api/v1/compliance/dnc/{dnc.id}", headers=_BEARER)
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True

    def test_delete_dnc_not_found(self, client):
        mock_db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)
        _override_db(mock_db)

        from app.auth import get_current_user, require_role
        admin_user = MagicMock()
        admin_user.id = uuid.uuid4()
        admin_user.role = UserRole.admin
        admin_user.is_active = True
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[require_role(UserRole.admin)] = lambda: admin_user

        fake_id = uuid.uuid4()
        response = client.delete(f"/api/v1/compliance/dnc/{fake_id}", headers=_BEARER)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_dnc_requires_auth(self, client):
        fake_id = uuid.uuid4()
        response = client.delete(f"/api/v1/compliance/dnc/{fake_id}", headers=_BEARER)
        assert response.status_code in (401, 403)
