"""Settings routes — encrypted API key management."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
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
