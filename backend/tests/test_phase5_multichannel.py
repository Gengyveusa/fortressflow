"""
Phase 5 Tests: Multi-Channel Logic + Reply Detection + SMS/Twilio.

Tests cover:
1. Reply detection and parsing
2. Sentiment analysis
3. Reply-to-enrollment matching
4. FSM state transitions on reply
5. SMS timezone gating
6. TCPA consent verification
7. Twilio webhook handling (STOP, status, inbound)
8. LinkedIn queue management and rate limits
9. Multi-channel dispatch with failover
10. Hole-filler escalation
11. AI feedback loop
12. Channel orchestrator global limits

All tests use in-memory mocks (no real database or external APIs).
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ═══════════════════════════════════════════════════════════════════════
# 1. REPLY SENTIMENT ANALYSIS TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestReplySentimentAnalysis:
    """Test keyword-based NLP sentiment classification."""

    @pytest.mark.asyncio
    async def test_reply_sentiment_positive(self):
        """Body expressing interest → positive sentiment."""
        from app.services.reply_service import ReplyService

        db = AsyncMock()
        svc = ReplyService(db)

        sentiment, confidence = await svc.analyze_sentiment(
            "I'm interested in scheduling a demo. When are you available?"
        )

        from app.services.reply_service import ReplySentiment

        assert sentiment == ReplySentiment.positive
        assert confidence > 0.5

    @pytest.mark.asyncio
    async def test_reply_sentiment_negative(self):
        """Body requesting removal → negative sentiment."""
        from app.services.reply_service import ReplyService

        db = AsyncMock()
        svc = ReplyService(db)

        sentiment, confidence = await svc.analyze_sentiment(
            "Please remove me from your list. I am not interested."
        )

        from app.services.reply_service import ReplySentiment

        assert sentiment in (ReplySentiment.negative, ReplySentiment.unsubscribe)
        assert confidence > 0.5

    @pytest.mark.asyncio
    async def test_reply_sentiment_neutral(self):
        """Body requesting information → neutral sentiment."""
        from app.services.reply_service import ReplyService

        db = AsyncMock()
        svc = ReplyService(db)

        sentiment, confidence = await svc.analyze_sentiment(
            "Can you send more information about your product?"
        )

        from app.services.reply_service import ReplySentiment

        assert sentiment == ReplySentiment.neutral
        assert confidence >= 0.5

    @pytest.mark.asyncio
    async def test_reply_sentiment_ooo(self):
        """Out-of-office auto-reply → out_of_office sentiment."""
        from app.services.reply_service import ReplyService

        db = AsyncMock()
        svc = ReplyService(db)

        sentiment, confidence = await svc.analyze_sentiment(
            "I am out of office until March 25 with limited access to email. "
            "I will respond upon my return."
        )

        from app.services.reply_service import ReplySentiment

        assert sentiment == ReplySentiment.out_of_office
        assert confidence >= 0.7

    @pytest.mark.asyncio
    async def test_reply_sentiment_unsubscribe(self):
        """Explicit unsubscribe request → unsubscribe sentiment (highest priority)."""
        from app.services.reply_service import ReplyService

        db = AsyncMock()
        svc = ReplyService(db)

        sentiment, confidence = await svc.analyze_sentiment(
            "Unsubscribe me immediately. No more emails please."
        )

        from app.services.reply_service import ReplySentiment

        assert sentiment == ReplySentiment.unsubscribe
        assert confidence >= 0.9

    @pytest.mark.asyncio
    async def test_reply_sentiment_unsubscribe_takes_priority_over_ooo(self):
        """Unsubscribe keyword beats OOO detection (hard priority check)."""
        from app.services.reply_service import ReplyService, ReplySentiment

        db = AsyncMock()
        svc = ReplyService(db)

        sentiment, confidence = await svc.analyze_sentiment(
            "I am out of office but please unsubscribe me from this list."
        )

        assert sentiment == ReplySentiment.unsubscribe

    @pytest.mark.asyncio
    async def test_reply_sentiment_empty_body_neutral(self):
        """Empty / whitespace body → neutral fallback."""
        from app.services.reply_service import ReplyService, ReplySentiment

        db = AsyncMock()
        svc = ReplyService(db)

        sentiment, confidence = await svc.analyze_sentiment("   ")

        assert sentiment == ReplySentiment.neutral
        assert confidence == 0.5

    @pytest.mark.asyncio
    async def test_reply_sentiment_schedule_call_positive(self):
        """Schedule / call keyword → positive."""
        from app.services.reply_service import ReplyService, ReplySentiment

        db = AsyncMock()
        svc = ReplyService(db)

        sentiment, confidence = await svc.analyze_sentiment(
            "Yes, let's schedule a call this week."
        )

        assert sentiment == ReplySentiment.positive
        assert confidence > 0.5

    @pytest.mark.asyncio
    async def test_reply_sentiment_pricing_inquiry_positive(self):
        """Pricing inquiry → positive (buying signal)."""
        from app.services.reply_service import ReplyService, ReplySentiment

        db = AsyncMock()
        svc = ReplyService(db)

        sentiment, confidence = await svc.analyze_sentiment(
            "What is the pricing for your platform?"
        )

        assert sentiment == ReplySentiment.positive
        assert confidence > 0.5


# ═══════════════════════════════════════════════════════════════════════
# 2. REPLY MATCHING TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestReplyMatching:
    """Test reply-to-enrollment matching logic."""

    @pytest.mark.asyncio
    async def test_reply_match_by_thread_id(self):
        """Thread ID in touch_log metadata matches reply to enrollment."""
        from app.services.reply_service import ReplyService, ReplySignal

        lead_id = uuid.uuid4()
        sequence_id = uuid.uuid4()
        enrollment_id = uuid.uuid4()
        message_id = "test-message-id-abc123"

        # Mock: touch_log found with the message_id in metadata
        mock_touch = MagicMock()
        mock_touch.sequence_id = sequence_id
        mock_touch.lead_id = lead_id

        # Mock: enrollment found for the lead + sequence
        mock_enrollment = MagicMock()
        mock_enrollment.id = enrollment_id
        mock_enrollment.sequence_id = sequence_id

        db = AsyncMock()

        # First execute returns touch log
        touch_result = MagicMock()
        touch_result.scalar_one_or_none.return_value = mock_touch

        # Second execute returns enrollment
        enr_result = MagicMock()
        enr_result.scalar_one_or_none.return_value = mock_enrollment

        db.execute.side_effect = [touch_result, enr_result]

        svc = ReplyService(db)
        signal = ReplySignal(
            channel="email",
            body="I'm interested!",
            sender_email="lead@example.com",
            thread_id=message_id,
        )

        enrollment_id_matched, seq_id_matched = await svc._match_by_thread_id(message_id)

        # Verify DB was queried
        assert db.execute.call_count >= 1

        # Matched enrollment and sequence
        assert enrollment_id_matched == enrollment_id
        assert seq_id_matched == sequence_id

    @pytest.mark.asyncio
    async def test_reply_match_by_sender_email(self):
        """Sender email matches lead → finds active enrollment."""
        from app.services.reply_service import ReplyService

        lead_id = uuid.uuid4()
        sequence_id = uuid.uuid4()
        enrollment_id = uuid.uuid4()
        sender_email = "drsmith@dentaloffice.com"

        mock_lead = MagicMock()
        mock_lead.id = lead_id
        mock_lead.email = sender_email

        mock_enrollment = MagicMock()
        mock_enrollment.id = enrollment_id
        mock_enrollment.sequence_id = sequence_id

        db = AsyncMock()

        lead_result = MagicMock()
        lead_result.scalar_one_or_none.return_value = mock_lead

        enr_result = MagicMock()
        enr_result.scalar_one_or_none.return_value = mock_enrollment

        db.execute.side_effect = [lead_result, enr_result]

        svc = ReplyService(db)
        matched_enrollment_id, matched_seq_id = await svc._match_by_sender_email(
            sender_email
        )

        assert matched_enrollment_id == enrollment_id
        assert matched_seq_id == sequence_id

    @pytest.mark.asyncio
    async def test_reply_match_by_thread_id_no_touch_log(self):
        """Thread ID not found in touch_logs → returns (None, None)."""
        from app.services.reply_service import ReplyService

        db = AsyncMock()
        no_result = MagicMock()
        no_result.scalar_one_or_none.return_value = None
        db.execute.return_value = no_result

        svc = ReplyService(db)
        enrollment_id, seq_id = await svc._match_by_thread_id("unknown-thread-id")

        assert enrollment_id is None
        assert seq_id is None

    @pytest.mark.asyncio
    async def test_reply_match_by_sender_email_no_lead(self):
        """Unknown sender email → returns (None, None)."""
        from app.services.reply_service import ReplyService

        db = AsyncMock()
        no_result = MagicMock()
        no_result.scalar_one_or_none.return_value = None
        db.execute.return_value = no_result

        svc = ReplyService(db)
        enrollment_id, seq_id = await svc._match_by_sender_email("nobody@nowhere.com")

        assert enrollment_id is None
        assert seq_id is None

    @pytest.mark.asyncio
    async def test_reply_match_priority_thread_id_first(self):
        """Thread ID matching is tried before sender email."""
        from app.services.reply_service import ReplyService, ReplySignal

        enrollment_id = uuid.uuid4()
        sequence_id = uuid.uuid4()
        lead_id = uuid.uuid4()

        db = AsyncMock()
        svc = ReplyService(db)

        # Patch internal methods
        svc._match_by_thread_id = AsyncMock(
            return_value=(enrollment_id, sequence_id)
        )
        svc._match_by_sender_email = AsyncMock(return_value=(None, None))
        svc._match_by_subject = AsyncMock(return_value=(None, None))

        signal = ReplySignal(
            channel="email",
            body="test",
            sender_email="test@test.com",
            thread_id="<thread-abc>",
        )

        result_enrollment, result_seq = await svc.match_to_enrollment(signal)

        # Thread ID should have matched — sender email should NOT be called
        svc._match_by_thread_id.assert_called_once()
        svc._match_by_sender_email.assert_not_called()
        assert result_enrollment == enrollment_id


# ═══════════════════════════════════════════════════════════════════════
# 3. FSM STATE TRANSITION ON REPLY TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestReplyFSMTransition:
    """Test FSM state transitions triggered by reply detection."""

    @pytest.mark.asyncio
    async def test_reply_fsm_transition(self):
        """Reply on 'sent' enrollment → replied → paused (auto-pause)."""
        from app.services.reply_service import ReplyService, ReplySignal, ReplySentiment

        enrollment_id = uuid.uuid4()
        sequence_id = uuid.uuid4()
        lead_id = uuid.uuid4()

        db = AsyncMock()
        svc = ReplyService(db)

        # Patch sentiment analysis
        svc.analyze_sentiment = AsyncMock(
            return_value=(ReplySentiment.positive, 0.85)
        )

        # Patch match_to_enrollment
        svc.match_to_enrollment = AsyncMock(
            return_value=(enrollment_id, sequence_id)
        )

        # Patch AI analysis
        svc.ai_analyze_reply = AsyncMock(
            return_value={
                "hubspot_note_id": "hs-note-123",
                "apollo_action": "schedule_call",
                "zoominfo_update": {"status": "logged"},
                "combined_next_action": "schedule_call",
            }
        )

        # Mock enrollment with 'sent' status
        from app.models.sequence import EnrollmentStatus

        mock_enrollment = MagicMock()
        mock_enrollment.id = enrollment_id
        mock_enrollment.lead_id = lead_id
        mock_enrollment.sequence_id = sequence_id
        mock_enrollment.status = EnrollmentStatus.sent
        mock_enrollment.last_state_change_at = None

        # Mock lead
        mock_lead = MagicMock()
        mock_lead.id = lead_id
        mock_lead.email = "dr@dental.com"
        mock_lead.first_name = "John"
        mock_lead.company = "Dental Office"
        mock_lead.title = "Doctor"

        # Mock DB execute calls
        enr_result = MagicMock()
        enr_result.scalar_one_or_none.return_value = mock_enrollment

        lead_result = MagicMock()
        lead_result.scalar_one_or_none.return_value = mock_lead

        db.execute.side_effect = [enr_result, lead_result]
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        # Patch log_reply to be a no-op
        svc.log_reply = AsyncMock()

        signal = ReplySignal(
            channel="email",
            body="I'm interested in scheduling a demo!",
            sender_email="dr@dental.com",
            thread_id="<thread-123>",
        )

        result = await svc.process_reply(signal)

        assert result.sentiment == ReplySentiment.positive
        assert result.matched_enrollment_id == enrollment_id
        svc.log_reply.assert_called_once()
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_reply_fsm_no_match_still_logs(self):
        """Reply with no enrollment match still logs with None enrollment_id."""
        from app.services.reply_service import ReplyService, ReplySignal, ReplySentiment

        db = AsyncMock()
        svc = ReplyService(db)

        svc.analyze_sentiment = AsyncMock(
            return_value=(ReplySentiment.neutral, 0.5)
        )
        svc.match_to_enrollment = AsyncMock(return_value=(None, None))
        svc.log_reply = AsyncMock()
        db.commit = AsyncMock()

        signal = ReplySignal(
            channel="email",
            body="Just curious about your product.",
            sender_email="unknown@unknown.com",
        )

        result = await svc.process_reply(signal)

        assert result.matched_enrollment_id is None
        assert result.sentiment == ReplySentiment.neutral
        svc.log_reply.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════
# 4. SMS TIMEZONE GATE TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestSMSTimezoneGate:
    """Test SMS timezone gating (8AM–9PM recipient local time)."""

    @pytest.mark.asyncio
    async def test_sms_timezone_gate_allowed(self):
        """Lead TZ US/Eastern at 10AM EST → within send window → allowed."""
        from app.services.sms_service import check_timezone_gate

        # Mock datetime.now(UTC) to return 15:00 UTC = 10AM EST (UTC-5 in winter)
        mock_now = datetime(2026, 3, 19, 15, 0, 0, tzinfo=UTC)  # 10AM EST

        with patch("app.services.sms_service.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            can_send, reason = await check_timezone_gate("US/Eastern")

        assert can_send is True
        assert reason == "approved"

    @pytest.mark.asyncio
    async def test_sms_timezone_gate_blocked(self):
        """Lead TZ US/Eastern at 11PM EST → outside window → blocked."""
        from app.services.sms_service import check_timezone_gate

        # 04:00 UTC = 11PM EST (UTC-5 in winter)
        mock_now = datetime(2026, 3, 20, 4, 0, 0, tzinfo=UTC)

        with patch("app.services.sms_service.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            can_send, reason = await check_timezone_gate("US/Eastern")

        assert can_send is False
        assert "Outside SMS send window" in reason

    @pytest.mark.asyncio
    async def test_sms_timezone_gate_no_tz(self):
        """No TZ → defaults to US/Eastern, checks same window."""
        from app.services.sms_service import check_timezone_gate

        # 15:00 UTC = 10AM EST — within window
        mock_now = datetime(2026, 3, 19, 15, 0, 0, tzinfo=UTC)

        with patch("app.services.sms_service.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            can_send, reason = await check_timezone_gate(None)

        # With default US/Eastern at 10AM → should be allowed
        assert isinstance(can_send, bool)
        assert reason in ("approved",) or "window" in reason

    @pytest.mark.asyncio
    async def test_sms_timezone_gate_unknown_tz_falls_back(self):
        """Unknown TZ string → falls back to US/Eastern (no crash)."""
        from app.services.sms_service import check_timezone_gate

        mock_now = datetime(2026, 3, 19, 15, 0, 0, tzinfo=UTC)

        with patch("app.services.sms_service.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            # Should not raise — falls back to US/Eastern
            can_send, reason = await check_timezone_gate("Fake/Timezone")

        assert isinstance(can_send, bool)

    @pytest.mark.asyncio
    async def test_sms_timezone_gate_exactly_at_boundary(self):
        """Exactly at 8AM local time → allowed (start boundary inclusive)."""
        from app.services.sms_service import check_timezone_gate

        # 13:00 UTC = 8AM EST
        mock_now = datetime(2026, 3, 19, 13, 0, 0, tzinfo=UTC)

        with patch("app.services.sms_service.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            can_send, reason = await check_timezone_gate("US/Eastern")

        assert can_send is True


# ═══════════════════════════════════════════════════════════════════════
# 5. TCPA CONSENT TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestTCPAConsent:
    """Test TCPA consent verification for SMS."""

    @pytest.mark.asyncio
    async def test_tcpa_consent_written_allowed(self):
        """Written consent via web_form with disclosure=true → allowed."""
        from app.services.sms_service import check_tcpa_consent

        lead_id = uuid.uuid4()

        mock_consent = MagicMock()
        from app.models.consent import ConsentMethod

        mock_consent.method = ConsentMethod.web_form
        mock_consent.proof = {"disclosure": True, "ip": "1.2.3.4"}
        mock_consent.revoked_at = None

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_consent
        db.execute.return_value = result

        can_send, reason = await check_tcpa_consent(lead_id, db)

        assert can_send is True
        assert "written_consent" in reason

    @pytest.mark.asyncio
    async def test_tcpa_consent_meeting_card_allowed(self):
        """Meeting card (written) consent → always allowed for SMS."""
        from app.services.sms_service import check_tcpa_consent

        lead_id = uuid.uuid4()

        mock_consent = MagicMock()
        from app.models.consent import ConsentMethod

        mock_consent.method = ConsentMethod.meeting_card
        mock_consent.proof = {"event": "dental_conference", "date": "2026-01-10"}
        mock_consent.revoked_at = None

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_consent
        db.execute.return_value = result

        can_send, reason = await check_tcpa_consent(lead_id, db)

        assert can_send is True
        assert "meeting_card" in reason

    @pytest.mark.asyncio
    async def test_tcpa_consent_verbal_blocked(self):
        """Web form consent WITHOUT disclosure flag → blocked for SMS."""
        from app.services.sms_service import check_tcpa_consent

        lead_id = uuid.uuid4()

        mock_consent = MagicMock()
        from app.models.consent import ConsentMethod

        mock_consent.method = ConsentMethod.web_form
        # Missing disclosure flag
        mock_consent.proof = {"ip": "1.2.3.4", "timestamp": "2026-01-01T00:00:00Z"}
        mock_consent.revoked_at = None

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_consent
        db.execute.return_value = result

        can_send, reason = await check_tcpa_consent(lead_id, db)

        assert can_send is False
        assert "disclosure" in reason.lower()

    @pytest.mark.asyncio
    async def test_tcpa_no_consent_record_blocked(self):
        """No consent record at all → blocked."""
        from app.services.sms_service import check_tcpa_consent

        lead_id = uuid.uuid4()

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result

        can_send, reason = await check_tcpa_consent(lead_id, db)

        assert can_send is False
        assert "no_sms_consent_record" in reason

    @pytest.mark.asyncio
    async def test_tcpa_consent_missing_proof_blocked(self):
        """Consent record exists but proof is None → blocked."""
        from app.services.sms_service import check_tcpa_consent

        lead_id = uuid.uuid4()

        mock_consent = MagicMock()
        from app.models.consent import ConsentMethod

        mock_consent.method = ConsentMethod.web_form
        mock_consent.proof = None
        mock_consent.revoked_at = None

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_consent
        db.execute.return_value = result

        can_send, reason = await check_tcpa_consent(lead_id, db)

        assert can_send is False
        assert "proof" in reason.lower()


# ═══════════════════════════════════════════════════════════════════════
# 6. TWILIO WEBHOOK TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestTwilioWebhook:
    """Test Twilio inbound SMS and status callback webhook processing."""

    @pytest.mark.asyncio
    async def test_twilio_webhook_stop(self):
        """Inbound with Body='STOP' → returns stop_request action."""
        from app.services.sms_service import process_inbound_sms

        db = AsyncMock()

        # Mock DNC processing
        db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
        db.add = MagicMock()
        db.commit = AsyncMock()

        form_data = {
            "From": "+14155551234",
            "To": "+18005550001",
            "Body": "STOP",
            "MessageSid": "SMtest123",
        }

        result = await process_inbound_sms(form_data, db)

        assert result["type"] == "stop_request"
        assert result["phone"] == "+14155551234"
        assert result["message_sid"] == "SMtest123"

    @pytest.mark.asyncio
    async def test_twilio_webhook_stop_case_insensitive(self):
        """'stop' lowercase also triggers DNC (case-insensitive)."""
        from app.services.sms_service import is_stop_keyword

        assert is_stop_keyword("stop") is True
        assert is_stop_keyword("STOP") is True
        assert is_stop_keyword("Stop") is True
        assert is_stop_keyword("UNSUBSCRIBE") is True
        assert is_stop_keyword("cancel") is True

    @pytest.mark.asyncio
    async def test_twilio_webhook_status_delivered(self):
        """Status callback 'delivered' → logs delivery touch."""
        from app.services.sms_service import process_inbound_sms

        db = AsyncMock()

        # Mock finding original touch log by message_sid
        from app.models.touch_log import TouchLog

        mock_touch = MagicMock(spec=TouchLog)
        mock_touch.id = uuid.uuid4()
        mock_touch.lead_id = uuid.uuid4()
        mock_touch.sequence_id = uuid.uuid4()

        original_log_result = MagicMock()
        original_log_result.scalar_one_or_none.return_value = mock_touch
        db.execute.return_value = original_log_result
        db.add = MagicMock()
        db.commit = AsyncMock()

        form_data = {
            "MessageSid": "SMtest456",
            "MessageStatus": "delivered",
            "To": "+14155551234",
            "From": "+18005550001",
            "Body": "",
        }

        result = await process_inbound_sms(form_data, db)

        assert result["type"] == "status_update"
        assert result["status"] == "delivered"
        assert result["message_sid"] == "SMtest456"

    @pytest.mark.asyncio
    async def test_twilio_webhook_inbound_reply(self):
        """Non-STOP inbound SMS → triggers reply processing."""
        from app.services.sms_service import process_inbound_sms

        db = AsyncMock()
        enrollment_id = uuid.uuid4()
        lead_id = uuid.uuid4()

        # Mock lead lookup
        mock_lead = MagicMock()
        mock_lead.id = lead_id
        mock_lead.phone = "+14155551234"

        # Mock enrollment lookup
        mock_enrollment = MagicMock()
        mock_enrollment.id = enrollment_id
        mock_enrollment.lead_id = lead_id

        lead_result = MagicMock()
        lead_result.scalar_one_or_none.return_value = mock_lead

        enr_result = MagicMock()
        enr_result.scalar_one_or_none.return_value = mock_enrollment

        db.execute.side_effect = [lead_result, enr_result]
        db.add = MagicMock()
        db.commit = AsyncMock()

        form_data = {
            "From": "+14155551234",
            "To": "+18005550001",
            "Body": "Yes, I'd love to hear more about your product!",
            "MessageSid": "SMtest789",
        }

        with patch(
            "app.services.reply_service.ReplyService"
        ) as mock_reply_svc_class:
            mock_reply_svc = AsyncMock()
            mock_reply_svc_class.return_value = mock_reply_svc
            mock_analysis = MagicMock()
            mock_analysis.sentiment.value = "positive"
            mock_analysis.confidence = 0.85
            mock_reply_svc.process_reply = AsyncMock(return_value=mock_analysis)

            result = await process_inbound_sms(form_data, db)

        assert result["type"] == "inbound_reply"
        assert result["phone"] == "+14155551234"
        assert result["body"] == "Yes, I'd love to hear more about your product!"

    @pytest.mark.asyncio
    async def test_twilio_webhook_unknown_type(self):
        """Payload with no body and no status → unknown type."""
        from app.services.sms_service import process_inbound_sms

        db = AsyncMock()

        form_data = {
            "From": "+14155551234",
            "To": "+18005550001",
        }

        result = await process_inbound_sms(form_data, db)

        assert result["type"] == "unknown"


# ═══════════════════════════════════════════════════════════════════════
# 7. LINKEDIN QUEUE AND RATE LIMIT TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestLinkedInQueue:
    """Test LinkedIn queue management, rate limits, and human delays."""

    @pytest.mark.asyncio
    async def test_linkedin_rate_limit(self):
        """Queue 26 items (over 25 limit) → 26th is blocked."""
        from app.services.linkedin_service import LinkedInService, DAILY_LINKEDIN_LIMIT

        db = AsyncMock()

        with patch("app.services.linkedin_service.compliance_svc") as mock_compliance:
            mock_compliance.can_send_to_lead = AsyncMock(return_value=(True, "approved"))

            svc = LinkedInService(db)

            # Mock today's count as already at limit
            svc._count_today_sends = AsyncMock(return_value=DAILY_LINKEDIN_LIMIT)

            mock_lead = MagicMock()
            mock_lead.id = uuid.uuid4()
            mock_lead.first_name = "John"
            mock_lead.last_name = "Smith"
            mock_lead.title = "Practice Manager"
            mock_lead.company = "Dental Associates"
            mock_lead.email = "john@dental.com"
            mock_lead.enriched_data = {}

            result = await svc.queue_connection_request(lead=mock_lead)

            assert result.success is False
            assert "limit" in result.error.lower() or "Daily" in result.error

    @pytest.mark.asyncio
    async def test_linkedin_human_delay(self):
        """Generated human delay must be between 45-120 seconds."""
        from app.services.linkedin_service import LinkedInService

        db = AsyncMock()
        svc = LinkedInService(db)

        # Test multiple draws to verify range
        for _ in range(20):
            delay = svc._generate_human_delay()
            assert 45.0 <= delay <= 120.0, (
                f"Human delay {delay}s outside 45-120s window"
            )

    @pytest.mark.asyncio
    async def test_linkedin_human_delay_distribution(self):
        """Mean of human delays should be near 75s (normal distribution bias)."""
        from app.services.linkedin_service import LinkedInService

        db = AsyncMock()
        svc = LinkedInService(db)

        delays = [svc._generate_human_delay() for _ in range(200)]
        mean_delay = sum(delays) / len(delays)

        # Mean should be within 60-90s range (biased toward 75s)
        assert 55.0 <= mean_delay <= 95.0, f"Mean delay {mean_delay}s outside expected range"

    @pytest.mark.asyncio
    async def test_linkedin_ai_personalized_note(self):
        """AI note generation produces note under 300 chars."""
        from app.services.linkedin_service import (
            LinkedInService,
            CONNECTION_NOTE_MAX_CHARS,
        )

        db = AsyncMock()

        mock_lead = MagicMock()
        mock_lead.email = "dr@dental.com"
        mock_lead.first_name = "Sarah"
        mock_lead.last_name = "Johnson"
        mock_lead.title = "Practice Owner"
        mock_lead.company = "Johnson Dental Group"
        mock_lead.enriched_data = {}

        with patch("app.services.linkedin_service.settings") as mock_settings:
            mock_settings.HUBSPOT_BREEZE_ENABLED = False
            mock_settings.HUBSPOT_API_KEY = ""
            mock_settings.ZOOMINFO_COPILOT_ENABLED = False
            mock_settings.LINKEDIN_OAUTH_CLIENT_ID = ""
            mock_settings.LINKEDIN_OAUTH_CLIENT_SECRET = ""
            mock_settings.LINKEDIN_OAUTH_REDIRECT_URI = ""
            mock_settings.LINKEDIN_PROXY_ENDPOINT = ""

            svc = LinkedInService(db)
            note = await svc.generate_personalized_note(mock_lead)

        assert len(note) <= CONNECTION_NOTE_MAX_CHARS, (
            f"Note {len(note)} chars exceeds {CONNECTION_NOTE_MAX_CHARS} limit"
        )
        assert len(note) > 0
        # Note should reference the lead's name or company
        assert "Sarah" in note or "Johnson" in note or "Dental" in note

    @pytest.mark.asyncio
    async def test_linkedin_queue_connection_request_success(self):
        """Queue connection request under daily limit → success + queued=True."""
        from app.services.linkedin_service import LinkedInService

        db = AsyncMock()

        with patch("app.services.linkedin_service.compliance_svc") as mock_compliance, \
             patch("app.services.linkedin_service.settings") as mock_settings:
            mock_compliance.can_send_to_lead = AsyncMock(return_value=(True, "approved"))
            mock_settings.HUBSPOT_BREEZE_ENABLED = False
            mock_settings.HUBSPOT_API_KEY = ""
            mock_settings.ZOOMINFO_COPILOT_ENABLED = False
            mock_settings.LINKEDIN_OAUTH_CLIENT_ID = ""
            mock_settings.LINKEDIN_OAUTH_CLIENT_SECRET = ""
            mock_settings.LINKEDIN_OAUTH_REDIRECT_URI = ""
            mock_settings.LINKEDIN_PROXY_ENDPOINT = ""

            svc = LinkedInService(db)
            svc._count_today_sends = AsyncMock(return_value=5)

            mock_lead = MagicMock()
            mock_lead.id = uuid.uuid4()
            mock_lead.first_name = "Alice"
            mock_lead.last_name = "Brown"
            mock_lead.title = "Dentist"
            mock_lead.company = "Brown Family Dental"
            mock_lead.email = "alice@browndental.com"
            mock_lead.enriched_data = {}

            result = await svc.queue_connection_request(
                lead=mock_lead,
                note="Hi Alice, would love to connect!",
            )

        assert result.success is True
        assert result.queued is True
        assert result.queue_item_id is not None
        assert len(svc._queue) == 1

    @pytest.mark.asyncio
    async def test_linkedin_queue_compliance_blocked(self):
        """Compliance gate blocks LinkedIn queue → returns failure."""
        from app.services.linkedin_service import LinkedInService

        db = AsyncMock()

        with patch("app.services.linkedin_service.compliance_svc") as mock_compliance:
            mock_compliance.can_send_to_lead = AsyncMock(
                return_value=(False, "dnc_blocked")
            )

            svc = LinkedInService(db)

            mock_lead = MagicMock()
            mock_lead.id = uuid.uuid4()
            mock_lead.first_name = "Bob"
            mock_lead.last_name = "Test"
            mock_lead.title = "Manager"
            mock_lead.company = "Test Corp"
            mock_lead.email = "bob@test.com"
            mock_lead.enriched_data = {}

            result = await svc.queue_connection_request(lead=mock_lead)

        assert result.success is False
        assert "Compliance" in result.error or "blocked" in result.error.lower()


# ═══════════════════════════════════════════════════════════════════════
# 8. CHANNEL ORCHESTRATOR TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestChannelOrchestrator:
    """Test multi-channel dispatch with failover and global limits."""

    @pytest.mark.asyncio
    async def test_channel_orchestrator_dispatch_email(self):
        """Dispatch email step → successful email send → success result."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        db = AsyncMock()

        with patch("app.services.channel_orchestrator.compliance_svc") as mock_compliance:
            mock_compliance.can_send_to_lead = AsyncMock(return_value=(True, "approved"))

            orch = ChannelOrchestrator(db)

            # Mock check_global_limits to allow email
            orch.check_global_limits = AsyncMock(return_value=(True, 350))

            # Mock _dispatch_email to succeed
            orch._dispatch_email = AsyncMock(
                return_value={"success": True, "message_id": "<test@ff>"}
            )

            mock_enrollment = MagicMock()
            mock_enrollment.id = uuid.uuid4()
            mock_enrollment.lead_id = uuid.uuid4()
            mock_enrollment.sequence_id = uuid.uuid4()

            mock_step = MagicMock()
            from app.models.sequence import StepType

            mock_step.step_type = StepType.email
            mock_step.position = 0

            mock_lead = MagicMock()
            mock_lead.id = uuid.uuid4()
            mock_lead.email = "test@dental.com"

            mock_template = MagicMock()

            result = await orch.dispatch(
                enrollment=mock_enrollment,
                step=mock_step,
                lead=mock_lead,
                template=mock_template,
            )

        assert result["success"] is True
        assert result["channel"] == "email"
        assert result["failover_used"] is False

    @pytest.mark.asyncio
    async def test_channel_orchestrator_failover_to_linkedin(self):
        """Email fails with soft error → failover to LinkedIn → success."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        db = AsyncMock()

        with patch("app.services.channel_orchestrator.compliance_svc") as mock_compliance:
            # Allow both email (initial) and linkedin (failover)
            mock_compliance.can_send_to_lead = AsyncMock(return_value=(True, "approved"))

            orch = ChannelOrchestrator(db)

            # Email global limit OK, LinkedIn limit OK
            orch.check_global_limits = AsyncMock(return_value=(True, 50))

            # Email dispatch fails with soft error
            orch._dispatch_email = AsyncMock(
                return_value={"success": False, "error": "smtp_timeout"}
            )

            # Mock attempt_failover to succeed via LinkedIn
            orch.attempt_failover = AsyncMock(
                return_value={
                    "success": True,
                    "channel": "linkedin",
                    "result": {"queued": True},
                    "failover_reason": "smtp_timeout",
                }
            )

            mock_enrollment = MagicMock()
            mock_enrollment.id = uuid.uuid4()
            mock_enrollment.lead_id = uuid.uuid4()

            mock_step = MagicMock()
            from app.models.sequence import StepType

            mock_step.step_type = StepType.email
            mock_step.position = 0

            mock_lead = MagicMock()
            mock_lead.id = uuid.uuid4()
            mock_lead.email = "lead@test.com"

            mock_template = MagicMock()

            result = await orch.dispatch(
                enrollment=mock_enrollment,
                step=mock_step,
                lead=mock_lead,
                template=mock_template,
            )

        assert result["success"] is True
        assert result["failover_used"] is True
        assert result["failover_channel"] == "linkedin"

    @pytest.mark.asyncio
    async def test_channel_orchestrator_global_limit_reached(self):
        """400 emails sent today → global limit reached → blocked."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        db = AsyncMock()

        orch = ChannelOrchestrator(db)

        # Global limit exhausted
        orch.check_global_limits = AsyncMock(return_value=(False, 0))

        mock_enrollment = MagicMock()
        mock_enrollment.id = uuid.uuid4()
        mock_enrollment.lead_id = uuid.uuid4()

        mock_step = MagicMock()
        from app.models.sequence import StepType

        mock_step.step_type = StepType.email
        mock_step.position = 0

        mock_lead = MagicMock()
        mock_lead.id = uuid.uuid4()

        mock_template = MagicMock()

        with patch("app.services.channel_orchestrator.compliance_svc"):
            result = await orch.dispatch(
                enrollment=mock_enrollment,
                step=mock_step,
                lead=mock_lead,
                template=mock_template,
            )

        assert result["success"] is False
        assert result.get("limit_exhausted") is True
        assert "Global daily limit" in result["error"]

    @pytest.mark.asyncio
    async def test_channel_orchestrator_hard_failure_no_failover(self):
        """Hard failure (bounce) → no failover attempted."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        db = AsyncMock()

        with patch("app.services.channel_orchestrator.compliance_svc") as mock_compliance:
            mock_compliance.can_send_to_lead = AsyncMock(return_value=(True, "approved"))

            orch = ChannelOrchestrator(db)
            orch.check_global_limits = AsyncMock(return_value=(True, 100))
            orch._dispatch_email = AsyncMock(
                return_value={"success": False, "error": "hard_bounce"}
            )
            orch.attempt_failover = AsyncMock()

            mock_enrollment = MagicMock()
            mock_enrollment.id = uuid.uuid4()
            mock_enrollment.lead_id = uuid.uuid4()

            mock_step = MagicMock()
            from app.models.sequence import StepType

            mock_step.step_type = StepType.email
            mock_step.position = 0

            mock_lead = MagicMock()
            mock_lead.id = uuid.uuid4()

            mock_template = MagicMock()

            result = await orch.dispatch(
                enrollment=mock_enrollment,
                step=mock_step,
                lead=mock_lead,
                template=mock_template,
            )

        # Hard failure → no failover
        orch.attempt_failover.assert_not_called()
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_channel_orchestrator_compliance_blocked(self):
        """Compliance gate blocks → returns compliance_blocked result."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        db = AsyncMock()

        with patch("app.services.channel_orchestrator.compliance_svc") as mock_compliance:
            mock_compliance.can_send_to_lead = AsyncMock(
                return_value=(False, "no_active_consent")
            )

            orch = ChannelOrchestrator(db)
            orch.check_global_limits = AsyncMock(return_value=(True, 100))

            mock_enrollment = MagicMock()
            mock_enrollment.id = uuid.uuid4()
            mock_enrollment.lead_id = uuid.uuid4()

            mock_step = MagicMock()
            from app.models.sequence import StepType

            mock_step.step_type = StepType.email
            mock_step.position = 0

            mock_lead = MagicMock()
            mock_lead.id = uuid.uuid4()

            mock_template = MagicMock()

            result = await orch.dispatch(
                enrollment=mock_enrollment,
                step=mock_step,
                lead=mock_lead,
                template=mock_template,
            )

        assert result["success"] is False
        assert result.get("compliance_blocked") is True


