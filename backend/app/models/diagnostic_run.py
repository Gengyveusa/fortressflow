"""Diagnostic run model — tracks testing agent scan history."""
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func
from app.database import Base

class DiagnosticRun(Base):
    __tablename__ = "diagnostic_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    run_type = Column(String(30), nullable=False)  # full_diagnostic, health_check, integration_test
    status = Column(String(20), nullable=False, default="running")  # running, completed, failed
    summary = Column(JSONB, nullable=True)  # {total_agents, passed, failed, skipped}
    details = Column(JSONB, nullable=True)  # array of per-action results
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_diagnostic_runs_user_created", "user_id", "created_at"),
        Index("ix_diagnostic_runs_status", "status"),
    )
