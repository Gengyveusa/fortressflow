"""
FortressFlow API — main application entry point (v0.6.0)

Phase 6 additions:
  • SecurityHeadersMiddleware  — hardened HTTP response headers
  • CSRFMiddleware             — double-submit cookie CSRF protection
  • RequestValidationMiddleware — body size guard, UA blocking, slow-request alerts
  • RedisRateLimitMiddleware   — distributed sliding-window rate limiting with fallback
  • Structured JSON logging    — machine-readable log output for log aggregators
  • Sentry performance tracing — full-transaction traces with profiling
"""

from __future__ import annotations

import logging
import logging.config
import sys

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.api.v1 import v1_router
from app.config import settings
from app.middleware.redis_rate_limit import RedisRateLimitMiddleware
from app.middleware.security import (
    CSRFMiddleware,
    RequestValidationMiddleware,
    SecurityHeadersMiddleware,
)

# ─────────────────────────────────────────────────────────────────────────────
# Structured logging configuration
# ─────────────────────────────────────────────────────────────────────────────

_LOG_FORMAT = "json" if settings.ENVIRONMENT == "production" else "text"

LOGGING_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
        "text": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d — %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": _LOG_FORMAT,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "uvicorn": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "sqlalchemy.engine": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "app": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}

try:
    logging.config.dictConfig(LOGGING_CONFIG)
except Exception:
    # python-json-logger not installed — fall back to basic text logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
        stream=sys.stdout,
    )

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Sentry initialization
# ─────────────────────────────────────────────────────────────────────────────

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=f"fortressflow@0.6.0",
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
            LoggingIntegration(
                level=logging.INFO,        # breadcrumb level
                event_level=logging.ERROR, # Sentry event level
            ),
            RedisIntegration(),
            SqlalchemyIntegration(),
        ],
        # Performance — sample 20% of requests in production, 100% in dev
        traces_sample_rate=0.2 if settings.ENVIRONMENT == "production" else 1.0,
        # Profiling — available with sentry-sdk[profiling]
        profiles_sample_rate=0.1 if settings.ENVIRONMENT == "production" else 0.0,
        # Filter out health / metrics noise from performance traces
        traces_sampler=lambda ctx: (
            0.0
            if ctx.get("asgi_scope", {}).get("path", "") in ("/health", "/metrics")
            else (0.2 if settings.ENVIRONMENT == "production" else 1.0)
        ),
        send_default_pii=False,
        attach_stacktrace=True,
        max_breadcrumbs=50,
    )
    logger.info("Sentry initialized for environment: %s", settings.ENVIRONMENT)

# ─────────────────────────────────────────────────────────────────────────────
# FastAPI application
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="FortressFlow API",
    description=(
        "Ethical B2B lead-generation and multi-channel sequencer platform for the dental "
        "and healthcare market. Built for Gengyve USA Inc."
    ),
    version="0.6.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    contact={
        "name": "Gengyve USA Engineering",
        "email": "thad@gengyveusa.com",
    },
    license_info={
        "name": "Proprietary — Gengyve USA Inc.",
    },
)

# ─────────────────────────────────────────────────────────────────────────────
# Middleware stack
#
# Starlette executes middleware in LIFO (last-added = outermost = first to run).
# Desired execution order (outermost → innermost):
#
#   RequestValidationMiddleware   ← first: rejects invalid/oversized requests
#   SecurityHeadersMiddleware     ← adds response headers on the way out
#   CSRFMiddleware                ← validates CSRF before CORS
#   CORSMiddleware                ← standard CORS handling
#   RedisRateLimitMiddleware      ← rate limiting (innermost before router)
#
# Therefore we add them in reverse order below.
# ─────────────────────────────────────────────────────────────────────────────

# 5. Rate limiting (innermost — closest to the route handlers)
app.add_middleware(RedisRateLimitMiddleware)

# 4. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. CSRF protection (after CORS so pre-flight OPTIONS requests pass through)
app.add_middleware(CSRFMiddleware)

# 2. Security headers (on the response path, after CSRF)
app.add_middleware(SecurityHeadersMiddleware)

# 1. Request validation (outermost — rejects bad requests before any other processing)
app.add_middleware(RequestValidationMiddleware)

# ─────────────────────────────────────────────────────────────────────────────
# Prometheus metrics
# ─────────────────────────────────────────────────────────────────────────────

Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=False,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/metrics"],
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# ─────────────────────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────────────────────

app.include_router(v1_router)


# ─────────────────────────────────────────────────────────────────────────────
# Built-in endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["health"], include_in_schema=True)
async def health_check() -> dict:
    """Liveness probe — returns 200 OK when the application is running."""
    return {
        "status": "ok",
        "version": "0.6.0",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/ready", tags=["health"], include_in_schema=True)
async def readiness_check() -> dict:
    """
    Readiness probe — checks that critical upstream dependencies are reachable.
    Returns 200 when ready to serve traffic, 503 when degraded.
    """
    import asyncpg
    import redis.asyncio as aioredis

    checks: dict[str, str] = {}
    healthy = True

    # PostgreSQL
    try:
        conn = await asyncpg.connect(
            settings.DATABASE_URL.replace("+asyncpg", ""),
            timeout=2,
        )
        await conn.fetchval("SELECT 1")
        await conn.close()
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"
        healthy = False

    # Redis
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        healthy = False

    status_code = 200 if healthy else 503
    from fastapi.responses import JSONResponse as _JSONResponse
    return _JSONResponse(
        status_code=status_code,
        content={"status": "ready" if healthy else "degraded", "checks": checks},
    )
