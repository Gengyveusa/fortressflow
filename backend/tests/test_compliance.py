"""
Compliance service unit tests.

All tests run without a real database — AsyncSession is mocked.
"""
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.compliance import (
    generate_unsubscribe_token,
    verify_unsubscribe_token,
    can_send_to_lead,
    record_consent,
    revoke_consent,
    add_to_dnc,
    get_audit_trail,
)


def _scalar_result(value):
    """Helper: mock db.execute(...).scalar_one_or_none() → value."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _scalar_one_result(value):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _scalars_result(values):
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = values
    result.scalars.return_value = scalars_mock
    return result


# ---------------------------------------------------------------------------
# can_send_to_lead
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_can_send_no_lead(mock_db, lead_id):
    """Returns False when lead does not exist."""
    mock_db.execute.return_value = _scalar_result(None)
    ok, reason = await can_send_to_lead(lead_id, "email", mock_db)
    assert ok is False
    assert reason == "lead_not_found"


@pytest.mark.asyncio
async def test_can_send_no_consent(mock_db, lead_id, mock_lead):
    """Returns False when there is no active consent."""
    execute_calls = [
        _scalar_result(mock_lead),   # Lead lookup
        _scalar_result(None),         # Consent lookup
    ]
    mock_db.execute.side_effect = execute_calls
    ok, reason = await can_send_to_lead(lead_id, "email", mock_db)
    assert ok is False
    assert reason == "no_active_consent"


@pytest.mark.asyncio
async def test_can_send_with_valid_consent(mock_db, lead_id, mock_lead, mock_consent):
    """Returns True when consent is active and no DNC or limit issues."""
    execute_calls = [
        _scalar_result(mock_lead),    # Lead
        _scalar_result(mock_consent), # Consent
        _scalar_result(None),          # DNC
        _scalar_one_result(0),         # Daily count
    ]
    mock_db.execute.side_effect = execute_calls
    ok, reason = await can_send_to_lead(lead_id, "email", mock_db)
    assert ok is True
    assert reason == "approved"


@pytest.mark.asyncio
async def test_can_send_revoked_consent(mock_db, lead_id, mock_lead):
    """Returns False after consent is revoked (no active consent found)."""
    execute_calls = [
        _scalar_result(mock_lead),
        _scalar_result(None),  # No active consent (revoked)
    ]
    mock_db.execute.side_effect = execute_calls
    ok, reason = await can_send_to_lead(lead_id, "email", mock_db)
    assert ok is False
    assert reason == "no_active_consent"


@pytest.mark.asyncio
async def test_can_send_on_dnc(mock_db, lead_id, mock_lead, mock_consent):
    """Returns False when lead is on DNC list."""
    dnc_block = MagicMock()
    dnc_block.reason = "unsubscribed"
    execute_calls = [
        _scalar_result(mock_lead),
        _scalar_result(mock_consent),
        _scalar_result(dnc_block),  # DNC hit
    ]
    mock_db.execute.side_effect = execute_calls
    ok, reason = await can_send_to_lead(lead_id, "email", mock_db)
    assert ok is False
    assert "on_dnc_list" in reason


@pytest.mark.asyncio
async def test_can_send_daily_limit_exceeded(mock_db, lead_id, mock_lead, mock_consent):
    """Returns False when the daily send limit is exceeded."""
    execute_calls = [
        _scalar_result(mock_lead),
        _scalar_result(mock_consent),
        _scalar_result(None),       # Not on DNC
        _scalar_one_result(100),    # 100 emails sent today (== limit)
    ]
    mock_db.execute.side_effect = execute_calls
    ok, reason = await can_send_to_lead(lead_id, "email", mock_db)
    assert ok is False
    assert "daily_limit_exceeded" in reason


# ---------------------------------------------------------------------------
# record_consent / revoke_consent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_consent(mock_db, lead_id):
    """record_consent creates and flushes a Consent object."""
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()

    consent = await record_consent(
        lead_id=lead_id,
        channel="email",
        method="web_form",
        proof={"timestamp": "2024-01-01T00:00:00Z", "source": "test", "ip": "127.0.0.1"},
        db=mock_db,
    )
    mock_db.add.assert_called_once()
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_revoke_consent_no_active(mock_db, lead_id):
    """revoke_consent returns False when there are no active consents."""
    mock_db.execute.return_value = _scalars_result([])
    revoked = await revoke_consent(lead_id, "email", mock_db)
    assert revoked is False


@pytest.mark.asyncio
async def test_revoke_consent_success(mock_db, lead_id, mock_consent):
    """revoke_consent sets revoked_at and returns True."""
    mock_db.execute.return_value = _scalars_result([mock_consent])
    mock_db.flush = AsyncMock()
    revoked = await revoke_consent(lead_id, "email", mock_db)
    assert revoked is True
    assert mock_consent.revoked_at is not None


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_trail_completeness(mock_db, lead_id, mock_lead, mock_consent):
    """Audit trail returns consents, touch logs, and DNC records."""
    mock_consent.revoked_at = None
    mock_consent.created_at = datetime.now(UTC)
    mock_consent.granted_at = datetime.now(UTC)
    mock_consent.channel = "email"
    mock_consent.method = "web_form"
    mock_consent.proof = {}

    touch = MagicMock()
    touch.id = uuid.uuid4()
    touch.channel = "email"
    touch.action = "sent"
    touch.sequence_id = None
    touch.step_number = 1
    touch.extra_metadata = {}
    touch.created_at = datetime.now(UTC)

    dnc = MagicMock()
    dnc.id = uuid.uuid4()
    dnc.identifier = "test@example.com"
    dnc.channel = "email"
    dnc.reason = "test"
    dnc.blocked_at = datetime.now(UTC)
    dnc.source = "test"
    dnc.created_at = datetime.now(UTC)

    execute_calls = [
        _scalar_result(mock_lead),
        _scalars_result([mock_consent]),
        _scalars_result([touch]),
        _scalars_result([dnc]),
        _scalars_result([]),  # phone DNC
    ]
    mock_db.execute.side_effect = execute_calls

    trail = await get_audit_trail(lead_id, mock_db)
    assert trail["lead_id"] == lead_id
    assert len(trail["consents"]) == 1
    assert len(trail["touch_logs"]) == 1
    assert len(trail["dnc_records"]) == 1


@pytest.mark.asyncio
async def test_audit_trail_no_lead(mock_db, lead_id):
    """Audit trail returns empty lists when lead does not exist."""
    mock_db.execute.return_value = _scalar_result(None)
    trail = await get_audit_trail(lead_id, mock_db)
    assert trail["consents"] == []
    assert trail["touch_logs"] == []
    assert trail["dnc_records"] == []


# ---------------------------------------------------------------------------
# Unsubscribe token
# ---------------------------------------------------------------------------

def test_generate_and_verify_token(lead_id):
    """Token round-trips correctly."""
    token = generate_unsubscribe_token(lead_id, "email")
    returned_lead_id, returned_channel = verify_unsubscribe_token(token)
    assert returned_lead_id == lead_id
    assert returned_channel == "email"


def test_verify_invalid_token():
    """Tampered token returns (None, None)."""
    result_id, result_channel = verify_unsubscribe_token("this-is-not-a-valid-token")
    assert result_id is None
    assert result_channel is None


def test_verify_tampered_token(lead_id):
    """Token with modified payload is rejected."""
    import base64, json
    token = generate_unsubscribe_token(lead_id, "email")
    decoded = json.loads(base64.urlsafe_b64decode(token.encode()).decode())
    # Tamper with the payload
    payload = json.loads(decoded["payload"])
    payload["channel"] = "sms"
    decoded["payload"] = json.dumps(payload, sort_keys=True)
    tampered = base64.urlsafe_b64encode(json.dumps(decoded).encode()).decode()
    result_id, result_channel = verify_unsubscribe_token(tampered)
    assert result_id is None
