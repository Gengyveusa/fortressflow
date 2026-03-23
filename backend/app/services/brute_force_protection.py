"""
Redis-backed brute force protection for login attempts.

Tracks failed login attempts per email address using Redis sorted sets.
After 5 failed attempts within a 15-minute window, the account is locked
for 15 minutes. Successful login resets the failure counter.
"""

import logging
import time

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 15 * 60  # 15 minutes

_redis_client: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis | None:
    """Return a connected Redis client or None."""
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
        logger.warning("Redis unavailable for brute force protection: %s", exc)
        _redis_client = None
        return None


def _key(email: str) -> str:
    return f"login_attempts:{email.lower()}"


async def check_login_allowed(email: str) -> tuple[bool, int]:
    """
    Check if login is allowed for the given email.

    Returns:
        (allowed, retry_after_seconds)
        If allowed is False, retry_after_seconds indicates when to retry.
    """
    r = await _get_redis()
    if r is None:
        # Fail open if Redis is unavailable
        return True, 0

    key = _key(email)
    now = time.time()
    window_start = now - LOCKOUT_WINDOW_SECONDS

    try:
        # Remove expired entries
        await r.zremrangebyscore(key, "-inf", window_start)

        # Count recent failures
        count = await r.zcard(key)

        if count >= MAX_ATTEMPTS:
            # Get the oldest attempt in the window to calculate retry-after
            oldest = await r.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_ts = oldest[0][1]
                retry_after = int(LOCKOUT_WINDOW_SECONDS - (now - oldest_ts)) + 1
                return False, max(1, retry_after)
            return False, LOCKOUT_WINDOW_SECONDS

        return True, 0
    except Exception as exc:
        logger.warning("Brute force check failed, allowing request: %s", exc)
        return True, 0


async def record_failed_attempt(email: str) -> None:
    """Record a failed login attempt for the given email."""
    r = await _get_redis()
    if r is None:
        return

    key = _key(email)
    now = time.time()

    try:
        async with r.pipeline(transaction=True) as pipe:
            pipe.zadd(key, {f"{now}": now})
            pipe.expire(key, LOCKOUT_WINDOW_SECONDS + 10)
            await pipe.execute()
    except Exception as exc:
        logger.warning("Failed to record login attempt: %s", exc)


async def reset_attempts(email: str) -> None:
    """Reset the failure counter after a successful login."""
    r = await _get_redis()
    if r is None:
        return

    try:
        await r.delete(_key(email))
    except Exception as exc:
        logger.warning("Failed to reset login attempts: %s", exc)
