"""
Refresh token rotation with family-based theft detection.

Each refresh token belongs to a "family" identified by a family_id.
When a refresh token is used:
  1. A new refresh token is issued (same family, incremented generation)
  2. The old token is blacklisted
  3. If a blacklisted token is reused, ALL tokens in that family are revoked

Uses Redis for token state storage with TTL matching token expiry.
"""

import logging
import uuid

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

# Token family TTL matches refresh token expiry (7 days + buffer)
FAMILY_TTL_SECONDS = 8 * 24 * 60 * 60  # 8 days

_redis_client: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis | None:
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None

    try:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=0.5,
        )
        await _redis_client.ping()
        return _redis_client
    except Exception as exc:
        logger.warning("Redis unavailable for token rotation: %s", exc)
        _redis_client = None
        return None


def _token_key(token_jti: str) -> str:
    return f"refresh_token:{token_jti}"


def _family_key(family_id: str) -> str:
    return f"token_family:{family_id}"


async def register_token(token_jti: str, family_id: str, user_id: str) -> None:
    """Register a newly issued refresh token."""
    r = await _get_redis()
    if r is None:
        return

    try:
        async with r.pipeline(transaction=True) as pipe:
            # Store token -> family mapping
            pipe.set(
                _token_key(token_jti),
                f"{family_id}:{user_id}:active",
                ex=FAMILY_TTL_SECONDS,
            )
            # Add token to family set
            pipe.sadd(_family_key(family_id), token_jti)
            pipe.expire(_family_key(family_id), FAMILY_TTL_SECONDS)
            await pipe.execute()
    except Exception as exc:
        logger.warning("Failed to register refresh token: %s", exc)


async def validate_and_rotate(token_jti: str) -> tuple[bool, str | None, str | None]:
    """
    Validate a refresh token for rotation.

    Returns:
        (valid, family_id, user_id)
        - valid=True: token is good, caller should issue new tokens
        - valid=False: token is blacklisted/revoked/unknown
    """
    r = await _get_redis()
    if r is None:
        # Fail open — allow refresh without rotation tracking
        return True, None, None

    try:
        token_data = await r.get(_token_key(token_jti))
        if token_data is None:
            # Unknown token — could be from before rotation was enabled, allow it
            return True, None, None

        parts = token_data.split(":", 2)
        if len(parts) < 3:
            return False, None, None

        family_id, user_id, state = parts[0], parts[1], parts[2]

        if state == "revoked":
            # This token was already rotated — potential theft!
            logger.warning(
                "Reuse of rotated refresh token detected! family=%s jti=%s — revoking entire family",
                family_id,
                token_jti,
            )
            await revoke_family(family_id)
            return False, family_id, user_id

        if state != "active":
            return False, family_id, user_id

        # Mark current token as revoked (it's been used)
        await r.set(
            _token_key(token_jti),
            f"{family_id}:{user_id}:revoked",
            ex=FAMILY_TTL_SECONDS,
        )

        return True, family_id, user_id

    except Exception as exc:
        logger.warning("Token rotation validation failed: %s", exc)
        # Fail open
        return True, None, None


async def revoke_family(family_id: str) -> None:
    """Revoke all tokens in a token family (theft detected)."""
    r = await _get_redis()
    if r is None:
        return

    try:
        members = await r.smembers(_family_key(family_id))
        if members:
            async with r.pipeline(transaction=True) as pipe:
                for jti in members:
                    # We don't know the user_id here, so read existing data
                    existing = await r.get(_token_key(jti))
                    if existing:
                        parts = existing.split(":", 2)
                        pipe.set(
                            _token_key(jti),
                            f"{parts[0]}:{parts[1] if len(parts) > 1 else 'unknown'}:revoked",
                            ex=FAMILY_TTL_SECONDS,
                        )
                await pipe.execute()
        logger.info("Revoked all tokens in family %s (%d tokens)", family_id, len(members))
    except Exception as exc:
        logger.warning("Failed to revoke token family: %s", exc)


def generate_family_id() -> str:
    """Generate a new token family ID."""
    return str(uuid.uuid4())


def generate_jti() -> str:
    """Generate a unique token identifier."""
    return str(uuid.uuid4())
