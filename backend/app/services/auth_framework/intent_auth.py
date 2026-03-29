"""
Intent Authentication System
Cryptographically binds user identity + intended action + timestamp into
verifiable credentials, stored in a tamper-resistant hash-chain ledger.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


# ── Secret used for HMAC signing (rotate in production) ────────────────────
_SIGNING_KEY: bytes = secrets.token_bytes(32)

# Actions that require explicit human approval before execution
ACTIONS_REQUIRING_APPROVAL = frozenset({
    "publish_content",
    "delete_record",
    "modify_patient_data",
    "send_communication",
    "override_recommendation",
    "export_pii",
})


@dataclass
class IntentCredential:
    """Immutable record of a user's authenticated intent."""
    user_id: str
    action: str
    params_hash: str
    timestamp: float
    signature: str
    expires_at: float
    approved: bool = False
    approval_timestamp: Optional[float] = None

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class _LedgerEntry:
    """Single entry in the tamper-resistant ledger."""
    index: int
    credential: IntentCredential
    previous_hash: str
    entry_hash: str
    recorded_at: float = field(default_factory=time.time)


class IntentLedger:
    """
    Append-only, hash-chained ledger of intent credentials.

    Each entry's hash covers the previous entry's hash, making retroactive
    tampering detectable.
    """

    def __init__(self, signing_key: Optional[bytes] = None, ttl_seconds: int = 300):
        self._key: bytes = signing_key or _SIGNING_KEY
        self._ttl: int = ttl_seconds
        self._chain: List[_LedgerEntry] = []

    # ── Public API ──────────────────────────────────────────────────────

    def create_credential(
        self,
        user_id: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        ttl_override: Optional[int] = None,
    ) -> IntentCredential:
        """Create a signed intent credential and append it to the ledger."""
        now = time.time()
        ttl = ttl_override or self._ttl
        params_hash = self._hash_params(params or {})

        signature = self._sign(user_id, action, params_hash, now)

        credential = IntentCredential(
            user_id=user_id,
            action=action,
            params_hash=params_hash,
            timestamp=now,
            signature=signature,
            expires_at=now + ttl,
        )

        self._append_to_chain(credential)
        return credential

    def verify_credential(self, credential: IntentCredential) -> bool:
        """
        Verify that a credential is authentic and has not expired.

        Checks:
        1. HMAC signature matches user+action+params+timestamp.
        2. Credential has not expired.
        3. If the action requires approval, the credential must be approved.
        """
        expected_sig = self._sign(
            credential.user_id,
            credential.action,
            credential.params_hash,
            credential.timestamp,
        )
        sig_valid = hmac.compare_digest(expected_sig, credential.signature)

        if not sig_valid:
            return False
        if credential.is_expired():
            return False
        if self.action_requires_approval(credential.action) and not credential.approved:
            return False
        return True

    def approve_credential(self, credential: IntentCredential) -> IntentCredential:
        """Mark a credential as human-approved (for sensitive actions)."""
        credential.approved = True
        credential.approval_timestamp = time.time()
        return credential

    def get_audit_trail(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        since: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Return ledger entries matching the given filters."""
        results: List[Dict[str, Any]] = []
        for entry in self._chain:
            cred = entry.credential
            if user_id and cred.user_id != user_id:
                continue
            if action and cred.action != action:
                continue
            if since and entry.recorded_at < since:
                continue
            results.append({
                "index": entry.index,
                "credential": cred.to_dict(),
                "previous_hash": entry.previous_hash,
                "entry_hash": entry.entry_hash,
                "recorded_at": datetime.fromtimestamp(
                    entry.recorded_at, tz=timezone.utc
                ).isoformat(),
            })
        return results

    def verify_chain_integrity(self) -> bool:
        """Walk the chain and confirm every hash links correctly."""
        for i, entry in enumerate(self._chain):
            expected = self._compute_entry_hash(entry.credential, entry.previous_hash)
            if expected != entry.entry_hash:
                return False
            if i > 0 and entry.previous_hash != self._chain[i - 1].entry_hash:
                return False
        return True

    @staticmethod
    def action_requires_approval(action: str) -> bool:
        return action in ACTIONS_REQUIRING_APPROVAL

    def prompt_for_approval(self, credential: IntentCredential) -> str:
        """
        Return a human-readable approval prompt for a sensitive action.
        In a real system this would trigger a UI dialog or notification.
        """
        ts = datetime.fromtimestamp(credential.timestamp, tz=timezone.utc).isoformat()
        return (
            f"[APPROVAL REQUIRED]\n"
            f"  User  : {credential.user_id}\n"
            f"  Action: {credential.action}\n"
            f"  Params: {credential.params_hash[:16]}...\n"
            f"  Time  : {ts}\n"
            f"  Expires: {int(credential.expires_at - time.time())}s remaining\n"
            f"Do you approve this action? (yes/no)"
        )

    # ── Internals ───────────────────────────────────────────────────────

    def _sign(self, user_id: str, action: str, params_hash: str, ts: float) -> str:
        message = f"{user_id}:{action}:{params_hash}:{ts}".encode()
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    @staticmethod
    def _hash_params(params: Dict[str, Any]) -> str:
        canonical = json.dumps(params, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _compute_entry_hash(self, credential: IntentCredential, prev_hash: str) -> str:
        payload = json.dumps(credential.to_dict(), sort_keys=True, separators=(",", ":"))
        block = f"{prev_hash}:{payload}".encode()
        return hashlib.sha256(block).hexdigest()

    def _append_to_chain(self, credential: IntentCredential) -> _LedgerEntry:
        prev_hash = self._chain[-1].entry_hash if self._chain else ("0" * 64)
        entry_hash = self._compute_entry_hash(credential, prev_hash)
        entry = _LedgerEntry(
            index=len(self._chain),
            credential=credential,
            previous_hash=prev_hash,
            entry_hash=entry_hash,
        )
        self._chain.append(entry)
        return entry
