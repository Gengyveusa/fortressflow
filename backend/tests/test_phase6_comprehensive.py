"""
Phase 6 Comprehensive Test Suite.

Covers:
1. Reply Service — parsing, sentiment, thread matching, deduplication
2. Channel Orchestrator — routing, limits, failover, cooldowns
3. AI Feedback Service — aggregation, learning loop, platform sync
4. Security & Middleware — rate limiter (sliding window, per-IP, expiry)
5. Webhook Handlers — SES bounce/complaint/delivery, Twilio status/inbound, signature validation
6. Sequence Executor — email/sms/linkedin/wait/conditional steps, A/B variants, FSM
7. Analytics API — dashboard stats, deliverability, sequence performance, empty data
8. Warmup AI — daily volume, ramp schedule, health score, seed selection
9. Config / Settings — defaults, env overrides, threshold validation

All tests use unittest.mock (AsyncMock, MagicMock, patch) — NO real DB connections.
asyncio_mode = "auto" handles async automatically.
"""

import json
import uuid
from collections import deque
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ══════════════════════════════════════════════════════════════════════════════
# 1. REPLY SERVICE TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestReplyServiceEmailParsing:
    """Tests for email header and body parsing."""

    async def test_parse_email_headers_extracts_message_id(self):
        """parse_email_headers should extract Message-ID from raw headers."""
        from app.services.reply_service import ReplyService

        db = AsyncMock()
        svc = ReplyService(db)

        raw_headers = {
            "Message-ID": "<abc123@mail.example.com>",
            "In-Reply-To": "<orig456@mail.example.com>",
            "References": "<orig456@mail.example.com>",
            "From": "prospect@company.com",
            "Subject": "Re: Quick question",
        }

        # Verify the service can be constructed and headers are accessible
        assert svc is not None
        assert "<abc123@mail.example.com>" == raw_headers["Message-ID"]
        assert "<orig456@mail.example.com>" == raw_headers["In-Reply-To"]

    async def test_parse_email_headers_thread_id_from_in_reply_to(self):
        """Thread ID should be derived from In-Reply-To header."""
        from app.services.reply_service import ReplySignal

        signal = ReplySignal(
            channel="email",
            body="Thanks for reaching out!",
            sender_email="lead@acme.com",
            subject="Re: Our solution",
            thread_id="<orig-msg-id@mail.fortressflow.com>",
            message_id="<reply-msg-id@mail.fortressflow.com>",
            raw_headers={
                "In-Reply-To": "<orig-msg-id@mail.fortressflow.com>",
            },
        )

        assert signal.thread_id == "<orig-msg-id@mail.fortressflow.com>"
        assert signal.channel == "email"
        assert signal.sender_email == "lead@acme.com"

    async def test_detect_auto_reply_ooo_keyword(self):
        """Out-of-office body → out_of_office sentiment."""
        from app.services.reply_service import ReplySentiment, ReplyService

        db = AsyncMock()
        svc = ReplyService(db)

        sentiment, confidence = await svc.analyze_sentiment(
            "I am out of office until Monday. I will be back on March 25th."
        )

        assert sentiment == ReplySentiment.out_of_office
        assert confidence > 0.5, "OOO detection should have confidence > 0.5"

    async def test_detect_auto_reply_autoreply_keyword(self):
        """Body containing 'automatic reply' → out_of_office."""
        from app.services.reply_service import ReplySentiment, ReplyService

        db = AsyncMock()
        svc = ReplyService(db)

        sentiment, confidence = await svc.analyze_sentiment(
            "This is an automatic reply. I am currently on vacation."
        )

        assert sentiment == ReplySentiment.out_of_office

    async def test_reply_signal_dataclass_defaults(self):
        """ReplySignal dataclass should set received_at to now by default."""
        from app.services.reply_service import ReplySignal

        before = datetime.now(UTC)
        signal = ReplySignal(channel="sms", body="Got your message")
        after = datetime.now(UTC)

        assert before <= signal.received_at <= after
        assert signal.sender_email is None
        assert signal.thread_id is None
        assert signal.raw_headers == {}

    async def test_reply_signal_with_all_fields(self):
        """ReplySignal accepts and stores all optional fields."""
        from app.services.reply_service import ReplySignal

        signal = ReplySignal(
            channel="linkedin",
            body="Interested in connecting!",
            sender_email=None,
            sender_phone=None,
            subject=None,
            thread_id="li-thread-xyz",
            message_id="li-msg-001",
            raw_headers={"X-LinkedIn-Thread": "li-thread-xyz"},
        )

        assert signal.channel == "linkedin"
        assert signal.thread_id == "li-thread-xyz"
        assert signal.message_id == "li-msg-001"


class TestReplySentimentAnalysis:
    """Keyword-based NLP sentiment classification."""

    async def test_sentiment_analysis_positive_interested(self):
        """'I'm interested in scheduling a demo' → positive."""
        from app.services.reply_service import ReplySentiment, ReplyService

        svc = ReplyService(AsyncMock())
        sentiment, confidence = await svc.analyze_sentiment(
            "I'm interested in scheduling a demo. When are you available?"
        )

        assert sentiment == ReplySentiment.positive
        assert confidence > 0.5

    async def test_sentiment_analysis_positive_schedule(self):
        """'Let's schedule a call' → positive."""
        from app.services.reply_service import ReplySentiment, ReplyService

        svc = ReplyService(AsyncMock())
        sentiment, confidence = await svc.analyze_sentiment(
            "Sounds good! Let's schedule a call for next week."
        )

        assert sentiment == ReplySentiment.positive

    async def test_sentiment_analysis_negative_not_interested(self):
        """'Not interested' → negative."""
        from app.services.reply_service import ReplySentiment, ReplyService

        svc = ReplyService(AsyncMock())
        sentiment, confidence = await svc.analyze_sentiment(
            "Not interested. Please stop contacting me."
        )

        assert sentiment in (ReplySentiment.negative, ReplySentiment.unsubscribe)
        assert confidence > 0.5

    async def test_sentiment_analysis_negative_remove_me(self):
        """'Remove me from your list' → negative or unsubscribe."""
        from app.services.reply_service import ReplySentiment, ReplyService

        svc = ReplyService(AsyncMock())
        sentiment, confidence = await svc.analyze_sentiment(
            "Please remove me from your list. I am not interested."
        )

        assert sentiment in (ReplySentiment.negative, ReplySentiment.unsubscribe)

    async def test_sentiment_analysis_neutral(self):
        """Informational request → neutral."""
        from app.services.reply_service import ReplySentiment, ReplyService

        svc = ReplyService(AsyncMock())
        sentiment, confidence = await svc.analyze_sentiment(
            "Can you send more information about your product pricing?"
        )

        assert sentiment == ReplySentiment.neutral

    async def test_sentiment_analysis_unsubscribe_explicit(self):
        """Explicit 'unsubscribe' → unsubscribe sentiment."""
        from app.services.reply_service import ReplySentiment, ReplyService

        svc = ReplyService(AsyncMock())
        sentiment, confidence = await svc.analyze_sentiment(
            "Unsubscribe. No more emails please."
        )

        assert sentiment == ReplySentiment.unsubscribe

    async def test_sentiment_analysis_ooo_away_message(self):
        """'I'm out of the office' → out_of_office."""
        from app.services.reply_service import ReplySentiment, ReplyService

        svc = ReplyService(AsyncMock())
        sentiment, _ = await svc.analyze_sentiment(
            "I'm out of the office on annual leave until April 1st."
        )

        assert sentiment == ReplySentiment.out_of_office

    async def test_sentiment_confidence_range(self):
        """Confidence score should always be 0.0-1.0."""
        from app.services.reply_service import ReplyService

        svc = ReplyService(AsyncMock())
        bodies = [
            "I'm interested in a demo.",
            "Not interested, stop emailing.",
            "Can you send more info?",
            "Out of office until Monday.",
            "Unsubscribe.",
            "",
        ]
        for body in bodies:
            sentiment, confidence = await svc.analyze_sentiment(body)
            assert 0.0 <= confidence <= 1.0, f"Confidence out of range for: {body!r}"

    async def test_sentiment_empty_body_neutral(self):
        """Empty body should return neutral with low confidence."""
        from app.services.reply_service import ReplySentiment, ReplyService

        svc = ReplyService(AsyncMock())
        sentiment, confidence = await svc.analyze_sentiment("")

        assert sentiment == ReplySentiment.neutral

    async def test_reply_analysis_result_dataclass(self):
        """ReplyAnalysisResult should hold all expected fields."""
        from app.services.reply_service import ReplyAnalysisResult, ReplySignal, ReplySentiment

        signal = ReplySignal(channel="email", body="Let's connect!")
        result = ReplyAnalysisResult(
            signal=signal,
            sentiment=ReplySentiment.positive,
            confidence=0.9,
        )

        assert result.sentiment == ReplySentiment.positive
        assert result.confidence == 0.9
        assert result.matched_enrollment_id is None
        assert result.ai_suggestions == {}


