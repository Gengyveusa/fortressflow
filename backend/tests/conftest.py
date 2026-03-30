"""
Shared pytest fixtures.

All fixtures use in-memory mocks — no real database required.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserRole


# ── Original Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def lead_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_lead(lead_id):
    lead = MagicMock()
    lead.id = lead_id
    lead.email = "test@example.com"
    lead.phone = "+14155552671"
    return lead


@pytest.fixture
def mock_consent(lead_id):
    consent = MagicMock()
    consent.id = uuid.uuid4()
    consent.lead_id = lead_id
    consent.channel = "email"
    consent.method = "web_form"
    consent.proof = {"timestamp": datetime.now(UTC).isoformat(), "source": "test", "ip": "127.0.0.1"}
    consent.granted_at = datetime.now(UTC)
    consent.revoked_at = None
    consent.created_at = datetime.now(UTC)
    return consent


@pytest.fixture
def mock_db():
    """Return a fully-mocked AsyncSession."""
    db = AsyncMock(spec=AsyncSession)
    return db


# ── Phase 6 Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def mock_sequence():
    """A mock Sequence ORM object."""
    seq = MagicMock()
    seq.id = uuid.uuid4()
    seq.name = "Test Q4 Outreach"
    seq.description = "Automated outreach for Q4 pipeline"
    seq.status = "active"
    seq.ai_generated = False
    seq.ai_generation_prompt = None
    seq.ai_generation_metadata = None
    seq.visual_config = None
    seq.steps = []
    seq.enrollments = []
    seq.created_at = datetime.now(UTC)
    seq.updated_at = datetime.now(UTC)
    return seq


@pytest.fixture
def mock_sequence_step(mock_sequence):
    """A mock SequenceStep ORM object."""
    step = MagicMock()
    step.id = uuid.uuid4()
    step.sequence_id = mock_sequence.id
    step.step_type = "email"
    step.position = 0
    step.config = {"template_id": str(uuid.uuid4())}
    step.delay_hours = 0.0
    step.condition = None
    step.true_next_position = None
    step.false_next_position = None
    step.ab_variants = None
    step.is_ab_test = False
    step.node_id = "node-1"
    step.created_at = datetime.now(UTC)
    return step


@pytest.fixture
def mock_enrollment(lead_id, mock_sequence):
    """A mock SequenceEnrollment ORM object."""
    enrollment = MagicMock()
    enrollment.id = uuid.uuid4()
    enrollment.sequence_id = mock_sequence.id
    enrollment.lead_id = lead_id
    enrollment.current_step = 0
    enrollment.status = "active"
    enrollment.last_touch_at = None
    enrollment.last_state_change_at = datetime.now(UTC)
    enrollment.ab_variant_assignments = {}
    enrollment.hole_filler_triggered = False
    enrollment.escalation_channel = None
    enrollment.last_dispatch_id = None
    enrollment.enrolled_at = datetime.now(UTC)
    return enrollment


@pytest.fixture
def mock_reply_log(lead_id, mock_sequence):
    """A mock reply TouchLog entry."""
    log = MagicMock()
    log.id = uuid.uuid4()
    log.lead_id = lead_id
    log.sequence_id = mock_sequence.id
    log.channel = "email"
    log.action = "replied"
    log.extra_metadata = {
        "sentiment": "positive",
        "confidence": 0.85,
        "subject": "Re: Quick question",
    }
    log.created_at = datetime.now(UTC)
    return log


@pytest.fixture
def mock_touch_log(lead_id, mock_sequence):
    """A mock sent TouchLog entry."""
    log = MagicMock()
    log.id = uuid.uuid4()
    log.lead_id = lead_id
    log.sequence_id = mock_sequence.id
    log.channel = "email"
    log.action = "sent"
    log.extra_metadata = {"message_id": "msg-abc-123", "template_id": str(uuid.uuid4())}
    log.created_at = datetime.now(UTC)
    return log


@pytest.fixture
def mock_domain():
    """A mock sending domain object."""
    domain = MagicMock()
    domain.id = uuid.uuid4()
    domain.domain = "mail.example.com"
    domain.verified = True
    domain.dkim_verified = True
    domain.spf_verified = True
    domain.dmarc_verified = True
    domain.created_at = datetime.now(UTC)
    return domain


@pytest.fixture
def mock_warmup_schedule():
    """A mock WarmupConfig object."""
    schedule = MagicMock()
    schedule.id = uuid.uuid4()
    schedule.inbox_id = uuid.uuid4()
    schedule.ramp_duration_weeks = 6
    schedule.initial_daily_volume = 5
    schedule.target_daily_volume = 50
    schedule.ramp_multiplier = 1.15
    schedule.ai_tuned = False
    schedule.ai_ramp_adjustments = None
    schedule.ai_seed_profile = None
    schedule.max_bounce_rate = 0.05
    schedule.max_spam_rate = 0.001
    schedule.min_open_rate = 0.15
    schedule.is_active = True
    schedule.paused_reason = None
    schedule.last_ai_review = None
    schedule.created_at = datetime.now(UTC)
    schedule.updated_at = datetime.now(UTC)
    return schedule


@pytest.fixture
def mock_sending_inbox():
    """A mock SendingInbox object."""
    inbox = MagicMock()
    inbox.id = uuid.uuid4()
    inbox.email = "sales@example.com"
    inbox.display_name = "Sales Team"
    inbox.status = "active"
    inbox.bounce_rate_7d = 0.01
    inbox.spam_rate_7d = 0.0002
    inbox.open_rate_7d = 0.25
    inbox.reply_rate_7d = 0.05
    inbox.total_sent = 150
    inbox.health_score = 92.5
    inbox.warmup_started_at = datetime.now(UTC)
    inbox.created_at = datetime.now(UTC)
    inbox.updated_at = datetime.now(UTC)
    return inbox


@pytest.fixture
def mock_redis():
    """A fully-mocked async Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=0)
    redis.lpush = AsyncMock(return_value=1)
    redis.lrange = AsyncMock(return_value=[])
    redis.zadd = AsyncMock(return_value=1)
    redis.zrangebyscore = AsyncMock(return_value=[])
    redis.zremrangebyscore = AsyncMock(return_value=0)
    redis.zcard = AsyncMock(return_value=0)
    return redis


