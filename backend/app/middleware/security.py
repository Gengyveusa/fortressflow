"""
Security middleware for FortressFlow.

Provides:
  - SecurityHeadersMiddleware  — hardened HTTP response headers
  - CSRFMiddleware             — double-submit cookie CSRF protection
  - RequestValidationMiddleware — body size limits, UA blocking, slow-request logging,
                                  and X-Request-ID injection
"""

from __future__ import annotations

import hmac
import logging
import secrets
import time
import uuid
from typing import Callable

import sentry_sdk
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

MAX_BODY_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
SLOW_REQUEST_THRESHOLD_SECONDS = 5.0

# User-agent substrings that indicate automated / malicious clients.
# These are checked case-insensitively against the User-Agent header.
BLOCKED_USER_AGENTS: list[str] = [
    "sqlmap",
    "nikto",
    "masscan",
    "zgrab",
    "nessus",
    "openvas",
    "qualysguard",
    "acunetix",
    "nmap",
    "dirbuster",
    "gobuster",
    "wfuzz",
    "hydra",
    "burpsuite",
    "w3af",
    "metasploit",
    "havoc",
]

# CSRF cookie / header names
CSRF_COOKIE_NAME = "ff_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_STATE_LENGTH = 32  # bytes → 64 hex chars

# HTTP methods that mutate state and therefore require CSRF verification
CSRF_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Paths that are exempt from CSRF checks:
#   • /api/v1/webhooks/* — signed by external sender (SES, Twilio, etc.)
#   • /docs, /openapi.json, /redoc — Swagger / ReDoc (GET only, not mutating)
CSRF_EXEMPT_PREFIXES = (
    "/api/v1/auth/",
    "/api/v1/tracking/",
    "/api/v1/webhooks/",
    "/docs",
    "/redoc",
    "/openapi.json",
)

# Content-Security-Policy (permissive enough for Swagger UI in non-production)
CSP_DEVELOPMENT = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net fonts.googleapis.com; "
    "font-src 'self' fonts.gstatic.com; "
    "img-src 'self' data: https:; "
    "connect-src 'self'; "
    "frame-ancestors 'none';"
)

CSP_PRODUCTION = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "upgrade-insecure-requests;"
)


# ─────────────────────────────────────────────────────────────────────────────
# SecurityHeadersMiddleware
# ─────────────────────────────────────────────────────────────────────────────


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Inject hardened HTTP security headers on every response and strip the
    Server header to reduce information disclosure.

    Headers applied:
      • X-Content-Type-Options: nosniff
      • X-Frame-Options: DENY
      • X-XSS-Protection: 1; mode=block
      • Referrer-Policy: strict-origin-when-cross-origin
      • Permissions-Policy: camera=(), microphone=(), geolocation=()
      • Strict-Transport-Security (production only)
      • Content-Security-Policy (environment-aware)
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._is_production = settings.ENVIRONMENT == "production"
        self._csp = CSP_PRODUCTION if self._is_production else CSP_DEVELOPMENT

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)

        # Information-disclosure reduction
        if "server" in response.headers:
            del response.headers["server"]
        if "Server" in response.headers:
            del response.headers["Server"]
        response.headers["X-Powered-By"] = "FortressFlow"

        # Standard hardening headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()"
        )
        response.headers["Content-Security-Policy"] = self._csp
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        # HSTS — only set over HTTPS in production to avoid breaking local dev
        if self._is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        return response


# ─────────────────────────────────────────────────────────────────────────────
# CSRFMiddleware
# ─────────────────────────────────────────────────────────────────────────────


def _generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_hex(CSRF_STATE_LENGTH)


def _validate_csrf_token(cookie_token: str, header_token: str) -> bool:
    """
    Compare the cookie-bound token with the value supplied in the request
    header using a constant-time comparison to prevent timing attacks.
    """
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token.encode(), header_token.encode())


