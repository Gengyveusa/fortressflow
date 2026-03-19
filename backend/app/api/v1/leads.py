import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.lead import Lead
from app.models.touch_log import TouchLog, TouchAction
from app.schemas.lead import (
    LeadCreate,
    LeadListResponse,
    LeadResponse,
    TouchLogCreate,
    TouchLogResponse,
)

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    body: LeadCreate,
    db: AsyncSession = Depends(get_db),
) -> LeadResponse:
    """Create a new lead."""
    result = await db.execute(select(Lead).where(Lead.email == body.email))
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


@router.post("/import/csv", status_code=status.HTTP_202_ACCEPTED)
async def import_leads_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Bulk-import leads from a CSV file.
    Required columns: email, first_name, last_name, company, title, source.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV files are accepted"
        )
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    required = {"email", "first_name", "last_name", "company", "title", "source"}
    created = 0
    skipped = 0
    errors: list[str] = []

    for row_num, row in enumerate(reader, start=2):
        missing = required - set(row.keys())
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CSV missing required columns: {missing}",
            )
        try:
            data = LeadCreate(**{k: v for k, v in row.items() if v})
        except Exception as exc:
            errors.append(f"Row {row_num}: {exc}")
            skipped += 1
            continue

        existing = await db.execute(select(Lead).where(Lead.email == data.email))
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            continue

        lead = Lead(**data.model_dump())
        db.add(lead)
        created += 1

    await db.flush()
    return {"created": created, "skipped": skipped, "errors": errors}


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
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
