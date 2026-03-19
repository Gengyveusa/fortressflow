"""
Phase 4 tests — State machine, sequence engine, AI generation,
visual builder, and dispatch.

All tests use in-memory mocks (no real database or external APIs).
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.state_machine import (
    EnrollmentState,
    StateTransitionError,
    can_transition,
    evaluate_condition,
    get_available_transitions,
    handle_bounce_signal,
    handle_complaint_signal,
    handle_open_signal,
    handle_reply_signal,
    is_live,
    is_sendable,
    is_terminal,
    transition,
    validate_transition,
)


# ═══════════════════════════════════════════════════════════════════════
# 1. STATE MACHINE TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestStateTransitions:
    """Test FSM state transition rules."""

    def test_pending_to_active(self):
        result = transition("pending", "active")
        assert result == "active"

    def test_active_to_sent(self):
        result = transition("active", "sent")
        assert result == "sent"

    def test_sent_to_opened(self):
        result = transition("sent", "opened")
        assert result == "opened"

    def test_sent_to_replied(self):
        result = transition("sent", "replied")
        assert result == "replied"

    def test_sent_to_active(self):
        """Timer elapsed, ready for next step."""
        result = transition("sent", "active")
        assert result == "active"

    def test_opened_to_replied(self):
        result = transition("opened", "replied")
        assert result == "replied"

    def test_replied_to_paused(self):
        """Auto-pause on reply."""
        result = transition("replied", "paused")
        assert result == "paused"

    def test_paused_to_active(self):
        """Resume."""
        result = transition("paused", "active")
        assert result == "active"

    def test_active_to_completed(self):
        result = transition("active", "completed")
        assert result == "completed"

    def test_active_to_escalated(self):
        result = transition("active", "escalated")
        assert result == "escalated"

    def test_escalated_to_sent(self):
        result = transition("escalated", "sent")
        assert result == "sent"

    def test_completed_is_terminal(self):
        assert is_terminal("completed")
        assert not is_sendable("completed")
        assert get_available_transitions("completed") == set()

    def test_failed_is_terminal(self):
        assert is_terminal("failed")
        assert get_available_transitions("failed") == set()


class TestInvalidTransitions:
    """Test that invalid transitions raise errors."""

    def test_completed_to_active_blocked(self):
        with pytest.raises(StateTransitionError):
            transition("completed", "active")

    def test_failed_to_active_blocked(self):
        with pytest.raises(StateTransitionError):
            transition("failed", "active")

    def test_pending_to_sent_blocked(self):
        """Can't send from pending — must activate first."""
        with pytest.raises(StateTransitionError):
            transition("pending", "sent")

    def test_pending_to_completed_blocked(self):
        with pytest.raises(StateTransitionError):
            transition("pending", "completed")

    def test_can_transition_returns_false(self):
        assert can_transition("completed", "active") is False
        assert can_transition("pending", "sent") is False


class TestSendableStates:
    """Test which states allow sending."""

    def test_active_is_sendable(self):
        assert is_sendable("active")

    def test_escalated_is_sendable(self):
        assert is_sendable("escalated")

    def test_pending_not_sendable(self):
        assert not is_sendable("pending")

    def test_sent_not_sendable(self):
        assert not is_sendable("sent")

    def test_paused_not_sendable(self):
        assert not is_sendable("paused")


class TestLiveStates:
    """Test live (non-terminal) states."""

    def test_all_live_states(self):
        for state in ["pending", "active", "sent", "opened", "replied", "paused", "escalated"]:
            assert is_live(state), f"{state} should be live"

    def test_terminal_states_not_live(self):
        for state in ["completed", "failed", "bounced", "unsubscribed"]:
            assert not is_live(state), f"{state} should not be live"


class TestSignalHandlers:
    """Test engagement signal handlers."""

    def test_open_signal_from_sent(self):
        result = handle_open_signal("sent")
        assert result == "opened"

    def test_open_signal_from_opened_stays(self):
        result = handle_open_signal("opened")
        assert result == "opened"

    def test_reply_signal_from_sent(self):
        result = handle_reply_signal("sent")
        assert result == "replied"

    def test_reply_signal_from_opened(self):
        result = handle_reply_signal("opened")
        assert result == "replied"

    def test_bounce_signal_from_sent(self):
        result = handle_bounce_signal("sent")
        assert result == "failed"

    def test_bounce_signal_from_active(self):
        result = handle_bounce_signal("active")
        assert result == "failed"

    def test_complaint_signal_from_active(self):
        result = handle_complaint_signal("active")
        assert result == "failed"

    def test_complaint_signal_from_terminal_no_change(self):
        result = handle_complaint_signal("completed")
        assert result == "completed"


