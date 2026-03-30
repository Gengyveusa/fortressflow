"""
Redis-backed distributed rate limiter for FortressFlow.

Uses a sliding window algorithm implemented with Redis sorted sets and
MULTI/EXEC transactions for atomicity. Falls back to the in-process
RateLimitMiddleware when Redis is unavailable.

Per-endpoint rate limit groups:
  - /api/v1/leads/import         →  10 req/min  (heavy import operation)
  - /api/v1/sequences/generate   →   5 req/min  (AI / LLM calls)
  - /api/v1/webhooks/*           → 500 req/min  (high-volume external events)
  - /health, /metrics            → unlimited
  - everything else              → 200 req/min  (default)

Response headers:
  X-RateLimit-Limit     — the limit for this endpoint group
  X-RateLimit-Remaining — requests remaining in the current window
  X-RateLimit-Reset     — Unix timestamp when the window resets
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

import redis.asyncio as aioredis
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings
from app.middleware.rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Endpoint group configuration
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RateLimitPolicy:
    """Defines a sliding-window rate-limit policy for an endpoint group."""

    group: str
    limit: int  # maximum requests allowed in the window
    window_seconds: int  # duration of the sliding window in seconds


# Ordered list — first match wins (more-specific prefixes before catch-all).
ENDPOINT_POLICIES: list[tuple[str, RateLimitPolicy]] = [
    # Unlimited — health probes and Prometheus scrapes must never be blocked
    ("/health", RateLimitPolicy(group="health", limit=0, window_seconds=60)),
    ("/metrics", RateLimitPolicy(group="metrics", limit=0, window_seconds=60)),
    # Heavy operations
    ("/api/v1/leads/import", RateLimitPolicy(group="leads_import", limit=10, window_seconds=60)),
    ("/api/v1/sequences/generate", RateLimitPolicy(group="sequences_generate", limit=5, window_seconds=60)),
    # High-volume webhook ingestion
    ("/api/v1/webhooks/", RateLimitPolicy(group="webhooks", limit=500, window_seconds=60)),
    # Default — must be last
    ("/", RateLimitPolicy(group="default", limit=200, window_seconds=60)),
]


def _resolve_policy(path: str) -> RateLimitPolicy:
    """Return the most-specific rate limit policy for the given request path."""
    for prefix, policy in ENDPOINT_POLICIES:
        if path.startswith(prefix):
            return policy
    # Fallback — should never be reached given the "/" catch-all
    return ENDPOINT_POLICIES[-1][1]


# ─────────────────────────────────────────────────────────────────────────────
# Redis client (lazy singleton)
# ─────────────────────────────────────────────────────────────────────────────

_redis_client: Optional[aioredis.Redis] = None


async def _get_redis() -> Optional[aioredis.Redis]:
    """Return a connected Redis client or None if the connection cannot be established."""
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
        logger.warning("Redis unavailable for rate limiting — using in-process fallback: %s", exc)
        _redis_client = None
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Sliding-window implementation
# ─────────────────────────────────────────────────────────────────────────────


async def _sliding_window_check(
    redis: aioredis.Redis,
    key: str,
    limit: int,
    window_seconds: int,
    now: float,
) -> tuple[bool, int, float]:
    """
    Evaluate a sliding-window rate limit using Redis sorted sets.

    Returns:
        (allowed, remaining, reset_timestamp)

    The key holds a sorted set where each member is a unique request
    ID (UUID-like) and the score is the epoch timestamp of the request.
    An atomic MULTI/EXEC pipeline ensures no TOCTOU race conditions.

    Key TTL is set to window_seconds + 10 s to allow natural expiry.
    """
    window_start = now - window_seconds
    reset_at = now + window_seconds
    request_member = f"{now:.6f}-{id(key)}"

    async with redis.pipeline(transaction=True) as pipe:
        try:
            # 1. Remove expired entries (outside the current window)
            pipe.zremrangebyscore(key, "-inf", window_start)
            # 2. Count current entries
            pipe.zcard(key)
            # 3. Add the current request (score = timestamp)
            pipe.zadd(key, {request_member: now})
            # 4. Set TTL so idle keys expire automatically
            pipe.expire(key, window_seconds + 10)

            results = await pipe.execute()
        except Exception as exc:
            logger.warning("Redis pipeline error in rate limiter: %s", exc)
            # Fail open — allow the request rather than block legitimate traffic
            return True, limit, reset_at

    current_count_after_remove: int = results[1]  # count after removal, before add

    if current_count_after_remove >= limit:
        # The request we just added pushed us over; undo by removing it
        try:
            await redis.zrem(key, request_member)
        except Exception:
            pass
        remaining = 0
        return False, remaining, reset_at

    remaining = max(0, limit - current_count_after_remove - 1)
    return True, remaining, reset_at


# ─────────────────────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────────────────────


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Distributed sliding-window rate limiter backed by Redis.

    Falls back transparently to the in-process RateLimitMiddleware when
    Redis is unavailable, ensuring the service remains operational during
    cache outages at the cost of per-instance rather than global limits.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        # Instantiate the fallback in-process limiter
        self._fallback = RateLimitMiddleware(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        policy = _resolve_policy(request.url.path)

        # Unlimited endpoints bypass all rate-limiting entirely
        if policy.limit == 0:
            return await call_next(request)

        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
            request.client.host if request.client else "unknown"
        )

        now = time.time()
        window_bucket = int(now // policy.window_seconds)
        redis_key = f"ratelimit:{client_ip}:{policy.group}:{window_bucket}"

        redis = await _get_redis()

        if redis is None:
            # ── Fallback to in-process rate limiting ──
            logger.debug("Rate limit fallback (no Redis): ip=%s path=%s", client_ip, request.url.path)
            return await self._fallback.dispatch(request, call_next)

        try:
            allowed, remaining, reset_at = await _sliding_window_check(
                redis=redis,
                key=redis_key,
                limit=policy.limit,
                window_seconds=policy.window_seconds,
                now=now,
            )
        except Exception as exc:
            logger.warning("Unexpected error in Redis rate limiter — failing open: %s", exc)
            return await call_next(request)

        # ── Build rate-limit headers (always attach, even on 429) ──
        rl_headers = {
            "X-RateLimit-Limit": str(policy.limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(reset_at)),
            "X-RateLimit-Policy": f"{policy.limit};w={policy.window_seconds}",
        }

        if not allowed:
            retry_after = int(reset_at - now) + 1
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please slow down.",
                    "retry_after": retry_after,
                    "limit": policy.limit,
                    "window_seconds": policy.window_seconds,
                },
            )
            for header_name, header_value in rl_headers.items():
                response.headers[header_name] = header_value
            response.headers["Retry-After"] = str(retry_after)
            return response

        response = await call_next(request)
        for header_name, header_value in rl_headers.items():
            response.headers[header_name] = header_value
        return response
