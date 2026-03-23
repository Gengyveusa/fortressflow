"""
Tests for auth API endpoints.

Covers:
- Registration with valid/invalid data
- Login with correct/incorrect credentials
- Brute force lockout after 5 attempts
- Password reset token generation and redemption
- Refresh token rotation
- Profile update
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User, UserRole

_BEARER = {"Authorization": "Bearer test-token"}


@pytest.fixture
def client():
    return TestClient(app)


def _override_db(mock_db):
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db


def _override_auth(user=None):
    from app.auth import get_current_user
    mock_user = user or MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.email = "test@test.com"
    mock_user.full_name = "Test User"
    mock_user.role = UserRole.user
    mock_user.is_active = True
    mock_user.password_hash = "$2b$12$fakehash"
    mock_user.created_at = datetime.now(UTC)
    mock_user.updated_at = datetime.now(UTC)
    mock_user.last_login_at = None
    app.dependency_overrides[get_current_user] = lambda: mock_user
    return mock_user


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()


# ── Registration ─────────────────────────────────────────────────────────


class TestRegistration:
    @patch("app.api.v1.auth.register_token", new_callable=AsyncMock)
    @patch("app.api.v1.auth.get_user_by_email", new_callable=AsyncMock)
    def test_register_success(self, mock_get_email, mock_register_token, client):
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        new_user = MagicMock()
        new_user.id = uuid.uuid4()
        new_user.email = "new@example.com"
        new_user.full_name = "New User"
        new_user.role = UserRole.user
        new_user.is_active = True
        new_user.created_at = datetime.now(UTC)
        new_user.updated_at = datetime.now(UTC)
        new_user.last_login_at = None

        mock_db.refresh = AsyncMock(return_value=None)
        mock_get_email.return_value = None  # No existing user
        _override_db(mock_db)

        # Patch User creation to return our mock
        with patch("app.api.v1.auth.User", return_value=new_user):
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "email": "new@example.com",
                    "password": "StrongP@ss1",
                    "full_name": "New User",
                },
                headers=_BEARER,
            )

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "new@example.com"

    @patch("app.api.v1.auth.get_user_by_email", new_callable=AsyncMock)
    def test_register_duplicate_email(self, mock_get_email, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        existing_user = MagicMock()
        existing_user.email = "existing@example.com"
        mock_get_email.return_value = existing_user

        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "existing@example.com",
                "password": "StrongP@ss1",
            },
            headers=_BEARER,
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_register_weak_password(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        response = client.post(
            "/api/v1/auth/register",
            json={"email": "user@test.com", "password": "weak"},
            headers=_BEARER,
        )
        assert response.status_code == 400

    def test_register_invalid_email(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        response = client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "StrongP@ss1"},
            headers=_BEARER,
        )
        assert response.status_code == 422


# ── Login ────────────────────────────────────────────────────────────────


class TestLogin:
    @patch("app.api.v1.auth.register_token", new_callable=AsyncMock)
    @patch("app.api.v1.auth.reset_attempts", new_callable=AsyncMock)
    @patch("app.api.v1.auth.authenticate_user", new_callable=AsyncMock)
    @patch("app.api.v1.auth.check_login_allowed", new_callable=AsyncMock)
    def test_login_success(
        self, mock_check, mock_auth, mock_reset, mock_register_token, client
    ):
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        _override_db(mock_db)

        mock_check.return_value = (True, 0)

        user = MagicMock()
        user.id = uuid.uuid4()
        user.email = "user@test.com"
        user.full_name = "Test User"
        user.role = UserRole.user
        user.is_active = True
        user.created_at = datetime.now(UTC)
        user.updated_at = datetime.now(UTC)
        user.last_login_at = None
        mock_auth.return_value = user

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "user@test.com", "password": "StrongP@ss1"},
            headers=_BEARER,
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @patch("app.api.v1.auth.record_failed_attempt", new_callable=AsyncMock)
    @patch("app.api.v1.auth.authenticate_user", new_callable=AsyncMock)
    @patch("app.api.v1.auth.check_login_allowed", new_callable=AsyncMock)
    def test_login_invalid_credentials(
        self, mock_check, mock_auth, mock_record, client
    ):
        mock_db = AsyncMock()
        _override_db(mock_db)

        mock_check.return_value = (True, 0)
        mock_auth.return_value = None

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "user@test.com", "password": "wrongpassword"},
            headers=_BEARER,
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()
        mock_record.assert_called_once()

    @patch("app.api.v1.auth.check_login_allowed", new_callable=AsyncMock)
    def test_login_brute_force_lockout(self, mock_check, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        mock_check.return_value = (False, 300)

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "user@test.com", "password": "anything"},
            headers=_BEARER,
        )
        assert response.status_code == 429
        assert "too many" in response.json()["detail"].lower()


# ── Refresh Token ────────────────────────────────────────────────────────


class TestRefreshToken:
    def test_refresh_invalid_token(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.jwt.token"},
            headers=_BEARER,
        )
        assert response.status_code == 401

    @patch("app.api.v1.auth.register_token", new_callable=AsyncMock)
    @patch("app.api.v1.auth.validate_and_rotate", new_callable=AsyncMock)
    @patch("app.services.auth_service.get_user_by_id", new_callable=AsyncMock)
    def test_refresh_success(
        self, mock_get_user, mock_rotate, mock_register_token, client
    ):
        mock_db = AsyncMock()
        _override_db(mock_db)

        from app.services.auth_service import create_refresh_token

        user_id = str(uuid.uuid4())
        token = create_refresh_token(user_id, jti="test-jti", family_id="test-family")

        user = MagicMock()
        user.id = uuid.UUID(user_id)
        user.email = "user@test.com"
        user.role = UserRole.user
        user.is_active = True

        mock_rotate.return_value = (True, "test-family", user_id)
        mock_get_user.return_value = user

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token},
            headers=_BEARER,
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @patch("app.api.v1.auth.validate_and_rotate", new_callable=AsyncMock)
    def test_refresh_revoked_token(self, mock_rotate, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        from app.services.auth_service import create_refresh_token

        user_id = str(uuid.uuid4())
        token = create_refresh_token(user_id, jti="revoked-jti", family_id="family")

        mock_rotate.return_value = (False, None, None)

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token},
            headers=_BEARER,
        )
        assert response.status_code == 401
        assert "revoked" in response.json()["detail"].lower()


# ── Profile ──────────────────────────────────────────────────────────────


class TestProfile:
    def test_get_me(self, client):
        user = _override_auth()
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@test.com"
        assert data["is_active"] is True

    def test_get_me_requires_auth(self, client):
        response = client.get("/api/v1/auth/me")
        assert response.status_code in (401, 403)

    def test_update_name(self, client):
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        _override_db(mock_db)
        user = _override_auth()

        response = client.put(
            "/api/v1/auth/me",
            json={"full_name": "Updated Name"},
            headers=_BEARER,
        )
        assert response.status_code == 200
        assert user.full_name == "Updated Name"

    def test_update_password_without_current(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)
        _override_auth()

        response = client.put(
            "/api/v1/auth/me",
            json={"new_password": "NewStrongP@ss1"},
            headers=_BEARER,
        )
        assert response.status_code == 400
        assert "current password" in response.json()["detail"].lower()

    @patch("app.services.auth_service.verify_password", return_value=False)
    def test_update_password_wrong_current(self, mock_verify, client):
        mock_db = AsyncMock()
        _override_db(mock_db)
        _override_auth()

        response = client.put(
            "/api/v1/auth/me",
            json={
                "current_password": "wrong",
                "new_password": "NewStrongP@ss1",
            },
            headers=_BEARER,
        )
        assert response.status_code == 400
        assert "incorrect" in response.json()["detail"].lower()


# ── Password Reset ───────────────────────────────────────────────────────


class TestPasswordReset:
    @patch("app.api.v1.auth._get_redis")
    @patch("app.api.v1.auth.get_user_by_email", new_callable=AsyncMock)
    def test_forgot_password_success(self, mock_get_email, mock_get_redis, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        user = MagicMock()
        user.id = uuid.uuid4()
        user.is_active = True
        mock_get_email.return_value = user

        mock_redis = MagicMock()
        mock_redis.setex = MagicMock()
        mock_redis.close = MagicMock()
        mock_get_redis.return_value = mock_redis

        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "user@test.com"},
            headers=_BEARER,
        )
        assert response.status_code == 200
        assert "sent" in response.json()["message"].lower()
        mock_redis.setex.assert_called_once()

    @patch("app.api.v1.auth._get_redis")
    @patch("app.api.v1.auth.get_user_by_email", new_callable=AsyncMock)
    def test_forgot_password_unknown_email(self, mock_get_email, mock_get_redis, client):
        """Always returns success to prevent email enumeration."""
        mock_db = AsyncMock()
        _override_db(mock_db)

        mock_get_email.return_value = None  # No user found

        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "unknown@test.com"},
            headers=_BEARER,
        )
        assert response.status_code == 200  # Still 200

    @patch("app.api.v1.auth._get_redis")
    @patch("app.services.auth_service.get_user_by_id", new_callable=AsyncMock)
    def test_reset_password_success(self, mock_get_user, mock_get_redis, client):
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        _override_db(mock_db)

        user_id = str(uuid.uuid4())
        mock_redis = MagicMock()
        mock_redis.get = MagicMock(return_value=user_id)
        mock_redis.delete = MagicMock()
        mock_redis.scan_iter = MagicMock(return_value=[])
        mock_redis.close = MagicMock()
        mock_get_redis.return_value = mock_redis

        user = MagicMock()
        user.id = uuid.UUID(user_id)
        user.password_hash = "$2b$12$old"
        user.updated_at = None
        mock_get_user.return_value = user

        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "valid-token", "new_password": "NewStr0ng!Pass"},
            headers=_BEARER,
        )
        assert response.status_code == 200
        assert "reset successfully" in response.json()["message"].lower()

    @patch("app.api.v1.auth._get_redis")
    def test_reset_password_invalid_token(self, mock_get_redis, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        mock_redis = MagicMock()
        mock_redis.get = MagicMock(return_value=None)
        mock_redis.close = MagicMock()
        mock_get_redis.return_value = mock_redis

        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "invalid-token", "new_password": "NewStr0ng!Pass"},
            headers=_BEARER,
        )
        assert response.status_code == 400
        assert "invalid or expired" in response.json()["detail"].lower()

    def test_reset_password_short_password(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "any-token", "new_password": "short"},
            headers=_BEARER,
        )
        assert response.status_code == 400
