"""API key encryption/decryption and storage service."""

import base64
import hashlib
import logging
from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.api_configuration import ApiConfiguration

logger = logging.getLogger(__name__)


_SERVICE_ALIASES: dict[str, tuple[str, ...]] = {
    "taplio": ("taplio", "taplio_webhook"),
    "taplio_webhook": ("taplio_webhook", "taplio"),
    "twilio": ("twilio", "twilio_auth_token"),
    "twilio_auth_token": ("twilio_auth_token", "twilio"),
    "phantombuster": ("phantombuster", "phantombuster_api_key"),
    "phantombuster_api_key": ("phantombuster_api_key", "phantombuster"),
    "phantombuster_connect_agent": ("phantombuster_connect_agent", "phantombuster_connect_agent_id"),
    "phantombuster_connect_agent_id": ("phantombuster_connect_agent_id", "phantombuster_connect_agent"),
    "phantombuster_message_agent": ("phantombuster_message_agent", "phantombuster_message_agent_id"),
    "phantombuster_message_agent_id": ("phantombuster_message_agent_id", "phantombuster_message_agent"),
}


def resolve_service_aliases(service_name: str) -> tuple[str, ...]:
    """Return candidate service names in lookup priority order."""
    return _SERVICE_ALIASES.get(service_name, (service_name,))


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a Fernet-compatible 32-byte key from the app SECRET_KEY."""
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    """Get a Fernet instance derived from the app's SECRET_KEY."""
    return Fernet(_derive_fernet_key(settings.SECRET_KEY))


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string and return the ciphertext as a string."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a ciphertext string and return the plaintext."""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


def mask_key(key: str) -> str:
    """Show only the last 4 characters of a key."""
    if len(key) <= 4:
        return "*" * len(key)
    return "*" * (len(key) - 4) + key[-4:]


async def list_api_keys(db: AsyncSession, user_id: UUID) -> list[dict]:
    """List all configured API keys for a user, with masked values."""
    result = await db.execute(select(ApiConfiguration).where(ApiConfiguration.user_id == user_id))
    configs = result.scalars().all()

    keys = []
    for cfg in configs:
        try:
            decrypted = decrypt_value(cfg.encrypted_key)
            masked = mask_key(decrypted)
        except Exception:
            masked = "****"
        keys.append(
            {
                "service_name": cfg.service_name,
                "masked_key": masked,
                "created_at": cfg.created_at.isoformat() if cfg.created_at else None,
                "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
            }
        )

    return keys


async def store_api_key(db: AsyncSession, user_id: UUID, service_name: str, api_key: str) -> dict:
    """Store or update an encrypted API key for a service."""
    encrypted = encrypt_value(api_key)

    # Check if exists
    result = await db.execute(
        select(ApiConfiguration).where(
            ApiConfiguration.user_id == user_id,
            ApiConfiguration.service_name == service_name,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.encrypted_key = encrypted
        await db.flush()
        await db.refresh(existing)
    else:
        cfg = ApiConfiguration(
            user_id=user_id,
            service_name=service_name,
            encrypted_key=encrypted,
        )
        db.add(cfg)
        await db.flush()

    return {"service_name": service_name, "masked_key": mask_key(api_key)}


async def delete_api_key(db: AsyncSession, user_id: UUID, service_name: str) -> bool:
    """Delete an API key for a service. Returns True if deleted."""
    result = await db.execute(
        delete(ApiConfiguration).where(
            ApiConfiguration.user_id == user_id,
            ApiConfiguration.service_name == service_name,
        )
    )
    return result.rowcount > 0


async def get_api_key(db: AsyncSession, service_name: str, user_id: UUID | None = None) -> str | None:
    """
    Retrieve a decrypted API key at runtime.

    If user_id is provided, look up user-specific key.
    Falls back to environment variable if no DB key found.
    """
    candidates = resolve_service_aliases(service_name)

    if user_id:
        result = await db.execute(
            select(ApiConfiguration).where(
                ApiConfiguration.user_id == user_id,
                ApiConfiguration.service_name.in_(candidates),
            )
        )
        configs = {cfg.service_name: cfg for cfg in result.scalars().all()}
        for candidate in candidates:
            cfg = configs.get(candidate)
            if not cfg:
                continue
            try:
                return decrypt_value(cfg.encrypted_key)
            except Exception:
                logger.warning("Failed to decrypt API key for service %s", candidate)

    # Fallback to environment variables
    env_mapping = {
        "hubspot": settings.HUBSPOT_API_KEY,
        "zoominfo": settings.ZOOMINFO_API_KEY,
        "zoominfo_client_id": settings.ZOOMINFO_CLIENT_ID,
        "apollo": settings.APOLLO_API_KEY,
        "twilio": settings.TWILIO_AUTH_TOKEN,
        "twilio_auth_token": settings.TWILIO_AUTH_TOKEN,
        "twilio_account_sid": settings.TWILIO_ACCOUNT_SID,
        "twilio_phone_number": settings.TWILIO_PHONE_NUMBER,
        "twilio_messaging_service_sid": getattr(settings, "TWILIO_MESSAGING_SERVICE_SID", ""),
        "twilio_verify_service_sid": getattr(settings, "TWILIO_VERIFY_SERVICE_SID", ""),
        "twilio_whatsapp_number": getattr(settings, "TWILIO_WHATSAPP_NUMBER", ""),
        "aws_ses": settings.AWS_SECRET_ACCESS_KEY,
        "groq": settings.GROQ_API_KEY,
        "openai": settings.OPENAI_API_KEY,
        "taplio": settings.TAPLIO_ZAPIER_WEBHOOK_URL,
        "taplio_webhook": settings.TAPLIO_ZAPIER_WEBHOOK_URL,
        "phantombuster": getattr(settings, "PHANTOMBUSTER_API_KEY", ""),
        "phantombuster_api_key": getattr(settings, "PHANTOMBUSTER_API_KEY", ""),
        "phantombuster_connect_agent": getattr(settings, "PHANTOMBUSTER_CONNECT_AGENT_ID", ""),
        "phantombuster_connect_agent_id": getattr(settings, "PHANTOMBUSTER_CONNECT_AGENT_ID", ""),
        "phantombuster_message_agent": getattr(settings, "PHANTOMBUSTER_MESSAGE_AGENT_ID", ""),
        "phantombuster_message_agent_id": getattr(settings, "PHANTOMBUSTER_MESSAGE_AGENT_ID", ""),
    }
    for candidate in candidates:
        env_val = env_mapping.get(candidate, "")
        if env_val:
            return env_val
    return None
