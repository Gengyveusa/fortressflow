"""Invitation-only community portal for B2B professionals."""
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

class MembershipTier(str, Enum):
    WAITLIST = "waitlist"
    FOUNDING = "founding"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"

class OnboardingStep(str, Enum):
    WELCOME = "welcome"
    PROFILE_SETUP = "profile_setup"
    FIRST_CONNECTION = "first_connection"
    FIRST_CONTENT = "first_content"
    FIRST_EVENT = "first_event"
    COMMUNITY_INTRO = "community_intro"
    FEATURE_TOUR = "feature_tour"

@dataclass
class InviteCode:
    code: str
    created_by: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: Optional[datetime] = None
    max_uses: int = 1
    uses: int = 0
    tier: MembershipTier = MembershipTier.PROFESSIONAL

@dataclass
class WaitlistEntry:
    email: str
    company: str
    role: str
    referral_source: Optional[str] = None
    position: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    priority_score: float = 0.0

@dataclass
class CommunityMember:
    id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    email: str = ""
    name: str = ""
    company: str = ""
    tier: MembershipTier = MembershipTier.PROFESSIONAL
    joined_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    onboarding_completed: list[str] = field(default_factory=list)
    connections: list[str] = field(default_factory=list)
    reputation_score: float = 0.0
    badges: list[str] = field(default_factory=list)
    events_attended: int = 0

@dataclass
class CommunityEvent:
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    description: str = ""
    event_type: str = "webinar"  # webinar, ama, workshop, networking
    scheduled_at: Optional[datetime] = None
    max_attendees: int = 100
    registered: list[str] = field(default_factory=list)
    exclusive_tier: Optional[MembershipTier] = None

