"""
Tests for analytics API endpoints — comprehensive coverage.

Tests all 7 endpoints: outreach-daily, recent-activity, sequence-performance,
response-trends, channel-breakdown, bounce-daily, audit-trail.
Also expands dashboard and deliverability coverage.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _override_db(mock_db):
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db


def _override_auth(user=None):
    """Override auth to bypass JWT validation."""
    from app.auth import get_current_user

    mock_user = user or MagicMock()
    mock_user.id = "00000000-0000-0000-0000-000000000001"
    mock_user.email = "test@test.com"
    mock_user.role = MagicMock()
    mock_user.role.value = "user"
    app.dependency_overrides[get_current_user] = lambda: mock_user


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()


# ── Dashboard Stats ──────────────────────────────────────────────────────


class TestDashboardStatsExtended:
    def test_dashboard_with_data(self, client):
        mock_db = AsyncMock()
        results = []
        for val in [250, 120, 1500, 180]:
            r = MagicMock()
            r.scalar_one.return_value = val
            results.append(r)
        mock_db.execute = AsyncMock(side_effect=results)
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["total_leads"] == 250
        assert data["active_consents"] == 120
        assert data["touches_sent"] == 1500
        assert data["response_rate"] == 12.0  # 180/1500*100

    def test_dashboard_zero_division(self, client):
        mock_db = AsyncMock()
        results = []
        for val in [0, 0, 0, 0]:
            r = MagicMock()
            r.scalar_one.return_value = val
            results.append(r)
        mock_db.execute = AsyncMock(side_effect=results)
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["response_rate"] == 0.0

    def test_dashboard_requires_auth(self, client):
        """Without auth override, should return 403/401."""
        mock_db = AsyncMock()
        _override_db(mock_db)
        # Don't override auth
        response = client.get("/api/v1/analytics/dashboard")
        assert response.status_code in (401, 403)


# ── Deliverability Stats ─────────────────────────────────────────────────


class TestDeliverabilityStatsExtended:
    def test_deliverability_with_data(self, client):
        mock_db = AsyncMock()
        # sent=500, bounced=25, spam=3, warmup_active=4, warmup_completed=8
        results = []
        for val in [500, 25, 3, 4, 8]:
            r = MagicMock()
            r.scalar_one.return_value = val
            results.append(r)
        mock_db.execute = AsyncMock(side_effect=results)
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/deliverability")
        assert response.status_code == 200
        data = response.json()
        assert data["total_sent"] == 500
        assert data["total_bounced"] == 25
        assert data["bounce_rate"] == 5.0
        assert data["spam_complaints"] == 3
        assert data["spam_rate"] == 0.6
        assert data["warmup_active"] == 4
        assert data["warmup_completed"] == 8

    def test_deliverability_empty_db(self, client):
        mock_db = AsyncMock()
        results = []
        for val in [0, 0, 0, 0, 0]:
            r = MagicMock()
            r.scalar_one.return_value = val
            results.append(r)
        mock_db.execute = AsyncMock(side_effect=results)
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/deliverability")
        assert response.status_code == 200
        data = response.json()
        assert data["bounce_rate"] == 0.0
        assert data["spam_rate"] == 0.0


# ── Outreach Daily ───────────────────────────────────────────────────────


class TestOutreachDaily:
    def test_outreach_daily_with_data(self, client):
        mock_db = AsyncMock()
        row1 = MagicMock()
        row1.day = "2024-01-15"
        row1.channel = "email"
        row1.count = 42
        row2 = MagicMock()
        row2.day = "2024-01-15"
        row2.channel = "sms"
        row2.count = 10
        mock_result = MagicMock()
        mock_result.all.return_value = [row1, row2]
        mock_db.execute = AsyncMock(return_value=mock_result)
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/outreach-daily")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["items"][0]["channel"] == "email"
        assert data["items"][0]["count"] == 42

    def test_outreach_daily_empty(self, client):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/outreach-daily")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []


# ── Recent Activity ──────────────────────────────────────────────────────


class TestRecentActivity:
    def test_recent_activity_with_data(self, client):
        mock_db = AsyncMock()
        import uuid

        touch = MagicMock()
        touch.id = uuid.uuid4()
        touch.channel = "email"
        touch.action = MagicMock()
        touch.action.value = "sent"
        touch.sequence_id = uuid.uuid4()
        touch.created_at = MagicMock()
        touch.created_at.isoformat.return_value = "2024-01-15T10:00:00"

        row = MagicMock()
        row.TouchLog = touch
        row.first_name = "John"
        row.last_name = "Doe"
        row.email = "john@example.com"

        mock_result = MagicMock()
        mock_result.all.return_value = [row]
        mock_db.execute = AsyncMock(return_value=mock_result)
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/recent-activity")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["lead_name"] == "John Doe"
        assert data["items"][0]["action"] == "sent"

    def test_recent_activity_empty(self, client):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/recent-activity")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []


# ── Sequence Performance ─────────────────────────────────────────────────


class TestSequencePerformance:
    def test_sequence_performance_with_data(self, client):
        mock_db = AsyncMock()
        import uuid

        seq_id = uuid.uuid4()
        row1 = MagicMock()
        row1.sequence_id = seq_id
        row1.action = MagicMock()
        row1.action.value = "sent"
        row1.count = 100

        row2 = MagicMock()
        row2.sequence_id = seq_id
        row2.action = MagicMock()
        row2.action.value = "opened"
        row2.count = 45

        # First call returns touch log aggregates
        perf_result = MagicMock()
        perf_result.all.return_value = [row1, row2]

        # Second call returns sequence name
        name_row = MagicMock()
        name_row.id = seq_id
        name_row.name = "Test Sequence"
        name_result = MagicMock()
        name_result.all.return_value = [name_row]

        mock_db.execute = AsyncMock(side_effect=[perf_result, name_result])
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/sequence-performance")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["sent"] == 100
        assert item["opened"] == 45
        assert item["open_rate"] == 45.0

    def test_sequence_performance_empty(self, client):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/sequence-performance")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []


# ── Response Trends ──────────────────────────────────────────────────────


class TestResponseTrends:
    def test_response_trends_with_data(self, client):
        mock_db = AsyncMock()
        from datetime import datetime, UTC

        week_dt = datetime(2024, 1, 15, tzinfo=UTC)

        sent_row = MagicMock()
        sent_row.week = week_dt
        sent_row.count = 200
        sent_result = MagicMock()
        sent_result.all.return_value = [sent_row]

        replied_row = MagicMock()
        replied_row.week = week_dt
        replied_row.count = 30
        replied_result = MagicMock()
        replied_result.all.return_value = [replied_row]

        mock_db.execute = AsyncMock(side_effect=[sent_result, replied_result])
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/response-trends")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["sent"] == 200
        assert data["items"][0]["replied"] == 30
        assert data["items"][0]["response_rate"] == 15.0

    def test_response_trends_empty(self, client):
        mock_db = AsyncMock()
        sent_result = MagicMock()
        sent_result.all.return_value = []
        replied_result = MagicMock()
        replied_result.all.return_value = []
        mock_db.execute = AsyncMock(side_effect=[sent_result, replied_result])
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/response-trends")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []


# ── Channel Breakdown ────────────────────────────────────────────────────


class TestChannelBreakdown:
    def test_channel_breakdown_with_data(self, client):
        mock_db = AsyncMock()
        rows = []
        for ch, cnt in [("email", 500), ("sms", 100), ("linkedin", 50)]:
            r = MagicMock()
            r.channel = ch
            r.count = cnt
            rows.append(r)
        mock_result = MagicMock()
        mock_result.all.return_value = rows
        mock_db.execute = AsyncMock(return_value=mock_result)
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/channel-breakdown")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        channels = {item["channel"] for item in data["items"]}
        assert channels == {"email", "sms", "linkedin"}

    def test_channel_breakdown_empty(self, client):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/channel-breakdown")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []


# ── Bounce Daily ─────────────────────────────────────────────────────────


class TestBounceDaily:
    def test_bounce_daily_with_data(self, client):
        mock_db = AsyncMock()
        row = MagicMock()
        row.day = "2024-01-15"
        row.count = 8
        mock_result = MagicMock()
        mock_result.all.return_value = [row]
        mock_db.execute = AsyncMock(return_value=mock_result)
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/bounce-daily")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["date"] == "2024-01-15"
        assert data["items"][0]["count"] == 8

    def test_bounce_daily_empty(self, client):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/bounce-daily")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []


# ── Audit Trail ──────────────────────────────────────────────────────────


class TestAuditTrail:
    def test_audit_trail_with_data(self, client):
        mock_db = AsyncMock()
        import uuid
        from datetime import datetime, UTC

        # Consent row
        consent = MagicMock()
        consent.id = uuid.uuid4()
        consent.granted_at = datetime.now(UTC)
        consent.created_at = datetime.now(UTC)
        consent.channel = MagicMock()
        consent.channel.value = "email"
        consent.method = MagicMock()
        consent.method.value = "web_form"
        consent.revoked_at = None

        consent_row = MagicMock()
        consent_row.Consent = consent
        consent_row.email = "user@example.com"
        consent_result = MagicMock()
        consent_result.all.return_value = [consent_row]

        # DNC row
        dnc = MagicMock()
        dnc.id = uuid.uuid4()
        dnc.identifier = "blocked@example.com"
        dnc.blocked_at = datetime.now(UTC)
        dnc.channel = "email"
        dnc.source = "ses_webhook"
        dnc.reason = "hard_bounce"
        dnc.created_at = datetime.now(UTC)
        dnc_scalars = MagicMock()
        dnc_scalars.all.return_value = [dnc]
        dnc_result = MagicMock()
        dnc_result.scalars.return_value = dnc_scalars

        mock_db.execute = AsyncMock(side_effect=[consent_result, dnc_result])
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/audit-trail")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2

    def test_audit_trail_empty(self, client):
        mock_db = AsyncMock()
        consent_result = MagicMock()
        consent_result.all.return_value = []
        dnc_scalars = MagicMock()
        dnc_scalars.all.return_value = []
        dnc_result = MagicMock()
        dnc_result.scalars.return_value = dnc_scalars
        mock_db.execute = AsyncMock(side_effect=[consent_result, dnc_result])
        _override_db(mock_db)
        _override_auth()

        response = client.get("/api/v1/analytics/audit-trail")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

    def test_audit_trail_requires_auth(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)
        response = client.get("/api/v1/analytics/audit-trail")
        assert response.status_code in (401, 403)
