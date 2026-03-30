"""
Email open tracking endpoint.

Serves a 1x1 transparent GIF pixel and records the open event in touch_logs.
This endpoint is unauthenticated — it is loaded by email clients.
"""

import base64
import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.lead import Lead
from app.models.touch_log import TouchAction, TouchLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tracking", tags=["tracking"])

# 1x1 transparent GIF (43 bytes)
_TRANSPARENT_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)

# Deduplication window: ignore duplicate opens within this period
_DEDUP_WINDOW = timedelta(minutes=30)


def generate_open_tracking_token(lead_id: UUID, sequence_id: UUID | None = None) -> str:
    """Generate an HMAC-signed tracking token encoding lead_id and optional sequence_id."""
    payload = json.dumps(
        {
            "lead_id": str(lead_id),
            "sequence_id": str(sequence_id) if sequence_id else None,
            "t": datetime.now(UTC).isoformat(),
        },
        sort_keys=True,
    )
    sig = hmac.new(
        settings.SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    token_data = base64.urlsafe_b64encode(
        json.dumps({"p": payload, "s": sig}).encode()
    ).decode()
    return token_data


def _verify_tracking_token(token: str) -> dict | None:
    """Verify HMAC token and return payload dict or None if invalid."""
    try:
        decoded = json.loads(base64.urlsafe_b64decode(token.encode()).decode())
        payload = decoded["p"]
        provided_sig = decoded["s"]
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(provided_sig, expected_sig):
            return None
        return json.loads(payload)
    except Exception:
        return None


def generate_open_tracking_url(lead_id: UUID, sequence_id: UUID | None = None) -> str:
    """Generate the full tracking pixel URL for embedding in emails."""
    token = generate_open_tracking_token(lead_id, sequence_id)
    base_url = settings.SENDING_SUBDOMAIN or "localhost:8000"
    scheme = "https" if settings.ENVIRONMENT != "development" else "http"
    return f"{scheme}://{base_url}/api/v1/tracking/open/{token}"


@router.get("/open/{token}")
async def track_open(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Record an email open event and return a 1x1 transparent GIF.

    This endpoint is unauthenticated — it is loaded by email clients when
    they render the tracking pixel <img> tag.

    Deduplication: ignores duplicate opens from the same lead within a
    30-minute window to avoid inflating open counts.
    """
    # Always return the GIF, even on errors — don't leak info via HTTP status
    gif_response = Response(
        content=_TRANSPARENT_GIF,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )

    data = _verify_tracking_token(token)
    if data is None:
        logger.warning("Tracking pixel: invalid token")
        return gif_response

    try:
        lead_id = UUID(data["lead_id"])
        sequence_id = UUID(data["sequence_id"]) if data.get("sequence_id") else None
    except (KeyError, ValueError):
        logger.warning("Tracking pixel: malformed token payload")
        return gif_response

    # Verify lead exists
    lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = lead_result.scalar_one_or_none()
    if lead is None:
        logger.warning("Tracking pixel: lead %s not found", lead_id)
        return gif_response

    # Deduplication: check for recent open from this lead
    dedup_cutoff = datetime.now(UTC) - _DEDUP_WINDOW
    existing_open = await db.execute(
        select(TouchLog).where(
            and_(
                TouchLog.lead_id == lead_id,
                TouchLog.channel == "email",
                TouchLog.action == TouchAction.opened,
                TouchLog.created_at >= dedup_cutoff,
            )
        ).limit(1)
    )
    if existing_open.scalar_one_or_none() is not None:
        logger.debug("Tracking pixel: deduplicated open for lead %s (within %s window)", lead_id, _DEDUP_WINDOW)
        return gif_response

    # Record the open event
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    touch = TouchLog(
        lead_id=lead_id,
        channel="email",
        action=TouchAction.opened,
        sequence_id=sequence_id,
        extra_metadata={
            "source": "tracking_pixel",
            "ip": client_ip,
            "user_agent": user_agent,
            "opened_at": datetime.now(UTC).isoformat(),
        },
    )
    db.add(touch)
    await db.commit()

    logger.info("Tracking pixel: recorded open for lead %s (ip=%s)", lead_id, client_ip)
    return gif_response
