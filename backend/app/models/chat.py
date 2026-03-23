"""
ChatLog model for Phase 7: In-app AI chatbot assistant.
"""

import uuid
from datetime import datetime, UTC

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from typing import Any

from app.database import Base


class ChatLog(Base):
    """Stores all chat interactions for history, analytics, and AI feedback."""

    __tablename__ = "chat_logs"
    __table_args__ = (
        Index("ix_chat_logs_user_id", "user_id"),
        Index("ix_chat_logs_session_id", "session_id"),
        Index("ix_chat_logs_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True, default="groq")
    ai_sources: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    context_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Command engine fields (Phase 8)
    session_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default="text"
    )
    response_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
