"""
Pydantic schemas for Phase 7: Chat API.
"""

from datetime import datetime
from typing import Optional

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


class ChatHistoryItem(BaseModel):
    id: str
    message: str
    response: str
    ai_sources: list[str]
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    items: list[ChatHistoryItem]
    total: int
    session_id: str
