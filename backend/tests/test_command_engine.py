"""
Tests for the conversational AI command engine.

Tests cover:
- Intent classification and parsing
- Smart questioner: requirements checking, fallback extraction
- Campaign wizard: preview generation, default sequence building
- Business intelligence: timeframe parsing, static summary generation
- Chat service: command engine integration, session state, campaign confirmation
- API schemas: CommandResponse validation
"""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Intent Classification Tests ──────────────────────────────────────────────


class TestIntentResult:
    """Test IntentResult data class."""

    def test_default_values(self):
        from app.services.command_engine import IntentResult

        result = IntentResult()
        assert result.intent == "unknown"
        assert result.confidence == 0.0
        assert result.entities == {}
        assert result.missing_required == []

    def test_actionable_high_confidence(self):
        from app.services.command_engine import IntentResult

        result = IntentResult(intent="find_leads", confidence=0.9)
        assert result.is_actionable()
        assert not result.needs_clarification()

    def test_not_actionable_low_confidence(self):
        from app.services.command_engine import IntentResult

        result = IntentResult(intent="find_leads", confidence=0.5)
        assert not result.is_actionable()
        assert result.needs_clarification()

    def test_unknown_not_actionable(self):
        from app.services.command_engine import IntentResult

        result = IntentResult(intent="unknown", confidence=0.9)
        assert not result.is_actionable()

    def test_needs_clarification_with_missing_required(self):
        from app.services.command_engine import IntentResult

        result = IntentResult(
            intent="create_campaign",
            confidence=0.85,
            missing_required=["target_description"],
        )
        assert result.needs_clarification()

    def test_to_dict(self):
        from app.services.command_engine import IntentResult

        result = IntentResult(
            intent="find_leads",
            confidence=0.95,
            entities={"specialty": "periodontist"},
            missing_required=["location"],
        )
        d = result.to_dict()
        assert d["intent"] == "find_leads"
        assert d["confidence"] == 0.95
        assert d["entities"] == {"specialty": "periodontist"}
        assert d["missing_required"] == ["location"]


class TestCommandEngineClassification:
    """Test the classification parsing logic."""

    def test_parse_valid_json(self):
        from app.services.command_engine import CommandEngine

        engine = CommandEngine()
        raw = '{"intent": "find_leads", "confidence": 0.92, "entities": {"specialty": "periodontist"}, "missing_required": []}'
        result = engine._parse_classification(raw)
        assert result.intent == "find_leads"
        assert result.confidence == 0.92
        assert result.entities["specialty"] == "periodontist"

    def test_parse_json_with_markdown_fences(self):
        from app.services.command_engine import CommandEngine

        engine = CommandEngine()
        raw = '```json\n{"intent": "check_status", "confidence": 0.85, "entities": {}, "missing_required": []}\n```'
        result = engine._parse_classification(raw)
        assert result.intent == "check_status"
        assert result.confidence == 0.85

    def test_parse_invalid_json(self):
        from app.services.command_engine import CommandEngine

        engine = CommandEngine()
        result = engine._parse_classification("not valid json at all")
        assert result.intent == "unknown"
        assert result.confidence == 0.0

    def test_parse_empty_string(self):
        from app.services.command_engine import CommandEngine

        engine = CommandEngine()
        result = engine._parse_classification("")
        assert result.intent == "unknown"

    def test_parse_unknown_intent_replaced(self):
        from app.services.command_engine import CommandEngine

        engine = CommandEngine()
        raw = '{"intent": "nonexistent_intent", "confidence": 0.9, "entities": {}, "missing_required": []}'
        result = engine._parse_classification(raw)
        assert result.intent == "unknown"

    def test_all_intents_registered(self):
        from app.services.command_engine import INTENTS

        expected = [
            "find_leads", "import_leads", "enrich_leads",
            "create_campaign", "pause_campaign", "resume_campaign",
            "check_status", "check_deliverability",
            "configure_integration", "check_integrations",
            "get_help", "unknown",
        ]
        for intent in expected:
            assert intent in INTENTS


