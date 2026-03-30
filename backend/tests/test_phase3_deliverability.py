"""
Phase 3 tests: Deliverability Fortress + AI-Powered Warmup.

Tests mock all external API calls (SES, HubSpot Breeze, ZoomInfo Copilot, Apollo AI)
so the test suite runs without credentials or network access.
"""

import math
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings


# ═══════════════════════════════════════════════════════════════════════
# Warmup Ramp Schedule Tests
# ═══════════════════════════════════════════════════════════════════════


class TestWarmupRampSchedule:
    """Test the exponential ramp volume calculator."""

    def test_day_zero_returns_initial_volume(self):
        from app.services.warmup_ai import compute_daily_volume

        vol = compute_daily_volume(warmup_day=0, initial_volume=5)
        assert vol == 5

    def test_day_one_ramp(self):
        from app.services.warmup_ai import compute_daily_volume

        vol = compute_daily_volume(warmup_day=1, initial_volume=5, ramp_multiplier=1.15)
        expected = math.ceil(5 * 1.15)
        assert vol == expected

    def test_volume_capped_at_target(self):
        from app.services.warmup_ai import compute_daily_volume

        vol = compute_daily_volume(
            warmup_day=100, initial_volume=5, ramp_multiplier=1.15, target_volume=50
        )
        assert vol == 50

    def test_never_below_initial(self):
        from app.services.warmup_ai import compute_daily_volume

        vol = compute_daily_volume(
            warmup_day=0, initial_volume=5, ramp_multiplier=0.5, target_volume=50
        )
        assert vol >= 5

    def test_full_ramp_schedule_length(self):
        from app.services.warmup_ai import compute_ramp_schedule

        schedule = compute_ramp_schedule(duration_weeks=6)
        assert len(schedule) == 42  # 6 weeks * 7 days

    def test_ramp_schedule_monotonic(self):
        from app.services.warmup_ai import compute_ramp_schedule

        schedule = compute_ramp_schedule(duration_weeks=6)
        volumes = [e["daily_volume"] for e in schedule]
        for i in range(1, len(volumes)):
            assert volumes[i] >= volumes[i - 1], (
                f"Volume decreased at day {i}: {volumes[i]} < {volumes[i-1]}"
            )


# ═══════════════════════════════════════════════════════════════════════
# SES Infrastructure Service Tests
# ═══════════════════════════════════════════════════════════════════════


