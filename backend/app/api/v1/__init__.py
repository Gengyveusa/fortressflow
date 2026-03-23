from fastapi import APIRouter

from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.compliance import router as compliance_router
from app.api.v1.deliverability import router as deliverability_router
from app.api.v1.leads import router as leads_router
from app.api.v1.presets import router as presets_router
from app.api.v1.sequences import router as sequences_router
from app.api.v1.templates import router as templates_router
from app.api.v1.tracking import router as tracking_router
from app.api.v1.unsubscribe import router as unsubscribe_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.chat import router as chat_router
from app.api.v1.deals import router as deals_router
from app.api.v1.settings import router as settings_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(analytics_router)
v1_router.include_router(compliance_router)
v1_router.include_router(deliverability_router)
v1_router.include_router(leads_router)
v1_router.include_router(presets_router)
v1_router.include_router(sequences_router)
v1_router.include_router(templates_router)
v1_router.include_router(tracking_router)
v1_router.include_router(unsubscribe_router)
v1_router.include_router(webhooks_router)
v1_router.include_router(chat_router)
v1_router.include_router(deals_router)
v1_router.include_router(settings_router)
