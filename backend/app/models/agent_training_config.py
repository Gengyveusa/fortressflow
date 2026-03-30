"""Agent training config model — per-agent system prompts, few-shot examples, guardrails."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class AgentTrainingConfig(Base):
    __tablename__ = "agent_training_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    agent_name = Column(String(50), nullable=False)
    config_type = Column(
        String(30), nullable=False
    )  # system_prompt, few_shot, guardrails, tool_descriptions, field_mappings
    config_key = Column(String(100), nullable=False)  # e.g. 'default', 'chat', 'generate_sequence_content'
    config_value = Column(JSONB, nullable=False)
    is_active = Column(Boolean, server_default="true", nullable=False)
    priority = Column(Integer, server_default="0", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_atc_user_agent_type_key", "user_id", "agent_name", "config_type", "config_key", unique=True),
        Index("ix_atc_agent_active", "agent_name", "is_active"),
    )
