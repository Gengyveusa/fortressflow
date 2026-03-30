"""Pydantic schemas for the Testing Agent API."""
from typing import Any, Optional
from pydantic import BaseModel, Field


class DiagnosticRequest(BaseModel):
    agent_filter: Optional[str] = Field(None, description="Filter to specific agent name")


class DiagnoseIssueRequest(BaseModel):
    agent_name: str
    action: str
    error_message: Optional[str] = None


class GenerateFixRequest(BaseModel):
    agent_name: str
    action: str
    error_message: Optional[str] = None


class ValidateFixRequest(BaseModel):
    agent_name: str
    action: str


class IntegrationTestRequest(BaseModel):
    workflow_name: str = Field("intelligence", description="Predefined workflow: intelligence, content_pipeline, sales_analysis")


class GenerateTestCasesRequest(BaseModel):
    agent_name: str
    action: str


class FailureAnalysisRequest(BaseModel):
    hours: int = Field(24, ge=1, le=720)
    limit: int = Field(100, ge=1, le=500)


class AgentHealthEntry(BaseModel):
    agent_name: str
    configured: bool
    has_db_key: bool
    has_env_key: bool
    total_actions: int
    status: str


class HealthCheckResponse(BaseModel):
    total_agents: int
    healthy: int
    unconfigured: int
    agents: list[AgentHealthEntry]
    timestamp: str


class DiagnosticResultEntry(BaseModel):
    agent: str
    action: str
    status: str
    error: Optional[str] = None
    latency_ms: Optional[int] = None
    reason: Optional[str] = None


class DiagnosticSummary(BaseModel):
    total: int
    passed: int
    failed: int
    skipped: int


class DiagnosticResponse(BaseModel):
    run_id: str
    status: str
    summary: DiagnosticSummary
    details: list[DiagnosticResultEntry]
    timestamp: str


class FailureEntry(BaseModel):
    action: str
    count: int
    latest_error: str
    category: str


class FailureAnalysisResponse(BaseModel):
    time_window_hours: int
    total_failures: int
    by_category: dict[str, int]
    top_failing_actions: list[FailureEntry]
    timestamp: str


class DiagnosisResponse(BaseModel):
    suggestion_id: str
    agent_name: str
    action: str
    diagnosis: dict[str, Any]
    timestamp: str


class FixResponse(BaseModel):
    agent_name: str
    action: str
    fix: dict[str, Any]
    status: str
    note: str
    timestamp: str


class ValidationResponse(BaseModel):
    agent_name: str
    action: str
    validated: bool
    result_status: str
    error: Optional[str] = None
    latency_ms: Optional[int] = None
    timestamp: str


class IntegrationTestResponse(BaseModel):
    workflow_name: str
    status: str
    steps: list[dict[str, Any]]
    timestamp: str


class TestCasesResponse(BaseModel):
    agent_name: str
    action: str
    test_cases: dict[str, Any]
    timestamp: str
