import csv
import io
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.lead import Lead
from app.models.user import User
from app.models.touch_log import TouchLog, TouchAction
from app.schemas.lead import (
    CSVImportResponse,
    HubSpotSyncResponse,
    LeadCreate,
    LeadListResponse,
    LeadResponse,
    TouchLogCreate,
    TouchLogResponse,
)
from app.services.email_validator import normalize_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    body: LeadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeadResponse:
    """Create a new lead."""
    result = await db.execute(
        select(Lead).where(func.lower(Lead.email) == body.email.lower())
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    lead = Lead(**body.model_dump())
    db.add(lead)
    await db.flush()
    await db.refresh(lead)
    return LeadResponse.model_validate(lead)


@router.get("/", response_model=LeadListResponse)
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeadListResponse:
    """List leads with pagination."""
    total_result = await db.execute(select(func.count(Lead.id)))
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        select(Lead).order_by(Lead.created_at.desc()).offset(offset).limit(page_size)
    )
    leads = result.scalars().all()

    return LeadListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[LeadResponse.model_validate(l) for l in leads],
    )


@router.post("/import/csv", response_model=CSVImportResponse, status_code=status.HTTP_200_OK)
async def import_leads_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CSVImportResponse:
    """Bulk-import leads from a CSV file.

    Required columns: email, first_name, last_name (minimum).
    Optional: company, title, phone, source.
    Deduplication by email (case-insensitive). Idempotent — re-running skips existing leads.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV files are accepted"
        )
    content = await file.read()
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File must be UTF-8 encoded"
        )

    reader = csv.DictReader(io.StringIO(decoded))
    required = {"email", "first_name", "last_name"}

    # Validate required columns exist in header
    if reader.fieldnames is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file is empty or malformed"
        )
    missing_cols = required - set(reader.fieldnames)
    if missing_cols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV missing required columns: {missing_cols}",
        )

    total_rows = 0
    imported = 0
    skipped_dupes = 0
    errors: list[str] = []

    for row_num, row in enumerate(reader, start=2):
        total_rows += 1

        email_raw = (row.get("email") or "").strip()
        if not email_raw:
            errors.append(f"Row {row_num}: missing email")
            continue

        try:
            email_normalized = normalize_email(email_raw)
        except ValueError as exc:
            errors.append(f"Row {row_num}: {exc}")
            continue

        # Dedupe by email (case-insensitive)
        existing = await db.execute(
            select(Lead).where(func.lower(Lead.email) == email_normalized.lower())
        )
        if existing.scalar_one_or_none() is not None:
            skipped_dupes += 1
            continue

        # Build lead data with defaults for optional fields
        try:
            lead = Lead(
                email=email_normalized,
                first_name=(row.get("first_name") or "").strip(),
                last_name=(row.get("last_name") or "").strip(),
                company=(row.get("company") or "Unknown").strip(),
                title=(row.get("title") or "Unknown").strip(),
                phone=(row.get("phone") or "").strip() or None,
                source="csv_upload",
                meeting_verified=False,
            )
            db.add(lead)
            imported += 1
        except Exception as exc:
            errors.append(f"Row {row_num}: {exc}")
            continue

    await db.flush()
    logger.info("CSV import: %d total, %d imported, %d dupes, %d errors", total_rows, imported, skipped_dupes, len(errors))
    return CSVImportResponse(
        total_rows=total_rows,
        imported=imported,
        skipped_dupes=skipped_dupes,
        errors=errors,
    )


@router.post("/import/hubspot", response_model=HubSpotSyncResponse, status_code=status.HTTP_200_OK)
async def import_leads_hubspot(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HubSpotSyncResponse:
    """Pull contacts from HubSpot CRM and sync to local leads table.

    Deduplication by email (case-insensitive).
    Source is set to "hubspot_sync". Never overwrites consent status.
    """
    from app.services.hubspot import HubSpotService

    hs = HubSpotService()
    contacts = await hs.pull_contacts_from_hubspot()

    total_contacts = len(contacts)
    synced = 0
    skipped = 0
    errors: list[str] = []

    for contact in contacts:
        email_raw = (contact.get("email") or "").strip()
        if not email_raw:
            errors.append(f"Contact missing email: {contact.get('hs_object_id', 'unknown')}")
            continue

        try:
            email_normalized = normalize_email(email_raw)
        except ValueError:
            errors.append(f"Invalid email: {email_raw}")
            continue

        # Dedupe by email (case-insensitive)
        result = await db.execute(
            select(Lead).where(func.lower(Lead.email) == email_normalized.lower())
        )
        existing_lead = result.scalar_one_or_none()

        if existing_lead is not None:
            # Update enriched_data if HubSpot data is newer, but never overwrite consent
            if existing_lead.enriched_data is None:
                existing_lead.enriched_data = {
                    "source": "hubspot_sync",
                    "data": contact,
                    "enriched_at": datetime.now(UTC).isoformat(),
                }
                existing_lead.last_enriched_at = datetime.now(UTC)
            skipped += 1
            continue

        # Create new lead
        try:
            lead = Lead(
                email=email_normalized,
                first_name=(contact.get("firstname") or "Unknown").strip(),
                last_name=(contact.get("lastname") or "Unknown").strip(),
                company=(contact.get("company") or "Unknown").strip(),
                title=(contact.get("jobtitle") or "Unknown").strip(),
                phone=(contact.get("phone") or "").strip() or None,
                source="hubspot_sync",
                meeting_verified=False,
            )
            db.add(lead)
            synced += 1
        except Exception as exc:
            errors.append(f"Error syncing {email_raw}: {exc}")
            continue

    await db.flush()
    logger.info("HubSpot sync: %d total, %d synced, %d skipped, %d errors", total_contacts, synced, skipped, len(errors))
    return HubSpotSyncResponse(
        total_contacts=total_contacts,
        synced=synced,
        skipped=skipped,
        errors=errors,
    )


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeadResponse:
    """Retrieve a single lead by ID."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return LeadResponse.model_validate(lead)


@router.post("/{lead_id}/touch", response_model=TouchLogResponse, status_code=status.HTTP_201_CREATED)
async def log_touch(
    lead_id: UUID,
    body: TouchLogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TouchLogResponse:
    """Log a touch event for a lead."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    log = TouchLog(
        lead_id=lead_id,
        channel=body.channel,
        action=TouchAction(body.action),
        sequence_id=body.sequence_id,
        step_number=body.step_number,
        extra_metadata=body.extra_metadata,
    )
    db.add(log)
    await db.flush()
    await db.refresh(log)
    return TouchLogResponse.model_validate(log)
