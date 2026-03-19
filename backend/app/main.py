import logging

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.api.v1 import v1_router
from app.config import settings
from app.middleware.rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)

# Sentry initialization (no-op when SENTRY_DSN is empty)
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.2,
    )

app = FastAPI(
    title="FortressFlow API",
    description="Ethical B2B lead-gen and multi-channel sequencer platform",
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

# Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)

# Prometheus metrics
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Routers
app.include_router(v1_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok", "environment": settings.ENVIRONMENT}