@pytest.fixture
def mock_settings():
    """Settings object pre-populated with safe test defaults."""
    s = MagicMock()
    # Core
    s.DATABASE_URL = "postgresql+asyncpg://test:test@localhost/test_fortressflow"
    s.REDIS_URL = "redis://localhost:6379/1"
    s.SECRET_KEY = "test-secret-key-for-testing-only"
    s.ENVIRONMENT = "test"
    # Limits
    s.DAILY_EMAIL_LIMIT = 100
    s.DAILY_SMS_LIMIT = 10
    s.DAILY_LINKEDIN_LIMIT = 5
    s.GLOBAL_DAILY_EMAIL_LIMIT = 400
    s.GLOBAL_DAILY_SMS_LIMIT = 30
    s.GLOBAL_DAILY_LINKEDIN_LIMIT = 25
    s.MAX_TOUCH_RETRIES = 3
    s.RETRY_BACKOFF_MINUTES = 30
    # Thresholds
    s.BOUNCE_RATE_PAUSE_THRESHOLD = 0.05
    s.SPAM_RATE_PAUSE_THRESHOLD = 0.001
    s.OPEN_RATE_MIN_THRESHOLD = 0.15
    # AWS / SES
    s.AWS_REGION = "us-east-1"
    s.AWS_ACCESS_KEY_ID = "test-key"
    s.AWS_SECRET_ACCESS_KEY = "test-secret"
    s.SES_FROM_EMAIL = "noreply@example.com"
    s.SES_CONFIGURATION_SET = "test-config-set"
    # Twilio
    s.TWILIO_ACCOUNT_SID = "ACtest123"
    s.TWILIO_AUTH_TOKEN = ""
    s.TWILIO_PHONE_NUMBER = "+15005550006"
    # HubSpot
    s.HUBSPOT_API_KEY = "test-hubspot-key"
    s.HUBSPOT_BREEZE_ENABLED = False
    # Apollo / ZoomInfo
    s.APOLLO_API_KEY = "test-apollo-key"
    s.APOLLO_AI_ENABLED = False
    s.ZOOMINFO_API_KEY = ""
    s.ZOOMINFO_COPILOT_ENABLED = False
    # Reply / IMAP
    s.IMAP_HOST = ""
    s.IMAP_USER = ""
    s.IMAP_PASSWORD = ""
    s.IMAP_FOLDER = "INBOX"
    s.REPLY_WEBHOOK_SECRET = "test-reply-secret"
    # Warmup
    s.WARMUP_INITIAL_DAILY_VOLUME = 5
    s.WARMUP_RAMP_MULTIPLIER = 1.15
    s.WARMUP_AI_SEED_BATCH_SIZE = 50
    s.WARMUP_AI_LEARNING_WINDOW_DAYS = 7
    return s


