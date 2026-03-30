"""
Authority Authentication (C2PA-style)
Implements provenance manifests, expert registries, and content signing
to establish verifiable chains of authorship and editorial authority.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class ExpertLevel(str, Enum):
    CONTRIBUTOR = "contributor"
    REVIEWER = "reviewer"
    EDITOR = "editor"
    LEAD_AUTHOR = "lead_author"
    BOARD_CERTIFIED = "board_certified"


@dataclass
class ExpertCredential:
    """Verified credentials for a domain expert."""

    author_id: str
    display_name: str
    level: ExpertLevel
    specialties: List[str]
    license_number: Optional[str] = None
    institution: Optional[str] = None
    registered_at: float = field(default_factory=time.time)
    credential_hash: str = ""

    def __post_init__(self):
        if not self.credential_hash:
            self.credential_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        payload = (
            f"{self.author_id}:{self.display_name}:{self.level.value}"
            f":{','.join(sorted(self.specialties))}:{self.license_number}"
            f":{self.institution}:{self.registered_at}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class ProvenanceManifest:
    """
    C2PA-inspired manifest that records who created/edited content,
    when, and how it links to prior versions.
    """

    content_hash: str
    author_id: str
    timestamp: float
    signature: str
    parent_manifests: List[str] = field(default_factory=list)
    manifest_id: str = ""
    action: str = "created"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.manifest_id:
            self.manifest_id = self._compute_id()

    def _compute_id(self) -> str:
        payload = (
            f"{self.content_hash}:{self.author_id}:{self.timestamp}:{self.signature}:{','.join(self.parent_manifests)}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:24]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data


class AuthorityRegistry:
    """Registry of verified domain experts and their credentials."""

    def __init__(self):
        self._experts: Dict[str, ExpertCredential] = {}
        self._revoked: Set[str] = set()

    def register_expert(
        self,
        author_id: str,
        display_name: str,
        level: ExpertLevel,
        specialties: List[str],
        license_number: Optional[str] = None,
        institution: Optional[str] = None,
    ) -> ExpertCredential:
        """Register and verify a new domain expert."""
        credential = ExpertCredential(
            author_id=author_id,
            display_name=display_name,
            level=level,
            specialties=specialties,
            license_number=license_number,
            institution=institution,
        )
        self._experts[author_id] = credential
        return credential

    def verify_author(self, author_id: str) -> bool:
        """Check if an author is registered and not revoked."""
        if author_id in self._revoked:
            return False
        return author_id in self._experts

    def get_expert_credentials(self, author_id: str) -> Optional[ExpertCredential]:
        if author_id in self._revoked:
            return None
        return self._experts.get(author_id)

    def revoke_expert(self, author_id: str) -> bool:
        if author_id in self._experts:
            self._revoked.add(author_id)
            return True
        return False

    def list_experts(
        self, specialty: Optional[str] = None, level: Optional[ExpertLevel] = None
    ) -> List[ExpertCredential]:
        results = []
        for aid, cred in self._experts.items():
            if aid in self._revoked:
                continue
            if specialty and specialty not in cred.specialties:
                continue
            if level and cred.level != level:
                continue
            results.append(cred)
        return results


class ContentSigner:
    """
    Signs and verifies content using HMAC-SHA256 (simulating asymmetric
    digital signatures for demonstration purposes).
    """

    def __init__(self, registry: AuthorityRegistry, signing_key: Optional[bytes] = None):
        self._registry = registry
        self._key: bytes = signing_key or secrets.token_bytes(32)
        self._manifests: Dict[str, ProvenanceManifest] = {}

    def sign_content(
        self,
        content: str | bytes,
        author_id: str,
        parent_manifest_ids: Optional[List[str]] = None,
        action: str = "created",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProvenanceManifest:
        """
        Hash the content, sign it with the author's identity, and return
        a provenance manifest.
        """
        if not self._registry.verify_author(author_id):
            raise PermissionError(f"Author '{author_id}' is not registered or has been revoked.")

        content_bytes = content.encode() if isinstance(content, str) else content
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        now = time.time()
        signature = self._create_signature(content_hash, author_id, now)

        manifest = ProvenanceManifest(
            content_hash=content_hash,
            author_id=author_id,
            timestamp=now,
            signature=signature,
            parent_manifests=parent_manifest_ids or [],
            action=action,
            metadata=metadata or {},
        )

        self._manifests[manifest.manifest_id] = manifest
        return manifest

    def verify_signature(self, manifest: ProvenanceManifest) -> bool:
        """Verify that the manifest's signature is authentic."""
        expected = self._create_signature(manifest.content_hash, manifest.author_id, manifest.timestamp)
        sig_valid = hmac.compare_digest(expected, manifest.signature)
        author_valid = self._registry.verify_author(manifest.author_id)
        return sig_valid and author_valid

    def create_manifest_chain(
        self,
        content_versions: List[tuple[str | bytes, str]],
        action: str = "edited",
    ) -> List[ProvenanceManifest]:
        """
        Build a chain of manifests for successive content versions.
        Each tuple is (content, author_id). The first item is treated as
        the original; subsequent items link back to their predecessor.
        """
        chain: List[ProvenanceManifest] = []
        for i, (content, author_id) in enumerate(content_versions):
            parent_ids = [chain[-1].manifest_id] if chain else []
            act = "created" if i == 0 else action
            manifest = self.sign_content(content, author_id, parent_manifest_ids=parent_ids, action=act)
            chain.append(manifest)
        return chain

    def get_manifest(self, manifest_id: str) -> Optional[ProvenanceManifest]:
        return self._manifests.get(manifest_id)

    def get_provenance_chain(self, manifest_id: str) -> List[ProvenanceManifest]:
        """Walk backwards through parent manifests to build the full chain."""
        chain: List[ProvenanceManifest] = []
        current = self._manifests.get(manifest_id)
        visited: Set[str] = set()

        while current and current.manifest_id not in visited:
            visited.add(current.manifest_id)
            chain.append(current)
            if current.parent_manifests:
                current = self._manifests.get(current.parent_manifests[0])
            else:
                break

        chain.reverse()
        return chain

    # ── Internal ────────────────────────────────────────────────────────

    def _create_signature(self, content_hash: str, author_id: str, ts: float) -> str:
        message = f"{content_hash}:{author_id}:{ts}".encode()
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()