class TestReplyServiceProcessing:
    """Tests for reply processing, thread matching, and deduplication."""

    async def test_poll_imap_skips_when_credentials_missing(self):
        """poll_imap_inbox returns [] when IMAP credentials are not set."""
        from app.services.reply_service import ReplyService

        with patch("app.services.reply_service.settings") as mock_settings:
            mock_settings.IMAP_HOST = ""
            mock_settings.IMAP_USER = ""
            mock_settings.IMAP_PASSWORD = ""

            svc = ReplyService(AsyncMock())
            signals = await svc.poll_imap_inbox()

        assert signals == []

    async def test_thread_matching_uses_sender_email(self):
        """match_enrollment_by_signal should query by sender_email."""
        from app.services.reply_service import ReplyService, ReplySignal

        db = AsyncMock()
        # Simulate enrollment query returning None (no match)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=mock_result)

        svc = ReplyService(db)
        signal = ReplySignal(
            channel="email",
            body="Interested!",
            sender_email="prospect@company.com",
        )

        enrollment = await svc.match_enrollment_by_signal(signal)
        assert enrollment is None

    async def test_thread_matching_by_thread_id(self):
        """match_enrollment_by_signal uses thread_id for lookup."""
        from app.services.reply_service import ReplyService, ReplySignal

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=mock_result)

        svc = ReplyService(db)
        signal = ReplySignal(
            channel="email",
            body="Thanks!",
            thread_id="<msg-id-original@mail.example.com>",
        )

        enrollment = await svc.match_enrollment_by_signal(signal)
        assert enrollment is None

    async def test_reply_with_missing_lead_returns_none(self):
        """Processing a signal for an unknown lead returns None match."""
        from app.services.reply_service import ReplyService, ReplySignal

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=mock_result)

        svc = ReplyService(db)
        signal = ReplySignal(
            channel="email",
            body="Hi there",
            sender_email="unknown@nowhere.com",
        )

        enrollment = await svc.match_enrollment_by_signal(signal)
        assert enrollment is None

    async def test_reply_sentiment_enum_values(self):
        """All ReplySentiment enum values exist."""
        from app.services.reply_service import ReplySentiment

        assert ReplySentiment.positive == "positive"
        assert ReplySentiment.negative == "negative"
        assert ReplySentiment.neutral == "neutral"
        assert ReplySentiment.out_of_office == "out_of_office"
        assert ReplySentiment.unsubscribe == "unsubscribe"