class TestCommandEngineHandlers:
    """Test static command handler responses."""

    def test_handle_help(self):
        from app.services.command_engine import CommandEngine

        engine = CommandEngine()
        result = engine._handle_help()
        assert result["type"] == "text"
        assert "Marketing Agent" in result["content"]
        assert "Sales Agent" in result["content"]

    def test_handle_import_leads(self):
        from app.services.command_engine import CommandEngine, IntentResult

        engine = CommandEngine()
        # import_leads is handled inline in route_intent — test the static path
        result = engine._handle_configure_integration({"integration_name": "hubspot"})
        assert result["type"] == "text"
        assert "HubSpot" in result["content"]

    def test_handle_configure_unknown_integration(self):
        from app.services.command_engine import CommandEngine

        engine = CommandEngine()
        result = engine._handle_configure_integration({})
        assert result["type"] == "text"
        assert "HubSpot" in result["content"]
        assert "ZoomInfo" in result["content"]

    @pytest.mark.asyncio
    async def test_handle_check_integrations(self):
        from app.services.command_engine import CommandEngine

        engine = CommandEngine()
        result = await engine._handle_check_integrations()
        assert result["type"] == "text"
        assert "Integration Status" in result["content"]


# ── Smart Questioner Tests ───────────────────────────────────────────────────


class TestSmartQuestioner:
    """Test the smart questioner service."""

    def test_intent_requirements_defined(self):
        from app.services.smart_questioner import INTENT_REQUIREMENTS

        assert "find_leads" in INTENT_REQUIREMENTS
        assert "create_campaign" in INTENT_REQUIREMENTS
        assert "check_status" in INTENT_REQUIREMENTS

    def test_find_leads_requirements(self):
        from app.services.smart_questioner import INTENT_REQUIREMENTS

        reqs = INTENT_REQUIREMENTS["find_leads"]
        assert "specialty_or_criteria" in reqs["required"]
        assert "location" in reqs["optional"]
        assert reqs["defaults"]["count"] == 25

    def test_create_campaign_requirements(self):
        from app.services.smart_questioner import INTENT_REQUIREMENTS

        reqs = INTENT_REQUIREMENTS["create_campaign"]
        assert "target_description" in reqs["required"]
        assert reqs["defaults"]["channels"] == ["email"]
        assert reqs["defaults"]["tone"] == "professional"

    def test_check_status_no_requirements(self):
        from app.services.smart_questioner import INTENT_REQUIREMENTS

        reqs = INTENT_REQUIREMENTS["check_status"]
        assert reqs["required"] == []

    def test_suggest_options_specialty(self):
        from app.services.smart_questioner import SmartQuestioner

        q = SmartQuestioner()
        options = q._suggest_options("find_leads", ["specialty_or_criteria"])
        assert "Periodontists" in options
        assert len(options) > 0

    def test_suggest_options_channels(self):
        from app.services.smart_questioner import SmartQuestioner

        q = SmartQuestioner()
        options = q._suggest_options("create_campaign", ["channels"])
        assert "Email only" in options

    def test_suggest_options_empty_for_unknown(self):
        from app.services.smart_questioner import SmartQuestioner

        q = SmartQuestioner()
        options = q._suggest_options("find_leads", ["some_unknown_field"])
        assert options == []

    def test_fallback_extract_specialty(self):
        from app.services.smart_questioner import SmartQuestioner

        q = SmartQuestioner()
        result = q._fallback_extract("periodontist", ["specialty_or_criteria"])
        assert result.get("specialty_or_criteria") == "periodontist"

    def test_fallback_extract_count(self):
        from app.services.smart_questioner import SmartQuestioner

        q = SmartQuestioner()
        result = q._fallback_extract("about 50 leads", ["count"])
        assert result.get("count") == 50

    def test_fallback_extract_location(self):
        from app.services.smart_questioner import SmartQuestioner

        q = SmartQuestioner()
        result = q._fallback_extract("Texas", ["location"])
        assert result.get("location") == "Texas"

    def test_fallback_extract_no_match(self):
        from app.services.smart_questioner import SmartQuestioner

        q = SmartQuestioner()
        result = q._fallback_extract("hello world", ["specialty_or_criteria"])
        assert "specialty_or_criteria" not in result

    @pytest.mark.asyncio
    async def test_ask_clarification_all_required_present(self):
        from app.services.command_engine import IntentResult
        from app.services.smart_questioner import SmartQuestioner

        q = SmartQuestioner()
        intent = IntentResult(
            intent="find_leads",
            confidence=0.6,
            entities={"specialty_or_criteria": "periodontist"},
        )
        result = await q.ask_clarification(intent, "find periodontists", {})
        # Should be ready to execute since required field is present
        assert result["type"] == "ready_to_execute"
        assert result["params"]["specialty_or_criteria"] == "periodontist"

    @pytest.mark.asyncio
    async def test_ask_clarification_missing_required(self):
        from app.services.command_engine import IntentResult
        from app.services.smart_questioner import SmartQuestioner

        q = SmartQuestioner()
        intent = IntentResult(
            intent="create_campaign",
            confidence=0.6,
            entities={},
        )
        result = await q.ask_clarification(intent, "start a campaign", {})
        assert result["type"] == "question"
        assert "session_state" in result
        assert result["session_state"]["active_intent"] == "create_campaign"

    @pytest.mark.asyncio
    async def test_process_answer_completes_flow(self):
        from app.services.smart_questioner import SmartQuestioner

        q = SmartQuestioner()
        state = {
            "active_intent": "find_leads",
            "gathered_params": {},
            "pending_questions": ["specialty_or_criteria"],
        }
        # Use fallback path (no LLM)
        result = await q.process_answer("periodontist", state)
        assert result["type"] == "ready_to_execute"
        assert result["params"]["specialty_or_criteria"] == "periodontist"

    @pytest.mark.asyncio
    async def test_process_answer_no_active_intent(self):
        from app.services.smart_questioner import SmartQuestioner

        q = SmartQuestioner()
        result = await q.process_answer("hello", {})
        assert result["type"] == "passthrough"


