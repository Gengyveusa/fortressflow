"""
Value / Connected Packaging Authentication
Manages product profiles linked to NFC/QR identifiers, with personalized
content delivery and scan-event tracking.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class CertificationType(str, Enum):
    ADA_SEAL = "ADA Seal of Acceptance"
    FDA_CLEARED = "FDA 510(k) Cleared"
    ORGANIC = "USDA Organic"
    NON_GMO = "Non-GMO Project Verified"
    CRUELTY_FREE = "Leaping Bunny Certified"
    VEGAN = "Vegan Certified"
    FAIR_TRADE = "Fair Trade Certified"
    ISO_13485 = "ISO 13485"


class ScanEventType(str, Enum):
    QR_SCAN = "qr_scan"
    NFC_TAP = "nfc_tap"
    MANUAL_ENTRY = "manual_entry"
    APP_DEEP_LINK = "app_deep_link"


@dataclass
class Ingredient:
    name: str
    purpose: str
    concentration: Optional[str] = None
    is_active: bool = False
    allergen_flag: bool = False


@dataclass
class ProvenanceRecord:
    """Where the product (or its key ingredients) came from."""
    origin_country: str
    manufacturer: str
    lot_number: str
    manufactured_date: str
    expiration_date: str
    supply_chain_hash: str = ""

    def __post_init__(self):
        if not self.supply_chain_hash:
            payload = (
                f"{self.origin_country}:{self.manufacturer}:{self.lot_number}"
                f":{self.manufactured_date}:{self.expiration_date}"
            )
            self.supply_chain_hash = hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class PackageProfile:
    """Full digital twin of a connected product package."""
    product_id: str
    nfc_id: Optional[str] = None
    qr_code: Optional[str] = None
    product_name: str = ""
    brand: str = ""
    provenance: Optional[ProvenanceRecord] = None
    ingredients: List[Ingredient] = field(default_factory=list)
    certifications: List[CertificationType] = field(default_factory=list)
    category: str = ""
    profile_hash: str = ""
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.profile_hash:
            self.profile_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        payload = json.dumps({
            "product_id": self.product_id,
            "nfc_id": self.nfc_id,
            "qr_code": self.qr_code,
            "product_name": self.product_name,
            "brand": self.brand,
            "certifications": [c.value for c in self.certifications],
        }, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PersonalizedTip:
    tip_id: str
    text: str
    relevance_score: float
    category: str


@dataclass
class ResearchSummary:
    title: str
    summary: str
    doi: Optional[str] = None
    relevance_score: float = 0.0


@dataclass
class ScanResponse:
    """Payload returned to a consumer who scans a product."""
    product_info: PackageProfile
    personalized_tips: List[PersonalizedTip] = field(default_factory=list)
    research_summaries: List[ResearchSummary] = field(default_factory=list)
    rewards: Dict[str, Any] = field(default_factory=dict)
    scan_timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScanEvent:
    """An immutable record that a product was scanned."""
    event_id: str
    product_id: str
    scan_type: ScanEventType
    user_id: Optional[str]
    timestamp: float
    location: Optional[str] = None
    device_fingerprint: Optional[str] = None


class ConnectedPackagingService:
    """
    Service layer for the connected-packaging value-authentication system.
    Manages product registration, scanning, personalization, and analytics.
    """

    def __init__(self):
        self._products: Dict[str, PackageProfile] = {}
        self._nfc_index: Dict[str, str] = {}   # nfc_id -> product_id
        self._qr_index: Dict[str, str] = {}    # qr_code -> product_id
        self._events: List[ScanEvent] = []
        self._user_profiles: Dict[str, Dict[str, Any]] = {}

    # ── Product Management ──────────────────────────────────────────────

    def register_product(self, profile: PackageProfile) -> PackageProfile:
        """Register a new product, indexing its NFC/QR identifiers."""
        if profile.product_id in self._products:
            raise ValueError(f"Product '{profile.product_id}' is already registered.")

        if not profile.nfc_id:
            profile.nfc_id = f"NFC-{secrets.token_hex(8).upper()}"
        if not profile.qr_code:
            profile.qr_code = f"https://fortressflow.com/p/{profile.product_id}?t={secrets.token_urlsafe(12)}"

        # Recompute hash now that identifiers are finalized
        profile.profile_hash = profile._compute_hash()

        self._products[profile.product_id] = profile
        self._nfc_index[profile.nfc_id] = profile.product_id
        self._qr_index[profile.qr_code] = profile.product_id
        return profile

    def get_product(self, product_id: str) -> Optional[PackageProfile]:
        return self._products.get(product_id)

    # ── Scanning ────────────────────────────────────────────────────────

    def scan_product(
        self,
        identifier: str,
        scan_type: ScanEventType = ScanEventType.QR_SCAN,
        user_id: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Optional[ScanResponse]:
        """
        Look up a product by NFC ID, QR code, or product ID, record the
        scan event, and return a personalized response.
        """
        product_id = self._resolve_identifier(identifier)
        if not product_id:
            return None

        profile = self._products[product_id]

        # Record the scan
        self.record_scan_event(product_id, scan_type, user_id, location)

        tips = self.get_personalized_content(product_id, user_id)
        summaries = self._get_research_summaries(profile)
        rewards = self._compute_rewards(user_id, product_id)

        return ScanResponse(
            product_info=profile,
            personalized_tips=tips,
            research_summaries=summaries,
            rewards=rewards,
        )

    def record_scan_event(
        self,
        product_id: str,
        scan_type: ScanEventType,
        user_id: Optional[str] = None,
        location: Optional[str] = None,
    ) -> ScanEvent:
        event = ScanEvent(
            event_id=secrets.token_hex(12),
            product_id=product_id,
            scan_type=scan_type,
            user_id=user_id,
            timestamp=time.time(),
            location=location,
        )
        self._events.append(event)
        return event

    # ── Personalization ─────────────────────────────────────────────────

    def set_user_profile(self, user_id: str, profile: Dict[str, Any]) -> None:
        """Store user preferences/conditions for personalized tips."""
        self._user_profiles[user_id] = profile

    def get_personalized_content(
        self,
        product_id: str,
        user_id: Optional[str] = None,
    ) -> List[PersonalizedTip]:
        """
        Generate tips personalized to the user's profile and the specific
        product they scanned.
        """
        profile = self._products.get(product_id)
        if not profile:
            return []

        tips: List[PersonalizedTip] = []
        user_prefs = self._user_profiles.get(user_id or "", {})
        conditions = user_prefs.get("conditions", [])

        # Generic tips based on product certifications
        if CertificationType.ADA_SEAL in profile.certifications:
            tips.append(PersonalizedTip(
                tip_id=secrets.token_hex(6),
                text="This product carries the ADA Seal of Acceptance, meaning it has been independently tested for safety and efficacy.",
                relevance_score=0.9,
                category="certification",
            ))

        # Condition-specific tips
        active_ingredients = [i for i in profile.ingredients if i.is_active]
        if active_ingredients:
            names = ", ".join(i.name for i in active_ingredients)
            tips.append(PersonalizedTip(
                tip_id=secrets.token_hex(6),
                text=f"Active ingredients in this product: {names}. Consult your dental professional for personalized guidance.",
                relevance_score=0.85,
                category="ingredients",
            ))

        if "diabetes" in conditions:
            tips.append(PersonalizedTip(
                tip_id=secrets.token_hex(6),
                text="Managing oral health is especially important with diabetes. Periodontal disease and blood sugar levels influence each other.",
                relevance_score=0.95,
                category="health_connection",
            ))

        if "pregnancy" in conditions:
            tips.append(PersonalizedTip(
                tip_id=secrets.token_hex(6),
                text="Maintaining gum health during pregnancy is linked to better outcomes. Ask your dentist about a pregnancy oral care plan.",
                relevance_score=0.93,
                category="health_connection",
            ))

        allergen_ingredients = [i for i in profile.ingredients if i.allergen_flag]
        if allergen_ingredients:
            names = ", ".join(i.name for i in allergen_ingredients)
            tips.append(PersonalizedTip(
                tip_id=secrets.token_hex(6),
                text=f"Allergen notice: this product contains {names}.",
                relevance_score=1.0,
                category="safety",
            ))

        return tips

    # ── Analytics ────────────────────────────────────────────────────────

    def get_scan_history(
        self,
        product_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        results = []
        for event in reversed(self._events):
            if product_id and event.product_id != product_id:
                continue
            if user_id and event.user_id != user_id:
                continue
            results.append(asdict(event))
            if len(results) >= limit:
                break
        return results

    # ── Internal helpers ────────────────────────────────────────────────

    def _resolve_identifier(self, identifier: str) -> Optional[str]:
        if identifier in self._products:
            return identifier
        if identifier in self._nfc_index:
            return self._nfc_index[identifier]
        if identifier in self._qr_index:
            return self._qr_index[identifier]
        # Partial QR match (URL might be trimmed)
        for qr, pid in self._qr_index.items():
            if identifier in qr:
                return pid
        return None

    @staticmethod
    def _get_research_summaries(profile: PackageProfile) -> List[ResearchSummary]:
        """Return canned research summaries relevant to the product category."""
        summaries: List[ResearchSummary] = []
        cat = profile.category.lower()

        if "toothpaste" in cat or "dentifrice" in cat:
            summaries.append(ResearchSummary(
                title="Fluoride Toothpaste Efficacy in Caries Prevention",
                summary="Systematic reviews confirm that fluoride toothpaste reduces caries incidence by 24-33% compared to non-fluoride alternatives.",
                doi="10.1002/14651858.CD007868.pub2",
                relevance_score=0.9,
            ))
        if "mouthwash" in cat or "rinse" in cat:
            summaries.append(ResearchSummary(
                title="Antimicrobial Mouth Rinses as Adjuncts to Oral Hygiene",
                summary="Chlorhexidine and CPC-based rinses show statistically significant plaque and gingivitis reduction when used alongside brushing.",
                doi="10.1002/14651858.CD008676.pub2",
                relevance_score=0.88,
            ))
        if not summaries:
            summaries.append(ResearchSummary(
                title="Oral Health and Overall Wellness",
                summary="Maintaining good oral hygiene is associated with reduced risk of systemic conditions including cardiovascular disease and diabetes.",
                relevance_score=0.75,
            ))
        return summaries

    def _compute_rewards(self, user_id: Optional[str], product_id: str) -> Dict[str, Any]:
        """Simple loyalty/rewards calculation based on scan frequency."""
        if not user_id:
            return {"eligible": False, "reason": "Sign in to earn rewards."}

        user_scans = sum(
            1 for e in self._events
            if e.user_id == user_id and e.product_id == product_id
        )
        points = user_scans * 10
        tier = "bronze"
        if points >= 100:
            tier = "silver"
        if points >= 500:
            tier = "gold"

        return {
            "eligible": True,
            "points_earned": 10,
            "total_points": points,
            "tier": tier,
            "next_tier_at": {"bronze": 100, "silver": 500, "gold": 1000}.get(tier, 9999),
        }