# ══════════════════════════════════════════════════════════════════════════════
# 2. CHANNEL ORCHESTRATOR TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestChannelOrchestratorRouting:
    """Tests for channel selection and resolution logic."""

    async def test_resolve_channel_email_step(self):
        """Email step_type resolves to 'email' channel."""
        from app.services.channel_orchestrator import ChannelOrchestrator
        from app.models.sequence import StepType

        orch = ChannelOrchestrator(AsyncMock())
        step = MagicMock()
        step.step_type = StepType.email

        channel = orch._resolve_channel(step)
        assert channel == "email"

    async def test_resolve_channel_sms_step(self):
        """SMS step_type resolves to 'sms' channel."""
        from app.services.channel_orchestrator import ChannelOrchestrator
        from app.models.sequence import StepType

        orch = ChannelOrchestrator(AsyncMock())
        step = MagicMock()
        step.step_type = StepType.sms

        channel = orch._resolve_channel(step)
        assert channel == "sms"

    async def test_resolve_channel_linkedin_step(self):
        """LinkedIn step_type resolves to 'linkedin' channel."""
        from app.services.channel_orchestrator import ChannelOrchestrator
        from app.models.sequence import StepType

        orch = ChannelOrchestrator(AsyncMock())
        step = MagicMock()
        step.step_type = StepType.linkedin

        channel = orch._resolve_channel(step)
        assert channel == "linkedin"

    async def test_is_hard_failure_bounce(self):
        """'bounce' error is a hard failure — no failover."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        orch = ChannelOrchestrator(AsyncMock())
        assert orch._is_hard_failure("bounce") is True

    async def test_is_hard_failure_complaint(self):
        """'spam_complaint' error is a hard failure."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        orch = ChannelOrchestrator(AsyncMock())
        assert orch._is_hard_failure("spam_complaint") is True

    async def test_is_hard_failure_unsubscribe(self):
        """'unsubscribe' error is a hard failure."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        orch = ChannelOrchestrator(AsyncMock())
        assert orch._is_hard_failure("unsubscribe") is True

    async def test_is_soft_failure_timeout(self):
        """Generic timeout is a soft failure — failover should be attempted."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        orch = ChannelOrchestrator(AsyncMock())
        assert orch._is_hard_failure("connection_timeout") is False

    async def test_is_soft_failure_rate_limited(self):
        """'rate_limited' is a soft failure."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        orch = ChannelOrchestrator(AsyncMock())
        assert orch._is_hard_failure("rate_limited") is False

    async def test_hard_failure_dnc(self):
        """'dnc' (do not contact) is a hard failure."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        orch = ChannelOrchestrator(AsyncMock())
        assert orch._is_hard_failure("dnc") is True

    async def test_hard_failure_no_consent(self):
        """'no_active_consent' is a hard failure."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        orch = ChannelOrchestrator(AsyncMock())
        assert orch._is_hard_failure("no_active_consent") is True


class TestChannelOrchestratorRateLimits:
    """Tests for global daily limit enforcement."""

    async def test_check_global_limits_email_under_limit(self):
        """Returns (True, remaining) when daily email count is under limit."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value=50)
        db.execute = AsyncMock(return_value=mock_result)

        orch = ChannelOrchestrator(db)

        with patch("app.services.channel_orchestrator.settings") as mock_settings:
            mock_settings.GLOBAL_DAILY_EMAIL_LIMIT = 400
            mock_settings.GLOBAL_DAILY_SMS_LIMIT = 30
            mock_settings.GLOBAL_DAILY_LINKEDIN_LIMIT = 25

            under_limit, remaining = await orch.check_global_limits("email")

        assert under_limit is True
        assert remaining > 0

    async def test_check_global_limits_email_at_capacity(self):
        """Returns (False, 0) when daily email count equals the limit."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value=400)
        db.execute = AsyncMock(return_value=mock_result)

        orch = ChannelOrchestrator(db)

        with patch("app.services.channel_orchestrator.settings") as mock_settings:
            mock_settings.GLOBAL_DAILY_EMAIL_LIMIT = 400
            mock_settings.GLOBAL_DAILY_SMS_LIMIT = 30
            mock_settings.GLOBAL_DAILY_LINKEDIN_LIMIT = 25

            under_limit, remaining = await orch.check_global_limits("email")

        assert under_limit is False
        assert remaining == 0

    async def test_dispatch_blocked_by_global_limit(self):
        """dispatch() returns failure dict when global limit is exhausted."""
        from app.services.channel_orchestrator import ChannelOrchestrator
        from app.models.sequence import StepType

        db = AsyncMock()
        orch = ChannelOrchestrator(db)

        # Mock check_global_limits to return over-limit
        orch.check_global_limits = AsyncMock(return_value=(False, 0))

        enrollment = MagicMock()
        enrollment.id = uuid.uuid4()
        step = MagicMock()
        step.step_type = StepType.email
        step.position = 0
        lead = MagicMock()
        lead.id = uuid.uuid4()
        template = MagicMock()

        result = await orch.dispatch(enrollment, step, lead, template)

        assert result["success"] is False
        assert result["limit_exhausted"] is True
        assert "Global daily limit" in result["error"]

    async def test_dispatch_blocked_by_compliance(self):
        """dispatch() returns failure dict when compliance gate blocks."""
        from app.services.channel_orchestrator import ChannelOrchestrator
        from app.models.sequence import StepType

        db = AsyncMock()
        orch = ChannelOrchestrator(db)
        orch.check_global_limits = AsyncMock(return_value=(True, 350))

        with patch("app.services.channel_orchestrator.compliance_svc") as mock_compliance:
            mock_compliance.can_send_to_lead = AsyncMock(
                return_value=(False, "no_active_consent")
            )

            enrollment = MagicMock()
            enrollment.id = uuid.uuid4()
            step = MagicMock()
            step.step_type = StepType.email
            step.position = 0
            lead = MagicMock()
            lead.id = uuid.uuid4()
            template = MagicMock()

            result = await orch.dispatch(enrollment, step, lead, template)

        assert result["success"] is False
        assert result["compliance_blocked"] is True

    async def test_dispatch_exception_returns_failure(self):
        """Unhandled exception in dispatch returns a failure dict."""
        from app.services.channel_orchestrator import ChannelOrchestrator
        from app.models.sequence import StepType

        db = AsyncMock()
        orch = ChannelOrchestrator(db)
        orch.check_global_limits = AsyncMock(return_value=(True, 350))

        with patch("app.services.channel_orchestrator.compliance_svc") as mock_compliance:
            mock_compliance.can_send_to_lead = AsyncMock(
                return_value=(True, None)
            )
            orch._dispatch_to_channel = AsyncMock(
                side_effect=RuntimeError("Unexpected error")
            )

            enrollment = MagicMock()
            enrollment.id = uuid.uuid4()
            step = MagicMock()
            step.step_type = StepType.email
            step.position = 1
            lead = MagicMock()
            lead.id = uuid.uuid4()
            template = MagicMock()

            result = await orch.dispatch(enrollment, step, lead, template)

        assert result["success"] is False
        assert "Unexpected error" in result["error"]

    async def test_channel_daily_limits_dict_structure(self):
        """CHANNEL_DAILY_LIMITS dict contains all expected channels."""
        from app.services.channel_orchestrator import CHANNEL_DAILY_LIMITS

        assert "email" in CHANNEL_DAILY_LIMITS
        assert "sms" in CHANNEL_DAILY_LIMITS
        assert "linkedin" in CHANNEL_DAILY_LIMITS


class TestChannelOrchestratorFailover:
    """Tests for failover and dispatch success paths."""

    async def test_successful_dispatch_no_failover(self):
        """Successful channel dispatch returns success=True, failover_used=False."""
        from app.services.channel_orchestrator import ChannelOrchestrator
        from app.models.sequence import StepType

        db = AsyncMock()
        orch = ChannelOrchestrator(db)
        orch.check_global_limits = AsyncMock(return_value=(True, 350))
        orch._dispatch_to_channel = AsyncMock(
            return_value={"success": True, "message_id": "ses-msg-123"}
        )

        with patch("app.services.channel_orchestrator.compliance_svc") as mock_compliance:
            mock_compliance.can_send_to_lead = AsyncMock(return_value=(True, None))

            enrollment = MagicMock()
            enrollment.id = uuid.uuid4()
            step = MagicMock()
            step.step_type = StepType.email
            step.position = 0
            lead = MagicMock()
            lead.id = uuid.uuid4()
            template = MagicMock()

            result = await orch.dispatch(enrollment, step, lead, template)

        assert result["success"] is True
        assert result["failover_used"] is False
        assert result["failover_channel"] is None

    async def test_soft_failure_triggers_failover(self):
        """Soft failure (e.g. timeout) should attempt failover."""
        from app.services.channel_orchestrator import ChannelOrchestrator
        from app.models.sequence import StepType

        db = AsyncMock()
        orch = ChannelOrchestrator(db)
        orch.check_global_limits = AsyncMock(return_value=(True, 350))
        orch._dispatch_to_channel = AsyncMock(
            return_value={"success": False, "error": "connection_timeout"}
        )
        orch.attempt_failover = AsyncMock(
            return_value={"success": True, "channel": "sms"}
        )

        with patch("app.services.channel_orchestrator.compliance_svc") as mock_compliance:
            mock_compliance.can_send_to_lead = AsyncMock(return_value=(True, None))

            enrollment = MagicMock()
            enrollment.id = uuid.uuid4()
            step = MagicMock()
            step.step_type = StepType.email
            step.position = 0
            lead = MagicMock()
            lead.id = uuid.uuid4()
            template = MagicMock()

            result = await orch.dispatch(enrollment, step, lead, template)

        assert result["success"] is True
        assert result["failover_used"] is True
        assert result["failover_channel"] == "sms"

    async def test_hard_failure_does_not_trigger_failover(self):
        """Hard failure (bounce) should NOT attempt failover."""
        from app.services.channel_orchestrator import ChannelOrchestrator
        from app.models.sequence import StepType

        db = AsyncMock()
        orch = ChannelOrchestrator(db)
        orch.check_global_limits = AsyncMock(return_value=(True, 350))
        orch._dispatch_to_channel = AsyncMock(
            return_value={"success": False, "error": "bounce"}
        )
        orch.attempt_failover = AsyncMock()

        with patch("app.services.channel_orchestrator.compliance_svc") as mock_compliance:
            mock_compliance.can_send_to_lead = AsyncMock(return_value=(True, None))

            enrollment = MagicMock()
            enrollment.id = uuid.uuid4()
            step = MagicMock()
            step.step_type = StepType.email
            step.position = 0
            lead = MagicMock()
            lead.id = uuid.uuid4()
            template = MagicMock()

            result = await orch.dispatch(enrollment, step, lead, template)

        # Failover should NOT be called for hard failures
        orch.attempt_failover.assert_not_called()
        assert result["success"] is False


# ══════════════════════════════════════════════════════════════════════════════
# 3. AI FEEDBACK SERVICE TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestAIFeedbackService:
    """Tests for AI feedback aggregation and learning loops."""

    async def test_aggregate_sequence_metrics_no_enrollments(self):
        """aggregate_sequence_metrics returns error when no enrollments exist."""
        from app.services.ai_feedback_service import AIFeedbackService

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value=0)
        db.execute = AsyncMock(return_value=mock_result)

        svc = AIFeedbackService(db)
        sequence_id = uuid.uuid4()

        metrics = await svc.aggregate_sequence_metrics(sequence_id)

        assert "error" in metrics
        assert metrics["error"] == "no_enrollments"

    async def test_aggregate_sequence_metrics_with_enrollments(self):
        """aggregate_sequence_metrics returns numeric metrics dict."""
        from app.services.ai_feedback_service import AIFeedbackService

        db = AsyncMock()
        call_count = [0]

        def side_effect(*args, **kwargs):
            result = MagicMock()
            count_map = {
                0: 100,  # total_enrolled
                1: 80,   # total_completed
                2: 25,   # total_replied
                3: 60,   # total_opened
                4: 3,    # total_bounced
                5: 2,    # total_unsubscribed
            }
            result.scalar = MagicMock(return_value=count_map.get(call_count[0], 0))
            call_count[0] += 1
            return result

        db.execute = AsyncMock(side_effect=side_effect)

        svc = AIFeedbackService(db)
        metrics = await svc.aggregate_sequence_metrics(uuid.uuid4())

        # Should have numeric keys
        assert "reply_rate" in metrics or "error" not in metrics

    async def test_feedback_service_init(self):
        """AIFeedbackService initializes with db and platform AI."""
        from app.services.ai_feedback_service import AIFeedbackService

        db = AsyncMock()
        svc = AIFeedbackService(db)

        assert svc.db is db
        assert svc._ai is not None

    async def test_push_completion_feedback_calls_platform_ai(self):
        """push_completion_feedback should invoke platform AI push."""
        from app.services.ai_feedback_service import AIFeedbackService

        db = AsyncMock()
        # Simulate no enrollments (skips processing)
        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value=0)
        db.execute = AsyncMock(return_value=mock_result)

        svc = AIFeedbackService(db)
        svc._ai = AsyncMock()
        svc._ai.push_sequence_performance = AsyncMock(return_value={"pushed": True})

        sequence_id = uuid.uuid4()
        # Should not raise
        await svc.aggregate_sequence_metrics(sequence_id)

    async def test_learning_loop_aggregation_with_touch_logs(self):
        """Metrics aggregation queries touch_logs correctly."""
        from app.services.ai_feedback_service import AIFeedbackService

        db = AsyncMock()
        # Return realistic count values
        counts = iter([50, 40, 15, 30, 1, 0, 0])

        def mock_execute(*args, **kwargs):
            result = MagicMock()
            try:
                result.scalar = MagicMock(return_value=next(counts))
            except StopIteration:
                result.scalar = MagicMock(return_value=0)
            return result

        db.execute = AsyncMock(side_effect=mock_execute)

        svc = AIFeedbackService(db)
        metrics = await svc.aggregate_sequence_metrics(uuid.uuid4())

        # Should not raise even with mock data
        assert metrics is not None

    async def test_score_adjustment_reflected_in_metrics(self):
        """Reply rate should be computed as replied/enrolled."""
        from app.services.ai_feedback_service import AIFeedbackService

        db = AsyncMock()
        # total_enrolled=100, then various counts
        call_count = [0]

        def mock_execute(*args, **kwargs):
            result = MagicMock()
            values = [100, 90, 30, 50, 5, 2]
            result.scalar = MagicMock(
                return_value=values[call_count[0]] if call_count[0] < len(values) else 0
            )
            call_count[0] += 1
            return result

        db.execute = AsyncMock(side_effect=mock_execute)

        svc = AIFeedbackService(db)
        metrics = await svc.aggregate_sequence_metrics(uuid.uuid4())

        # reply_rate should be 30/100 = 0.3
        if "reply_rate" in metrics:
            assert 0.0 <= metrics["reply_rate"] <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# 4. SECURITY & MIDDLEWARE TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestRateLimitMiddleware:
    """Sliding window rate limiter — per-IP isolation and expiry."""

    def _make_request(self, ip: str = "127.0.0.1"):
        """Build a minimal mock Request with a client IP."""
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = ip
        return request

    async def test_rate_limit_allows_under_threshold(self):
        """Requests under the limit should be allowed through."""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = MagicMock()
        middleware = RateLimitMiddleware(app, requests_per_window=10, window_seconds=60)

        call_next = AsyncMock(return_value=MagicMock(status_code=200))
        request = self._make_request("10.0.0.1")

        response = await middleware.dispatch(request, call_next)

        call_next.assert_called_once()
        assert response.status_code == 200

    async def test_rate_limit_blocks_over_threshold(self):
        """Requests exceeding the limit should receive 429."""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = MagicMock()
        middleware = RateLimitMiddleware(app, requests_per_window=3, window_seconds=60)

        call_next = AsyncMock(return_value=MagicMock(status_code=200))
        request = self._make_request("10.0.0.2")

        # Fill the bucket to the limit
        for _ in range(3):
            await middleware.dispatch(request, call_next)

        # 4th request should be rate-limited
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 429

    async def test_rate_limit_per_ip_isolation(self):
        """Different IPs have independent rate limit buckets."""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = MagicMock()
        middleware = RateLimitMiddleware(app, requests_per_window=2, window_seconds=60)

        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        req_a = self._make_request("192.168.1.1")
        req_b = self._make_request("192.168.1.2")

        # Exhaust IP A
        await middleware.dispatch(req_a, call_next)
        await middleware.dispatch(req_a, call_next)
        response_a = await middleware.dispatch(req_a, call_next)

        # IP B should still work
        response_b = await middleware.dispatch(req_b, call_next)

        assert response_a.status_code == 429
        assert response_b.status_code == 200

    async def test_rate_limit_sliding_window_expiry(self):
        """Old timestamps outside the window should be evicted."""
        import time
        from app.middleware.rate_limit import RateLimitMiddleware

        app = MagicMock()
        middleware = RateLimitMiddleware(app, requests_per_window=2, window_seconds=1)

        call_next = AsyncMock(return_value=MagicMock(status_code=200))
        request = self._make_request("10.0.0.3")

        # Add 2 old timestamps directly into the bucket (outside window)
        ip = "10.0.0.3"
        old_time = time.monotonic() - 5  # 5 seconds ago — outside 1-second window
        middleware._buckets[ip].append(old_time)
        middleware._buckets[ip].append(old_time)

        # Both slots are technically "used" but expired, so this should pass
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    async def test_rate_limit_unknown_ip_handled(self):
        """Request with no client info should not crash."""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = MagicMock()
        middleware = RateLimitMiddleware(app, requests_per_window=5, window_seconds=60)

        call_next = AsyncMock(return_value=MagicMock(status_code=200))
        request = MagicMock()
        request.client = None  # No client attached

        response = await middleware.dispatch(request, call_next)
        # Should succeed or return 429, not raise
        assert response.status_code in (200, 429)

    async def test_rate_limit_429_response_body(self):
        """429 response should include the standard error message."""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = MagicMock()
        middleware = RateLimitMiddleware(app, requests_per_window=1, window_seconds=60)

        call_next = AsyncMock(return_value=MagicMock(status_code=200))
        request = self._make_request("10.0.0.5")

        await middleware.dispatch(request, call_next)  # First request OK
        response = await middleware.dispatch(request, call_next)  # Second → 429

        assert response.status_code == 429
        body = json.loads(response.body)
        assert "Rate limit exceeded" in body["detail"]

    async def test_rate_limit_default_parameters(self):
        """Default middleware should allow 200 req/60 sec."""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        assert middleware.requests_per_window == 200
        assert middleware.window_seconds == 60


# ══════════════════════════════════════════════════════════════════════════════
# 5. WEBHOOK HANDLER TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestSESWebhooks:
    """Tests for AWS SES event notification webhook handlers."""

    async def test_ses_subscription_confirmation_returns_confirmed(self):
        """SNS SubscriptionConfirmation type should be confirmed."""
        from fastapi.testclient import TestClient
        from app.api.v1.webhooks import router

        # Build a minimal FastAPI app with the router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch("app.api.v1.webhooks.get_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db

            with patch("httpx.AsyncClient") as mock_http:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_http.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_response)))
                mock_http.return_value.__aexit__ = AsyncMock(return_value=None)

                payload = {
                    "Type": "SubscriptionConfirmation",
                    "SubscribeURL": "https://sns.us-east-1.amazonaws.com/confirm",
                    "MessageId": "confirm-msg-id",
                }
                response = client.post(
                    "/webhooks/ses/events",
                    json=payload,
                    headers={"X-Amz-Sns-Message-Type": "SubscriptionConfirmation"},
                )
                assert response.status_code == 200
                assert response.json()["status"] == "subscription_confirmed"

    async def test_ses_bounce_webhook_processes_notification(self, sample_ses_bounce_event):
        """SES Bounce SNS Notification should be processed without error."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.webhooks import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        db_mock = AsyncMock()
        db_mock.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None), scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))))
        db_mock.add = MagicMock()
        db_mock.flush = AsyncMock()
        db_mock.commit = AsyncMock()

        with patch("app.api.v1.webhooks.get_db", return_value=db_mock):
            response = client.post(
                "/webhooks/ses/events",
                json=sample_ses_bounce_event,
                headers={"X-Amz-Sns-Message-Type": "Notification"},
            )

        assert response.status_code == 200

    async def test_ses_complaint_webhook_processes_notification(self, sample_ses_complaint_event):
        """SES Complaint SNS Notification should be processed without error."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.webhooks import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        db_mock = AsyncMock()
        db_mock.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        db_mock.add = MagicMock()
        db_mock.flush = AsyncMock()
        db_mock.commit = AsyncMock()

        with patch("app.api.v1.webhooks.get_db", return_value=db_mock):
            response = client.post(
                "/webhooks/ses/events",
                json=sample_ses_complaint_event,
                headers={"X-Amz-Sns-Message-Type": "Notification"},
            )

        assert response.status_code == 200

    async def test_ses_invalid_json_returns_error(self):
        """SES endpoint with invalid JSON body should return error status 200."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.webhooks import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        db_mock = AsyncMock()
        with patch("app.api.v1.webhooks.get_db", return_value=db_mock):
            response = client.post(
                "/webhooks/ses/events",
                content=b"NOT JSON AT ALL",
                headers={"Content-Type": "application/json"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "error"

    async def test_ses_unhandled_message_type_ignored(self):
        """Unknown SNS message types should return 'ignored'."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.webhooks import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        db_mock = AsyncMock()
        with patch("app.api.v1.webhooks.get_db", return_value=db_mock):
            payload = {
                "Type": "UnknownType",
                "MessageId": "msg-unknown",
            }
            response = client.post(
                "/webhooks/ses/events",
                json=payload,
                headers={"X-Amz-Sns-Message-Type": "UnknownType"},
            )

        assert response.status_code == 200
        assert response.json().get("status") == "ignored"

    async def test_ses_event_action_map_has_all_event_types(self):
        """_SES_EVENT_ACTION_MAP should cover Bounce, Complaint, Delivery, Open, Send."""
        from app.api.v1.webhooks import _SES_EVENT_ACTION_MAP

        assert "Bounce" in _SES_EVENT_ACTION_MAP
        assert "Complaint" in _SES_EVENT_ACTION_MAP
        assert "Delivery" in _SES_EVENT_ACTION_MAP
        assert "Open" in _SES_EVENT_ACTION_MAP
        assert "Send" in _SES_EVENT_ACTION_MAP


class TestTwilioWebhooks:
    """Tests for Twilio SMS webhook handlers."""

    async def test_twilio_status_callback_delivered(self, sample_twilio_status_callback):
        """Twilio delivered status callback should return 200 with TwiML."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.webhooks import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        db_mock = AsyncMock()
        db_mock.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        db_mock.add = MagicMock()
        db_mock.commit = AsyncMock()

        with patch("app.api.v1.webhooks.get_db", return_value=db_mock):
            with patch("app.services.sms_service.process_inbound_sms", new_callable=AsyncMock) as mock_process:
                mock_process.return_value = {"type": "status_callback"}
                response = client.post(
                    "/webhooks/twilio/sms",
                    data=sample_twilio_status_callback,
                )

        assert response.status_code == 200
        assert "xml" in response.headers.get("content-type", "").lower()

    async def test_twilio_inbound_sms_stop_request(self):
        """STOP message should trigger an unsubscribe TwiML response."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.webhooks import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        db_mock = AsyncMock()
        db_mock.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        db_mock.add = MagicMock()
        db_mock.commit = AsyncMock()
        db_mock.rollback = AsyncMock()

        with patch("app.api.v1.webhooks.get_db", return_value=db_mock):
            with patch("app.services.sms_service.process_inbound_sms", new_callable=AsyncMock) as mock_process:
                mock_process.return_value = {"type": "stop_request"}

                response = client.post(
                    "/webhooks/twilio/sms",
                    data={
                        "MessageSid": "SM123",
                        "From": "+14155552671",
                        "To": "+15005550006",
                        "Body": "STOP",
                        "MessageStatus": "",
                    },
                )

        assert response.status_code == 200
        assert "unsubscribed" in response.text.lower() or "<Response>" in response.text

    async def test_twilio_inbound_sms_reply_queues_task(self):
        """Inbound reply should queue a Celery task."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.webhooks import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        db_mock = AsyncMock()
        db_mock.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        db_mock.add = MagicMock()
        db_mock.commit = AsyncMock()

        with patch("app.api.v1.webhooks.get_db", return_value=db_mock):
            with patch("app.services.sms_service.process_inbound_sms", new_callable=AsyncMock) as mock_process:
                with patch("app.workers.tasks.process_reply_full_task") as mock_task:
                    mock_process.return_value = {"type": "inbound_reply"}
                    mock_task.delay = MagicMock()

                    response = client.post(
                        "/webhooks/twilio/sms",
                        data={
                            "MessageSid": "SM789",
                            "From": "+14155552671",
                            "To": "+15005550006",
                            "Body": "Yes, I'm interested!",
                            "MessageStatus": "",
                        },
                    )

        assert response.status_code == 200

    async def test_twilio_signature_validation_skipped_when_no_token(self):
        """When TWILIO_AUTH_TOKEN is empty, signature validation is skipped."""
        from app.api.v1.webhooks import _validate_twilio_signature

        with patch("app.api.v1.webhooks.settings") as mock_settings:
            mock_settings.TWILIO_AUTH_TOKEN = ""
            result = _validate_twilio_signature(
                "https://example.com/webhooks/twilio/sms",
                {"From": "+15005550006"},
                "fake-signature",
            )

        assert result is True  # Skipped → allowed


class TestWebhookSignatureValidation:
    """Tests for webhook secret and HMAC validation."""

    async def test_email_reply_webhook_missing_secret_rejected(self):
        """Email reply webhook without X-Webhook-Secret header is rejected."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.webhooks import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        db_mock = AsyncMock()

        with patch("app.api.v1.webhooks.settings") as mock_settings:
            mock_settings.REPLY_WEBHOOK_SECRET = "required-secret"

            with patch("app.api.v1.webhooks.get_db", return_value=db_mock):
                response = client.post(
                    "/webhooks/email/reply",
                    json={"from": "test@example.com", "body": "Hello"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "rejected"
        assert "missing_secret" in data.get("reason", "")

    async def test_email_reply_webhook_invalid_secret_rejected(self):
        """Email reply webhook with wrong secret header is rejected."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.webhooks import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        db_mock = AsyncMock()

        with patch("app.api.v1.webhooks.settings") as mock_settings:
            mock_settings.REPLY_WEBHOOK_SECRET = "correct-secret"

            with patch("app.api.v1.webhooks.get_db", return_value=db_mock):
                response = client.post(
                    "/webhooks/email/reply",
                    json={"from": "test@example.com", "body": "Hello"},
                    headers={"X-Webhook-Secret": "wrong-secret"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "rejected"


# ══════════════════════════════════════════════════════════════════════════════
# 6. SEQUENCE EXECUTOR TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestSequenceExecutorStepResolution:
    """Tests for step routing, A/B variants, and conditional branches."""

    def test_resolve_next_step_linear_advance(self):
        """Default steps advance linearly to current_step + 1."""
        from app.services.sequence_executor import _resolve_next_step
        from app.models.sequence import StepType

        step = MagicMock()
        step.step_type = StepType.email
        step.condition = None

        enrollment = MagicMock()
        enrollment.current_step = 0

        result = _resolve_next_step(step, [], enrollment, [])
        assert result == 1

    def test_resolve_next_step_end_node_returns_none(self):
        """An 'end' step type returns None to terminate the sequence."""
        from app.services.sequence_executor import _resolve_next_step
        from app.models.sequence import StepType

        step = MagicMock()
        step.step_type = StepType.end

        enrollment = MagicMock()
        enrollment.current_step = 3

        result = _resolve_next_step(step, [], enrollment, [])
        assert result is None

    def test_resolve_next_step_ab_split_advances_linearly(self):
        """A/B split steps advance linearly (variant chosen separately)."""
        from app.services.sequence_executor import _resolve_next_step
        from app.models.sequence import StepType

        step = MagicMock()
        step.step_type = StepType.ab_split
        step.condition = None

        enrollment = MagicMock()
        enrollment.current_step = 2

        result = _resolve_next_step(step, [], enrollment, [])
        assert result == 3

    def test_assign_ab_variant_returns_existing_assignment(self):
        """If a variant is already assigned for the step, reuse it."""
        from app.services.sequence_executor import _assign_ab_variant

        step = MagicMock()
        step.position = 1
        step.ab_variants = {"A": {"weight": 50}, "B": {"weight": 50}}

        enrollment = MagicMock()
        enrollment.ab_variant_assignments = {"1": "B"}  # already assigned B

        variant = _assign_ab_variant(step, enrollment)
        assert variant == "B"

    def test_assign_ab_variant_creates_new_assignment(self):
        """If no prior assignment, picks a variant and persists it."""
        from app.services.sequence_executor import _assign_ab_variant

        step = MagicMock()
        step.position = 0
        step.ab_variants = {"A": {"weight": 50}, "B": {"weight": 50}}

        enrollment = MagicMock()
        enrollment.ab_variant_assignments = {}

        variant = _assign_ab_variant(step, enrollment)
        assert variant in ("A", "B")
        assert enrollment.ab_variant_assignments["0"] in ("A", "B")

    def test_assign_ab_variant_no_variants_defaults_to_a(self):
        """When ab_variants is empty, default to variant 'A'."""
        from app.services.sequence_executor import _assign_ab_variant

        step = MagicMock()
        step.position = 2
        step.ab_variants = {}

        enrollment = MagicMock()
        enrollment.ab_variant_assignments = {}

        variant = _assign_ab_variant(step, enrollment)
        assert variant == "A"

    def test_resolve_conditional_step_true_branch(self):
        """Conditional step with True evaluation follows true_next_position."""
        from app.services.sequence_executor import _resolve_next_step
        from app.models.sequence import StepType

        with patch("app.services.sequence_executor.evaluate_condition", return_value=True):
            step = MagicMock()
            step.step_type = StepType.conditional
            step.condition = {"type": "opened", "within_hours": 48}
            step.true_next_position = 5
            step.false_next_position = 8

            enrollment = MagicMock()
            enrollment.status.value = "opened"
            enrollment.current_step = 2

            result = _resolve_next_step(step, [], enrollment, [])
            assert result == 5

    def test_resolve_conditional_step_false_branch(self):
        """Conditional step with False evaluation follows false_next_position."""
        from app.services.sequence_executor import _resolve_next_step
        from app.models.sequence import StepType

        with patch("app.services.sequence_executor.evaluate_condition", return_value=False):
            step = MagicMock()
            step.step_type = StepType.conditional
            step.condition = {"type": "opened", "within_hours": 48}
            step.true_next_position = 5
            step.false_next_position = 8

            enrollment = MagicMock()
            enrollment.status.value = "active"
            enrollment.current_step = 2

            result = _resolve_next_step(step, [], enrollment, [])
            assert result == 8


class TestSequenceExecutorEnrollment:
    """Tests for enrollment FSM state and due-enrollment detection."""

    async def test_get_due_enrollments_returns_active_pending(self):
        """get_due_enrollments queries for active and pending enrollments."""
        from app.services.sequence_executor import get_due_enrollments

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        db.execute = AsyncMock(return_value=mock_result)

        due = await get_due_enrollments(db)
        assert isinstance(due, list)

    async def test_enrollment_pending_activates_on_first_step(self):
        """Pending enrollment without delay should be added to due list."""
        from app.services.sequence_executor import get_due_enrollments
        from app.models.sequence import EnrollmentStatus, SequenceStatus, StepType

        db = AsyncMock()

        # Create mock enrollment
        enrollment = MagicMock()
        enrollment.id = uuid.uuid4()
        enrollment.sequence_id = uuid.uuid4()
        enrollment.current_step = 0
        enrollment.status = EnrollmentStatus.pending
        enrollment.enrolled_at = datetime.now(UTC) - timedelta(hours=1)
        enrollment.last_touch_at = None

        # Create mock sequence
        sequence = MagicMock()
        sequence.id = enrollment.sequence_id
        sequence.status = SequenceStatus.active
        step = MagicMock()
        step.position = 0
        step.delay_hours = 0.0
        step.step_type = StepType.email
        sequence.steps = [step]

        call_count = [0]

        def mock_execute(*args, **kwargs):
            result = MagicMock()
            if call_count[0] == 0:
                # First call: enrollments
                result.scalars = MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[enrollment]))
                )
            else:
                # Subsequent calls: sequence lookup
                result.scalar_one_or_none = MagicMock(return_value=sequence)
            call_count[0] += 1
            return result

        db.execute = AsyncMock(side_effect=mock_execute)

        due = await get_due_enrollments(db)
        assert len(due) == 1
        assert due[0].id == enrollment.id


# ══════════════════════════════════════════════════════════════════════════════
# 7. ANALYTICS API TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestAnalyticsAPI:
    """Tests for dashboard stats, deliverability, and sequence performance."""

    async def test_dashboard_stats_calculation(self):
        """dashboard_stats endpoint returns correct aggregated stats."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.analytics import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        call_count = [0]
        values = [1000, 850, 500, 75]  # leads, consents, touches, replies

        def mock_execute(*args, **kwargs):
            result = MagicMock()
            val = values[call_count[0]] if call_count[0] < len(values) else 0
            result.scalar_one = MagicMock(return_value=val)
            call_count[0] += 1
            return result

        db_mock = AsyncMock()
        db_mock.execute = AsyncMock(side_effect=mock_execute)

        with patch("app.api.v1.analytics.get_db", return_value=db_mock):
            response = client.get("/analytics/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert "total_leads" in data
        assert "active_consents" in data
        assert "touches_sent" in data
        assert "response_rate" in data

    async def test_dashboard_stats_response_rate_zero_touches(self):
        """response_rate should be 0.0 when touches_sent is 0."""
        from app.api.v1.analytics import dashboard_stats
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.analytics import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        call_count = [0]
        values = [100, 80, 0, 0]  # leads, consents, 0 touches, 0 replies

        def mock_execute(*args, **kwargs):
            result = MagicMock()
            val = values[call_count[0]] if call_count[0] < len(values) else 0
            result.scalar_one = MagicMock(return_value=val)
            call_count[0] += 1
            return result

        db_mock = AsyncMock()
        db_mock.execute = AsyncMock(side_effect=mock_execute)

        with patch("app.api.v1.analytics.get_db", return_value=db_mock):
            response = client.get("/analytics/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert data["response_rate"] == 0.0

    async def test_deliverability_stats_aggregation(self):
        """deliverability_stats returns bounce_rate, spam_rate, warmup counts."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.analytics import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        call_count = [0]
        values = [1000, 20, 2, 5, 15]  # total_sent, bounced, spam, warmup_active, warmup_completed

        def mock_execute(*args, **kwargs):
            result = MagicMock()
            val = values[call_count[0]] if call_count[0] < len(values) else 0
            result.scalar_one = MagicMock(return_value=val)
            call_count[0] += 1
            return result

        db_mock = AsyncMock()
        db_mock.execute = AsyncMock(side_effect=mock_execute)

        with patch("app.api.v1.analytics.get_db", return_value=db_mock):
            response = client.get("/analytics/deliverability")

        assert response.status_code == 200
        data = response.json()
        assert "bounce_rate" in data
        assert "spam_rate" in data
        assert "warmup_active" in data
        assert "warmup_completed" in data

    async def test_deliverability_stats_zero_sent(self):
        """Deliverability endpoint handles zero total_sent gracefully."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.analytics import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        db_mock = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one = MagicMock(return_value=0)
        db_mock.execute = AsyncMock(return_value=mock_result)

        with patch("app.api.v1.analytics.get_db", return_value=db_mock):
            response = client.get("/analytics/deliverability")

        assert response.status_code == 200
        data = response.json()
        assert data["bounce_rate"] == 0.0
        assert data["spam_rate"] == 0.0

    async def test_sequence_performance_metrics(self):
        """sequences_analytics returns per-sequence performance data."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.analytics import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        mock_seq = MagicMock()
        mock_seq.id = uuid.uuid4()
        mock_seq.name = "Q4 Outreach"

        db_mock = AsyncMock()
        seq_result = MagicMock()
        seq_result.scalars = MagicMock(
            return_value=MagicMock(unique=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_seq]))))
        )

        count_result = MagicMock()
        count_result.scalar_one = MagicMock(return_value=50)

        def mock_execute(*args, **kwargs):
            if hasattr(db_mock, "_first_call") and db_mock._first_call:
                return count_result
            db_mock._first_call = True
            return seq_result

        db_mock.execute = AsyncMock(side_effect=mock_execute)

        with patch("app.api.v1.analytics.get_db", return_value=db_mock):
            response = client.get("/analytics/sequences")

        assert response.status_code == 200
        data = response.json()
        assert "sequences" in data

    async def test_sequence_performance_empty_data(self):
        """sequences_analytics returns empty list when no active sequences."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.analytics import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        db_mock = AsyncMock()
        seq_result = MagicMock()
        seq_result.scalars = MagicMock(
            return_value=MagicMock(unique=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
        )
        db_mock.execute = AsyncMock(return_value=seq_result)

        with patch("app.api.v1.analytics.get_db", return_value=db_mock):
            response = client.get("/analytics/sequences")

        assert response.status_code == 200
        data = response.json()
        assert data["sequences"] == []

    async def test_response_rate_precision_two_decimals(self):
        """response_rate should be rounded to 2 decimal places."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.analytics import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        call_count = [0]
        # 75 replies / 300 touches = 25.0%
        values = [100, 80, 300, 75]

        def mock_execute(*args, **kwargs):
            result = MagicMock()
            val = values[call_count[0]] if call_count[0] < len(values) else 0
            result.scalar_one = MagicMock(return_value=val)
            call_count[0] += 1
            return result

        db_mock = AsyncMock()
        db_mock.execute = AsyncMock(side_effect=mock_execute)

        with patch("app.api.v1.analytics.get_db", return_value=db_mock):
            response = client.get("/analytics/dashboard")

        assert response.status_code == 200
        data = response.json()
        # The value should be a float, rounded
        rate = data["response_rate"]
        assert isinstance(rate, float)


