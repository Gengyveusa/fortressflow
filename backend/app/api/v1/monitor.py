"""Mission Control monitoring endpoints — live feed, heatmap, provenance, funnel, timeline."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.agent_action_log import AgentActionLog
from app.models.consent import Consent
from app.models.lead import Lead
from app.models.sequence import SequenceEnrollment
from app.models.touch_log import TouchLog
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitor", tags=["monitor"])

# ---------------------------------------------------------------------------
# Registry of all known agents (guarantees heatmap shows all 10 even at 0)
# ---------------------------------------------------------------------------
_AGENT_REGISTRY = [
    "groq",
    "openai",
    "hubspot",
    "zoominfo",
    "twilio",
    "apollo",
    "taplio",
    "sendgrid",
    "linkedin",
    "internal",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _params_preview(params) -> str:
    """First 100 chars of JSON-serialized params, or empty string."""
    if params is None:
        return ""
    try:
        raw = json.dumps(params, default=str)
        return raw[:100]
    except Exception:
        return str(params)[:100]


def _agent_status(total: int, error_count: int, last_execution: datetime | None) -> str:
    """Derive health status from execution stats."""
    if total == 0 or last_execution is None:
        return "inactive"
    now = datetime.now(timezone.utc)
    age = now - last_execution.replace(tzinfo=timezone.utc) if last_execution.tzinfo is None else now - last_execution
    if age > timedelta(hours=6):
        return "inactive"
    if total > 0 and error_count / total > 0.15:
        return "degraded"
    return "healthy"


# ---------------------------------------------------------------------------
# 1. Agent Live Feed
# ---------------------------------------------------------------------------


@router.get("/agent-live-feed")
async def agent_live_feed(
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Recent agent executions ordered newest-first."""
    try:
        stmt = (
            select(AgentActionLog)
            .where(AgentActionLog.user_id == current_user.id)
            .order_by(AgentActionLog.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        items = [
            {
                "id": str(row.id),
                "agent_name": row.agent_name,
                "action": row.action,
                "status": row.status,
                "params_preview": _params_preview(row.params),
                "latency_ms": row.latency_ms,
                "error": row.error_message,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
        return {"items": items}

    except Exception as exc:
        logger.exception("agent-live-feed failed")
        # Fallback so the dashboard still renders
        return {"items": [], "_error": str(exc)}


# ---------------------------------------------------------------------------
# 2. Agent Heatmap
# ---------------------------------------------------------------------------


@router.get("/agent-heatmap")
async def agent_heatmap(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Per-agent execution stats for the last 24 hours, merged with full registry."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        stmt = (
            select(
                AgentActionLog.agent_name,
                func.count().label("total"),
                func.count().filter(AgentActionLog.status == "success").label("success_count"),
                func.count().filter(AgentActionLog.status != "success").label("error_count"),
                func.avg(AgentActionLog.latency_ms).label("avg_latency"),
                func.max(AgentActionLog.created_at).label("last_execution"),
            )
            .where(
                and_(
                    AgentActionLog.user_id == current_user.id,
                    AgentActionLog.created_at >= cutoff,
                )
            )
            .group_by(AgentActionLog.agent_name)
        )
        result = await db.execute(stmt)
        db_rows = {row.agent_name: row for row in result.all()}

        agents = []
        for name in _AGENT_REGISTRY:
            row = db_rows.get(name)
            if row:
                total = row.total or 0
                success = row.success_count or 0
                errors = row.error_count or 0
                avg_lat = round(float(row.avg_latency), 1) if row.avg_latency else 0
                last_exec = row.last_execution
                agents.append(
                    {
                        "name": name,
                        "total": total,
                        "success_rate": round(success / total, 3) if total else 0,
                        "avg_latency_ms": avg_lat,
                        "errors": errors,
                        "last_execution": last_exec.isoformat() if last_exec else None,
                        "status": _agent_status(total, errors, last_exec),
                    }
                )
            else:
                agents.append(
                    {
                        "name": name,
                        "total": 0,
                        "success_rate": 0,
                        "avg_latency_ms": 0,
                        "errors": 0,
                        "last_execution": None,
                        "status": "inactive",
                    }
                )

        return {"agents": agents}

    except Exception as exc:
        logger.exception("agent-heatmap failed")
        return {
            "agents": [
                {
                    "name": n,
                    "total": 0,
                    "success_rate": 0,
                    "avg_latency_ms": 0,
                    "errors": 0,
                    "last_execution": None,
                    "status": "inactive",
                }
                for n in _AGENT_REGISTRY
            ],
            "_error": str(exc),
        }


# ---------------------------------------------------------------------------
# 3. Provenance
# ---------------------------------------------------------------------------


@router.get("/provenance")
async def provenance(
    lead_id: Optional[UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    If lead_id provided: build chronological provenance chain for that lead.
    Otherwise: aggregate source breakdown + enrichment coverage stats.
    """
    try:
        if lead_id:
            return await _provenance_for_lead(lead_id, current_user, db)
        return await _provenance_aggregate(current_user, db)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("provenance failed")
        return {
            "source_breakdown": {},
            "enrichment_coverage": {
                "total_leads": 0,
                "enriched": 0,
                "enriched_pct": 0,
                "verified_phone": 0,
                "verified_email": 0,
                "crm_synced": 0,
            },
            "provenance_chain": [],
            "_error": str(exc),
        }


async def _provenance_aggregate(current_user: User, db: AsyncSession) -> dict:
    """Source breakdown + enrichment coverage across all leads."""
    # Source breakdown
    src_stmt = select(Lead.source, func.count()).group_by(Lead.source)
    src_result = await db.execute(src_stmt)
    source_breakdown = {row[0]: row[1] for row in src_result.all()}

    # Enrichment coverage
    total_stmt = select(func.count()).select_from(Lead)
    total = (await db.execute(total_stmt)).scalar() or 0

    enriched_stmt = select(func.count()).select_from(Lead).where(Lead.enriched_data.isnot(None))
    enriched = (await db.execute(enriched_stmt)).scalar() or 0

    phone_stmt = select(func.count()).select_from(Lead).where(Lead.phone.isnot(None))
    verified_phone = (await db.execute(phone_stmt)).scalar() or 0

    email_stmt = select(func.count()).select_from(Lead).where(Lead.email.isnot(None))
    verified_email = (await db.execute(email_stmt)).scalar() or 0

    # CRM synced: leads that have a HubSpot touch or enrichment via hubspot
    crm_stmt = select(func.count(func.distinct(TouchLog.lead_id))).where(TouchLog.channel == "hubspot")
    crm_synced = (await db.execute(crm_stmt)).scalar() or 0

    return {
        "source_breakdown": source_breakdown,
        "enrichment_coverage": {
            "total_leads": total,
            "enriched": enriched,
            "enriched_pct": round((enriched / total) * 100, 1) if total else 0,
            "verified_phone": verified_phone,
            "verified_email": verified_email,
            "crm_synced": crm_synced,
        },
        "provenance_chain": [],
    }


async def _provenance_for_lead(lead_id: UUID, current_user: User, db: AsyncSession) -> dict:
    """Build a chronological provenance chain for a single lead."""
    lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = lead_result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    chain: list[dict] = []

    # 1. Import event
    chain.append(
        {
            "event": "imported",
            "source": lead.source,
            "timestamp": lead.created_at.isoformat() if lead.created_at else None,
            "agent": None,
        }
    )

    # 2. Enrichment
    if lead.enriched_data and lead.last_enriched_at:
        agent_name = lead.enriched_data.get("provider") if isinstance(lead.enriched_data, dict) else None
        chain.append(
            {
                "event": "enriched",
                "source": agent_name or "unknown",
                "timestamp": lead.last_enriched_at.isoformat(),
                "agent": agent_name,
            }
        )

    # 3. Consents
    consent_result = await db.execute(select(Consent).where(Consent.lead_id == lead_id).order_by(Consent.granted_at))
    for c in consent_result.scalars().all():
        chain.append(
            {
                "event": "consent_granted",
                "source": f"{c.channel.value} via {c.method.value}",
                "timestamp": c.granted_at.isoformat() if c.granted_at else None,
                "agent": None,
            }
        )

    # 4. Touches
    touch_result = await db.execute(select(TouchLog).where(TouchLog.lead_id == lead_id).order_by(TouchLog.created_at))
    for t in touch_result.scalars().all():
        chain.append(
            {
                "event": f"touch_{t.action.value}",
                "source": t.channel,
                "timestamp": t.created_at.isoformat() if t.created_at else None,
                "agent": None,
            }
        )

    # 5. Agent actions referencing this lead (search params JSONB for the lead_id)
    agent_stmt = (
        select(AgentActionLog)
        .where(
            and_(
                AgentActionLog.user_id == current_user.id,
                AgentActionLog.params.op("@>")(json.dumps({"lead_id": str(lead_id)})),
            )
        )
        .order_by(AgentActionLog.created_at)
    )
    agent_result = await db.execute(agent_stmt)
    for a in agent_result.scalars().all():
        chain.append(
            {
                "event": f"agent_{a.action}",
                "source": a.agent_name,
                "timestamp": a.created_at.isoformat() if a.created_at else None,
                "agent": a.agent_name,
            }
        )

    # Sort everything chronologically
    chain.sort(key=lambda e: e["timestamp"] or "")

    return {
        "source_breakdown": {},
        "enrichment_coverage": {},
        "provenance_chain": chain,
    }


# ---------------------------------------------------------------------------
# 4. Journey Funnel
# ---------------------------------------------------------------------------


@router.get("/journey-funnel")
async def journey_funnel(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Count leads at each journey stage for the funnel visualisation."""
    try:
        # Discovered = total leads
        total = (await db.execute(select(func.count()).select_from(Lead))).scalar() or 0

        # Enriched = enriched_data IS NOT NULL
        enriched = (
            await db.execute(select(func.count()).select_from(Lead).where(Lead.enriched_data.isnot(None)))
        ).scalar() or 0

        # Contacted = leads with at least one TouchLog(action='sent')
        contacted = (
            await db.execute(select(func.count(func.distinct(TouchLog.lead_id))).where(TouchLog.action == "sent"))
        ).scalar() or 0

        # Engaged = leads with TouchLog(action='opened')
        engaged = (
            await db.execute(select(func.count(func.distinct(TouchLog.lead_id))).where(TouchLog.action == "opened"))
        ).scalar() or 0

        # Replied
        replied = (
            await db.execute(select(func.count(func.distinct(TouchLog.lead_id))).where(TouchLog.action == "replied"))
        ).scalar() or 0

        # Meeting = meeting_verified == True
        meeting = (
            await db.execute(select(func.count()).select_from(Lead).where(Lead.meeting_verified.is_(True)))
        ).scalar() or 0

        stages = [
            {"name": "Discovered", "count": total, "pct": 100.0},
            {"name": "Enriched", "count": enriched, "pct": round((enriched / total) * 100, 1) if total else 0},
            {"name": "Contacted", "count": contacted, "pct": round((contacted / total) * 100, 1) if total else 0},
            {"name": "Engaged", "count": engaged, "pct": round((engaged / total) * 100, 1) if total else 0},
            {"name": "Replied", "count": replied, "pct": round((replied / total) * 100, 1) if total else 0},
            {"name": "Meeting", "count": meeting, "pct": round((meeting / total) * 100, 1) if total else 0},
        ]

        return {"stages": stages}

    except Exception as exc:
        logger.exception("journey-funnel failed")
        return {
            "stages": [
                {"name": s, "count": 0, "pct": 0}
                for s in ["Discovered", "Enriched", "Contacted", "Engaged", "Replied", "Meeting"]
            ],
            "_error": str(exc),
        }


# ---------------------------------------------------------------------------
# 5. Journey Timeline
# ---------------------------------------------------------------------------


@router.get("/journey-timeline")
async def journey_timeline(
    lead_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Build a full chronological timeline of all events for a specific lead."""
    # Fetch lead
    lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = lead_result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    lead_info = {
        "id": str(lead.id),
        "name": f"{lead.first_name} {lead.last_name}".strip(),
        "company": lead.company,
    }

    timeline: list[dict] = []

    # 1. Created / imported
    timeline.append(
        {
            "event": "imported",
            "timestamp": lead.created_at.isoformat() if lead.created_at else None,
            "details": f"{lead.source} import",
            "agent": None,
        }
    )

    # 2. Enrichment
    if lead.enriched_data and lead.last_enriched_at:
        provider = lead.enriched_data.get("provider") if isinstance(lead.enriched_data, dict) else None
        timeline.append(
            {
                "event": "enriched",
                "timestamp": lead.last_enriched_at.isoformat(),
                "details": provider or "enrichment provider",
                "agent": provider,
            }
        )

    # 3. Consents
    consent_result = await db.execute(select(Consent).where(Consent.lead_id == lead_id).order_by(Consent.granted_at))
    for c in consent_result.scalars().all():
        timeline.append(
            {
                "event": "consent_granted",
                "timestamp": c.granted_at.isoformat() if c.granted_at else None,
                "details": f"{c.channel.value} consent via {c.method.value}",
                "agent": None,
            }
        )
        if c.revoked_at:
            timeline.append(
                {
                    "event": "consent_revoked",
                    "timestamp": c.revoked_at.isoformat(),
                    "details": f"{c.channel.value} consent revoked",
                    "agent": None,
                }
            )

    # 4. Touches
    touch_result = await db.execute(select(TouchLog).where(TouchLog.lead_id == lead_id).order_by(TouchLog.created_at))
    for t in touch_result.scalars().all():
        timeline.append(
            {
                "event": t.action.value,
                "timestamp": t.created_at.isoformat() if t.created_at else None,
                "details": f"{t.channel} — step {t.step_number}" if t.step_number else t.channel,
                "agent": None,
            }
        )

    # 5. Sequence enrollments
    enroll_result = await db.execute(
        select(SequenceEnrollment).where(SequenceEnrollment.lead_id == lead_id).order_by(SequenceEnrollment.enrolled_at)
    )
    for e in enroll_result.scalars().all():
        timeline.append(
            {
                "event": "sequence_enrolled",
                "timestamp": e.enrolled_at.isoformat() if e.enrolled_at else None,
                "details": f"Enrolled in sequence (status: {e.status.value})",
                "agent": None,
            }
        )
        if e.last_state_change_at:
            timeline.append(
                {
                    "event": "sequence_state_change",
                    "timestamp": e.last_state_change_at.isoformat(),
                    "details": f"Sequence status changed to {e.status.value}",
                    "agent": None,
                }
            )

    # 6. Agent actions referencing this lead
    try:
        agent_stmt = (
            select(AgentActionLog)
            .where(
                and_(
                    AgentActionLog.user_id == current_user.id,
                    AgentActionLog.params.op("@>")(json.dumps({"lead_id": str(lead_id)})),
                )
            )
            .order_by(AgentActionLog.created_at)
        )
        agent_result = await db.execute(agent_stmt)
        for a in agent_result.scalars().all():
            timeline.append(
                {
                    "event": f"agent_{a.action}",
                    "timestamp": a.created_at.isoformat() if a.created_at else None,
                    "details": f"{a.agent_name}: {a.action} ({a.status})",
                    "agent": a.agent_name,
                }
            )
    except Exception:
        logger.debug("JSONB contains query not supported — skipping agent action lookup")

    # Sort chronologically
    timeline.sort(key=lambda e: e["timestamp"] or "")

    return {"lead": lead_info, "timeline": timeline}
