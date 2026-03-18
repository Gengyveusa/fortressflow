from fastapi import APIRouter

from app.api.v1.compliance import router as compliance_router
from app.api.v1.leads import router as leads_router
from app.api.v1.unsubscribe import router as unsubscribe_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(compliance_router)
v1_router.include_router(leads_router)
v1_router.include_router(unsubscribe_router)