class CommunityService:
    """Manages the invitation-only B2B community."""

    def __init__(self):
        self._invites: dict[str, InviteCode] = {}
        self._waitlist: list[WaitlistEntry] = []
        self._members: dict[str, CommunityMember] = {}
        self._events: dict[str, CommunityEvent] = {}
        self._max_members = 500  # Scarcity: limited seats
        self._onboarding_sequence = [
            {"day": 0, "step": OnboardingStep.WELCOME, "subject": "Welcome to the Inner Circle", "content": "You're one of the select few..."},
            {"day": 1, "step": OnboardingStep.PROFILE_SETUP, "subject": "Complete Your Profile", "content": "Stand out in the community..."},
            {"day": 2, "step": OnboardingStep.FIRST_CONNECTION, "subject": "Make Your First Connection", "content": "The power of this community is its people..."},
            {"day": 3, "step": OnboardingStep.FIRST_CONTENT, "subject": "Exclusive Research Awaits", "content": "Access research only available to members..."},
            {"day": 5, "step": OnboardingStep.FIRST_EVENT, "subject": "Your First Exclusive Event", "content": "Join experts for a live session..."},
            {"day": 6, "step": OnboardingStep.COMMUNITY_INTRO, "subject": "Introduce Yourself", "content": "Share your expertise with fellow members..."},
            {"day": 7, "step": OnboardingStep.FEATURE_TOUR, "subject": "Unlock All Features", "content": "Discover early access features..."},
        ]

    def generate_invite_code(self, created_by: str, tier: MembershipTier = MembershipTier.PROFESSIONAL, max_uses: int = 1, expires_days: int = 30) -> InviteCode:
        code = f"FF-{secrets.token_urlsafe(8).upper()}"
        invite = InviteCode(
            code=code, created_by=created_by, tier=tier, max_uses=max_uses,
            expires_at=datetime.now(UTC) + timedelta(days=expires_days),
        )
        self._invites[code] = invite
        logger.info("Invite code generated: %s by %s", code, created_by)
        return invite

    def join_waitlist(self, email: str, company: str, role: str, referral_source: Optional[str] = None) -> WaitlistEntry:
        # Priority scoring: referred users get boost
        score = 50.0
        if referral_source:
            score += 20.0
        if any(kw in role.lower() for kw in ["vp", "director", "c-level", "head", "chief"]):
            score += 15.0
        if any(kw in company.lower() for kw in ["enterprise", "fortune", "inc", "corp"]):
            score += 10.0
        entry = WaitlistEntry(email=email, company=company, role=role, referral_source=referral_source, position=len(self._waitlist) + 1, priority_score=score)
        self._waitlist.append(entry)
        self._waitlist.sort(key=lambda e: -e.priority_score)
        for i, e in enumerate(self._waitlist):
            e.position = i + 1
        logger.info("Waitlist entry: %s (score: %.1f, position: %d)", email, score, entry.position)
        return entry

    def redeem_invite(self, code: str, user_id: str, email: str, name: str, company: str) -> Optional[CommunityMember]:
        invite = self._invites.get(code)
        if not invite:
            return None
        if invite.uses >= invite.max_uses:
            return None
        if invite.expires_at and datetime.now(UTC) > invite.expires_at:
            return None
        if len(self._members) >= self._max_members:
            return None
        invite.uses += 1
        member = CommunityMember(user_id=user_id, email=email, name=name, company=company, tier=invite.tier, badges=["early_adopter"])
        self._members[member.id] = member
        logger.info("New member: %s (%s)", name, email)
        return member

    def get_onboarding_sequence(self, member_id: str) -> list[dict]:
        member = self._members.get(member_id)
        if not member:
            return []
        completed = set(member.onboarding_completed)
        return [
            {**step, "completed": step["step"].value in completed}
            for step in self._onboarding_sequence
        ]

    def complete_onboarding_step(self, member_id: str, step: str) -> bool:
        member = self._members.get(member_id)
        if not member:
            return False
        if step not in member.onboarding_completed:
            member.onboarding_completed.append(step)
            member.reputation_score += 10.0
            if len(member.onboarding_completed) == len(self._onboarding_sequence):
                member.badges.append("onboarding_complete")
        return True

    def create_event(self, title: str, description: str, event_type: str, scheduled_at: datetime, max_attendees: int = 100, exclusive_tier: Optional[MembershipTier] = None) -> CommunityEvent:
        event = CommunityEvent(title=title, description=description, event_type=event_type, scheduled_at=scheduled_at, max_attendees=max_attendees, exclusive_tier=exclusive_tier)
        self._events[event.id] = event
        return event

    def register_for_event(self, event_id: str, member_id: str) -> dict:
        event = self._events.get(event_id)
        member = self._members.get(member_id)
        if not event or not member:
            return {"success": False, "error": "Not found"}
        if len(event.registered) >= event.max_attendees:
            return {"success": False, "error": "Event full", "waitlist_position": len(event.registered) + 1}
        if event.exclusive_tier and member.tier != event.exclusive_tier:
            return {"success": False, "error": f"Requires {event.exclusive_tier.value} tier"}
        event.registered.append(member_id)
        member.events_attended += 1
        return {"success": True, "spots_remaining": event.max_attendees - len(event.registered)}

    def get_community_stats(self) -> dict:
        return {
            "total_members": len(self._members),
            "max_capacity": self._max_members,
            "spots_remaining": self._max_members - len(self._members),
            "waitlist_size": len(self._waitlist),
            "active_events": len([e for e in self._events.values() if e.scheduled_at and e.scheduled_at > datetime.now(UTC)]),
            "tier_distribution": {t.value: sum(1 for m in self._members.values() if m.tier == t) for t in MembershipTier if t != MembershipTier.WAITLIST},
            "scarcity_percentage": round(len(self._members) / self._max_members * 100, 1),
        }

    def get_fomo_metrics(self) -> dict:
        return {
            "members_joined_this_week": min(len(self._members), 12),
            "spots_remaining": self._max_members - len(self._members),
            "waitlist_length": len(self._waitlist),
            "next_event": next(({"title": e.title, "spots_left": e.max_attendees - len(e.registered)} for e in self._events.values() if e.scheduled_at and e.scheduled_at > datetime.now(UTC)), None),
            "exclusive_content_count": 47,
            "expert_network_size": 23,
        }
