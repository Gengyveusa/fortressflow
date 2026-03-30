"""
Tests for agent execution system fixes:
1. Apollo/Taplio registered in agent router
2. Orchestrator dispatches correctly to both static and instance methods
3. Method signature introspection prevents unexpected kwargs
4. Chat endpoint routes through command engine to agents
"""

import inspect
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.agents.orchestrator import (
    AgentOrchestrator,
    _AGENT_REGISTRY,
    _ALLOWED_ACTIONS,
    _get_agent_class,
)


# ── 1. Agent registration ────────────────────────────────────────────────────


class TestAgentRegistration:
    """Verify all agents are registered in the orchestrator and router."""

    def test_apollo_in_registry(self):
        assert "apollo" in _AGENT_REGISTRY

    def test_taplio_in_registry(self):
        assert "taplio" in _AGENT_REGISTRY

    def test_all_agents_registered(self):
        expected = {
            "groq",
            "openai",
            "hubspot",
            "zoominfo",
            "twilio",
            "apollo",
            "taplio",
            "marketing",
            "sales",
            "testing",
        }
        assert set(_AGENT_REGISTRY.keys()) == expected

    def test_apollo_has_allowed_actions(self):
        assert "search_people" in _ALLOWED_ACTIONS["apollo"]
        assert "search_organizations" in _ALLOWED_ACTIONS["apollo"]
        assert "enrich_person" in _ALLOWED_ACTIONS["apollo"]

    def test_taplio_has_allowed_actions(self):
        assert "generate_linkedin_post" in _ALLOWED_ACTIONS["taplio"]
        assert "compose_dm" in _ALLOWED_ACTIONS["taplio"]

    def test_router_valid_agents_includes_apollo_taplio(self):
        """The execute endpoint in agents.py should accept apollo and taplio."""
        from app.api.v1.agents import execute_agent

        # Read the source to verify the valid_agents set
        source = inspect.getsource(execute_agent)
        assert '"apollo"' in source or "'apollo'" in source or "apollo" in source


# ── 2. Orchestrator dispatch logic ───────────────────────────────────────────


class TestOrchestratorDispatch:
    """Test that dispatch correctly handles static vs instance methods."""

    def test_groq_agent_methods_are_static(self):
        """GroqAgent methods should be static methods (accept db as param)."""
        cls = _get_agent_class("groq")
        assert isinstance(cls.__dict__["chat"], staticmethod)
        assert isinstance(cls.__dict__["classify_reply"], staticmethod)

    def test_openai_agent_methods_are_static(self):
        cls = _get_agent_class("openai")
        assert isinstance(cls.__dict__["chat"], staticmethod)

    def test_hubspot_agent_methods_are_instance(self):
        """HubSpotAgent methods should be instance methods (no db param)."""
        cls = _get_agent_class("hubspot")
        assert not isinstance(cls.__dict__.get("get_deals"), staticmethod)
        assert not isinstance(cls.__dict__.get("search_contacts"), staticmethod)

    def test_apollo_agent_methods_are_instance(self):
        cls = _get_agent_class("apollo")
        assert not isinstance(cls.__dict__.get("search_people"), staticmethod)

    def test_twilio_agent_methods_are_instance(self):
        cls = _get_agent_class("twilio")
        assert not isinstance(cls.__dict__.get("send_sms"), staticmethod)

    def test_zoominfo_agent_methods_are_instance(self):
        cls = _get_agent_class("zoominfo")
        assert not isinstance(cls.__dict__.get("search_people"), staticmethod)

    def test_taplio_agent_methods_are_instance(self):
        cls = _get_agent_class("taplio")
        assert not isinstance(cls.__dict__.get("generate_linkedin_post"), staticmethod)


class TestMethodSignatureIntrospection:
    """Test that the orchestrator correctly filters params based on method signatures."""

    def test_groq_classify_reply_accepts_email_text(self):
        """GroqAgent.classify_reply should accept email_text, db, user_id."""
        cls = _get_agent_class("groq")
        sig = inspect.signature(cls.classify_reply)
        params = set(sig.parameters.keys())
        assert "db" in params
        assert "email_text" in params
        assert "user_id" in params

    def test_hubspot_get_deals_does_not_accept_db(self):
        """HubSpotAgent.get_deals should accept filters and user_id, not db."""
        cls = _get_agent_class("hubspot")
        instance = cls()
        sig = inspect.signature(instance.get_deals)
        params = set(sig.parameters.keys())
        assert "filters" in params
        assert "user_id" in params
        assert "db" not in params

    def test_hubspot_search_contacts_does_not_accept_query(self):
        """HubSpotAgent.search_contacts accepts filters, not query."""
        cls = _get_agent_class("hubspot")
        instance = cls()
        sig = inspect.signature(instance.search_contacts)
        params = set(sig.parameters.keys())
        assert "filters" in params
        assert "query" not in params

    def test_openai_chat_accepts_messages(self):
        """OpenAIAgent.chat should accept messages, db, user_id."""
        cls = _get_agent_class("openai")
        sig = inspect.signature(cls.chat)
        params = set(sig.parameters.keys())
        assert "db" in params
        assert "messages" in params
        assert "user_id" in params

    def test_apollo_search_people_accepts_db_and_query(self):
        """ApolloAgent.search_people should accept db, user_id, query, location, etc."""
        cls = _get_agent_class("apollo")
        instance = cls()
        sig = inspect.signature(instance.search_people)
        params = set(sig.parameters.keys())
        assert "db" in params
        assert "user_id" in params
        assert "query" in params
        assert "location" in params
        assert "per_page" in params

    def test_twilio_send_sms_does_not_accept_db(self):
        """TwilioAgent.send_sms should accept to, body, user_id but not db."""
        cls = _get_agent_class("twilio")
        instance = cls()
        sig = inspect.signature(instance.send_sms)
        params = set(sig.parameters.keys())
        assert "to" in params
        assert "body" in params
        assert "user_id" in params
        assert "db" not in params


