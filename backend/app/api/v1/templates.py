from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.template import Template, TemplateCategory, TemplateChannel
from app.models.user import User
from app.schemas.template import (
    TemplateCreate,
    TemplateListResponse,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateResponse,
    TemplateUpdate,
)
from app.services.template_engine import (
    extract_variables,
    render_template,
    validate_template,
)

router = APIRouter(prefix="/templates", tags=["templates"])


def _template_to_response(t: Template) -> TemplateResponse:
    return TemplateResponse(
        id=t.id,
        name=t.name,
        channel=t.channel.value if isinstance(t.channel, TemplateChannel) else t.channel,
        category=t.category.value if isinstance(t.category, TemplateCategory) else t.category,
        subject=t.subject,
        html_body=t.html_body,
        plain_body=t.plain_body,
        linkedin_action=t.linkedin_action,
        variables=t.variables,
        variant_group=t.variant_group,
        variant_label=t.variant_label,
        is_system=t.is_system,
        is_active=t.is_active,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.post("/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TemplateResponse:
    """Create a new message template."""
    template = Template(
        name=body.name,
        channel=TemplateChannel(body.channel),
        category=TemplateCategory(body.category),
        subject=body.subject,
        html_body=body.html_body,
        plain_body=body.plain_body,
        linkedin_action=body.linkedin_action,
        variables=body.variables or extract_variables(body.plain_body + (body.subject or "")),
        variant_group=body.variant_group,
        variant_label=body.variant_label,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return _template_to_response(template)


@router.get("/", response_model=TemplateListResponse)
async def list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    channel: str | None = Query(None, pattern="^(email|sms|linkedin)$"),
    category: str | None = Query(None),
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TemplateListResponse:
    """List templates with filtering."""
    filters = []
    if channel:
        filters.append(Template.channel == channel)
    if category:
        filters.append(Template.category == category)
    if active_only:
        filters.append(Template.is_active.is_(True))

    total_q = select(func.count(Template.id)).where(*filters) if filters else select(func.count(Template.id))
    total_result = await db.execute(total_q)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    q = select(Template).order_by(Template.created_at.desc()).offset(offset).limit(page_size)
    if filters:
        q = q.where(*filters)
    result = await db.execute(q)
    templates = result.scalars().all()

    return TemplateListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_template_to_response(t) for t in templates],
    )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TemplateResponse:
    """Get a single template."""
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return _template_to_response(template)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: UUID,
    body: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TemplateResponse:
    """Update an existing template."""
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if template.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System templates cannot be modified. Clone it instead.",
        )

    update_data = body.model_dump(exclude_unset=True)
    if "channel" in update_data:
        update_data["channel"] = TemplateChannel(update_data["channel"])
    if "category" in update_data:
        update_data["category"] = TemplateCategory(update_data["category"])
    for key, value in update_data.items():
        setattr(template, key, value)

    await db.flush()
    await db.refresh(template)
    return _template_to_response(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a template (soft delete by deactivating)."""
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    if template.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System templates cannot be deleted.",
        )
    template.is_active = False
    await db.flush()


@router.post("/preview", response_model=TemplatePreviewResponse)
async def preview_template(
    body: TemplatePreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TemplatePreviewResponse:
    """Preview a template with sample data."""
    plain_body = body.plain_body or ""
    html_body = body.html_body
    subject = body.subject

    # If template_id provided, load from DB
    if body.template_id:
        result = await db.execute(select(Template).where(Template.id == body.template_id))
        template = result.scalar_one_or_none()
        if template:
            plain_body = template.plain_body
            html_body = template.html_body
            subject = template.subject

    context = body.context

    rendered_plain = render_template(plain_body, context)
    rendered_html = render_template(html_body, context) if html_body else None
    rendered_subject = render_template(subject, context) if subject else None

    all_text = plain_body + (html_body or "") + (subject or "")
    variables_used = extract_variables(all_text)
    warnings = validate_template(all_text)

    return TemplatePreviewResponse(
        rendered_subject=rendered_subject,
        rendered_plain_body=rendered_plain,
        rendered_html_body=rendered_html,
        variables_used=variables_used,
        warnings=warnings,
    )