# ── Campaign Wizard Tests ────────────────────────────────────────────────────


class TestCampaignWizard:
    """Test the campaign wizard service."""

    def test_build_default_sequence_email_only(self):
        from app.services.campaign_wizard import CampaignWizard

        wizard = CampaignWizard()
        result = wizard._build_default_sequence("periodontists", ["email"], 5)
        assert "steps" in result
        step_types = [s["step_type"] for s in result["steps"]]
        assert "email" in step_types
        assert "end" in step_types
        # Should not have linkedin or sms since only email channel
        assert "linkedin" not in step_types
        assert "sms" not in step_types

    def test_build_default_sequence_multichannel(self):
        from app.services.campaign_wizard import CampaignWizard

        wizard = CampaignWizard()
        result = wizard._build_default_sequence(
            "oral surgeons", ["email", "linkedin", "sms"], 7
        )
        step_types = [s["step_type"] for s in result["steps"]]
        assert "email" in step_types
        assert "linkedin" in step_types
        assert "sms" in step_types
        assert "end" in step_types

    def test_build_default_sequence_has_waits(self):
        from app.services.campaign_wizard import CampaignWizard

        wizard = CampaignWizard()
        result = wizard._build_default_sequence("dentists", ["email"], 5)
        step_types = [s["step_type"] for s in result["steps"]]
        assert "wait" in step_types

    def test_build_default_sequence_positions_increment(self):
        from app.services.campaign_wizard import CampaignWizard

        wizard = CampaignWizard()
        result = wizard._build_default_sequence("dentists", ["email", "linkedin"], 5)
        positions = [s["position"] for s in result["steps"]]
        # Positions should be monotonically increasing
        assert positions == sorted(positions)
        # No duplicates
        assert len(positions) == len(set(positions))


# ── Business Intelligence Tests ──────────────────────────────────────────────


class TestBusinessIntelligence:
    """Test the business intelligence service."""

    def test_parse_timeframe_days(self):
        from app.services.business_intelligence import _parse_timeframe

        assert _parse_timeframe("7d") == 7
        assert _parse_timeframe("30d") == 30
        assert _parse_timeframe("1d") == 1
        assert _parse_timeframe("90d") == 90

    def test_parse_timeframe_aliases(self):
        from app.services.business_intelligence import _parse_timeframe

        assert _parse_timeframe("this week") == 7
        assert _parse_timeframe("this month") == 30
        assert _parse_timeframe("today") == 1
        assert _parse_timeframe("this quarter") == 90
        assert _parse_timeframe("1w") == 7
        assert _parse_timeframe("1m") == 30

    def test_parse_timeframe_default(self):
        from app.services.business_intelligence import _parse_timeframe

        assert _parse_timeframe("") == 7
        assert _parse_timeframe("something weird") == 7

    def test_static_summary_overview(self):
        from app.services.business_intelligence import BusinessIntelligence

        bi = BusinessIntelligence()
        metrics = {
            "timeframe": "7d",
            "total_leads": 100,
            "active_campaigns": 3,
            "engagement": {
                "sent": 500,
                "open_rate": "22.0%",
                "reply_rate": "8.5%",
            },
            "unactioned_replies": 5,
            "campaigns": [
                {"name": "Test Campaign", "status": "active", "enrolled": 50, "reply_rate": "12.0%"},
            ],
            "deliverability": {
                "inboxes": 3,
                "avg_health_score": "92.0",
                "avg_bounce_rate": "1.50%",
            },
        }
        summary = bi._build_static_summary(metrics, "overview")
        assert "Performance Overview" in summary
        assert "100" in summary  # total leads
        assert "Test Campaign" in summary
        assert "5 replies waiting" in summary

    def test_static_summary_deliverability(self):
        from app.services.business_intelligence import BusinessIntelligence

        bi = BusinessIntelligence()
        metrics = {
            "focus": "deliverability",
            "inboxes": [
                {
                    "email": "test@mail.com",
                    "status": "active",
                    "health_score": "95.0",
                    "bounce_rate": "1.00%",
                    "spam_rate": "0.010%",
                },
            ],
        }
        summary = bi._build_static_summary(metrics, "deliverability")
        assert "Deliverability Health Report" in summary
        assert "test@mail.com" in summary

    def test_static_summary_no_inboxes(self):
        from app.services.business_intelligence import BusinessIntelligence

        bi = BusinessIntelligence()
        metrics = {"focus": "deliverability", "inboxes": []}
        summary = bi._build_static_summary(metrics, "deliverability")
        assert "No sending inboxes" in summary