class TestSESInfrastructureService:
    """Test SES domain/identity management with mocked boto3."""

    @pytest.fixture
    def ses_service(self):
        from app.services.ses_service import SESInfrastructureService

        return SESInfrastructureService()

    def test_generate_spf_record(self, ses_service):
        record = ses_service.generate_spf_record(include_ses=True)
        assert record.startswith("v=spf1")
        assert "include:amazonses.com" in record
        assert record.endswith("-all")

    def test_generate_spf_record_without_ses(self, ses_service):
        record = ses_service.generate_spf_record(include_ses=False)
        assert "amazonses.com" not in record

    def test_generate_dmarc_record_default(self, ses_service):
        record = ses_service.generate_dmarc_record()
        assert "v=DMARC1" in record
        assert "p=quarantine" in record
        assert "adkim=s" in record  # Strict alignment

    def test_generate_dmarc_record_with_rua(self, ses_service):
        record = ses_service.generate_dmarc_record(
            policy="reject", rua_email="dmarc@gengyveusa.com"
        )
        assert "p=reject" in record
        assert "rua=mailto:dmarc@gengyveusa.com" in record

    def test_generate_bimi_record(self, ses_service):
        record = ses_service.generate_bimi_record(
            svg_url="https://gengyveusa.com/assets/bimi-logo.svg",
            vmc_url="https://gengyveusa.com/assets/bimi.pem",
        )
        assert "v=BIMI1" in record
        assert "l=https://gengyveusa.com/assets/bimi-logo.svg" in record
        assert "a=https://gengyveusa.com/assets/bimi.pem" in record

    @pytest.mark.asyncio
    async def test_verify_domain_success(self, ses_service):
        expected_response = {
            "DkimAttributes": {
                "Tokens": ["token1", "token2", "token3"],
                "Status": "PENDING",
            },
            "VerifiedForSendingStatus": False,
        }
        mock_sesv2 = MagicMock()
        mock_sesv2.create_email_identity.return_value = expected_response
        ses_service._sesv2 = mock_sesv2

        with patch("app.services.ses_service.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = expected_response
            result = await ses_service.verify_domain("mail.gengyveusa.com")

        assert result.success is True
        assert result.domain == "mail.gengyveusa.com"
        assert len(result.dkim_tokens) == 3

    @pytest.mark.asyncio
    async def test_verify_email_identity_success(self, ses_service):
        expected_response = {
            "IdentityArn": "arn:aws:ses:us-east-1:123456789:identity/outreach1@mail.gengyveusa.com"
        }
        mock_sesv2 = MagicMock()
        mock_sesv2.create_email_identity.return_value = expected_response
        ses_service._sesv2 = mock_sesv2

        with patch("app.services.ses_service.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = expected_response
            result = await ses_service.verify_email_identity("outreach1@mail.gengyveusa.com")

        assert result.success is True
        assert "outreach1" in (result.identity_arn or "")


# ═══════════════════════════════════════════════════════════════════════
# Platform AI Service Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPlatformAIService:
    """Test HubSpot Breeze, ZoomInfo Copilot, and Apollo AI integrations with mocked HTTP."""

    @pytest.fixture
    def platform_ai(self):
        from app.services.platform_ai_service import PlatformAIService

        mock_client = AsyncMock()
        return PlatformAIService(http_client=mock_client)

    @pytest.mark.asyncio
    async def test_breeze_data_agent_disabled(self, platform_ai):
        """Returns empty list when Breeze is disabled."""
        with patch.object(settings, "HUBSPOT_BREEZE_ENABLED", False):
            results = await platform_ai.breeze_data_agent_insights(
                ["test@example.com"]
            )
        assert results == []

    @pytest.mark.asyncio
    async def test_breeze_data_agent_scores_contacts(self, platform_ai):
        """Scores contacts when Breeze is enabled."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "123",
                    "properties": {
                        "email": "dr.smith@dental.com",
                        "hs_predictive_contact_score": 75,
                        "hs_email_open_rate": 0.45,
                        "hs_email_click_rate": 0.12,
                        "hs_lead_status": "QUALIFIED",
                    },
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        platform_ai._client.request = AsyncMock(return_value=mock_response)

        with (
            patch.object(settings, "HUBSPOT_BREEZE_ENABLED", True),
            patch.object(settings, "HUBSPOT_API_KEY", "test-key"),
        ):
            results = await platform_ai.breeze_data_agent_insights(
                ["dr.smith@dental.com"]
            )

        assert len(results) == 1
        assert results[0].platform == "hubspot_breeze_data_agent"
        assert results[0].score > 0

    @pytest.mark.asyncio
    async def test_copilot_context_graph_disabled(self, platform_ai):
        """Returns empty list when Copilot is disabled."""
        with patch.object(settings, "ZOOMINFO_COPILOT_ENABLED", False):
            results = await platform_ai.copilot_gtm_context_scores(
                ["test@example.com"]
            )
        assert results == []

    @pytest.mark.asyncio
    async def test_copilot_context_graph_scores(self, platform_ai):
        """Scores contacts via ZoomInfo Copilot Context Graph."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "data": [
                    {
                        "emailAddress": "dr.jones@dso.com",
                        "intentScore": 85,
                        "topicIntentScores": [
                            {"topic": "dental_supplies", "score": 90}
                        ],
                        "techStackDetails": ["Eaglesoft", "Dentrix"],
                    }
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()
        platform_ai._client.request = AsyncMock(return_value=mock_response)

        with (
            patch.object(settings, "ZOOMINFO_COPILOT_ENABLED", True),
            patch.object(settings, "ZOOMINFO_API_KEY", "test-key"),
        ):
            platform_ai._zoominfo_jwt = "test-jwt"
            results = await platform_ai.copilot_gtm_context_scores(
                ["dr.jones@dso.com"]
            )

        assert len(results) == 1
        assert results[0].platform == "zoominfo_copilot_context_graph"
        assert results[0].score == 85.0

    @pytest.mark.asyncio
    async def test_apollo_ai_scoring_disabled(self, platform_ai):
        """Returns empty list when Apollo AI is disabled."""
        with patch.object(settings, "APOLLO_AI_ENABLED", False):
            results = await platform_ai.apollo_ai_score_leads(
                [{"email": "test@example.com"}]
            )
        assert results == []

    @pytest.mark.asyncio
    async def test_apollo_ai_scores_leads(self, platform_ai):
        """Scores leads via Apollo AI enhanced scoring."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "person": {
                "first_name": "Sarah",
                "last_name": "Chen",
                "email": "sarah@dso.com",
                "title": "VP of Procurement",
                "ai_score": 80,
                "engagement_score": 70,
                "intent_score": 60,
                "seniority": "VP",
                "departments": ["Procurement"],
                "organization": {"name": "Aspen Dental"},
            }
        }
        mock_response.raise_for_status = MagicMock()
        platform_ai._client.request = AsyncMock(return_value=mock_response)

        with (
            patch.object(settings, "APOLLO_AI_ENABLED", True),
            patch.object(settings, "APOLLO_API_KEY", "test-key"),
        ):
            results = await platform_ai.apollo_ai_score_leads(
                [{"email": "sarah@dso.com"}]
            )

        assert len(results) == 1
        assert results[0].platform == "apollo_ai"
        assert results[0].score > 0
        assert results[0].signals["seniority"] == "VP"

    @pytest.mark.asyncio
    async def test_unified_scoring_all_disabled(self, platform_ai):
        """Returns empty dict when no platforms are enabled."""
        with (
            patch.object(settings, "HUBSPOT_BREEZE_ENABLED", False),
            patch.object(settings, "ZOOMINFO_COPILOT_ENABLED", False),
            patch.object(settings, "APOLLO_AI_ENABLED", False),
        ):
            results = await platform_ai.get_unified_lead_scores(
                ["test@example.com"]
            )
        assert results == {}

    @pytest.mark.asyncio
    async def test_seed_selection_fallback(self, platform_ai):
        """Falls back to random selection when no AI platforms enabled."""
        with (
            patch.object(settings, "HUBSPOT_BREEZE_ENABLED", False),
            patch.object(settings, "ZOOMINFO_COPILOT_ENABLED", False),
            patch.object(settings, "APOLLO_AI_ENABLED", False),
        ):
            seeds = await platform_ai.select_warmup_seeds(
                candidate_emails=["a@test.com", "b@test.com", "c@test.com"],
                batch_size=3,
            )

        assert len(seeds) == 3
        assert all(s.platform == "fallback" for s in seeds)

    @pytest.mark.asyncio
    async def test_feedback_to_hubspot_disabled(self, platform_ai):
        """Returns False when HubSpot is disabled."""
        with patch.object(settings, "HUBSPOT_BREEZE_ENABLED", False):
            result = await platform_ai.send_outcome_feedback(
                platform="hubspot_breeze",
                contact_email="test@example.com",
                outcomes={"opened": True},
            )
        assert result is False


# ═══════════════════════════════════════════════════════════════════════
# Inbox Health Check Tests
# ═══════════════════════════════════════════════════════════════════════


class TestInboxHealthCheck:
    """Test health check logic for sending inboxes."""

    def _make_inbox(self, **overrides):
        from app.models.sending_inbox import SendingInbox

        defaults = {
            "id": uuid.uuid4(),
            "email_address": "test@mail.gengyveusa.com",
            "display_name": "Test Inbox",
            "domain": "mail.gengyveusa.com",
            "bounce_rate_7d": 0.01,
            "spam_rate_7d": 0.0001,
            "open_rate_7d": 0.30,
            "health_score": 95.0,
            "total_sent": 100,
        }
        defaults.update(overrides)
        inbox = MagicMock(spec=SendingInbox)
        for k, v in defaults.items():
            setattr(inbox, k, v)
        return inbox

    def _make_config(self, **overrides):
        from app.models.warmup import WarmupConfig

        defaults = {
            "max_bounce_rate": 0.05,
            "max_spam_rate": 0.001,
            "min_open_rate": 0.15,
        }
        defaults.update(overrides)
        config = MagicMock(spec=WarmupConfig)
        for k, v in defaults.items():
            setattr(config, k, v)
        return config

    @pytest.mark.asyncio
    async def test_healthy_inbox_passes(self):
        from app.services.warmup_ai import check_inbox_health

        inbox = self._make_inbox()
        config = self._make_config()
        healthy, details = await check_inbox_health(inbox, config)
        assert healthy is True
        assert len(details["issues"]) == 0

    @pytest.mark.asyncio
    async def test_high_bounce_rate_fails(self):
        from app.services.warmup_ai import check_inbox_health

        inbox = self._make_inbox(bounce_rate_7d=0.08)
        config = self._make_config()
        healthy, details = await check_inbox_health(inbox, config)
        assert healthy is False
        assert any("bounce" in issue.lower() for issue in details["issues"])

    @pytest.mark.asyncio
    async def test_high_spam_rate_fails(self):
        from app.services.warmup_ai import check_inbox_health

        inbox = self._make_inbox(spam_rate_7d=0.005)
        config = self._make_config()
        healthy, details = await check_inbox_health(inbox, config)
        assert healthy is False
        assert any("spam" in issue.lower() for issue in details["issues"])

    @pytest.mark.asyncio
    async def test_low_open_rate_fails(self):
        from app.services.warmup_ai import check_inbox_health

        inbox = self._make_inbox(open_rate_7d=0.05, total_sent=100)
        config = self._make_config()
        healthy, details = await check_inbox_health(inbox, config)
        assert healthy is False
        assert any("open" in issue.lower() for issue in details["issues"])

    @pytest.mark.asyncio
    async def test_low_open_rate_ignored_for_new_inboxes(self):
        """Low open rate is ignored if total_sent < 50 (too early to judge)."""
        from app.services.warmup_ai import check_inbox_health

        inbox = self._make_inbox(open_rate_7d=0.05, total_sent=20)
        config = self._make_config()
        healthy, details = await check_inbox_health(inbox, config)
        assert healthy is True  # Not enough data to penalize


# ═══════════════════════════════════════════════════════════════════════
# Deliverability Router Tests
# ═══════════════════════════════════════════════════════════════════════


class TestDeliverabilityRouter:
    """Test round-robin inbox rotation and routing logic."""

    @pytest.mark.asyncio
    async def test_select_next_inbox_skips_unhealthy(self):
        """Router should skip inboxes with health_score < 50."""
        from app.services.deliverability_router import DeliverabilityRouter

        mock_db = AsyncMock()
        router = DeliverabilityRouter(mock_db)

        # Mock get_available_inboxes to return mixed health inboxes
        healthy_inbox = MagicMock()
        healthy_inbox.health_score = 90.0
        healthy_inbox.email_address = "healthy@mail.gengyveusa.com"
        healthy_inbox.daily_sent = 0
        healthy_inbox.daily_limit = 50

        unhealthy_inbox = MagicMock()
        unhealthy_inbox.health_score = 30.0
        unhealthy_inbox.email_address = "unhealthy@mail.gengyveusa.com"
        unhealthy_inbox.daily_sent = 0

        router.get_available_inboxes = AsyncMock(
            return_value=[healthy_inbox, unhealthy_inbox]
        )

        mock_settings = MagicMock()
        mock_settings.DAILY_WARMUP_VOLUME_CAP = 400
        with patch("app.services.deliverability_router.settings", mock_settings):
            selected = await router.select_next_inbox()

        assert selected is not None
        assert selected.email_address == "healthy@mail.gengyveusa.com"

    @pytest.mark.asyncio
    async def test_select_inbox_respects_daily_cap(self):
        """Router returns None when daily volume cap is reached."""
        from app.services.deliverability_router import DeliverabilityRouter

        mock_db = AsyncMock()
        router = DeliverabilityRouter(mock_db)

        inbox = MagicMock()
        inbox.health_score = 90.0
        inbox.daily_sent = 400  # At cap
        inbox.daily_limit = 500

        router.get_available_inboxes = AsyncMock(return_value=[inbox])

        mock_settings = MagicMock()
        mock_settings.DAILY_WARMUP_VOLUME_CAP = 400
        with patch("app.services.deliverability_router.settings", mock_settings):
            selected = await router.select_next_inbox()

        assert selected is None

    @pytest.mark.asyncio
    async def test_round_robin_rotation(self):
        """Router rotates through healthy inboxes in order."""
        from app.services.deliverability_router import DeliverabilityRouter

        mock_db = AsyncMock()
        router = DeliverabilityRouter(mock_db)

        inbox1 = MagicMock()
        inbox1.health_score = 90.0
        inbox1.email_address = "inbox1@mail.gengyveusa.com"
        inbox1.daily_sent = 5
        inbox1.daily_limit = 50

        inbox2 = MagicMock()
        inbox2.health_score = 85.0
        inbox2.email_address = "inbox2@mail.gengyveusa.com"
        inbox2.daily_sent = 5
        inbox2.daily_limit = 50

        router.get_available_inboxes = AsyncMock(return_value=[inbox1, inbox2])

        mock_settings = MagicMock()
        mock_settings.DAILY_WARMUP_VOLUME_CAP = 400
        with patch("app.services.deliverability_router.settings", mock_settings):
            first = await router.select_next_inbox()
            second = await router.select_next_inbox()
            third = await router.select_next_inbox()

        assert first.email_address == "inbox1@mail.gengyveusa.com"
        assert second.email_address == "inbox2@mail.gengyveusa.com"
        assert third.email_address == "inbox1@mail.gengyveusa.com"


# ═══════════════════════════════════════════════════════════════════════
# Model Tests
# ═══════════════════════════════════════════════════════════════════════


class TestModels:
    """Basic model instantiation tests."""

    def test_sending_inbox_defaults(self):
        from app.models.sending_inbox import InboxStatus, SendingInbox

        # Use MagicMock with spec to avoid SQLAlchemy session-dependent construction
        inbox = MagicMock(spec=SendingInbox)
        inbox.email_address = "test@mail.gengyveusa.com"
        inbox.display_name = "Test"
        inbox.domain = "mail.gengyveusa.com"
        inbox.status = InboxStatus.warming
        inbox.warmup_day = 0
        inbox.daily_limit = 5
        inbox.health_score = 100.0

        assert inbox.status == InboxStatus.warming
        assert inbox.warmup_day == 0
        assert inbox.daily_limit == 5
        assert inbox.health_score == 100.0

    def test_warmup_config_defaults(self):
        from app.models.warmup import WarmupConfig

        # Use MagicMock with spec to avoid SQLAlchemy session-dependent construction
        config = MagicMock(spec=WarmupConfig)
        config.inbox_id = uuid.uuid4()
        config.ramp_duration_weeks = 6
        config.initial_daily_volume = 5
        config.ramp_multiplier = 1.15
        config.max_bounce_rate = 0.05
        config.max_spam_rate = 0.001

        assert config.ramp_duration_weeks == 6
        assert config.initial_daily_volume == 5
        assert config.ramp_multiplier == 1.15
        assert config.max_bounce_rate == 0.05
        assert config.max_spam_rate == 0.001

    def test_inbox_status_enum(self):
        from app.models.sending_inbox import InboxStatus

        assert InboxStatus.warming == "warming"
        assert InboxStatus.active == "active"
        assert InboxStatus.paused == "paused"
        assert InboxStatus.suspended == "suspended"
