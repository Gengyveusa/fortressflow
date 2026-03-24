"""Agent API routes — execute agents, query logs, run workflows."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.agent_action_log import AgentActionLog
from app.models.user import User
from app.schemas.agents import (
    AgentActionLogResponse,
    AgentExecuteRequest,
    AgentExecuteResponse,
    AgentLogsResponse,
    AgentStatusEntry,
    AgentStatusResponse,
    WorkflowRequest,
    WorkflowResponse,
    WorkflowStepResult,
)
from app.services.agents.orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/status", response_model=AgentStatusResponse)
async def get_agent_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return which agents are configured (have API keys) for the current user."""
    statuses = await AgentOrchestrator.get_agent_status(db, current_user.id)
    return AgentStatusResponse(
        agents=[AgentStatusEntry(**s) for s in statuses]
    )


@router.post("/{agent_name}/execute", response_model=AgentExecuteResponse)
async def execute_agent(
    agent_name: str,
    body: AgentExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute an agent action. Body: {"action": "chat", "params": {...}}."""
    valid_agents = {"groq", "openai", "hubspot", "zoominfo", "twilio"}
    if agent_name not in valid_agents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid agent: {agent_name}. Valid: {', '.join(sorted(valid_agents))}",
        )

    result = await AgentOrchestrator.dispatch(
        db=db,
        agent_name=agent_name,
        action=body.action,
        params=body.params,
        user_id=current_user.id,
    )

    return AgentExecuteResponse(
        agent_name=agent_name,
        action=body.action,
        status=result["status"],
        result=result.get("result"),
        error=result.get("error"),
        latency_ms=result.get("latency_ms"),
    )


@router.get("/logs", response_model=AgentLogsResponse)
async def get_agent_logs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    agent_name: str | None = Query(None, description="Filter by agent name"),
    action_status: str | None = Query(None, alias="status", description="Filter by status"),
    date_from: datetime | None = Query(None, description="Start date filter"),
    date_to: datetime | None = Query(None, description="End date filter"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Paginated agent action history with filters."""
    query = select(AgentActionLog).where(AgentActionLog.user_id == current_user.id)
    count_query = select(func.count(AgentActionLog.id)).where(AgentActionLog.user_id == current_user.id)

    if agent_name:
        query = query.where(AgentActionLog.agent_name == agent_name)
        count_query = count_query.where(AgentActionLog.agent_name == agent_name)
    if action_status:
        query = query.where(AgentActionLog.status == action_status)
        count_query = count_query.where(AgentActionLog.status == action_status)
    if date_from:
        query = query.where(AgentActionLog.created_at >= date_from)
        count_query = count_query.where(AgentActionLog.created_at >= date_from)
    if date_to:
        query = query.where(AgentActionLog.created_at <= date_to)
        count_query = count_query.where(AgentActionLog.created_at <= date_to)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.order_by(AgentActionLog.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    logs = result.scalars().all()

    return AgentLogsResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[AgentActionLogResponse.model_validate(log) for log in logs],
    )


@router.post("/workflow", response_model=WorkflowResponse)
async def execute_workflow(
    body: WorkflowRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute a multi-agent workflow."""
    steps = [
        {
            "agent_name": s.agent_name,
            "action": s.action,
            "params": s.params,
            "depends_on": s.depends_on,
        }
        for s in body.steps
    ]

    result = await AgentOrchestrator.run_workflow(db, steps, current_user.id)

    return WorkflowResponse(
        status=result["status"],
        steps=[WorkflowStepResult(**step) for step in result["steps"]],
    )