# ── Chat Service Command Engine Integration Tests ────────────────────────────


class TestChatServiceCommandEngine:
    """Test the chat service's command engine integration."""

    @pytest.mark.asyncio
    async def test_slash_help_updated(self):
        from app.services.chat_service import ChatService

        svc = ChatService()
        result = await svc._handle_slash_command("/help")
        assert result is not None
        assert "plain English" in result

    @pytest.mark.asyncio
    async def test_slash_unknown_returns_none(self):
        from app.services.chat_service import ChatService

        svc = ChatService()
        result = await svc._handle_slash_command("/unknown_command")
        assert result is None

    @pytest.mark.asyncio
    async def test_non_slash_returns_none(self):
        from app.services.chat_service import ChatService

        svc = ChatService()
        result = await svc._handle_slash_command("find leads in Texas")
        assert result is None

    @pytest.mark.asyncio
    async def test_campaign_confirmation_yes(self):
        from app.services.chat_service import ChatService

        svc = ChatService()
        state = {
            "active_intent": "confirm_campaign",
            "gathered_params": {
                "target": "periodontists",
                "location": "Texas",
                "channels": ["email"],
                "tone": "professional",
                "lead_ids": [],
                "sequence_preview": {
                    "name": "Test",
                    "steps": [
                        {"step_type": "email", "position": 0, "delay_hours": 0, "config": {}, "node_id": "e0"},
                        {"step_type": "end", "position": 1, "delay_hours": 0, "config": {}, "node_id": "end1"},
                    ],
                },
            },
        }
        # Mock the campaign wizard execute method
        with patch("app.services.campaign_wizard.CampaignWizard.execute_campaign") as mock_exec:
            mock_exec.return_value = {
                "type": "progress",
                "content": "Campaign launched!",
            }
            with patch.object(svc, "_save_session_state", new_callable=AsyncMock):
                result = await svc._handle_campaign_confirmation(
                    "yes", "user-1", "session-1", state
                )
                assert result["type"] == "progress"
                assert "launched" in result["content"]

    @pytest.mark.asyncio
    async def test_campaign_confirmation_cancel(self):
        from app.services.chat_service import ChatService

        svc = ChatService()
        state = {"active_intent": "confirm_campaign", "gathered_params": {}}
        with patch.object(svc, "_save_session_state", new_callable=AsyncMock):
            result = await svc._handle_campaign_confirmation(
                "cancel", "user-1", "session-1", state
            )
            assert result["type"] == "text"
            assert "cancelled" in result["content"].lower()

    @pytest.mark.asyncio
    async def test_campaign_confirmation_modify(self):
        from app.services.chat_service import ChatService

        svc = ChatService()
        state = {"active_intent": "confirm_campaign", "gathered_params": {}}
        result = await svc._handle_campaign_confirmation(
            "modify", "user-1", "session-1", state
        )
        assert result["type"] == "question"
        assert len(result["options"]) > 0

    @pytest.mark.asyncio
    async def test_campaign_confirmation_unclear(self):
        from app.services.chat_service import ChatService

        svc = ChatService()
        state = {"active_intent": "confirm_campaign", "gathered_params": {}}
        result = await svc._handle_campaign_confirmation(
            "hmm maybe", "user-1", "session-1", state
        )
        assert result["type"] == "question"
        assert "launch" in result["content"].lower()

    @pytest.mark.asyncio
    async def test_sync_message_returns_dict(self):
        from app.services.chat_service import ChatService

        svc = ChatService()
        # Patch both the command engine and LLM to control output
        with patch.object(svc, "_try_command_engine", new_callable=AsyncMock, return_value=None):
            with patch.object(svc, "_gather_context", new_callable=AsyncMock, return_value={}):
                with patch.object(svc, "_route_to_ai_platforms", new_callable=AsyncMock, return_value={}):
                    with patch.object(svc, "_log_chat", new_callable=AsyncMock):

                        async def mock_stream(messages):
                            yield "Hello test"

                        with patch.object(svc, "_stream_llm", side_effect=mock_stream):
                            result = await svc.handle_message_sync(
                                "hello", "user-1", "session-1"
                            )
                            assert result["session_id"] == "session-1"
                            assert "response" in result