# ═══════════════════════════════════════════════════════════════════════
# 2. CONDITION EVALUATOR TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestConditionEvaluator:
    """Test the branch condition evaluator."""

    def test_opened_condition_true(self):
        result = evaluate_condition(
            condition={"type": "opened"},
            enrollment_state="opened",
            touch_history=[],
        )
        assert result is True

    def test_opened_condition_from_history(self):
        result = evaluate_condition(
            condition={"type": "opened"},
            enrollment_state="active",
            touch_history=[{"step_number": 1, "action": "opened"}],
        )
        assert result is True

    def test_not_opened_condition(self):
        result = evaluate_condition(
            condition={"type": "not_opened"},
            enrollment_state="active",
            touch_history=[{"step_number": 1, "action": "sent"}],
        )
        assert result is True

    def test_replied_condition(self):
        result = evaluate_condition(
            condition={"type": "replied"},
            enrollment_state="replied",
            touch_history=[],
        )
        assert result is True

    def test_not_replied_condition(self):
        result = evaluate_condition(
            condition={"type": "not_replied"},
            enrollment_state="active",
            touch_history=[],
        )
        assert result is True

    def test_clicked_condition(self):
        result = evaluate_condition(
            condition={"type": "clicked"},
            enrollment_state="active",
            touch_history=[{"step_number": 1, "action": "clicked"}],
        )
        assert result is True

    def test_clicked_condition_false(self):
        result = evaluate_condition(
            condition={"type": "clicked"},
            enrollment_state="active",
            touch_history=[{"step_number": 1, "action": "sent"}],
        )
        assert result is False

    def test_bounced_condition(self):
        result = evaluate_condition(
            condition={"type": "bounced"},
            enrollment_state="failed",
            touch_history=[],
        )
        assert result is True

    def test_step_position_filter(self):
        result = evaluate_condition(
            condition={"type": "opened", "step_position": 2},
            enrollment_state="active",
            touch_history=[
                {"step_number": 1, "action": "opened"},
                {"step_number": 2, "action": "sent"},
            ],
        )
        # Step 2 was sent but not opened
        assert result is False

    def test_unknown_condition_type(self):
        result = evaluate_condition(
            condition={"type": "custom_unknown"},
            enrollment_state="active",
            touch_history=[],
        )
        assert result is False


