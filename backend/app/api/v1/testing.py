"""Testing Agent API — diagnostics, failure analysis, fix generation."""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.agents.orchestrator import AgentOrchestrator
from app.schemas.testing import (
    DiagnosticRequest, DiagnoseIssueRequest, GenerateFixRequest,
    ValidateFixRequest, IntegrationTestRequest, GenerateTestCasesRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/testing", tags=["testing"])


@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Quick health check of all agents."""
    result = await AgentOrchestrator.dispatch(db, "testing", "health_check", {}, user.id)
    return result.get("result", result)


@router.post("/diagnostic")
async def run_diagnostic(
    request: DiagnosticRequest = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run full diagnostic scan across all agents."""
    params = {}
    if request and request.agent_filter:
        params["agent_filter"] = request.agent_filter
    result = await AgentOrchestrator.dispatch(db, "testing", "run_diagnostic", params, user.id)
    return result.get("result", result)


@router.get("/failures")
async def analyze_failures(
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Analyze recent failures with categorization."""
    result = await AgentOrchestrator.dispatch(
        db, "testing", "analyze_failures", {"hours": hours, "limit": limit}, user.id
    )
    return result.get("result", result)


@router.post("/diagnose")
async def diagnose_issue(
    request: DiagnoseIssueRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Diagnose a specific agent/action failure using LLM."""
    result = await AgentOrchestrator.dispatch(
        db, "testing", "diagnose_issue",
        {"agent_name": request.agent_name, "action": request.action, "error_message": request.error_message},
        user.id,
    )
    return result.get("result", result)


@router.post("/fix")
async def generate_fix(
    request: GenerateFixRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a code fix suggestion (never auto-applied)."""
    result = await AgentOrchestrator.dispatch(
        db, "testing", "generate_fix",
        {"agent_name": request.agent_name, "action": request.action, "error_message": request.error_message},
        user.id,
    )
    return result.get("result", result)


@router.post("/validate")
async def validate_fix(
    request: ValidateFixRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Validate a fix by re-running the workflow."""
    result = await AgentOrchestrator.dispatch(
        db, "testing", "validate_fix",
        {"agent_name": request.agent_name, "action": request.action},
        user.id,
    )
    return result.get("result", result)


@router.post("/integration-test")
async def run_integration_test(
    request: IntegrationTestRequest = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run a predefined multi-agent integration test."""
    workflow = request.workflow_name if request else "intelligence"
    result = await AgentOrchestrator.dispatch(
        db, "testing", "run_integration_test", {"workflow_name": workflow}, user.id
    )
    return result.get("result", result)


@router.post("/generate-tests")
async def generate_test_cases(
    request: GenerateTestCasesRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate pytest test cases for an agent action."""
    result = await AgentOrchestrator.dispatch(
        db, "testing", "generate_test_cases",
        {"agent_name": request.agent_name, "action": request.action},
        user.id,
    )
    return result.get("result", result)


@router.get("/suggestions")
async def list_fix_suggestions(
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List fix suggestions."""
    from app.models.fix_suggestion import FixSuggestion
    query = select(FixSuggestion).where(FixSuggestion.user_id == user.id)
    if status:
        query = query.where(FixSuggestion.status == status)
    query = query.order_by(FixSuggestion.created_at.desc()).limit(limit)
    result = await db.execute(query)
    suggestions = result.scalars().all()
    return [
        {
            "id": str(s.id), "agent_name": s.agent_name, "action": s.action,
            "severity": s.severity, "fix_type": s.fix_type, "status": s.status,
            "diagnosis": s.diagnosis[:200] if s.diagnosis else "",
            "suggested_fix": s.suggested_fix[:200] if s.suggested_fix else "",
            "created_at": s.created_at.isoformat() if s.created_at else "",
        }
        for s in suggestions
    ]


@router.get("/runs")
async def list_diagnostic_runs(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List recent diagnostic runs."""
    from app.models.diagnostic_run import DiagnosticRun
    query = (
        select(DiagnosticRun)
        .where(DiagnosticRun.user_id == user.id)
        .order_by(DiagnosticRun.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    runs = result.scalars().all()
    return [
        {
            "id": str(r.id), "run_type": r.run_type, "status": r.status,
            "summary": r.summary, "started_at": r.started_at.isoformat() if r.started_at else "",
            "completed_at": r.completed_at.isoformat() if r.completed_at else "",
        }
        for r in runs
    ]