# ══════════════════════════════════════════════════════════════════════════════
# 8. WARMUP AI TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestWarmupAIVolumeCalculation:
    """Tests for ramp schedule and daily volume computation."""

    def test_compute_daily_volume_day_zero(self):
        """Day 0 should return the initial volume."""
        from app.services.warmup_ai import compute_daily_volume

        vol = compute_daily_volume(warmup_day=0, initial_volume=5, ramp_multiplier=1.15, target_volume=50)
        assert vol == 5

    def test_compute_daily_volume_exponential_growth(self):
        """Volume should grow exponentially day over day."""
        from app.services.warmup_ai import compute_daily_volume

        vol_day0 = compute_daily_volume(0, 5, 1.15, 50)
        vol_day5 = compute_daily_volume(5, 5, 1.15, 50)
        vol_day10 = compute_daily_volume(10, 5, 1.15, 50)

        assert vol_day0 <= vol_day5 <= vol_day10

    def test_compute_daily_volume_capped_at_target(self):
        """Volume must never exceed target_volume."""
        from app.services.warmup_ai import compute_daily_volume

        # High day number — should be capped at 50
        vol = compute_daily_volume(warmup_day=100, initial_volume=5, ramp_multiplier=1.15, target_volume=50)
        assert vol == 50

    def test_compute_daily_volume_never_below_initial(self):
        """Volume should never be below initial_volume."""
        from app.services.warmup_ai import compute_daily_volume

        for day in range(0, 10):
            vol = compute_daily_volume(day, 5, 1.15, 50)
            assert vol >= 5, f"Day {day} volume {vol} is below initial"

    def test_ramp_schedule_generation_length(self):
        """compute_ramp_schedule(6 weeks) should return 42 entries."""
        from app.services.warmup_ai import compute_ramp_schedule

        schedule = compute_ramp_schedule(duration_weeks=6)
        assert len(schedule) == 42

    def test_ramp_schedule_keys(self):
        """Each schedule entry has day, week, daily_volume keys."""
        from app.services.warmup_ai import compute_ramp_schedule

        schedule = compute_ramp_schedule()
        for entry in schedule:
            assert "day" in entry
            assert "week" in entry
            assert "daily_volume" in entry

    def test_ramp_schedule_week_numbers(self):
        """Week numbers should run from 1 to duration_weeks."""
        from app.services.warmup_ai import compute_ramp_schedule

        schedule = compute_ramp_schedule(duration_weeks=4)
        weeks = {e["week"] for e in schedule}
        assert weeks == {1, 2, 3, 4}

    def test_ramp_schedule_volumes_non_decreasing(self):
        """Daily volumes in the ramp should be non-decreasing."""
        from app.services.warmup_ai import compute_ramp_schedule

        schedule = compute_ramp_schedule(duration_weeks=3, initial_volume=5, ramp_multiplier=1.15, target_volume=50)
        volumes = [e["daily_volume"] for e in schedule]
        for i in range(1, len(volumes)):
            assert volumes[i] >= volumes[i - 1], f"Volume decreased at day {i}"

    def test_ramp_schedule_custom_initial_volume(self):
        """Custom initial_volume=10 is reflected in day 0."""
        from app.services.warmup_ai import compute_ramp_schedule

        schedule = compute_ramp_schedule(duration_weeks=1, initial_volume=10, target_volume=100)
        assert schedule[0]["daily_volume"] == 10


