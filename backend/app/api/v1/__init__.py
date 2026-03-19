from fastapi import APIRouter

from app.api.v1.analytics import router as analytics_router
from app.api.v1.compliance import router as compliance_router
from app.api.v1.deliverability import router as deliverability_router
from app.api.v1.leads import router as leads_router
from app.api.v1.sequences import router as sequences_router
from app.api.v1.unsubscribe import router as unsubscribe_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(analytics_router)
v1_router.include_router(compliance_router)
v1_router.include_router(deliverability_router)
v1_router.include_router(leads_router)
v1_router.include_router(sequences_router)
v1_router.include_router(unsubscribe_router)
