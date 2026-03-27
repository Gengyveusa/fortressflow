"""Settings routes — encrypted API key management and integration status."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import settings as app_settings
from app.database import get_db
from app.models.user import User
from app.services.api_key_service import (
    delete_api_key,
    list_api_keys,
    store_api_key,
)

router = APIRouter(prefix="/settings", tags=["settings"])


class StoreKeyRequest(BaseModel):
    api_key: str


class KeyResponse(BaseModel):
    service_name: str
    masked_key: str
    created_at: str | None = None
    updated_at: str | None = None


@router.get("/api-keys", response_model=list[KeyResponse])
async def get_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all configured API keys with masked values."""
    return await list_api_keys(db, current_user.id)


@router.put("/api-keys/{service}", response_model=KeyResponse)
async def upsert_api_key(
    service: str,
    body: StoreKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store or update an API key for a service."""
    if not body.api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key cannot be empty",
        )
    return await store_api_key(db, current_user.id, service, body.api_key.strip())


@router.delete("/api-keys/{service}")
async def remove_api_key(
    service: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove an API key for a service."""
    deleted = await delete_api_key(db, current_user.id, service)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found for this service",
        )
    return {"message": f"API key for {service} removed"}


class IntegrationStatusEntry(BaseModel):
    name: str
    configured: bool
    mode: str  # "active", "manual", "not_configured"


class IntegrationStatusResponse(BaseModel):
    integrations: list[IntegrationStatusEntry]


@router.get("/integration-status", response_model=IntegrationStatusResponse)
async def get_integration_status(
    current_user: User = Depends(get_current_user),
):
    """Return which integrations are configured and their mode."""
    integrations: list[IntegrationStatusEntry] = []

    # LinkedIn / Phantombuster
    pb_key = getattr(app_settings, "PHANTOMBUSTER_API_KEY", "")
    pb_connect = getattr(app_settings, "PHANTOMBUSTER_CONNECT_AGENT_ID", "")
    pb_message = getattr(app_settings, "PHANTOMBUSTER_MESSAGE_AGENT_ID", "")
    if pb_key and (pb_connect or pb_message):
        integrations.append(IntegrationStatusEntry(
            name="linkedin", configured=True, mode="active",
        ))
    else:
        integrations.append(IntegrationStatusEntry(
            name="linkedin", configured=False, mode="manual",
        ))

    # HubSpot
    hs_key = app_settings.HUBSPOT_API_KEY
    integrations.append(IntegrationStatusEntry(
        name="hubspot",
        configured=bool(hs_key),
        mode="active" if hs_key else "not_configured",
    ))

    # ZoomInfo — configured if API key, or client_id + private key are set
    zi_configured = bool(
        app_settings.ZOOMINFO_API_KEY
        or (app_settings.ZOOMINFO_CLIENT_ID and app_settings.ZOOMINFO_PRIVATE_KEY)
        or (app_settings.ZOOMINFO_CLIENT_ID and app_settings.ZOOMINFO_CLIENT_SECRET)
    )
    integrations.append(IntegrationStatusEntry(
        name="zoominfo",
        configured=zi_configured,
        mode="active" if zi_configured else "not_configured",
    ))

    # Apollo
    ap_key = app_settings.APOLLO_API_KEY
    integrations.append(IntegrationStatusEntry(
        name="apollo",
        configured=bool(ap_key),
        mode="active" if ap_key else "not_configured",
    ))

    # Twilio SMS
    tw_sid = app_settings.TWILIO_ACCOUNT_SID
    integrations.append(IntegrationStatusEntry(
        name="twilio",
        configured=bool(tw_sid),
        mode="active" if tw_sid else "not_configured",
    ))

    # AWS SES
    ses_key = app_settings.AWS_ACCESS_KEY_ID
    integrations.append(IntegrationStatusEntry(
        name="aws_ses",
        configured=bool(ses_key),
        mode="active" if ses_key else "not_configured",
    ))

    return IntegrationStatusResponse(integrations=integrations)