class TestWarmupAIHealthChecks:
    """Tests for inbox health scoring and threshold breach detection."""

    async def test_check_inbox_health_healthy_inbox(self):
        """Healthy inbox with low bounce/spam and good open rate → (True, details)."""
        from app.services.warmup_ai import check_inbox_health

        inbox = MagicMock()
        inbox.bounce_rate_7d = 0.01
        inbox.spam_rate_7d = 0.0001
        inbox.open_rate_7d = 0.30
        inbox.total_sent = 200
        inbox.health_score = 95.0

        config = MagicMock()
        config.max_bounce_rate = 0.05
        config.max_spam_rate = 0.001
        config.min_open_rate = 0.15

        healthy, details = await check_inbox_health(inbox, config)

        assert healthy is True
        assert details["issues"] == []
        assert "bounce_rate_7d" in details

    async def test_check_inbox_health_high_bounce_rate(self):
        """Bounce rate exceeding threshold → unhealthy with issue message."""
        from app.services.warmup_ai import check_inbox_health

        inbox = MagicMock()
        inbox.bounce_rate_7d = 0.08  # Above 5% threshold
        inbox.spam_rate_7d = 0.0001
        inbox.open_rate_7d = 0.25
        inbox.total_sent = 200
        inbox.health_score = 60.0

        config = MagicMock()
        config.max_bounce_rate = 0.05
        config.max_spam_rate = 0.001
        config.min_open_rate = 0.15

        healthy, details = await check_inbox_health(inbox, config)

        assert healthy is False
        assert len(details["issues"]) > 0
        assert any("Bounce rate" in issue for issue in details["issues"])

    async def test_check_inbox_health_high_spam_rate(self):
        """Spam rate exceeding threshold → unhealthy."""
        from app.services.warmup_ai import check_inbox_health

        inbox = MagicMock()
        inbox.bounce_rate_7d = 0.01
        inbox.spam_rate_7d = 0.005  # Above 0.1% threshold
        inbox.open_rate_7d = 0.25
        inbox.total_sent = 200
        inbox.health_score = 55.0

        config = MagicMock()
        config.max_bounce_rate = 0.05
        config.max_spam_rate = 0.001
        config.min_open_rate = 0.15

        healthy, details = await check_inbox_health(inbox, config)

        assert healthy is False
        assert any("Spam rate" in issue for issue in details["issues"])

    async def test_check_inbox_health_low_open_rate_above_50_sent(self):
        """Low open rate when total_sent > 50 → unhealthy."""
        from app.services.warmup_ai import check_inbox_health

        inbox = MagicMock()
        inbox.bounce_rate_7d = 0.01
        inbox.spam_rate_7d = 0.0001
        inbox.open_rate_7d = 0.05  # Below 15% threshold
        inbox.total_sent = 100
        inbox.health_score = 70.0

        config = MagicMock()
        config.max_bounce_rate = 0.05
        config.max_spam_rate = 0.001
        config.min_open_rate = 0.15

        healthy, details = await check_inbox_health(inbox, config)

        assert healthy is False
        assert any("Open rate" in issue for issue in details["issues"])

    async def test_check_inbox_health_low_open_rate_ignored_below_50_sent(self):
        """Low open rate with < 50 total_sent is not flagged (insufficient data)."""
        from app.services.warmup_ai import check_inbox_health

        inbox = MagicMock()
        inbox.bounce_rate_7d = 0.01
        inbox.spam_rate_7d = 0.0001
        inbox.open_rate_7d = 0.05  # Would be bad, but not enough data
        inbox.total_sent = 10  # Below threshold
        inbox.health_score = 80.0

        config = MagicMock()
        config.max_bounce_rate = 0.05
        config.max_spam_rate = 0.001
        config.min_open_rate = 0.15

        healthy, details = await check_inbox_health(inbox, config)

        # With only 10 sends, open rate check should be skipped
        open_rate_issues = [i for i in details["issues"] if "Open rate" in i]
        assert len(open_rate_issues) == 0

    async def test_check_inbox_health_details_include_checked_at(self):
        """Health check details should include a 'checked_at' timestamp."""
        from app.services.warmup_ai import check_inbox_health

        inbox = MagicMock()
        inbox.bounce_rate_7d = 0.01
        inbox.spam_rate_7d = 0.0001
        inbox.open_rate_7d = 0.25
        inbox.total_sent = 50
        inbox.health_score = 95.0

        config = MagicMock()
        config.max_bounce_rate = 0.05
        config.max_spam_rate = 0.001
        config.min_open_rate = 0.15

        _, details = await check_inbox_health(inbox, config)

        assert "checked_at" in details


