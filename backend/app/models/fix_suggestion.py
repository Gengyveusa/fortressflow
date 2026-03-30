"""Fix suggestion model — stores LLM-generated fix proposals for human review."""

import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func
from app.database import Base


class FixSuggestion(Base):
    __tablename__ = "fix_suggestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    diagnostic_run_id = Column(UUID(as_uuid=True), ForeignKey("diagnostic_runs.id"), nullable=True)
    agent_name = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)
    error_message = Column(Text, nullable=True)
    diagnosis = Column(Text, nullable=True)  # LLM-generated root cause
    suggested_fix = Column(Text, nullable=True)  # LLM-generated patch or config change
    fix_type = Column(String(30), nullable=True)  # config, code_patch, param_fix, api_key, dependency
    severity = Column(String(20), nullable=True)  # critical, high, medium, low
    status = Column(String(20), nullable=False, default="pending")  # pending, applied, rejected, validated
    applied_at = Column(DateTime(timezone=True), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    validation_result = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_fix_suggestions_user_created", "user_id", "created_at"),
        Index("ix_fix_suggestions_agent_action", "agent_name", "action"),
        Index("ix_fix_suggestions_status", "status"),
    )
