"""Pydantic schemas for the agents API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Request schemas ──────────────────────────────────────────────────────────


class AgentExecuteRequest(BaseModel):
    action: str = Field(..., description="Agent method to invoke (e.g. 'chat', 'embed')")
    params: dict = Field(default_factory=dict, description="Parameters for the action")


class WorkflowStepRequest(BaseModel):
    agent_name: str = Field(..., description="Agent to use: groq, openai, hubspot, zoominfo, twilio")
    action: str = Field(..., description="Method to invoke on the agent")
    params: dict = Field(default_factory=dict, description="Parameters for this step")
    depends_on: int | None = Field(None, description="Index of step whose result feeds into this step")


class WorkflowRequest(BaseModel):
    steps: list[WorkflowStepRequest] = Field(..., min_length=1, description="Ordered list of workflow steps")


class AgentLogsQuery(BaseModel):
    agent_name: str | None = None
    status: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


# ── Response schemas ─────────────────────────────────────────────────────────


class AgentStatusEntry(BaseModel):
    agent_name: str
    configured: bool
    has_db_key: bool
    has_env_key: bool


class AgentStatusResponse(BaseModel):
    agents: list[AgentStatusEntry]


class AgentExecuteResponse(BaseModel):
    agent_name: str
    action: str
    status: str
    result: dict | list | str | None = None
    error: str | None = None
    latency_ms: int | None = None


class WorkflowStepResult(BaseModel):
    step_index: int
    agent_name: str
    action: str
    status: str
    result: dict | list | str | None = None
    error: str | None = None


class WorkflowResponse(BaseModel):
    status: str
    steps: list[WorkflowStepResult]


class AgentActionLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    agent_name: str
    action: str
    params: dict | None = None
    result_summary: dict | None = None
    status: str
    latency_ms: int | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentLogsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AgentActionLogResponse]