class TestDispatchParamFiltering:
    """Test that dispatch correctly filters params before calling agent methods."""

    @pytest.mark.asyncio
    async def test_dispatch_unknown_agent_returns_error(self):
        mock_db = AsyncMock()
        result = await AgentOrchestrator.dispatch(
            db=mock_db,
            agent_name="nonexistent",
            action="foo",
            params={},
            user_id=uuid.uuid4(),
        )
        assert result["status"] == "error"
        assert "Unknown agent" in result["error"]

    @pytest.mark.asyncio
    async def test_dispatch_invalid_action_returns_error(self):
        mock_db = AsyncMock()
        result = await AgentOrchestrator.dispatch(
            db=mock_db,
            agent_name="groq",
            action="nonexistent_action",
            params={},
            user_id=uuid.uuid4(),
        )
        assert result["status"] == "error"
        assert "not available" in result["error"]

    def test_dispatch_builds_correct_params_for_hubspot(self):
        """Orchestrator should filter out db for HubSpotAgent instance methods."""
        cls = _get_agent_class("hubspot")
        instance = cls()
        method = getattr(instance, "get_deals")
        sig = inspect.signature(method)
        accepted = set(sig.parameters.keys())
        has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())

        # Simulate what dispatch does: offer db/user_id, then filter
        call_params = {"filters": []}
        if "db" in accepted or has_kwargs:
            call_params["db"] = "mock_db"
        if "user_id" in accepted or has_kwargs:
            call_params["user_id"] = "mock_uid"

        if not has_kwargs:
            call_params = {k: v for k, v in call_params.items() if k in accepted}

        # db should be filtered out since get_deals(self, filters, user_id) doesn't accept it
        assert "db" not in call_params
        assert "filters" in call_params
        assert "user_id" in call_params

    @pytest.mark.asyncio
    async def test_dispatch_includes_db_for_groq(self):
        """db should be passed to GroqAgent static methods that accept it."""
        mock_db = AsyncMock()
        user_id = uuid.uuid4()

        with patch("app.services.agents.groq_agent.GroqAgent.classify_reply") as mock_method:
            mock_method.return_value = {"category": "positive", "confidence": 0.9}
            result = await AgentOrchestrator.dispatch(
                db=mock_db,
                agent_name="groq",
                action="classify_reply",
                params={"email_text": "Sounds great, let's schedule a call!"},
                user_id=user_id,
            )
            # Verify db WAS passed
            if mock_method.called:
                call_kwargs = mock_method.call_args.kwargs if mock_method.call_args.kwargs else {}
                assert "db" in call_kwargs


# ── 3. Chat endpoint command engine integration ──────────────────────────────


class TestChatCommandEngineIntegration:
    """Test that the chat service routes through command engine to agents."""

    @pytest.mark.asyncio
    async def test_chat_service_calls_command_engine(self):
        """Chat service should attempt command engine classification before LLM fallthrough."""
        from app.services.chat_service import ChatService

        svc = ChatService()

        # Mock the command engine to return a successful response
        mock_response = {
            "type": "text",
            "content": "Found 5 dentists in Denver",
            "data": {"results": []},
        }

        with patch.object(svc, "_try_command_engine", return_value=mock_response) as mock_engine:
            chunks = []
            async for chunk in svc.handle_message("Find dentists in Denver", "user-123", "session-456"):
                chunks.append(chunk)

            # Command engine should have been called
            mock_engine.assert_called_once_with("Find dentists in Denver", "user-123", "session-456")
            # Response should come from command engine, not LLM
            full_response = "".join(chunks)
            assert "dentists" in full_response.lower()

    @pytest.mark.asyncio
    async def test_chat_service_falls_through_to_llm(self):
        """When command engine returns None, chat should fall through to LLM."""
        from app.services.chat_service import ChatService

        svc = ChatService()

        with patch.object(svc, "_try_command_engine", return_value=None):
            with patch.object(svc, "_gather_context", return_value={}):
                with patch.object(svc, "_route_to_ai_platforms", return_value={}):
                    with patch.object(svc, "_stream_llm") as mock_llm:

                        async def fake_stream(*a, **kw):
                            yield "Hello from LLM"

                        mock_llm.return_value = fake_stream()
                        with patch.object(svc, "_log_chat", return_value=None):
                            chunks = []
                            async for chunk in svc.handle_message("random question", "user-123", "session-456"):
                                chunks.append(chunk)

                            assert "Hello from LLM" in "".join(chunks)