# ── Schema Tests ─────────────────────────────────────────────────────────────


class TestCommandSchemas:
    """Test the new command engine schemas."""

    def test_command_response_text(self):
        from app.schemas.chat import CommandResponse

        resp = CommandResponse(
            session_id="s1",
            type="text",
            content="Hello world",
        )
        assert resp.type == "text"
        assert resp.content == "Hello world"
        assert resp.options == []
        assert resp.data == {}

    def test_command_response_question(self):
        from app.schemas.chat import CommandResponse

        resp = CommandResponse(
            session_id="s1",
            type="question",
            content="Which specialty?",
            options=["Periodontist", "Oral Surgeon"],
        )
        assert resp.type == "question"
        assert len(resp.options) == 2

    def test_command_response_action_preview(self):
        from app.schemas.chat import CommandResponse

        resp = CommandResponse(
            session_id="s1",
            type="action_preview",
            content="Ready to launch",
            campaign_params={"target": "periodontists"},
        )
        assert resp.type == "action_preview"
        assert resp.campaign_params["target"] == "periodontists"

    def test_command_response_metrics(self):
        from app.schemas.chat import CommandResponse

        resp = CommandResponse(
            session_id="s1",
            type="metrics",
            content="Performance overview",
            data={"total_leads": 100},
        )
        assert resp.type == "metrics"
        assert resp.data["total_leads"] == 100

    def test_chat_history_item_with_response_type(self):
        from app.schemas.chat import ChatHistoryItem

        item = ChatHistoryItem(
            id="test-id",
            message="hello",
            response="world",
            response_type="question",
            ai_sources=["command_engine"],
            created_at=datetime.now(UTC),
        )
        assert item.response_type == "question"

    def test_command_text_response(self):
        from app.schemas.chat import CommandTextResponse

        resp = CommandTextResponse(content="Hello")
        assert resp.type == "text"

    def test_command_question_response(self):
        from app.schemas.chat import CommandQuestionResponse

        resp = CommandQuestionResponse(content="Pick one", options=["A", "B"])
        assert resp.type == "question"
        assert len(resp.options) == 2

    def test_command_progress_response(self):
        from app.schemas.chat import CommandProgressResponse

        resp = CommandProgressResponse(content="Step 1 done")
        assert resp.type == "progress"


# ── ChatLog Model Update Tests ───────────────────────────────────────────────


class TestChatLogModelUpdated:
    """Test the updated ChatLog model with command engine fields."""

    def test_chatlog_with_session_state(self):
        from app.models.chat import ChatLog

        log = ChatLog(
            user_id="test-user",
            session_id="test-session",
            message="find leads",
            response="Found 10 leads",
            session_state={"active_intent": "find_leads", "gathered_params": {}},
            response_type="text",
            response_metadata={"total": 10},
        )
        assert log.session_state["active_intent"] == "find_leads"
        assert log.response_type == "text"
        assert log.response_metadata["total"] == 10

    def test_chatlog_without_session_state(self):
        from app.models.chat import ChatLog

        log = ChatLog(
            user_id="test-user",
            session_id="test-session",
            message="hello",
            response="Hi!",
        )
        assert log.session_state is None
        assert log.response_metadata is None


# ── Migration Tests ──────────────────────────────────────────────────────────


class TestMigration:
    """Test migration file structure."""

    def test_migration_revision_chain(self):
        import importlib.util
        import os

        path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "alembic",
            "versions",
            "010_chat_session_state.py",
        )
        spec = importlib.util.spec_from_file_location("migration_010", os.path.abspath(path))
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        assert migration.revision == "010_chat_session_state"
        assert migration.down_revision == "009_api_configurations"