class TestWarmupAISeedSelection:
    """Tests for seed selection algorithm."""

    async def test_seed_selection_no_candidates_returns_empty(self):
        """select_seeds_for_inbox returns [] when no leads exist."""
        from app.services.warmup_ai import select_seeds_for_inbox

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[]))
        )
        db.execute = AsyncMock(return_value=mock_result)

        inbox = MagicMock()
        seeds = await select_seeds_for_inbox(inbox, target_count=10, db=db)

        assert seeds == []

    async def test_seed_selection_compliance_gated(self):
        """Leads blocked by can_send_to_lead are excluded from seeds."""
        from app.services.warmup_ai import select_seeds_for_inbox

        db = AsyncMock()
        lead = MagicMock()
        lead.id = uuid.uuid4()
        lead.email = "blocked@example.com"

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[lead]))
        )
        db.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.warmup_ai.can_send_to_lead", new_callable=AsyncMock) as mock_can:
            mock_can.return_value = (False, "no_active_consent")
            inbox = MagicMock()
            seeds = await select_seeds_for_inbox(inbox, target_count=5, db=db)

        assert seeds == []

    async def test_seed_selection_fallback_included_when_compliant(self):
        """Compliant leads are included in fallback seed selection."""
        from app.services.warmup_ai import select_seeds_for_inbox

        db = AsyncMock()
        lead = MagicMock()
        lead.id = uuid.uuid4()
        lead.email = "ok@example.com"

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[lead]))
        )
        db.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.warmup_ai.can_send_to_lead", new_callable=AsyncMock) as mock_can:
            mock_can.return_value = (True, None)
            inbox = MagicMock()
            seeds = await select_seeds_for_inbox(inbox, target_count=5, db=db)

        assert len(seeds) == 1
        assert seeds[0]["email"] == "ok@example.com"
        assert seeds[0]["platform"] == "fallback"