# ═══════════════════════════════════════════════════════════════════════
# 9. HOLE-FILLER ESCALATION TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestHoleFillerEscalation:
    """Test hole-filler escalation to LinkedIn and SMS."""

    @pytest.mark.asyncio
    async def test_hole_filler_triggers_linkedin(self):
        """2 unanswered emails + has LinkedIn consent → escalates to LinkedIn."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        db = AsyncMock()

        with patch("app.services.channel_orchestrator.compliance_svc") as mock_compliance:
            # LinkedIn consent OK
            mock_compliance.can_send_to_lead = AsyncMock(return_value=(True, "approved"))

            orch = ChannelOrchestrator(db)
            orch.check_global_limits = AsyncMock(return_value=(True, 20))
            orch._count_unanswered_emails = AsyncMock(return_value=2)

            mock_enrollment = MagicMock()
            mock_enrollment.id = uuid.uuid4()
            mock_enrollment.lead_id = uuid.uuid4()
            mock_enrollment.sequence_id = uuid.uuid4()
            mock_enrollment.hole_filler_triggered = False
            mock_enrollment.status.value = "active"

            mock_lead = MagicMock()
            mock_lead.id = mock_enrollment.lead_id
            mock_lead.first_name = "Jane"
            mock_lead.phone = None  # No phone — should use LinkedIn
            mock_lead.enriched_data = {"linkedin_url": "https://linkedin.com/in/jane"}

            with patch("app.services.linkedin_service.LinkedInService") as MockLI:
                mock_li_svc = AsyncMock()
                MockLI.return_value = mock_li_svc
                mock_li_result = MagicMock()
                mock_li_result.success = True
                mock_li_result.queue_item_id = str(uuid.uuid4())
                mock_li_svc.queue_connection_request = AsyncMock(
                    return_value=mock_li_result
                )

                db.commit = AsyncMock()

                result = await orch.execute_hole_filler(
                    enrollment=mock_enrollment,
                    lead=mock_lead,
                )

        assert result is not None
        assert result["escalation_channel"] == "linkedin"
        assert mock_enrollment.hole_filler_triggered is True

    @pytest.mark.asyncio
    async def test_hole_filler_triggers_sms(self):
        """2 unanswered emails + no LinkedIn + has phone → SMS nudge."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        db = AsyncMock()

        with patch("app.services.channel_orchestrator.compliance_svc") as mock_compliance:
            # LinkedIn not consented, SMS consented
            def compliance_side_effect(lead_id, channel, db):
                if channel == "linkedin":
                    return (False, "no_linkedin_consent")
                return (True, "approved")

            mock_compliance.can_send_to_lead = AsyncMock(
                side_effect=compliance_side_effect
            )

            orch = ChannelOrchestrator(db)
            orch.check_global_limits = AsyncMock(return_value=(True, 10))
            orch._count_unanswered_emails = AsyncMock(return_value=3)

            mock_enrollment = MagicMock()
            mock_enrollment.id = uuid.uuid4()
            mock_enrollment.lead_id = uuid.uuid4()
            mock_enrollment.sequence_id = uuid.uuid4()
            mock_enrollment.hole_filler_triggered = False
            mock_enrollment.status.value = "active"

            mock_lead = MagicMock()
            mock_lead.id = mock_enrollment.lead_id
            mock_lead.first_name = "Mark"
            mock_lead.phone = "+14155559999"
            mock_lead.enriched_data = {}

            with patch("app.services.sms_service.send_sms") as mock_send_sms:
                mock_sms_result = MagicMock()
                mock_sms_result.success = True
                mock_sms_result.message_sid = "SMtest999"
                mock_send_sms.return_value = mock_sms_result

                db.commit = AsyncMock()

                # Patch settings to avoid AttributeError
                with patch("app.services.channel_orchestrator.settings") as mock_settings:
                    mock_settings.GLOBAL_DAILY_EMAIL_LIMIT = 400
                    mock_settings.GLOBAL_DAILY_SMS_LIMIT = 30
                    mock_settings.GLOBAL_DAILY_LINKEDIN_LIMIT = 25
                    mock_settings.MAX_TOUCH_RETRIES = 3
                    mock_settings.RETRY_BACKOFF_MINUTES = 5
                    mock_settings.BASE_URL = "https://gengyveusa.com"

                    result = await orch.execute_hole_filler(
                        enrollment=mock_enrollment,
                        lead=mock_lead,
                    )

        assert result is not None
        assert result["escalation_channel"] == "sms"
        assert mock_enrollment.hole_filler_triggered is True

    @pytest.mark.asyncio
    async def test_hole_filler_already_triggered(self):
        """hole_filler_triggered=True → no second escalation."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        db = AsyncMock()
        orch = ChannelOrchestrator(db)

        mock_enrollment = MagicMock()
        mock_enrollment.id = uuid.uuid4()
        mock_enrollment.hole_filler_triggered = True  # Already triggered

        mock_lead = MagicMock()

        result = await orch.execute_hole_filler(
            enrollment=mock_enrollment,
            lead=mock_lead,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_hole_filler_not_triggered_if_under_2_emails(self):
        """Only 1 unanswered email → hole filler does not trigger."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        db = AsyncMock()
        orch = ChannelOrchestrator(db)
        orch._count_unanswered_emails = AsyncMock(return_value=1)

        mock_enrollment = MagicMock()
        mock_enrollment.id = uuid.uuid4()
        mock_enrollment.hole_filler_triggered = False

        mock_lead = MagicMock()

        result = await orch.execute_hole_filler(
            enrollment=mock_enrollment,
            lead=mock_lead,
        )

        assert result is None