@pytest.fixture
def mock_user():
    """A mock User ORM object for authentication tests."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "testuser@fortressflow.io"
    user.full_name = "Test User"
    user.role = UserRole.user
    user.is_active = True
    user.password_hash = "$2b$12$fakehashfortest"
    user.created_at = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)
    user.last_login_at = None
    return user


@pytest.fixture
def mock_admin_user():
    """A mock admin User ORM object."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "admin@fortressflow.io"
    user.full_name = "Admin User"
    user.role = UserRole.admin
    user.is_active = True
    user.password_hash = "$2b$12$fakehashfortest"
    user.created_at = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)
    user.last_login_at = None
    return user


@pytest.fixture
def auth_token(mock_user):
    """Generate a valid JWT access token for the mock user."""
    from app.services.auth_service import create_access_token

    return create_access_token(str(mock_user.id), mock_user.email, mock_user.role.value)


@pytest.fixture
def admin_auth_token(mock_admin_user):
    """Generate a valid JWT access token for the mock admin user."""
    from app.services.auth_service import create_access_token

    return create_access_token(str(mock_admin_user.id), mock_admin_user.email, mock_admin_user.role.value)


@pytest.fixture
def sample_ses_bounce_event():
    """A realistic SES bounce SNS notification payload."""
    return {
        "Type": "Notification",
        "Message": '{"eventType":"Bounce","bounce":{"bounceType":"Permanent","bounceSubType":"General","bouncedRecipients":[{"emailAddress":"bounce@invalid.com","action":"failed","status":"5.1.1","diagnosticCode":"smtp; 550 5.1.1 The email account does not exist"}],"timestamp":"2026-03-19T12:00:00.000Z","feedbackId":"feedback-id-123"},"mail":{"timestamp":"2026-03-19T11:59:00.000Z","messageId":"ses-message-id-abc","destination":["bounce@invalid.com"],"headers":[{"name":"X-FortressFlow-Enrollment-Id","value":"00000000-0000-0000-0000-000000000001"},{"name":"X-FortressFlow-Lead-Id","value":"00000000-0000-0000-0000-000000000002"},{"name":"X-FortressFlow-Sequence-Id","value":"00000000-0000-0000-0000-000000000003"}]}}',
        "Timestamp": "2026-03-19T12:00:01.000Z",
        "MessageId": "sns-message-id-xyz",
    }


@pytest.fixture
def sample_ses_complaint_event():
    """A realistic SES complaint SNS notification payload."""
    return {
        "Type": "Notification",
        "Message": '{"eventType":"Complaint","complaint":{"complainedRecipients":[{"emailAddress":"complaint@example.com"}],"timestamp":"2026-03-19T12:00:00.000Z","feedbackId":"feedback-complaint-123","complaintFeedbackType":"abuse"},"mail":{"timestamp":"2026-03-19T11:58:00.000Z","messageId":"ses-message-id-complaint","destination":["complaint@example.com"],"headers":[{"name":"X-FortressFlow-Enrollment-Id","value":"00000000-0000-0000-0000-000000000011"},{"name":"X-FortressFlow-Lead-Id","value":"00000000-0000-0000-0000-000000000012"},{"name":"X-FortressFlow-Sequence-Id","value":"00000000-0000-0000-0000-000000000013"}]}}',
        "Timestamp": "2026-03-19T12:00:02.000Z",
        "MessageId": "sns-complaint-message-id",
    }


@pytest.fixture
def sample_twilio_status_callback():
    """A realistic Twilio status callback form payload."""
    return {
        "MessageSid": "SMtest1234567890abcdef",
        "SmsSid": "SMtest1234567890abcdef",
        "AccountSid": "ACtest123",
        "From": "+15005550006",
        "To": "+14155552671",
        "Body": "",
        "MessageStatus": "delivered",
        "NumMedia": "0",
    }


@pytest.fixture
def auth_headers(auth_token):
    """HTTP headers with a valid JWT for a regular user."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def admin_auth_headers(admin_auth_token):
    """HTTP headers with a valid JWT for an admin user."""
    return {"Authorization": f"Bearer {admin_auth_token}"}
