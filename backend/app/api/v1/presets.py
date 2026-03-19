"""
Sequence presets API — deploy pre-built outreach sequences with one click.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.sequence import Sequence, SequenceStatus, SequenceStep, StepType
from app.models.template import Template, TemplateCategory, TemplateChannel
from app.schemas.template import SequencePreset
from app.services.gengyve_presets import SEQUENCE_PRESETS
from app.services.template_engine import extract_variables

router = APIRouter(prefix="/presets", tags=["presets"])


@router.get("/", response_model=list[SequencePreset])
async def list_presets() -> list[SequencePreset]:
    """List all available sequence presets."""
    return [
        SequencePreset(
            name=p["name"],
            description=p["description"],
            category=p["category"],
            steps=[
                {
                    "step_type": s["step_type"],
                    "position": s["position"],
                    "delay_hours": s["delay_hours"],
                    "has_template": s.get("template") is not None,
                    "template_name": s["template"]["name"] if s.get("template") else None,
                    "channel": s["template"]["channel"] if s.get("template") else None,
                }
                for s in p["steps"]
            ],
        )
        for p in SEQUENCE_PRESETS
    ]


@router.post("/{preset_index}/deploy", status_code=status.HTTP_201_CREATED)
async def deploy_preset(
    preset_index: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Deploy a preset: creates the sequence, all templates, and wires them together.
    """
    if preset_index < 0 or preset_index >= len(SEQUENCE_PRESETS):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset index {preset_index} not found. Valid range: 0-{len(SEQUENCE_PRESETS)-1}",
        )

    preset = SEQUENCE_PRESETS[preset_index]

    # Create the sequence
    sequence = Sequence(
        name=preset["name"],
        description=preset["description"],
        status=SequenceStatus.draft,
    )
    db.add(sequence)
    await db.flush()
    await db.refresh(sequence)

    # Create templates and steps
    created_templates = []
    for step_def in preset["steps"]:
        template_id = None

        if step_def.get("template"):
            t_def = step_def["template"]
            template = Template(
                name=t_def["name"],
                channel=TemplateChannel(t_def["channel"]),
                category=TemplateCategory(t_def["category"]),
                subject=t_def.get("subject"),
                html_body=t_def.get("html_body"),
                plain_body=t_def["plain_body"],
                linkedin_action=t_def.get("linkedin_action"),
                variables=t_def.get("variables") or extract_variables(
                    t_def["plain_body"] + (t_def.get("subject") or "")
                ),
                is_system=True,
                is_active=True,
            )
            db.add(template)
            await db.flush()
            await db.refresh(template)
            template_id = str(template.id)
            created_templates.append({"id": str(template.id), "name": template.name})

        step = SequenceStep(
            sequence_id=sequence.id,
            step_type=StepType(step_def["step_type"]),
            position=step_def["position"],
            delay_hours=step_def["delay_hours"],
            config={"template_id": template_id} if template_id else None,
        )
        db.add(step)

    await db.flush()

    return {
        "sequence_id": str(sequence.id),
        "sequence_name": sequence.name,
        "templates_created": len(created_templates),
        "steps_created": len(preset["steps"]),
        "templates": created_templates,
        "status": "deployed_as_draft",
    }