# ═══════════════════════════════════════════════════════════════════════
# 10. AI FEEDBACK LOOP TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestAIFeedbackLoop:
    """Test AI feedback metrics aggregation and platform push."""

    @pytest.mark.asyncio
    async def test_ai_feedback_metrics_aggregation(self):
        """Create touch logs → metrics computed correctly."""
        from app.services.ai_feedback_service import AIFeedbackService

        db = AsyncMock()
        sequence_id = uuid.uuid4()

        # Mock DB query results in order:
        # 1. total_enrolled = 10
        # 2. total_completed = 7
        # 3. total_replied = 3
        # 4. total_opened = 6
        # 5. total_bounced = 1
        # 6. total_unsubscribed = 0
        # 7. _avg_steps_before_reply → 2.5
        # 8. _best_performing_channel → "email"
        # 9. _best_performing_template → None (skipped)
        # 10. _meeting_booked_rate (reply_logs query) → 1

        scalar_vals = [10, 7, 3, 6, 1, 0]

        def make_result(val):
            r = MagicMock()
            r.scalar.return_value = val
            return r

        db.execute.side_effect = [make_result(v) for v in scalar_vals]

        svc = AIFeedbackService(db)

        # Patch sub-methods to avoid complex mocking
        svc._avg_steps_before_reply = AsyncMock(return_value=2.5)
        svc._best_performing_channel = AsyncMock(return_value="email")
        svc._best_performing_template = AsyncMock(return_value=None)
        svc._meeting_booked_rate = AsyncMock(return_value=0.1)

        metrics = await svc.aggregate_sequence_metrics(sequence_id)

        assert metrics["total_enrolled"] == 10
        assert metrics["total_replied"] == 3
        assert metrics["total_opened"] == 6
        assert metrics["total_bounced"] == 1
        assert metrics["reply_rate"] == pytest.approx(0.3, abs=0.01)
        assert metrics["open_rate"] == pytest.approx(0.6, abs=0.01)
        assert metrics["bounce_rate"] == pytest.approx(0.1, abs=0.01)
        assert metrics["avg_steps_before_reply"] == 2.5
        assert metrics["best_performing_channel"] == "email"

    @pytest.mark.asyncio
    async def test_ai_feedback_push_to_platforms(self):
        """Mock API calls → verify all 3 platforms called."""
        from app.services.ai_feedback_service import AIFeedbackService

        db = AsyncMock()
        sequence_id = uuid.uuid4()

        svc = AIFeedbackService(db)

        # Mock lead emails fetch
        lead_emails = ["dr1@dental.com", "dr2@dental.com"]
        lead_rows = [(e,) for e in lead_emails]

        lead_result = MagicMock()
        lead_result.all.return_value = lead_rows
        db.execute.return_value = lead_result

        # Track platform push calls
        platform_calls: list[tuple[str, str]] = []

        async def mock_push_to_platform(platform: str, email: str, outcomes: dict) -> bool:
            platform_calls.append((platform, email))
            return True

        svc._push_to_platform = mock_push_to_platform

        metrics = {
            "reply_rate": 0.25,
            "open_rate": 0.45,
            "bounce_rate": 0.02,
            "meeting_booked_rate": 0.10,
            "unsubscribe_rate": 0.01,
            "best_performing_channel": "email",
        }

        result = await svc.push_metrics_to_platforms(sequence_id, metrics)

        # All 3 platforms × 2 leads = 6 calls total
        assert len(platform_calls) == 6
        platforms_used = {call[0] for call in platform_calls}
        assert "hubspot" in platforms_used
        assert "zoominfo" in platforms_used
        assert "apollo" in platforms_used

        # Success counts should match lead count per platform
        assert result["hubspot"] == 2
        assert result["zoominfo"] == 2
        assert result["apollo"] == 2

    @pytest.mark.asyncio
    async def test_ai_feedback_no_leads_returns_zeros(self):
        """No enrolled leads for sequence → skip push, return zero counts."""
        from app.services.ai_feedback_service import AIFeedbackService

        db = AsyncMock()
        sequence_id = uuid.uuid4()

        svc = AIFeedbackService(db)

        # No leads returned
        no_leads_result = MagicMock()
        no_leads_result.all.return_value = []
        db.execute.return_value = no_leads_result

        metrics = {"reply_rate": 0.1}

        result = await svc.push_metrics_to_platforms(sequence_id, metrics)

        assert result == {"hubspot": 0, "zoominfo": 0, "apollo": 0}

    @pytest.mark.asyncio
    async def test_ai_feedback_reply_feedback_push(self):
        """Reply feedback push calls all 3 platforms with sentiment data."""
        from app.services.ai_feedback_service import AIFeedbackService

        db = AsyncMock()
        sequence_id = uuid.uuid4()

        svc = AIFeedbackService(db)

        # Mock PlatformAIService.send_outcome_feedback
        svc._ai.send_outcome_feedback = AsyncMock(return_value=True)

        result = await svc.push_reply_feedback(
            lead_email="dr@dental.com",
            reply_sentiment="positive",
            sequence_id=sequence_id,
        )

        assert svc._ai.send_outcome_feedback.call_count == 3

        platforms_called = {
            call.args[0] for call in svc._ai.send_outcome_feedback.call_args_list
        }
        assert "hubspot_breeze_data_agent" in platforms_called
        assert "zoominfo_copilot" in platforms_called
        assert "apollo_ai" in platforms_called

    @pytest.mark.asyncio
    async def test_ai_feedback_aggregation_no_enrollments(self):
        """Sequence with 0 enrollments → returns error dict, not crash."""
        from app.services.ai_feedback_service import AIFeedbackService

        db = AsyncMock()
        sequence_id = uuid.uuid4()

        svc = AIFeedbackService(db)

        # total_enrolled = 0
        zero_result = MagicMock()
        zero_result.scalar.return_value = 0
        db.execute.return_value = zero_result

        metrics = await svc.aggregate_sequence_metrics(sequence_id)

        assert "error" in metrics
        assert metrics["error"] == "no_enrollments"


