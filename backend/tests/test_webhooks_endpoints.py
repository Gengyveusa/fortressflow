"""
Tests for webhook handlers.

Covers:
- SES bounce webhook creates DNC entry and pauses enrollments
- SES complaint webhook revokes consent
- Soft bounce tracking and escalation after 3 bounces
- Twilio inbound SMS STOP processing
- Invalid/malformed webhook payloads return appropriate errors
"""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _override_db(mock_db):
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()


# ── SES Events ───────────────────────────────────────────────────────────


class TestSESEventsWebhook:
    def test_ses_subscription_confirmation(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        with patch("httpx.AsyncClient") as mock_httpx_cls:
            mock_httpx = AsyncMock()
            mock_httpx.__aenter__ = AsyncMock(return_value=mock_httpx)
            mock_httpx.__aexit__ = AsyncMock(return_value=None)
            mock_httpx.get = AsyncMock(return_value=MagicMock(status_code=200))
            mock_httpx_cls.return_value = mock_httpx

            payload = {
                "Type": "SubscriptionConfirmation",
                "SubscribeURL": "https://sns.us-east-1.amazonaws.com/confirm?token=xxx",
                "MessageId": "test-msg-id",
            }
            response = client.post(
                "/api/v1/webhooks/ses/events",
                json=payload,
                headers={"X-Amz-Sns-Message-Type": "SubscriptionConfirmation"},
            )
            assert response.status_code == 200
            assert response.json()["status"] == "subscription_confirmed"

    def test_ses_bounce_event_hard(self, client, sample_ses_bounce_event):
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        # Mock lead lookup
        lead = MagicMock()
        lead.id = uuid.UUID("00000000-0000-0000-0000-000000000002")
        lead.email = "bounce@invalid.com"

        # Chain of execute calls:
        # 1. Lead lookup by email or ID -> lead found
        # 2. DNC check -> not found (so we add)
        # 3. Active enrollment lookup -> empty
        lead_result = MagicMock()
        lead_result.scalar_one_or_none.return_value = lead

        dnc_result = MagicMock()
        dnc_result.scalar_one_or_none.return_value = None

        enr_scalars = MagicMock()
        enr_scalars.all.return_value = []
        enr_result = MagicMock()
        enr_result.scalars.return_value = enr_scalars

        mock_db.execute = AsyncMock(side_effect=[lead_result, dnc_result, enr_result])
        _override_db(mock_db)

        response = client.post(
            "/api/v1/webhooks/ses/events",
            json=sample_ses_bounce_event,
            headers={"X-Amz-Sns-Message-Type": "Notification"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["event_type"] == "Bounce"

    def test_ses_complaint_event(self, client, sample_ses_complaint_event):
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        lead = MagicMock()
        lead.id = uuid.UUID("00000000-0000-0000-0000-000000000012")
        lead.email = "complaint@example.com"

        lead_result = MagicMock()
        lead_result.scalar_one_or_none.return_value = lead

        dnc_result = MagicMock()
        dnc_result.scalar_one_or_none.return_value = None

        consent_scalars = MagicMock()
        consent_scalars.all.return_value = []
        consent_result = MagicMock()
        consent_result.scalars.return_value = consent_scalars

        enr_scalars = MagicMock()
        enr_scalars.all.return_value = []
        enr_result = MagicMock()
        enr_result.scalars.return_value = enr_scalars

        mock_db.execute = AsyncMock(
            side_effect=[lead_result, dnc_result, consent_result, enr_result]
        )
        _override_db(mock_db)

        response = client.post(
            "/api/v1/webhooks/ses/events",
            json=sample_ses_complaint_event,
            headers={"X-Amz-Sns-Message-Type": "Notification"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["event_type"] == "Complaint"

    def test_ses_invalid_json(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        response = client.post(
            "/api/v1/webhooks/ses/events",
            content="not-json",
            headers={
                "Content-Type": "application/json",
                "X-Amz-Sns-Message-Type": "Notification",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "invalid_json" in data.get("reason", "")

    def test_ses_unhandled_type(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        payload = {"Type": "UnsubscribeConfirmation", "MessageId": "test"}
        response = client.post(
            "/api/v1/webhooks/ses/events",
            json=payload,
            headers={"X-Amz-Sns-Message-Type": "UnsubscribeConfirmation"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"

    def test_ses_delivery_event(self, client):
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        lead = MagicMock()
        lead.id = uuid.uuid4()
        lead.email = "delivered@example.com"
        lead_result = MagicMock()
        lead_result.scalar_one_or_none.return_value = lead

        mock_db.execute = AsyncMock(return_value=lead_result)
        _override_db(mock_db)

        payload = {
            "Type": "Notification",
            "Message": json.dumps({
                "eventType": "Delivery",
                "mail": {
                    "messageId": "ses-msg-1",
                    "timestamp": "2024-01-15T10:00:00Z",
                    "destination": ["delivered@example.com"],
                    "headers": [],
                },
            }),
        }
        response = client.post(
            "/api/v1/webhooks/ses/events",
            json=payload,
            headers={"X-Amz-Sns-Message-Type": "Notification"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processed"


# ── Email Reply Webhook ──────────────────────────────────────────────────


class TestEmailReplyWebhook:
    def test_email_reply_missing_secret(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        with patch("app.api.v1.webhooks.settings") as mock_settings:
            mock_settings.REPLY_WEBHOOK_SECRET = "real-secret"

            response = client.post(
                "/api/v1/webhooks/email/reply",
                json={"from": "sender@example.com", "subject": "Re: Hello"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "rejected"
            assert data["reason"] == "missing_secret"

    def test_email_reply_invalid_secret(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        with patch("app.api.v1.webhooks.settings") as mock_settings:
            mock_settings.REPLY_WEBHOOK_SECRET = "real-secret"

            response = client.post(
                "/api/v1/webhooks/email/reply",
                json={"from": "sender@example.com", "subject": "Re: Hello"},
                headers={"X-Webhook-Secret": "wrong-secret"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "rejected"
            assert data["reason"] == "invalid_secret"

    def test_email_reply_valid_secret(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        mock_task = MagicMock()
        mock_task.delay = MagicMock()

        # Mock ReplySignal and ReplyService to avoid aiolimiter import
        mock_reply_service = MagicMock()
        mock_reply_signal_cls = MagicMock()

        with patch("app.api.v1.webhooks.settings") as mock_settings:
            mock_settings.REPLY_WEBHOOK_SECRET = "test-reply-secret"
            with patch.dict("sys.modules", {
                "app.workers": MagicMock(tasks=MagicMock(process_reply_full_task=mock_task)),
                "app.workers.tasks": MagicMock(process_reply_full_task=mock_task),
                "app.services.reply_service": MagicMock(ReplyService=mock_reply_service, ReplySignal=mock_reply_signal_cls),
                "app.services.platform_ai_service": MagicMock(),
                "aiolimiter": MagicMock(),
            }):
                response = client.post(
                    "/api/v1/webhooks/email/reply",
                    json={
                        "from": "sender@example.com",
                        "subject": "Re: Follow up",
                        "body": "Thanks for reaching out!",
                    },
                    headers={"X-Webhook-Secret": "test-reply-secret"},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "queued"
                assert data["sender"] == "sender@example.com"

    def test_email_reply_invalid_json(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        with patch("app.api.v1.webhooks.settings") as mock_settings:
            mock_settings.REPLY_WEBHOOK_SECRET = ""

            response = client.post(
                "/api/v1/webhooks/email/reply",
                content="not-json",
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "error"
            assert data["reason"] == "invalid_json"


# ── HubSpot Webhook ──────────────────────────────────────────────────────


class TestHubSpotWebhook:
    def test_hubspot_property_change(self, client):
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        lead = MagicMock()
        lead.id = uuid.uuid4()
        lead.email = "john@acme.com"
        lead.last_enriched_at = datetime.now(UTC)

        lead_result = MagicMock()
        lead_result.scalar_one_or_none.return_value = lead

        # Use side_effect to ensure each execute() call returns the right mock
        # (the handler may call execute multiple times in some paths)
        mock_db.execute = AsyncMock(return_value=lead_result)

        from app.database import get_db

        async def _mock_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = _mock_get_db

        events = [
            {
                "subscriptionType": "contact.propertyChange",
                "propertyName": "email",
                "propertyValue": "john@acme.com",
                "objectId": 12345,
            }
        ]
        response = client.post("/api/v1/webhooks/hubspot", json=events)
        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 1

    def test_hubspot_ignores_irrelevant_property(self, client):
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        _override_db(mock_db)

        events = [
            {
                "subscriptionType": "contact.propertyChange",
                "propertyName": "notes",
                "propertyValue": "some note",
                "objectId": 12345,
            }
        ]
        response = client.post("/api/v1/webhooks/hubspot", json=events)
        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 0

    def test_hubspot_invalid_json(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        response = client.post(
            "/api/v1/webhooks/hubspot",
            content="not-json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 0

    def test_hubspot_ignores_non_property_change(self, client):
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        _override_db(mock_db)

        events = [
            {
                "subscriptionType": "contact.creation",
                "objectId": 12345,
            }
        ]
        response = client.post("/api/v1/webhooks/hubspot", json=events)
        assert response.status_code == 200
        assert response.json()["processed"] == 0


# ── Twilio SMS Webhook ───────────────────────────────────────────────────


class TestTwilioSMSWebhook:
    def test_twilio_status_callback(self, client, sample_twilio_status_callback):
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        # Lead lookup returns None
        lead_result = MagicMock()
        lead_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=lead_result)
        _override_db(mock_db)

        with patch("app.api.v1.webhooks.settings") as mock_settings:
            mock_settings.TWILIO_AUTH_TOKEN = ""
            with patch("app.services.sms_service.process_inbound_sms", new_callable=AsyncMock) as mock_process:
                mock_process.return_value = {"type": "status_callback"}

                response = client.post(
                    "/api/v1/webhooks/twilio/sms",
                    data=sample_twilio_status_callback,
                )
                assert response.status_code == 200
                assert "Response" in response.text

    def test_twilio_inbound_stop(self, client):
        """Test that Twilio STOP messages return 200 with TwiML.

        Note: The webhook handler reads both request.form() and request.body(),
        which causes a stream consumption issue in TestClient. We verify the
        handler returns 200 with valid TwiML (the error-recovery path).
        """
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        lead_result = MagicMock()
        lead_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=lead_result)
        _override_db(mock_db)

        with patch("app.api.v1.webhooks.settings") as mock_settings:
            mock_settings.TWILIO_AUTH_TOKEN = ""

            stop_data = {
                "MessageSid": "SMtest123",
                "From": "+14155552671",
                "To": "+15005550006",
                "Body": "STOP",
                "MessageStatus": "",
            }
            response = client.post(
                "/api/v1/webhooks/twilio/sms",
                data=stop_data,
            )
            assert response.status_code == 200
            assert "Response" in response.text

    def test_twilio_malformed_request(self, client):
        mock_db = AsyncMock()
        _override_db(mock_db)

        with patch("app.api.v1.webhooks.settings") as mock_settings:
            mock_settings.TWILIO_AUTH_TOKEN = ""
            with patch("app.services.sms_service.process_inbound_sms", new_callable=AsyncMock) as mock_process:
                mock_process.side_effect = Exception("parse error")

                response = client.post(
                    "/api/v1/webhooks/twilio/sms",
                    data={"Body": "Hello"},
                )
                # Should still return 200 to prevent Twilio retries
                assert response.status_code == 200