# ═══════════════════════════════════════════════════════════════════════
# 3. AI SEQUENCE GENERATION TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestSequenceAIService:
    """Test AI sequence generation service (mocked platforms)."""

    @pytest.mark.asyncio
    async def test_generate_sequence_all_platforms_disabled(self):
        """When no platforms are enabled, generation falls back to defaults."""
        from app.services.sequence_ai_service import SequenceAIService

        with patch("app.services.sequence_ai_service.settings") as mock_settings:
            mock_settings.ZOOMINFO_COPILOT_ENABLED = False
            mock_settings.APOLLO_AI_ENABLED = False
            mock_settings.HUBSPOT_BREEZE_ENABLED = False
            mock_settings.APOLLO_API_KEY = ""
            mock_settings.HUBSPOT_API_KEY = ""

            svc = SequenceAIService()
            result = await svc.generate_sequence(
                prompt="Create an outreach sequence for dental offices",
            )

            assert result.success is True
            assert len(result.sequence_config.get("steps", [])) > 0
            assert result.sequence_config["ai_generated"] is True
            assert result.visual_config is not None
            assert "nodes" in result.visual_config
            assert "edges" in result.visual_config

    @pytest.mark.asyncio
    async def test_generate_includes_ab_test(self):
        from app.services.sequence_ai_service import SequenceAIService

        with patch("app.services.sequence_ai_service.settings") as mock_settings:
            mock_settings.ZOOMINFO_COPILOT_ENABLED = False
            mock_settings.APOLLO_AI_ENABLED = False
            mock_settings.HUBSPOT_BREEZE_ENABLED = False

            svc = SequenceAIService()
            result = await svc.generate_sequence(
                prompt="Create a dental outreach sequence",
                include_ab_test=True,
            )

            steps = result.sequence_config["steps"]
            ab_steps = [s for s in steps if s["step_type"] == "ab_split"]
            assert len(ab_steps) >= 1
            assert ab_steps[0]["ab_variants"] is not None
            assert "A" in ab_steps[0]["ab_variants"]
            assert "B" in ab_steps[0]["ab_variants"]

    @pytest.mark.asyncio
    async def test_generate_includes_conditionals(self):
        from app.services.sequence_ai_service import SequenceAIService

        with patch("app.services.sequence_ai_service.settings") as mock_settings:
            mock_settings.ZOOMINFO_COPILOT_ENABLED = False
            mock_settings.APOLLO_AI_ENABLED = False
            mock_settings.HUBSPOT_BREEZE_ENABLED = False

            svc = SequenceAIService()
            result = await svc.generate_sequence(
                prompt="Create a dental outreach sequence",
                include_conditionals=True,
            )

            steps = result.sequence_config["steps"]
            cond_steps = [s for s in steps if s["step_type"] == "conditional"]
            assert len(cond_steps) >= 1
            assert cond_steps[0]["condition"] is not None

    @pytest.mark.asyncio
    async def test_generate_without_ab_or_conditionals(self):
        from app.services.sequence_ai_service import SequenceAIService

        with patch("app.services.sequence_ai_service.settings") as mock_settings:
            mock_settings.ZOOMINFO_COPILOT_ENABLED = False
            mock_settings.APOLLO_AI_ENABLED = False
            mock_settings.HUBSPOT_BREEZE_ENABLED = False

            svc = SequenceAIService()
            result = await svc.generate_sequence(
                prompt="Create a basic email sequence",
                include_ab_test=False,
                include_conditionals=False,
                channels=["email"],
            )

            steps = result.sequence_config["steps"]
            assert all(s["step_type"] != "ab_split" for s in steps)
            assert all(s["step_type"] != "conditional" for s in steps)

    @pytest.mark.asyncio
    async def test_visual_config_has_start_node(self):
        from app.services.sequence_ai_service import SequenceAIService

        with patch("app.services.sequence_ai_service.settings") as mock_settings:
            mock_settings.ZOOMINFO_COPILOT_ENABLED = False
            mock_settings.APOLLO_AI_ENABLED = False
            mock_settings.HUBSPOT_BREEZE_ENABLED = False

            svc = SequenceAIService()
            result = await svc.generate_sequence(
                prompt="Quick dental outreach",
            )

            nodes = result.visual_config["nodes"]
            start_nodes = [n for n in nodes if n["id"] == "start"]
            assert len(start_nodes) == 1
            assert start_nodes[0]["type"] == "start"

    @pytest.mark.asyncio
    async def test_visual_config_edges_connect_all_nodes(self):
        from app.services.sequence_ai_service import SequenceAIService

        with patch("app.services.sequence_ai_service.settings") as mock_settings:
            mock_settings.ZOOMINFO_COPILOT_ENABLED = False
            mock_settings.APOLLO_AI_ENABLED = False
            mock_settings.HUBSPOT_BREEZE_ENABLED = False

            svc = SequenceAIService()
            result = await svc.generate_sequence(
                prompt="Quick dental outreach",
                include_conditionals=False,
                include_ab_test=False,
            )

            nodes = result.visual_config["nodes"]
            edges = result.visual_config["edges"]

            # Every non-start node should have at least one incoming edge
            non_start_ids = {n["id"] for n in nodes if n["id"] != "start"}
            targets = {e["target"] for e in edges}
            assert non_start_ids == targets


# ═══════════════════════════════════════════════════════════════════════
# 4. A/B VARIANT ASSIGNMENT TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestABVariantAssignment:
    """Test deterministic A/B variant assignment."""

    def test_first_assignment(self):
        from app.services.sequence_executor import _assign_ab_variant

        step = MagicMock()
        step.position = 0
        step.ab_variants = {
            "A": {"template_id": "t1", "weight": 50},
            "B": {"template_id": "t2", "weight": 50},
        }

        enrollment = MagicMock()
        enrollment.ab_variant_assignments = None

        variant = _assign_ab_variant(step, enrollment)
        assert variant in ("A", "B")

    def test_idempotent_assignment(self):
        from app.services.sequence_executor import _assign_ab_variant

        step = MagicMock()
        step.position = 0
        step.ab_variants = {
            "A": {"template_id": "t1", "weight": 50},
            "B": {"template_id": "t2", "weight": 50},
        }

        enrollment = MagicMock()
        enrollment.ab_variant_assignments = {"0": "B"}

        # Should return the already-assigned variant
        variant = _assign_ab_variant(step, enrollment)
        assert variant == "B"

    def test_empty_variants_defaults_to_a(self):
        from app.services.sequence_executor import _assign_ab_variant

        step = MagicMock()
        step.position = 0
        step.ab_variants = {}

        enrollment = MagicMock()
        enrollment.ab_variant_assignments = None

        variant = _assign_ab_variant(step, enrollment)
        assert variant == "A"


