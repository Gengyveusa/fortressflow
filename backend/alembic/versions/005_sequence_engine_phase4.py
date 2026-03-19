"""Phase 4: Sequence Engine — FSM state machine, visual builder,
A/B testing, conditional branching, AI generation.

Revision ID: 005_sequence_engine_phase4
Revises: 004_deliverability_fortress
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "005_sequence_engine_phase4"
down_revision = "004_deliverability_fortress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extend step_type enum ─────────────────────────────────────────
    # Add new step types: conditional, ab_split, end
    op.execute("ALTER TYPE step_type ADD VALUE IF NOT EXISTS 'conditional'")
    op.execute("ALTER TYPE step_type ADD VALUE IF NOT EXISTS 'ab_split'")
    op.execute("ALTER TYPE step_type ADD VALUE IF NOT EXISTS 'end'")

    # ── Extend enrollment_status enum ─────────────────────────────────
    # Add new FSM states: pending, sent, opened, replied, escalated, failed
    op.execute("ALTER TYPE enrollment_status ADD VALUE IF NOT EXISTS 'pending'")
    op.execute("ALTER TYPE enrollment_status ADD VALUE IF NOT EXISTS 'sent'")
    op.execute("ALTER TYPE enrollment_status ADD VALUE IF NOT EXISTS 'opened'")
    op.execute("ALTER TYPE enrollment_status ADD VALUE IF NOT EXISTS 'replied'")
    op.execute("ALTER TYPE enrollment_status ADD VALUE IF NOT EXISTS 'escalated'")
    op.execute("ALTER TYPE enrollment_status ADD VALUE IF NOT EXISTS 'failed'")

    # ── Enhance sequences table ───────────────────────────────────────
    # Visual builder config (React Flow nodes/edges/viewport)
    op.add_column(
        "sequences",
        sa.Column("visual_config", JSONB, nullable=True),
    )
    # AI generation metadata
    op.add_column(
        "sequences",
        sa.Column(
            "ai_generated",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "sequences",
        sa.Column("ai_generation_prompt", sa.Text, nullable=True),
    )
    op.add_column(
        "sequences",
        sa.Column("ai_generation_metadata", JSONB, nullable=True),
    )

    # ── Enhance sequence_steps table ──────────────────────────────────
    # Conditional branching
    op.add_column(
        "sequence_steps",
        sa.Column("condition", JSONB, nullable=True),
    )
    op.add_column(
        "sequence_steps",
        sa.Column("true_next_position", sa.Integer, nullable=True),
    )
    op.add_column(
        "sequence_steps",
        sa.Column("false_next_position", sa.Integer, nullable=True),
    )
    # A/B testing
    op.add_column(
        "sequence_steps",
        sa.Column("ab_variants", JSONB, nullable=True),
    )
    op.add_column(
        "sequence_steps",
        sa.Column(
            "is_ab_test",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # React Flow node ID mapping
    op.add_column(
        "sequence_steps",
        sa.Column("node_id", sa.String(100), nullable=True),
    )

    # ── Enhance sequence_enrollments table ────────────────────────────
    # FSM tracking
    op.add_column(
        "sequence_enrollments",
        sa.Column(
            "last_touch_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "sequence_enrollments",
        sa.Column(
            "last_state_change_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    # A/B variant tracking
    op.add_column(
        "sequence_enrollments",
        sa.Column("ab_variant_assignments", JSONB, nullable=True),
    )
    # Hole-filler tracking
    op.add_column(
        "sequence_enrollments",
        sa.Column(
            "hole_filler_triggered",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "sequence_enrollments",
        sa.Column("escalation_channel", sa.String(50), nullable=True),
    )
    # Idempotency dispatch ID
    op.add_column(
        "sequence_enrollments",
        sa.Column("last_dispatch_id", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_sequence_enrollments_last_dispatch_id",
        "sequence_enrollments",
        ["last_dispatch_id"],
    )

    # ── Set default status for existing enrollments ───────────────────
    # Existing 'active' enrollments stay active (valid FSM state)
    # No data migration needed — enum values are additive


def downgrade() -> None:
    # ── Remove indexes ────────────────────────────────────────────────
    op.drop_index(
        "ix_sequence_enrollments_last_dispatch_id",
        table_name="sequence_enrollments",
    )

    # ── Remove enrollment columns ─────────────────────────────────────
    op.drop_column("sequence_enrollments", "last_dispatch_id")
    op.drop_column("sequence_enrollments", "escalation_channel")
    op.drop_column("sequence_enrollments", "hole_filler_triggered")
    op.drop_column("sequence_enrollments", "ab_variant_assignments")
    op.drop_column("sequence_enrollments", "last_state_change_at")
    op.drop_column("sequence_enrollments", "last_touch_at")

    # ── Remove step columns ───────────────────────────────────────────
    op.drop_column("sequence_steps", "node_id")
    op.drop_column("sequence_steps", "is_ab_test")
    op.drop_column("sequence_steps", "ab_variants")
    op.drop_column("sequence_steps", "false_next_position")
    op.drop_column("sequence_steps", "true_next_position")
    op.drop_column("sequence_steps", "condition")

    # ── Remove sequence columns ───────────────────────────────────────
    op.drop_column("sequences", "ai_generation_metadata")
    op.drop_column("sequences", "ai_generation_prompt")
    op.drop_column("sequences", "ai_generated")
    op.drop_column("sequences", "visual_config")

    # Note: Enum values cannot be easily removed in PostgreSQL.
    # The added enum values (conditional, ab_split, end, pending, sent,
    # opened, replied, escalated, failed) will remain in the enum types.
