"""
Phase 7: Tests for the in-app AI chatbot assistant.

Tests cover:
- Chat service: context gathering, slash commands, LLM streaming, AI platform routing
- Chat API: endpoint validation, rate limiting, streaming SSE, history
- Chat model: ChatLog creation
- Celery task: feedback push, topic categorization
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Chat Model Tests ──────────────────────────────────────────────────────────

class TestChatLogModel:
    """Test ChatLog model and schema."""

    def test_chat_log_creation(self):
        from app.models.chat import ChatLog
        log = ChatLog(
            user_id="test-user",
            session_id="test-session",
            message="Hello",
            response="Hi there!",
            ai_model="groq",
            ai_sources={"sources": ["system"]},
            tokens_used=50,
            latency_ms=200,
        )
        assert log.user_id == "test-user"
        assert log.session_id == "test-session"
        assert log.message == "Hello"
        assert log.response == "Hi there!"
        assert log.ai_model == "groq"
        assert log.tokens_used == 50
        assert log.latency_ms == 200

    def test_chat_request_schema_validation(self):
        from app.schemas.chat import ChatRequest
        req = ChatRequest(message="Hello", session_id="s1")
        assert req.message == "Hello"
        assert req.session_id == "s1"

    def test_chat_request_empty_message_rejected(self):
        from app.schemas.chat import ChatRequest
        with pytest.raises(Exception):
            ChatRequest(message="", session_id="s1")

    def test_chat_request_max_length(self):
        from app.schemas.chat import ChatRequest
        # Should succeed at 4000 chars
        req = ChatRequest(message="a" * 4000)
        assert len(req.message) == 4000
        # Should fail at 4001
        with pytest.raises(Exception):
            ChatRequest(message="a" * 4001)

    def test_chat_response_schema(self):
        from app.schemas.chat import ChatResponse
        resp = ChatResponse(
            session_id="s1",
            message="Hi",
            response="Hello!",
            ai_model="groq",
            ai_sources=["system"],
            created_at=datetime.now(UTC),
        )
        assert resp.session_id == "s1"
        assert resp.response == "Hello!"

    def test_chat_history_response_schema(self):
        from app.schemas.chat import ChatHistoryResponse, ChatHistoryItem
        items = [ChatHistoryItem(
            id="abc",
            message="Hi",
            response="Hello",
            ai_sources=["system"],
            created_at=datetime.now(UTC),
        )]
        resp = ChatHistoryResponse(items=items, total=1, session_id="s1")
        assert resp.total == 1


# ── Slash Command Tests ───────────────────────────────────────────────────────

class TestSlashCommands:
    """Test slash command handling."""

    @pytest.mark.asyncio
    async def test_help_command(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        result = await svc._handle_slash_command("/help")
        assert result is not None
        assert "/status" in result
        assert "/warmup" in result
        assert "/sequences" in result

    @pytest.mark.asyncio
    async def test_status_command(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        with patch.object(svc, "_gather_context", return_value={
            "sequences": {"active_count": 3, "total_enrolled": 50},
            "deliverability": {"bounce_rate": "2.1%", "spam_rate": "0.05%", "warmup_active": 2},
            "leads": {"total": 200},
        }):
            result = await svc._handle_slash_command("/status")
        assert result is not None
        assert "Active Sequences" in result
        assert "3" in result

    @pytest.mark.asyncio
    async def test_warmup_command(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        with patch.object(svc, "_gather_context", return_value={
            "deliverability": {"warmup_active": 0, "warmup_completed": 5},
        }):
            result = await svc._handle_slash_command("/warmup")
        assert result is not None
        assert "Warmup Status" in result
        assert "No active warmup" in result

    @pytest.mark.asyncio
    async def test_sequences_command_empty(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        with patch.object(svc, "_gather_context", return_value={
            "sequences": {"recent": []},
        }):
            result = await svc._handle_slash_command("/sequences")
        assert result is not None
        assert "No sequences found" in result

    @pytest.mark.asyncio
    async def test_sequences_command_with_data(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        with patch.object(svc, "_gather_context", return_value={
            "sequences": {"recent": [
                {"name": "Q1 Outreach", "status": "active", "enrolled": 25, "reply_rate": "12%"},
            ]},
        }):
            result = await svc._handle_slash_command("/sequences")
        assert result is not None
        assert "Q1 Outreach" in result

    @pytest.mark.asyncio
    async def test_compliance_command(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        result = await svc._handle_slash_command("/compliance")
        assert result is not None
        assert "Compliance" in result
        assert "can_send_to_lead" in result

    @pytest.mark.asyncio
    async def test_leads_command(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        with patch.object(svc, "_gather_context", return_value={
            "leads": {"total": 500},
        }):
            result = await svc._handle_slash_command("/leads")
        assert result is not None
        assert "500" in result

    @pytest.mark.asyncio
    async def test_deliverability_command(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        with patch.object(svc, "_gather_context", return_value={
            "deliverability": {"total_sent": 1200, "bounce_rate": "1.5%", "spam_rate": "0.03%", "warmup_active": 3},
        }):
            result = await svc._handle_slash_command("/deliverability")
        assert result is not None
        assert "1200" in result

    @pytest.mark.asyncio
    async def test_unknown_command_returns_none(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        result = await svc._handle_slash_command("/unknown_cmd")
        assert result is None

    @pytest.mark.asyncio
    async def test_non_command_returns_none(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        result = await svc._handle_slash_command("hello there")
        assert result is None


# ── Context Gathering Tests ───────────────────────────────────────────────────

class TestContextGathering:
    """Test context injection for LLM prompts."""

    @pytest.mark.asyncio
    async def test_gather_context_handles_db_errors(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        # Should not raise — returns context with error key
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(side_effect=Exception("DB down"))
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with patch("app.database.AsyncSessionLocal", return_value=mock_session):
            context = await svc._gather_context()
        assert "error" in context

    def test_build_messages_with_context(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        context = {
            "sequences": {"active_count": 2, "total_enrolled": 30, "recent": []},
            "deliverability": {"total_sent": 100, "bounce_rate": "1%", "warmup_active": 1},
            "leads": {"total": 50},
        }
        messages = svc._build_messages("How are things?", context, {}, "session-1")
        # Should have system prompt + context + user message
        assert len(messages) >= 3
        assert messages[0]["role"] == "system"
        assert "FortressFlow" in messages[0]["content"]
        assert "LIVE CONTEXT" in messages[1]["content"]
        assert messages[-1]["role"] == "user"

    def test_build_messages_with_platform_insights(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        insights = {"hubspot_breeze": "Open rates are trending up 5%"}
        messages = svc._build_messages("How are my emails doing?", {}, insights, "s1")
        assert any("HubSpot Breeze" in m.get("content", "") for m in messages)

    def test_build_messages_minimal(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        messages = svc._build_messages("Hello", {}, {}, "s1")
        assert len(messages) == 2  # system + user
        assert messages[-1]["content"] == "Hello"


# ── AI Platform Routing Tests ─────────────────────────────────────────────────

class TestAIPlatformRouting:
    """Test routing to HubSpot Breeze / ZoomInfo / Apollo."""

    @pytest.mark.asyncio
    async def test_route_sequence_question_to_hubspot(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        with patch.object(svc, "_query_hubspot_breeze", return_value="Open rate is 25%") as mock_hs:
            with patch("app.services.chat_service.settings") as mock_settings:
                mock_settings.HUBSPOT_BREEZE_ENABLED = True
                mock_settings.HUBSPOT_API_KEY = "test-key"
                mock_settings.ZOOMINFO_COPILOT_ENABLED = False
                mock_settings.APOLLO_AI_ENABLED = False
                insights = await svc._route_to_ai_platforms("What's my sequence open rate?")
        assert "hubspot_breeze" in insights

    @pytest.mark.asyncio
    async def test_route_lead_question_to_zoominfo(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        with patch.object(svc, "_query_zoominfo_copilot", return_value="Lead is at Fortune 500 company") as mock_zi:
            with patch("app.services.chat_service.settings") as mock_settings:
                mock_settings.HUBSPOT_BREEZE_ENABLED = False
                mock_settings.ZOOMINFO_COPILOT_ENABLED = True
                mock_settings.ZOOMINFO_API_KEY = "test-key"
                mock_settings.APOLLO_AI_ENABLED = False
                insights = await svc._route_to_ai_platforms("Tell me about my leads")
        assert "zoominfo_copilot" in insights

    @pytest.mark.asyncio
    async def test_route_action_question_to_apollo(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        with patch.object(svc, "_query_apollo_ai", return_value="Recommend warming up first") as mock_ap:
            with patch("app.services.chat_service.settings") as mock_settings:
                mock_settings.HUBSPOT_BREEZE_ENABLED = False
                mock_settings.ZOOMINFO_COPILOT_ENABLED = False
                mock_settings.APOLLO_AI_ENABLED = True
                mock_settings.APOLLO_API_KEY = "test-key"
                insights = await svc._route_to_ai_platforms("What should I do next?")
        assert "apollo_ai" in insights

    @pytest.mark.asyncio
    async def test_no_routing_when_disabled(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        with patch("app.services.chat_service.settings") as mock_settings:
            mock_settings.HUBSPOT_BREEZE_ENABLED = False
            mock_settings.ZOOMINFO_COPILOT_ENABLED = False
            mock_settings.APOLLO_AI_ENABLED = False
            insights = await svc._route_to_ai_platforms("What's my sequence doing?")
        assert len(insights) == 0

    @pytest.mark.asyncio
    async def test_platform_failure_handled_gracefully(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        with patch.object(svc, "_query_hubspot_breeze", side_effect=Exception("API error")):
            with patch("app.services.chat_service.settings") as mock_settings:
                mock_settings.HUBSPOT_BREEZE_ENABLED = True
                mock_settings.HUBSPOT_API_KEY = "test-key"
                mock_settings.ZOOMINFO_COPILOT_ENABLED = False
                mock_settings.APOLLO_AI_ENABLED = False
                insights = await svc._route_to_ai_platforms("How are my sequences?")
        # Should not crash, just return empty
        assert "hubspot_breeze" not in insights


# ── Chat Rate Limiting Tests ──────────────────────────────────────────────────

class TestChatRateLimiting:
    """Test per-user chat rate limiting (Redis sliding window)."""

    @pytest.mark.asyncio
    async def test_rate_limit_allows_under_threshold(self):
        from app.api.v1.chat import _check_chat_rate_limit

        mock_redis = AsyncMock()
        mock_pipe = AsyncMock()
        mock_pipe.zremrangebyscore = MagicMock(return_value=mock_pipe)
        mock_pipe.zcard = MagicMock(return_value=mock_pipe)
        mock_pipe.zadd = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[0, 5, 1, True])  # count=5, under limit
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=False)
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch("app.api.v1.chat._get_chat_redis", new_callable=AsyncMock, return_value=mock_redis):
            # Should not raise
            await _check_chat_rate_limit("user-1")

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_over_threshold(self):
        from app.api.v1.chat import _check_chat_rate_limit, _CHAT_RATE_LIMIT
        from fastapi import HTTPException

        mock_redis = AsyncMock()
        mock_pipe = AsyncMock()
        mock_pipe.zremrangebyscore = MagicMock(return_value=mock_pipe)
        mock_pipe.zcard = MagicMock(return_value=mock_pipe)
        mock_pipe.zadd = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[0, _CHAT_RATE_LIMIT, 1, True])  # at limit
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=False)
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)
        mock_redis.zrem = AsyncMock()

        with patch("app.api.v1.chat._get_chat_redis", new_callable=AsyncMock, return_value=mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                await _check_chat_rate_limit("user-2")
            assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_per_user_isolation(self):
        from app.api.v1.chat import _check_chat_rate_limit

        mock_redis = AsyncMock()
        mock_pipe = AsyncMock()
        mock_pipe.zremrangebyscore = MagicMock(return_value=mock_pipe)
        mock_pipe.zcard = MagicMock(return_value=mock_pipe)
        mock_pipe.zadd = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[0, 5, 1, True])  # under limit
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=False)
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch("app.api.v1.chat._get_chat_redis", new_callable=AsyncMock, return_value=mock_redis):
            # Both users should succeed independently
            await _check_chat_rate_limit("user-3")
            await _check_chat_rate_limit("user-4")


# ── Chat Feedback Task Tests ──────────────────────────────────────────────────

class TestChatFeedback:
    """Test feedback push and topic categorization."""

    def test_categorize_sequences_topic(self):
        from app.workers.tasks import _categorize_chat_topic
        assert _categorize_chat_topic("How do I create a sequence?") == "sequences"

    def test_categorize_deliverability_topic(self):
        from app.workers.tasks import _categorize_chat_topic
        assert _categorize_chat_topic("What is my warmup status?") == "deliverability"
        assert _categorize_chat_topic("My bounce rate is high") == "deliverability"

    def test_categorize_leads_topic(self):
        from app.workers.tasks import _categorize_chat_topic
        assert _categorize_chat_topic("How do I import leads?") == "leads"

    def test_categorize_compliance_topic(self):
        from app.workers.tasks import _categorize_chat_topic
        assert _categorize_chat_topic("Am I GDPR compliant?") == "compliance"

    def test_categorize_templates_topic(self):
        from app.workers.tasks import _categorize_chat_topic
        assert _categorize_chat_topic("Help me write a better email subject") == "templates"

    def test_categorize_analytics_topic(self):
        from app.workers.tasks import _categorize_chat_topic
        assert _categorize_chat_topic("Show me my dashboard metrics") == "analytics"

    def test_categorize_setup_topic(self):
        from app.workers.tasks import _categorize_chat_topic
        assert _categorize_chat_topic("How do I setup FortressFlow?") == "setup"

    def test_categorize_general_topic(self):
        from app.workers.tasks import _categorize_chat_topic
        assert _categorize_chat_topic("What's the meaning of life?") == "general"


# ── LLM Streaming Tests ──────────────────────────────────────────────────────

class TestLLMStreaming:
    """Test LLM streaming and provider fallback."""

    @pytest.mark.asyncio
    async def test_stream_fallback_without_api_key(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        with patch("app.services.chat_service.settings") as mock_settings:
            mock_settings.GROQ_API_KEY = ""
            mock_settings.OPENAI_API_KEY = ""
            chunks = []
            async for chunk in svc._stream_llm([], provider="groq"):
                chunks.append(chunk)
            # Should return a fallback message, not raise
            assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_handle_message_slash_command(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        chunks = []
        async for chunk in svc.handle_message("/help", "user-1", "session-1"):
            chunks.append(chunk)
        full = "".join(chunks)
        assert "/status" in full
        assert "/warmup" in full

    @pytest.mark.asyncio
    async def test_handle_message_sync(self):
        from app.services.chat_service import ChatService
        # Test slash commands via sync
        svc2 = ChatService()
        result = await svc2.handle_message_sync("/help", "user-1", "session-1")
        assert "/status" in result["response"]

    @pytest.mark.asyncio
    async def test_chat_logging(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        mock_db = AsyncMock()
        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        with patch("app.database.AsyncSessionLocal", return_value=mock_session_ctx):
            await svc._log_chat("user-1", "session-1", "Hello", "Hi!", "groq", ["system"], 100)
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_logging_handles_db_error(self):
        from app.services.chat_service import ChatService
        svc = ChatService()
        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(side_effect=Exception("DB error"))
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        with patch("app.database.AsyncSessionLocal", return_value=mock_session_ctx):
            # Should not raise
            await svc._log_chat("user-1", "session-1", "Hello", "Hi!", "groq", [], 100)


# ── System Prompt Tests ───────────────────────────────────────────────────────

class TestSystemPrompt:
    """Verify system prompt contents."""

    def test_system_prompt_has_key_instructions(self):
        from app.services.chat_service import SYSTEM_PROMPT
        assert "FortressFlow" in SYSTEM_PROMPT
        assert "compliance" in SYSTEM_PROMPT.lower()
        assert "never" in SYSTEM_PROMPT.lower()
        assert "Gengyve" in SYSTEM_PROMPT

    def test_slash_commands_defined(self):
        from app.services.chat_service import SLASH_COMMANDS
        assert "/status" in SLASH_COMMANDS
        assert "/help" in SLASH_COMMANDS
        assert "/warmup" in SLASH_COMMANDS
        assert len(SLASH_COMMANDS) >= 7
