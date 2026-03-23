"""Phase 4: Sequence Engine — FSM state machine, visual builder,
A/B testing, conditional branching, AI generation.

Revision ID: 005_sequence_engine_phase4
Revises: 004_deliverability_fortress
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from migration_helpers import column_exists, index_exists

revision = "005_sequence_engine_phase4"
down_revision = "004_deliverability_fortress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # ── Extend step_type enum ─────────────────────────────────────────
    op.execute("ALTER TYPE step_type ADD VALUE IF NOT EXISTS 'conditional'")
    op.execute("ALTER TYPE step_type ADD VALUE IF NOT EXISTS 'ab_split'")
    op.execute("ALTER TYPE step_type ADD VALUE IF NOT EXISTS 'end'")

    # ── Extend enrollment_status enum ─────────────────────────────────
    op.execute("ALTER TYPE enrollment_status ADD VALUE IF NOT EXISTS 'pending'")
    op.execute("ALTER TYPE enrollment_status ADD VALUE IF NOT EXISTS 'sent'")
    op.execute("ALTER TYPE enrollment_status ADD VALUE IF NOT EXISTS 'opened'")
    op.execute("ALTER TYPE enrollment_status ADD VALUE IF NOT EXISTS 'replied'")
    op.execute("ALTER TYPE enrollment_status ADD VALUE IF NOT EXISTS 'escalated'")
    op.execute("ALTER TYPE enrollment_status ADD VALUE IF NOT EXISTS 'failed'")

    # ── Enhance sequences table ───────────────────────────────────────
    if not column_exists(bind, "sequences", "visual_config"):
        op.add_column(
            "sequences",
            sa.Column("visual_config", JSONB, nullable=True),
        )
    if not column_exists(bind, "sequences", "ai_generated"):
        op.add_column(
            "sequences",
            sa.Column(
                "ai_generated",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if not column_exists(bind, "sequences", "ai_generation_prompt"):
        op.add_column(
            "sequences",
            sa.Column("ai_generation_prompt", sa.Text, nullable=True),
        )
    if not column_exists(bind, "sequences", "ai_generation_metadata"):
        op.add_column(
            "sequences",
            sa.Column("ai_generation_metadata", JSONB, nullable=True),
        )

    # ── Enhance sequence_steps table ──────────────────────────────────
    if not column_exists(bind, "sequence_steps", "condition"):
        op.add_column(
            "sequence_steps",
            sa.Column("condition", JSONB, nullable=True),
        )
    if not column_exists(bind, "sequence_steps", "true_next_position"):
        op.add_column(
            "sequence_steps",
            sa.Column("true_next_position", sa.Integer, nullable=True),
        )
    if not column_exists(bind, "sequence_steps", "false_next_position"):
        op.add_column(
            "sequence_steps",
            sa.Column("false_next_position", sa.Integer, nullable=True),
        )
    if not column_exists(bind, "sequence_steps", "ab_variants"):
        op.add_column(
            "sequence_steps",
            sa.Column("ab_variants", JSONB, nullable=True),
        )
    if not column_exists(bind, "sequence_steps", "is_ab_test"):
        op.add_column(
            "sequence_steps",
            sa.Column(
                "is_ab_test",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if not column_exists(bind, "sequence_steps", "node_id"):
        op.add_column(
            "sequence_steps",
            sa.Column("node_id", sa.String(100), nullable=True),
        )

    # ── Enhance sequence_enrollments table ────────────────────────────
    if not column_exists(bind, "sequence_enrollments", "last_touch_at"):
        op.add_column(
            "sequence_enrollments",
            sa.Column(
                "last_touch_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )
    if not column_exists(bind, "sequence_enrollments", "last_state_change_at"):
        op.add_column(
            "sequence_enrollments",
            sa.Column(
                "last_state_change_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )
    if not column_exists(bind, "sequence_enrollments", "ab_variant_assignments"):
        op.add_column(
            "sequence_enrollments",
            sa.Column("ab_variant_assignments", JSONB, nullable=True),
        )
    if not column_exists(bind, "sequence_enrollments", "hole_filler_triggered"):
        op.add_column(
            "sequence_enrollments",
            sa.Column(
                "hole_filler_triggered",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if not column_exists(bind, "sequence_enrollments", "escalation_channel"):
        op.add_column(
            "sequence_enrollments",
            sa.Column("escalation_channel", sa.String(50), nullable=True),
        )
    if not column_exists(bind, "sequence_enrollments", "last_dispatch_id"):
        op.add_column(
            "sequence_enrollments",
            sa.Column("last_dispatch_id", sa.String(255), nullable=True),
        )
    if not index_exists(bind, "ix_sequence_enrollments_last_dispatch_id"):
        op.create_index(
            "ix_sequence_enrollments_last_dispatch_id",
            "sequence_enrollments",
            ["last_dispatch_id"],
        )


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