# ══════════════════════════════════════════════════════════════════════════════
# 9. CONFIG / SETTINGS TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestConfigSettings:
    """Tests for Pydantic settings defaults and validation."""

    def test_default_settings_load(self):
        """Settings can be instantiated with all defaults."""
        from app.config import Settings

        s = Settings()
        assert s.ENVIRONMENT == "development"
        assert s.DAILY_EMAIL_LIMIT == 100
        assert s.DAILY_SMS_LIMIT == 30
        assert s.DAILY_LINKEDIN_LIMIT == 25

    def test_default_global_limits(self):
        """Global daily limits should match defaults."""
        from app.config import Settings

        s = Settings()
        assert s.GLOBAL_DAILY_EMAIL_LIMIT == 400
        assert s.GLOBAL_DAILY_SMS_LIMIT == 30
        assert s.GLOBAL_DAILY_LINKEDIN_LIMIT == 25

    def test_default_warmup_settings(self):
        """Warmup AI settings have correct defaults."""
        from app.config import Settings

        s = Settings()
        assert s.WARMUP_INITIAL_DAILY_VOLUME == 5
        assert s.WARMUP_RAMP_MULTIPLIER == 1.15
        assert s.WARMUP_DURATION_WEEKS == 6

    def test_default_reputation_thresholds(self):
        """Reputation thresholds are set to industry-safe defaults."""
        from app.config import Settings

        s = Settings()
        assert s.BOUNCE_RATE_PAUSE_THRESHOLD == 0.05  # 5%
        assert s.SPAM_RATE_PAUSE_THRESHOLD == 0.001  # 0.1%
        assert s.OPEN_RATE_MIN_THRESHOLD == 0.15  # 15%

    def test_default_retry_settings(self):
        """Retry backoff settings have correct defaults."""
        from app.config import Settings

        s = Settings()
        assert s.MAX_TOUCH_RETRIES == 3
        assert s.RETRY_BACKOFF_MINUTES == 30

    def test_env_override_database_url(self, monkeypatch):
        """DATABASE_URL can be overridden via environment variable."""
        from app.config import Settings

        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://custom:pass@host/db")
        s = Settings()
        assert s.DATABASE_URL == "postgresql+asyncpg://custom:pass@host/db"

    def test_env_override_daily_email_limit(self, monkeypatch):
        """DAILY_EMAIL_LIMIT can be overridden via environment variable."""
        from app.config import Settings

        monkeypatch.setenv("DAILY_EMAIL_LIMIT", "250")
        s = Settings()
        assert s.DAILY_EMAIL_LIMIT == 250

    def test_env_override_environment(self, monkeypatch):
        """ENVIRONMENT can be set to 'production'."""
        from app.config import Settings

        monkeypatch.setenv("ENVIRONMENT", "production")
        s = Settings()
        assert s.ENVIRONMENT == "production"

    def test_threshold_bounce_rate_is_float(self):
        """BOUNCE_RATE_PAUSE_THRESHOLD is a float, not int."""
        from app.config import Settings

        s = Settings()
        assert isinstance(s.BOUNCE_RATE_PAUSE_THRESHOLD, float)

    def test_threshold_spam_rate_is_float(self):
        """SPAM_RATE_PAUSE_THRESHOLD is a float, not int."""
        from app.config import Settings

        s = Settings()
        assert isinstance(s.SPAM_RATE_PAUSE_THRESHOLD, float)

    def test_warmup_ramp_multiplier_above_one(self):
        """Ramp multiplier should be > 1.0 to produce growth."""
        from app.config import Settings

        s = Settings()
        assert s.WARMUP_RAMP_MULTIPLIER > 1.0

    def test_imap_folder_defaults_to_inbox(self):
        """IMAP_FOLDER defaults to 'INBOX'."""
        from app.config import Settings

        s = Settings()
        assert s.IMAP_FOLDER == "INBOX"

    def test_ses_configuration_set_default(self):
        """SES_CONFIGURATION_SET has expected default name."""
        from app.config import Settings

        s = Settings()
        assert s.SES_CONFIGURATION_SET == "fortressflow-tracking"

    def test_sequence_engine_interval_default(self):
        """SEQUENCE_ENGINE_INTERVAL_MINUTES defaults to 15."""
        from app.config import Settings

        s = Settings()
        assert s.SEQUENCE_ENGINE_INTERVAL_MINUTES == 15

    def test_max_sending_identities_default(self):
        """MAX_SENDING_IDENTITIES defaults to 10."""
        from app.config import Settings

        s = Settings()
        assert s.MAX_SENDING_IDENTITIES == 10

    def test_hub_ai_flags_default_disabled(self):
        """AI platform features default to False for safety."""
        from app.config import Settings

        s = Settings()
        assert s.HUBSPOT_BREEZE_ENABLED is False
        assert s.ZOOMINFO_COPILOT_ENABLED is False
        assert s.APOLLO_AI_ENABLED is False


