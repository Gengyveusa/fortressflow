"""Auth routes — register, login, refresh, profile management."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User, UserRole
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_by_email,
    hash_password,
)
from app.services.brute_force_protection import (
    check_login_allowed,
    record_failed_attempt,
    reset_attempts,
)
from app.services.token_rotation import (
    generate_family_id,
    generate_jti,
    register_token,
    validate_and_rotate,
)
from app.utils.password_validation import validate_password_strength

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ───────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    current_password: str | None = None
    new_password: str | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: str
    last_login_at: str | None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value if isinstance(user.role, UserRole) else str(user.role),
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else "",
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
    )


# ── Routes ────────────────────────────────────────────────────────────────


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Create a new user account."""
    password_errors = validate_password_strength(body.password)
    if password_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Password does not meet requirements", "errors": password_errors},
        )

    existing = await get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=UserRole.user,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    access_token = create_access_token(str(user.id), user.email, user.role.value)
    family_id = generate_family_id()
    jti = generate_jti()
    refresh_token = create_refresh_token(str(user.id), jti=jti, family_id=family_id)
    await register_token(jti, family_id, str(user.id))

    return AuthResponse(
        user=_user_response(user),
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate with email and password."""
    # Brute force protection — check if login is allowed for this email
    allowed, retry_after = await check_login_allowed(body.email)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = await authenticate_user(db, body.email, body.password)
    if user is None:
        await record_failed_attempt(body.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Successful login — reset failure counter
    await reset_attempts(body.email)

    user.last_login_at = datetime.now(UTC)
    await db.flush()

    access_token = create_access_token(str(user.id), user.email, user.role.value)
    family_id = generate_family_id()
    jti = generate_jti()
    refresh_token = create_refresh_token(str(user.id), jti=jti, family_id=family_id)
    await register_token(jti, family_id, str(user.id))

    return AuthResponse(
        user=_user_response(user),
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a refresh token for a new access + refresh token pair (rotation)."""
    payload = decode_token(body.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Token rotation check
    old_jti = payload.get("jti")
    old_family_id = payload.get("family_id")

    if old_jti:
        valid, family_id, _ = await validate_and_rotate(old_jti)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )
        if family_id:
            old_family_id = family_id

    from app.services.auth_service import get_user_by_id
    from uuid import UUID

    user = await get_user_by_id(db, UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    access_token = create_access_token(str(user.id), user.email, user.role.value)

    # Issue new refresh token in the same family (rotation)
    new_family_id = old_family_id or generate_family_id()
    new_jti = generate_jti()
    new_refresh_token = create_refresh_token(
        str(user.id), jti=new_jti, family_id=new_family_id
    )
    await register_token(new_jti, new_family_id, str(user.id))

    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return _user_response(current_user)


@router.put("/me", response_model=UserResponse)
async def update_me(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's profile."""
    if body.full_name is not None:
        current_user.full_name = body.full_name

    if body.new_password:
        if not body.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is required to set a new password",
            )
        from app.services.auth_service import verify_password

        if not verify_password(body.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        password_errors = validate_password_strength(body.new_password)
        if password_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Password does not meet requirements", "errors": password_errors},
            )
        current_user.password_hash = hash_password(body.new_password)

    current_user.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(current_user)

    return _user_response(current_user)