# ═══════════════════════════════════════════════════════════════════════
# 5. SCHEMA VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestSchemaValidation:
    """Test Pydantic schema validation for Phase 4."""

    def test_sequence_step_create_with_conditional(self):
        from app.schemas.sequence import SequenceStepCreate

        step = SequenceStepCreate(
            step_type="conditional",
            position=2,
            condition={"type": "opened", "within_hours": 48},
            true_next_position=3,
            false_next_position=4,
        )
        assert step.step_type == "conditional"
        assert step.condition["type"] == "opened"

    def test_sequence_step_create_with_ab_split(self):
        from app.schemas.sequence import SequenceStepCreate

        step = SequenceStepCreate(
            step_type="ab_split",
            position=0,
            is_ab_test=True,
            ab_variants={
                "A": {"template_id": "abc", "weight": 50},
                "B": {"template_id": "def", "weight": 50},
            },
        )
        assert step.is_ab_test is True
        assert "A" in step.ab_variants

    def test_sequence_create_with_visual_config(self):
        from app.schemas.sequence import SequenceCreate

        seq = SequenceCreate(
            name="Test Sequence",
            visual_config={
                "nodes": [{"id": "start", "type": "start", "position": {"x": 0, "y": 0}, "data": {}}],
                "edges": [],
                "viewport": {"x": 0, "y": 0, "zoom": 1},
            },
            ai_generated=True,
        )
        assert seq.visual_config is not None
        assert seq.ai_generated is True

    def test_generate_request_validation(self):
        from app.schemas.sequence import SequenceGenerateRequest

        req = SequenceGenerateRequest(
            prompt="Create a dental outreach sequence with 5 steps",
            target_industry="dental",
            channels=["email", "linkedin"],
            include_ab_test=True,
        )
        assert len(req.prompt) >= 10
        assert "email" in req.channels

    def test_generate_request_min_prompt_length(self):
        from app.schemas.sequence import SequenceGenerateRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SequenceGenerateRequest(prompt="too short")

    def test_enrollment_response_with_phase4_fields(self):
        from app.schemas.sequence import EnrollmentResponse

        resp = EnrollmentResponse(
            id=uuid.uuid4(),
            sequence_id=uuid.uuid4(),
            lead_id=uuid.uuid4(),
            current_step=2,
            status="sent",
            enrolled_at=datetime.now(UTC),
            last_touch_at=datetime.now(UTC),
            last_state_change_at=datetime.now(UTC),
            ab_variant_assignments={"0": "A"},
            hole_filler_triggered=False,
            escalation_channel=None,
            last_dispatch_id="abc-123",
        )
        assert resp.ab_variant_assignments == {"0": "A"}
        assert resp.last_dispatch_id == "abc-123"

    def test_ab_variant_analytics(self):
        from app.schemas.sequence import ABVariantAnalytics

        analytics = ABVariantAnalytics(
            step_position=0,
            variant="A",
            sent=100,
            opened=45,
            replied=12,
            bounced=3,
            open_rate=0.45,
            reply_rate=0.12,
        )
        assert analytics.open_rate == 0.45
        assert analytics.reply_rate == 0.12


# ═══════════════════════════════════════════════════════════════════════
# 6. VISUAL CONFIG BUILDER TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestVisualConfigBuilder:
    """Test the visual config (React Flow) builder."""

    def test_build_visual_config_basic(self):
        from app.services.sequence_ai_service import SequenceAIService

        svc = SequenceAIService()
        steps = [
            {"step_type": "email", "position": 0, "delay_hours": 0, "node_id": "email_0", "config": {}},
            {"step_type": "wait", "position": 1, "delay_hours": 48, "node_id": "wait_1", "config": {}},
            {"step_type": "email", "position": 2, "delay_hours": 0, "node_id": "email_2", "config": {}},
            {"step_type": "end", "position": 3, "delay_hours": 0, "node_id": "end_3", "config": {}},
        ]

        config = svc._build_visual_config(steps)

        # Start node + 4 step nodes = 5 total
        assert len(config["nodes"]) == 5
        assert config["nodes"][0]["id"] == "start"
        assert config["nodes"][0]["type"] == "start"

        # Edges: start→email_0, email_0→wait_1, wait_1→email_2, email_2→end_3
        assert len(config["edges"]) == 4

    def test_step_label_generation(self):
        from app.services.sequence_ai_service import SequenceAIService

        assert SequenceAIService._step_label(
            {"step_type": "email", "config": {"subject_hint": "Test Subject"}}
        ) == "Test Subject"

        assert SequenceAIService._step_label(
            {"step_type": "wait", "delay_hours": 48}
        ) == "Wait 2 days"

        assert SequenceAIService._step_label(
            {"step_type": "wait", "delay_hours": 12}
        ) == "Wait 12h"

        assert SequenceAIService._step_label(
            {"step_type": "conditional", "condition": {"type": "opened"}}
        ) == "If: opened"

        assert SequenceAIService._step_label(
            {"step_type": "ab_split"}
        ) == "A/B Test"

        assert SequenceAIService._step_label(
            {"step_type": "end"}
        ) == "End"
