"""
Pydantic schemas for Chat API — includes command engine response types.
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    message: str
    response: str
    ai_model: str
    ai_sources: list[str]
    created_at: datetime


# ── Command Engine Response Types ────────────────────────────────────────────


class CommandTextResponse(BaseModel):
    """Standard text response from the command engine."""
    type: Literal["text"] = "text"
    content: str


class CommandQuestionResponse(BaseModel):
    """Clarifying question with suggested options."""
    type: Literal["question"] = "question"
    content: str
    options: list[str] = Field(default_factory=list)


class CommandActionPreviewResponse(BaseModel):
    """Campaign/action preview with confirm/modify/cancel."""
    type: Literal["action_preview"] = "action_preview"
    content: str
    campaign_params: dict[str, Any] = Field(default_factory=dict)


class CommandProgressResponse(BaseModel):
    """Step-by-step execution progress."""
    type: Literal["progress"] = "progress"
    content: str


class CommandMetricsResponse(BaseModel):
    """Formatted metrics/charts data."""
    type: Literal["metrics"] = "metrics"
    content: str
    data: dict[str, Any] = Field(default_factory=dict)


class CommandResponse(BaseModel):
    """
    Unified command engine response — wraps all response types.

    The `type` field determines how the frontend renders the response:
    - "text": normal chat bubble
    - "question": shows clarifying question with quick-reply buttons
    - "action_preview": shows campaign preview with confirm/modify/cancel
    - "progress": shows step-by-step execution with checkmarks
    - "metrics": shows formatted metrics/dashboard data
    """
    session_id: str
    type: str = "text"
    content: str = ""
    options: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    campaign_params: dict[str, Any] = Field(default_factory=dict)
    ai_model: str = ""
    ai_sources: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class ChatHistoryItem(BaseModel):
    id: str
    message: str
    response: str
    response_type: str = "text"
    ai_sources: list[str]
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    items: list[ChatHistoryItem]
    total: int
    session_id: str