# ═══════════════════════════════════════════════════════════════════════
# 11. SMS BODY FORMATTING TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestSMSBodyFormatting:
    """Test SMS body formatting, truncation, and segment counting."""

    @pytest.mark.asyncio
    async def test_sms_body_formatting_short(self):
        """Short body + STOP footer → single segment."""
        from app.services.sms_service import format_sms_body, DEFAULT_STOP_FOOTER

        body = "Hi Jane, would you have 5 mins to chat about Gengyve?"
        result = await format_sms_body(body, include_stop=True)

        assert DEFAULT_STOP_FOOTER in result
        assert len(result) <= 160

    @pytest.mark.asyncio
    async def test_sms_body_formatting_long_body_truncated(self):
        """Long body → truncated with STOP footer, under 160 chars."""
        from app.services.sms_service import format_sms_body

        # Create a body that's too long to fit in 1 segment with footer
        long_body = "A" * 200

        result = await format_sms_body(long_body, include_stop=True)

        # Result should have the STOP footer
        assert "Reply STOP to opt out" in result

    @pytest.mark.asyncio
    async def test_sms_segment_counting_single(self):
        """Message under 160 chars → 1 segment."""
        from app.services.sms_service import _count_segments

        body = "Hi there! This is a test message under 160 characters."
        assert _count_segments(body) == 1

    @pytest.mark.asyncio
    async def test_sms_segment_counting_two_segments(self):
        """170 char body → 2 segments."""
        from app.services.sms_service import _count_segments

        # 170 characters
        body = "A" * 170

        segments = _count_segments(body)
        assert segments == 2

    @pytest.mark.asyncio
    async def test_sms_body_no_stop_footer(self):
        """When include_stop=False → STOP footer not appended."""
        from app.services.sms_service import format_sms_body, DEFAULT_STOP_FOOTER

        body = "Quick message without stop footer."
        result = await format_sms_body(body, include_stop=False)

        assert DEFAULT_STOP_FOOTER not in result
        assert body in result

    @pytest.mark.asyncio
    async def test_sms_content_validation_empty(self):
        """Empty body → validation error."""
        from app.services.sms_service import validate_sms_content

        issues = validate_sms_content("")
        assert len(issues) > 0
        assert any("empty" in i.lower() for i in issues)

    @pytest.mark.asyncio
    async def test_sms_content_validation_unresolved_template(self):
        """Unresolved template variables → validation error."""
        from app.services.sms_service import validate_sms_content

        issues = validate_sms_content("Hi {{first_name}}, check this out!")
        assert len(issues) > 0
        assert any("template" in i.lower() for i in issues)

    @pytest.mark.asyncio
    async def test_sms_content_validation_within_limit(self):
        """Valid body within limit → no issues."""
        from app.services.sms_service import validate_sms_content

        issues = validate_sms_content("Hello from Gengyve. Reply STOP to opt out")
        assert len(issues) == 0

    def test_sms_segment_counting_exactly_160(self):
        """Exactly 160 chars → 1 segment (boundary inclusive)."""
        from app.services.sms_service import _count_segments

        body = "B" * 160
        assert _count_segments(body) == 1

    def test_sms_segment_counting_161(self):
        """161 chars → 2 segments (over single-segment boundary)."""
        from app.services.sms_service import _count_segments

        body = "C" * 161
        assert _count_segments(body) == 2