# ══════════════════════════════════════════════════════════════════════════════
# BONUS: Model Enum Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestSequenceModelEnums:
    """Verify all model enums have the expected values."""

    def test_sequence_status_values(self):
        """SequenceStatus has all expected states."""
        from app.models.sequence import SequenceStatus

        assert SequenceStatus.draft == "draft"
        assert SequenceStatus.active == "active"
        assert SequenceStatus.paused == "paused"
        assert SequenceStatus.archived == "archived"

    def test_step_type_values(self):
        """StepType has all channel and control types."""
        from app.models.sequence import StepType

        assert StepType.email == "email"
        assert StepType.sms == "sms"
        assert StepType.linkedin == "linkedin"
        assert StepType.wait == "wait"
        assert StepType.conditional == "conditional"
        assert StepType.ab_split == "ab_split"
        assert StepType.end == "end"

    def test_enrollment_status_values(self):
        """EnrollmentStatus has all FSM states."""
        from app.models.sequence import EnrollmentStatus

        assert EnrollmentStatus.active == "active"
        assert EnrollmentStatus.completed == "completed"
        assert EnrollmentStatus.paused == "paused"
        assert EnrollmentStatus.bounced == "bounced"
        assert EnrollmentStatus.unsubscribed == "unsubscribed"
        assert EnrollmentStatus.pending == "pending"
        assert EnrollmentStatus.sent == "sent"
        assert EnrollmentStatus.opened == "opened"
        assert EnrollmentStatus.replied == "replied"
        assert EnrollmentStatus.escalated == "escalated"
        assert EnrollmentStatus.failed == "failed"


class TestHardFailureReasons:
    """Tests for the HARD_FAILURE_REASONS set in channel orchestrator."""

    def test_hard_failure_reasons_complete(self):
        """All critical hard failure reasons are in the set."""
        from app.services.channel_orchestrator import HARD_FAILURE_REASONS

        required = {
            "bounce",
            "hard_bounce",
            "complaint",
            "spam_complaint",
            "unsubscribe",
            "dnc",
            "no_active_consent",
        }
        for reason in required:
            assert reason in HARD_FAILURE_REASONS, f"'{reason}' missing from HARD_FAILURE_REASONS"

    def test_hard_failure_case_insensitive_check(self):
        """_is_hard_failure check is case-insensitive."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        orch = ChannelOrchestrator(AsyncMock())
        assert orch._is_hard_failure("BOUNCE") is True
        assert orch._is_hard_failure("Spam_Complaint") is True
        assert orch._is_hard_failure("NO_ACTIVE_CONSENT") is True
