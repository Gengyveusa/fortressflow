"""Agent action log model — audit trail for all agent executions."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class AgentActionLog(Base):
    __tablename__ = "agent_action_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    agent_name = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)
    params = Column(JSONB, nullable=True)
    result_summary = Column(JSONB, nullable=True)
    status = Column(String(20), nullable=False)
    latency_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_agent_action_logs_user_created", "user_id", "created_at"),
        Index("ix_agent_action_logs_agent_created", "agent_name", "created_at"),
    )