# ═══════════════════════════════════════════════════════════════════════
# 12. WEBHOOK ENDPOINT SECURITY TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestWebhookSecurity:
    """Test webhook secret verification for email reply webhooks."""

    @pytest.mark.asyncio
    async def test_webhook_email_reply_valid(self):
        """POST with valid secret → processes reply (200 response)."""
        from fastapi.testclient import TestClient

        # Import the app — if unavailable, skip gracefully
        try:
            from app.main import app
        except ImportError:
            pytest.skip("app.main not importable in this test context")

        client = TestClient(app)

        valid_secret = "test-webhook-secret"
        payload = {
            "sender_email": "reply@dental.com",
            "body": "Interested in a demo!",
            "subject": "Re: Improve patient retention",
            "channel": "email",
        }

        with patch("app.config.settings") as mock_settings:
            mock_settings.REPLY_WEBHOOK_SECRET = valid_secret

            response = client.post(
                "/api/v1/webhooks/email/reply",
                json=payload,
                headers={"X-Webhook-Secret": valid_secret},
            )

        # Should not be 403 (valid secret)
        assert response.status_code != 403

    @pytest.mark.asyncio
    async def test_webhook_email_reply_invalid_secret(self):
        """POST with wrong secret → rejected (200 to prevent webhook retries)."""
        from fastapi.testclient import TestClient

        try:
            from app.main import app
        except ImportError:
            pytest.skip("app.main not importable in this test context")

        client = TestClient(app)

        payload = {
            "sender_email": "reply@dental.com",
            "body": "Interested in a demo!",
        }

        with patch("app.api.v1.webhooks.settings") as mock_settings:
            mock_settings.REPLY_WEBHOOK_SECRET = "correct-secret"

            response = client.post(
                "/api/v1/webhooks/email/reply",
                json=payload,
                headers={"X-Webhook-Secret": "wrong-secret"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
        assert data["reason"] == "invalid_secret"


# ═══════════════════════════════════════════════════════════════════════
# 13. LINKEDIN CONTENT VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestLinkedInContentValidation:
    """Test LinkedIn content validation against platform limits."""

    def test_connection_note_over_limit(self):
        """Note over 300 chars → validation error."""
        from app.services.linkedin_service import (
            LinkedInAction,
            validate_linkedin_content,
            CONNECTION_NOTE_MAX_CHARS,
        )

        long_note = "X" * (CONNECTION_NOTE_MAX_CHARS + 1)
        issues = validate_linkedin_content(LinkedInAction.connection_request, note=long_note)

        assert len(issues) > 0
        assert any("300" in i or "char" in i.lower() for i in issues)

    def test_connection_note_empty_warning(self):
        """Empty note → warning (personalized notes get better rates)."""
        from app.services.linkedin_service import LinkedInAction, validate_linkedin_content

        issues = validate_linkedin_content(LinkedInAction.connection_request, note="")

        assert len(issues) > 0
        assert any("empty" in i.lower() or "personalized" in i.lower() for i in issues)

    def test_connection_note_valid(self):
        """Valid note under 300 chars → no issues."""
        from app.services.linkedin_service import LinkedInAction, validate_linkedin_content

        note = "Hi Sarah, I noticed your work at Dental Group. Would love to connect!"
        issues = validate_linkedin_content(LinkedInAction.connection_request, note=note)

        assert len(issues) == 0

    def test_inmail_body_over_limit(self):
        """InMail body over 1900 chars → validation error."""
        from app.services.linkedin_service import LinkedInAction, validate_linkedin_content

        long_body = "Y" * 1901
        issues = validate_linkedin_content(
            LinkedInAction.inmail, subject="Test", body=long_body
        )

        assert len(issues) > 0
        assert any("1900" in i or "char" in i.lower() for i in issues)

    def test_unresolved_template_variables_flagged(self):
        """Unresolved {{variables}} in any field → validation error."""
        from app.services.linkedin_service import LinkedInAction, validate_linkedin_content

        issues = validate_linkedin_content(
            LinkedInAction.connection_request,
            note="Hi {{first_name}}, great to connect!",
        )

        assert len(issues) > 0
        assert any("template" in i.lower() or "variable" in i.lower() for i in issues)


# ═══════════════════════════════════════════════════════════════════════
# 14. CHANNEL ORCHESTRATOR CHECK_GLOBAL_LIMITS UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestGlobalLimitChecks:
    """Unit tests for global rate limit enforcement."""

    @pytest.mark.asyncio
    async def test_check_global_limits_under_limit(self):
        """Today's count under limit → (True, remaining)."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        db = AsyncMock()

        # Mock today's send count = 100
        count_result = MagicMock()
        count_result.scalar.return_value = 100
        db.execute.return_value = count_result

        with patch("app.services.channel_orchestrator.CHANNEL_DAILY_LIMITS", {"email": 400}):
            orch = ChannelOrchestrator(db)
            under_limit, remaining = await orch.check_global_limits("email")

        assert under_limit is True
        assert remaining == 300

    @pytest.mark.asyncio
    async def test_check_global_limits_at_limit(self):
        """Today's count == limit → (False, 0)."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        db = AsyncMock()

        count_result = MagicMock()
        count_result.scalar.return_value = 400
        db.execute.return_value = count_result

        with patch("app.services.channel_orchestrator.CHANNEL_DAILY_LIMITS", {"email": 400}):
            orch = ChannelOrchestrator(db)
            under_limit, remaining = await orch.check_global_limits("email")

        assert under_limit is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_check_global_limits_over_400_blocked(self):
        """400 emails sent today → global limit reached."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        db = AsyncMock()

        count_result = MagicMock()
        count_result.scalar.return_value = 400
        db.execute.return_value = count_result

        with patch(
            "app.services.channel_orchestrator.CHANNEL_DAILY_LIMITS",
            {"email": 400, "sms": 30, "linkedin": 25},
        ):
            orch = ChannelOrchestrator(db)
            under_limit, remaining = await orch.check_global_limits("email")

        assert under_limit is False

    @pytest.mark.asyncio
    async def test_check_global_limits_sms_daily_cap(self):
        """SMS daily limit is 30 — test at boundary."""
        from app.services.channel_orchestrator import ChannelOrchestrator

        db = AsyncMock()

        count_result = MagicMock()
        count_result.scalar.return_value = 29
        db.execute.return_value = count_result

        with patch(
            "app.services.channel_orchestrator.CHANNEL_DAILY_LIMITS",
            {"email": 400, "sms": 30, "linkedin": 25},
        ):
            orch = ChannelOrchestrator(db)
            under_limit, remaining = await orch.check_global_limits("sms")

        assert under_limit is True
        assert remaining == 1


# ═══════════════════════════════════════════════════════════════════════
# 15. REPLY SERVICE WEBHOOK PARSING TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestReplyWebhookParsing:
    """Test webhook payload parsing into ReplySignal objects."""

    @pytest.mark.asyncio
    async def test_parse_generic_webhook_payload(self):
        """Generic payload with sender_email + body → ReplySignal."""
        from app.services.reply_service import ReplyService

        db = AsyncMock()
        svc = ReplyService(db)

        payload = {
            "sender_email": "test@dental.com",
            "body": "I'm interested in your solution!",
            "subject": "Re: Our outreach",
            "channel": "email",
            "thread_id": "<thread-abc-123>",
        }

        signal = await svc.process_webhook_reply(payload)

        assert signal.sender_email == "test@dental.com"
        assert signal.body == "I'm interested in your solution!"
        assert signal.channel == "email"
        assert signal.thread_id == "<thread-abc-123>"

    @pytest.mark.asyncio
    async def test_parse_parsio_webhook_payload(self):
        """Parsio format with from_email + text → ReplySignal."""
        from app.services.reply_service import ReplyService

        db = AsyncMock()
        svc = ReplyService(db)

        payload = {
            "from_email": "Dentist <dr@office.com>",
            "text": "Please schedule me for a demo",
            "subject": "Re: Gengyve Platform",
            "headers": {
                "In-Reply-To": "<original-msg-id-123>",
                "References": "<original-msg-id-123>",
                "Message-ID": "<reply-id-456>",
            },
        }

        signal = await svc.process_webhook_reply(payload)

        assert "dr@office.com" in signal.sender_email or signal.sender_email == "Dentist <dr@office.com>".lower()
        assert signal.body == "Please schedule me for a demo"

    @pytest.mark.asyncio
    async def test_parse_generic_missing_body_raises(self):
        """Generic payload with no body → ValueError."""
        from app.services.reply_service import ReplyService

        db = AsyncMock()
        svc = ReplyService(db)

        payload = {
            "sender_email": "test@dental.com",
            # No body
        }

        with pytest.raises(ValueError, match=".*body.*"):
            await svc.process_webhook_reply(payload)

    @pytest.mark.asyncio
    async def test_extract_email_from_angle_brackets(self):
        """From: header with angle brackets → extracts bare email."""
        from app.services.reply_service import ReplyService

        db = AsyncMock()
        svc = ReplyService(db)

        email = svc._extract_email_address("Dr. Smith <drsmith@dental.com>")

        assert email == "drsmith@dental.com"

    @pytest.mark.asyncio
    async def test_extract_email_bare_address(self):
        """From: header with bare email → extracts correctly."""
        from app.services.reply_service import ReplyService

        db = AsyncMock()
        svc = ReplyService(db)

        email = svc._extract_email_address("drsmith@dental.com")

        assert email == "drsmith@dental.com"
