"""
Simple in-process rate limiter middleware using aiolimiter.

Production deployments should use a distributed rate limiter (e.g. Redis-backed).
"""

import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter keyed by client IP.
    Default: 200 requests per 60 seconds per IP.
    """

    def __init__(self, app, requests_per_window: int = 200, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window_start = now - self.window_seconds

        bucket = self._buckets[client_ip]
        # Remove timestamps outside the window
        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= self.requests_per_window:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please slow down."},
            )

        bucket.append(now)
        return await call_next(request)