def _is_bearer_authenticated(request: Request) -> bool:
    """Return True if the request carries a Bearer token in Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    return auth_header.lower().startswith("bearer ")


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Double-submit cookie CSRF protection.

    • On every request a CSRF token cookie is issued (if not already present).
    • Mutating requests (POST/PUT/PATCH/DELETE) must supply the token via the
      X-CSRF-Token header.
    • Requests with a valid Bearer token (machine-to-machine API calls) are
      exempt — the assumption is they are authenticated via a shared secret
      that a browser cannot forge.
    • Webhook endpoints are also exempt as they use their own signature scheme.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._is_production = settings.ENVIRONMENT == "production"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # ── Exempt paths ──
        for prefix in CSRF_EXEMPT_PREFIXES:
            if request.url.path.startswith(prefix):
                return await call_next(request)

        # ── Exempt Bearer-authenticated API calls ──
        if _is_bearer_authenticated(request):
            return await call_next(request)

        # ── Retrieve or create the CSRF token ──
        cookie_token: str = request.cookies.get(CSRF_COOKIE_NAME, "")
        if not cookie_token:
            cookie_token = _generate_csrf_token()

        # ── Validate on mutating methods ──
        if request.method in CSRF_UNSAFE_METHODS:
            header_token = request.headers.get(CSRF_HEADER_NAME, "")
            if not _validate_csrf_token(cookie_token, header_token):
                logger.warning(
                    "CSRF validation failed",
                    extra={
                        "path": request.url.path,
                        "method": request.method,
                        "ip": request.client.host if request.client else "unknown",
                    },
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "CSRF token missing or invalid.",
                        "hint": f"Include the token from the '{CSRF_COOKIE_NAME}' cookie "
                        f"in the '{CSRF_HEADER_NAME}' request header.",
                    },
                )

        response: Response = await call_next(request)

        # ── Refresh / set the cookie on the response ──
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=cookie_token,
            httponly=False,  # must be readable by JS to set the header
            samesite="strict",
            secure=self._is_production,
            path="/",
            max_age=3600 * 24,  # 24-hour lifetime; refreshed on each response
        )

        return response


# ─────────────────────────────────────────────────────────────────────────────
# RequestValidationMiddleware
# ─────────────────────────────────────────────────────────────────────────────


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Request-level guardrails:

    1. **Request ID** — generates a UUID4 X-Request-ID and propagates it on the
       response so requests can be correlated across logs, Sentry, and metrics.
    2. **Body size limit** — rejects requests with Content-Length > 10 MB before
       the body is read.
    3. **Suspicious User-Agent blocking** — returns 403 for known scan / exploit
       tools (sqlmap, nikto, etc.).
    4. **Slow request logging** — any request taking longer than 5 s is logged at
       WARNING level and captured as a Sentry performance breadcrumb.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # ── 1. Request ID ──
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        # Attach to request state so route handlers can reference it
        request.state.request_id = request_id

        # ── 2. Body size guard ──
        content_length_raw = request.headers.get("Content-Length")
        if content_length_raw:
            try:
                content_length = int(content_length_raw)
                if content_length > MAX_BODY_SIZE_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": (
                                f"Request body too large. Maximum allowed size is "
                                f"{MAX_BODY_SIZE_BYTES // (1024 * 1024)} MB."
                            )
                        },
                    )
            except ValueError:
                pass  # Malformed Content-Length — let the framework handle it

        # ── 3. User-Agent blocking ──
        user_agent = request.headers.get("User-Agent", "").lower()
        for blocked in BLOCKED_USER_AGENTS:
            if blocked in user_agent:
                logger.warning(
                    "Blocked suspicious user-agent",
                    extra={
                        "user_agent": user_agent,
                        "ip": request.client.host if request.client else "unknown",
                        "path": request.url.path,
                    },
                )
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Forbidden."},
                )

        # ── 4. Slow-request instrumentation ──
        start_time = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = time.perf_counter() - start_time

        if elapsed > SLOW_REQUEST_THRESHOLD_SECONDS:
            logger.warning(
                "Slow request detected",
                extra={
                    "request_id": request_id,
                    "path": request.url.path,
                    "method": request.method,
                    "duration_s": round(elapsed, 3),
                    "status_code": response.status_code,
                },
            )
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("request_id", request_id)
                scope.set_extra("path", request.url.path)
                scope.set_extra("method", request.method)
                scope.set_extra("duration_s", round(elapsed, 3))
                scope.set_extra("status_code", response.status_code)
                sentry_sdk.capture_message(
                    f"Slow request: {request.method} {request.url.path} took {elapsed:.2f}s",
                    level="warning",
                )

        # ── Propagate Request ID on response ──
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed * 1000:.2f}ms"

        return response
