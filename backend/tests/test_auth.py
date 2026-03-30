"""
Tests for the authentication system.

Covers:
- Password hashing and verification
- JWT token creation and decoding
- Token expiry and type validation
- Auth service functions
- Role-based access control
"""



from app.models.user import UserRole
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


# ── Password Hashing Tests ───────────────────────────────────────────────────


class TestPasswordHashing:
    def test_hash_password_returns_bcrypt_hash(self):
        hashed = hash_password("mysecretpassword")
        assert hashed.startswith("$2b$")
        assert hashed != "mysecretpassword"

    def test_verify_password_correct(self):
        hashed = hash_password("testpass123")
        assert verify_password("testpass123", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("testpass123")
        assert verify_password("wrongpassword", hashed) is False

    def test_hash_password_unique_per_call(self):
        h1 = hash_password("samepassword")
        h2 = hash_password("samepassword")
        assert h1 != h2  # bcrypt uses unique salts


# ── JWT Token Tests ──────────────────────────────────────────────────────────


class TestJWTTokens:
    def test_create_access_token_returns_string(self):
        token = create_access_token("user-123", "test@example.com", "user")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_access_token(self):
        token = create_access_token("user-123", "test@example.com", "admin")
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    def test_create_refresh_token(self):
        token = create_refresh_token("user-456")
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-456"
        assert payload["type"] == "refresh"

    def test_decode_invalid_token_returns_none(self):
        assert decode_token("invalid.jwt.token") is None

    def test_decode_empty_token_returns_none(self):
        assert decode_token("") is None

    def test_access_token_has_expected_claims(self):
        token = create_access_token("id-1", "a@b.com", "viewer")
        payload = decode_token(token)
        assert "exp" in payload
        assert payload["type"] == "access"

    def test_refresh_token_has_expected_claims(self):
        token = create_refresh_token("id-2")
        payload = decode_token(token)
        assert "exp" in payload
        assert payload["type"] == "refresh"


# ── Auth Fixture Tests ───────────────────────────────────────────────────────


class TestAuthFixtures:
    def test_auth_token_fixture_is_valid(self, mock_user, auth_token):
        payload = decode_token(auth_token)
        assert payload is not None
        assert payload["sub"] == str(mock_user.id)
        assert payload["email"] == mock_user.email
        assert payload["role"] == "user"
        assert payload["type"] == "access"

    def test_admin_auth_token_fixture_is_valid(self, mock_admin_user, admin_auth_token):
        payload = decode_token(admin_auth_token)
        assert payload is not None
        assert payload["sub"] == str(mock_admin_user.id)
        assert payload["role"] == "admin"


# ── Role Enum Tests ──────────────────────────────────────────────────────────


class TestUserRole:
    def test_role_values(self):
        assert UserRole.admin.value == "admin"
        assert UserRole.user.value == "user"
        assert UserRole.viewer.value == "viewer"

    def test_role_is_string_enum(self):
        assert isinstance(UserRole.admin, str)
        assert UserRole.admin == "admin"
