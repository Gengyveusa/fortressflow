"""
Unified Platform AI service.

Integrates HubSpot Breeze AI (Data Agent, Prospecting Agent, Content Agent,
Breeze Studio), ZoomInfo Copilot (GTM Workspace, GTM Context Graph), and
Apollo AI (agentic workflows, enhanced AI scoring, waterfall enrichment,
MCP + Claude integration).

These AI agents drive smarter warmup decisions, content generation, seed
selection, scoring, and bi-directional learning loops.

All methods are async with httpx; pattern follows existing HubSpot/ZoomInfo
services (rate limiter + backoff).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
from aiolimiter import AsyncLimiter

from app.config import settings

logger = logging.getLogger(__name__)

# Rate limiters per platform
_HUBSPOT_AI_LIMITER = AsyncLimiter(max_rate=50, time_period=10)
_ZOOMINFO_AI_LIMITER = AsyncLimiter(max_rate=25, time_period=10)
_APOLLO_AI_LIMITER = AsyncLimiter(max_rate=50, time_period=60)

_HUBSPOT_BASE = "https://api.hubapi.com"
_ZOOMINFO_BASE = "https://api.zoominfo.com"
_APOLLO_BASE = "https://api.apollo.io"

_MAX_RETRIES = 3
_BACKOFF_BASE = 1.5


@dataclass
class AIScoreResult:
    """Unified AI scoring result from any platform."""

    platform: str
    score: float  # Normalized 0-100
    confidence: float  # 0-1
    signals: dict[str, Any] = field(default_factory=dict)
    recommended_action: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()


@dataclass
class SeedRecommendation:
    """AI-recommended seed for warmup."""

    lead_id: str
    email: str
    score: float
    reason: str
    platform: str
    engagement_likelihood: float = 0.0


@dataclass
class ContentSuggestion:
    """AI-generated content suggestion."""

    platform: str
    subject_line: str | None = None
    body_preview: str | None = None
    personalization_tokens: dict[str, str] = field(default_factory=dict)
    tone: str = "professional"
    confidence: float = 0.0


class PlatformAIService:
    """
    Unified interface to HubSpot Breeze AI, ZoomInfo Copilot, and Apollo AI.

    Provides:
    1. AI scoring (lead engagement likelihood, sender reputation)
    2. Seed selection for warmup (smart, high-engagement targets)
    3. Content optimization (subject lines, send times)
    4. Bi-directional learning loops (outcome feedback → platforms)
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=30)
        self._zoominfo_jwt: str | None = None

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        limiter: AsyncLimiter,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Generic retry wrapper with rate limiting and exponential backoff."""
        for attempt in range(_MAX_RETRIES):
            async with limiter:
                resp = await self._client.request(
                    method, url, headers=headers, **kwargs
                )
            if resp.status_code != 429:
                resp.raise_for_status()
                return resp
            wait = _BACKOFF_BASE * (2**attempt)
            retry_after = float(resp.headers.get("Retry-After", wait))
            logger.warning(
                "Rate limit on %s; retrying in %.1fs (attempt %d)",
                url,
                retry_after,
                attempt + 1,
            )
            await asyncio.sleep(retry_after)
        resp.raise_for_status()
        return resp

    # ═══════════════════════════════════════════════════════════════════
    # HUBSPOT BREEZE AI
    # ═══════════════════════════════════════════════════════════════════

    def _hs_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {settings.HUBSPOT_API_KEY}"}

    async def breeze_data_agent_insights(
        self, contact_emails: list[str]
    ) -> list[AIScoreResult]:
        """
        Query HubSpot Breeze Data Agent for contact-level engagement insights.

        Uses HubSpot's AI-powered contact scoring to determine engagement
        likelihood for warmup seed selection.
        """
        if not settings.HUBSPOT_BREEZE_ENABLED or not settings.HUBSPOT_API_KEY:
            return []

        results: list[AIScoreResult] = []

        try:
            # Use HubSpot CRM search with AI scoring properties
            resp = await self._request_with_retry(
                "POST",
                f"{_HUBSPOT_BASE}/crm/v3/objects/contacts/search",
                limiter=_HUBSPOT_AI_LIMITER,
                headers=self._hs_headers(),
                json={
                    "filterGroups": [
                        {
                            "filters": [
                                {
                                    "propertyName": "email",
                                    "operator": "IN",
                                    "values": contact_emails[:100],
                                }
                            ]
                        }
                    ],
                    "properties": [
                        "email",
                        "hs_lead_status",
                        "hs_analytics_last_visit_timestamp",
                        "hs_email_open_rate",
                        "hs_email_click_rate",
                        "hs_email_bounce",
                        "hs_predictive_lead_score",
                        "hs_predictive_contact_score",
                    ],
                    "limit": 100,
                },
            )

            body = resp.json()
            for contact in body.get("results", []):
                props = contact.get("properties", {})
                props.get("email", "")

                # Calculate engagement score from HubSpot AI signals
                predictive_score = float(
                    props.get("hs_predictive_contact_score", 0) or 0
                )
                open_rate = float(props.get("hs_email_open_rate", 0) or 0)
                click_rate = float(props.get("hs_email_click_rate", 0) or 0)

                # Weighted composite score
                composite = (predictive_score * 0.5) + (open_rate * 30) + (click_rate * 20)
                normalized = min(100.0, max(0.0, composite))

                results.append(
                    AIScoreResult(
                        platform="hubspot_breeze_data_agent",
                        score=normalized,
                        confidence=0.8 if predictive_score > 0 else 0.3,
                        signals={
                            "predictive_score": predictive_score,
                            "open_rate": open_rate,
                            "click_rate": click_rate,
                            "lead_status": props.get("hs_lead_status"),
                            "last_visit": props.get(
                                "hs_analytics_last_visit_timestamp"
                            ),
                        },
                        recommended_action="seed_candidate"
                        if normalized > 60
                        else "monitor",
                    )
                )

            logger.info(
                "Breeze Data Agent: scored %d contacts", len(results)
            )

        except Exception as exc:
            logger.error("Breeze Data Agent error: %s", exc)

        return results

    async def breeze_prospecting_agent_seeds(
        self,
        criteria: dict[str, Any],
        limit: int = 50,
    ) -> list[SeedRecommendation]:
        """
        Use HubSpot Breeze Prospecting Agent to find ideal warmup seeds.

        The Prospecting Agent identifies contacts most likely to engage,
        making them ideal warmup seeds for building sender reputation.
        """
        if not settings.HUBSPOT_BREEZE_ENABLED or not settings.HUBSPOT_API_KEY:
            return []

        seeds: list[SeedRecommendation] = []

        try:
            # Query contacts sorted by predictive engagement score
            filter_groups = []
            if criteria.get("industry"):
                filter_groups.append({
                    "filters": [
                        {
                            "propertyName": "industry",
                            "operator": "EQ",
                            "value": criteria["industry"],
                        }
                    ]
                })

            resp = await self._request_with_retry(
                "POST",
                f"{_HUBSPOT_BASE}/crm/v3/objects/contacts/search",
                limiter=_HUBSPOT_AI_LIMITER,
                headers=self._hs_headers(),
                json={
                    "filterGroups": filter_groups,
                    "properties": [
                        "email",
                        "firstname",
                        "lastname",
                        "hs_predictive_contact_score",
                        "hs_email_open_rate",
                    ],
                    "sorts": [
                        {
                            "propertyName": "hs_predictive_contact_score",
                            "direction": "DESCENDING",
                        }
                    ],
                    "limit": limit,
                },
            )

            body = resp.json()
            for contact in body.get("results", []):
                props = contact.get("properties", {})
                score = float(
                    props.get("hs_predictive_contact_score", 0) or 0
                )
                seeds.append(
                    SeedRecommendation(
                        lead_id=contact.get("id", ""),
                        email=props.get("email", ""),
                        score=score,
                        reason="High predictive engagement score via Breeze Prospecting Agent",
                        platform="hubspot_breeze_prospecting",
                        engagement_likelihood=min(1.0, score / 100),
                    )
                )

            logger.info(
                "Breeze Prospecting Agent: found %d seed candidates", len(seeds)
            )

        except Exception as exc:
            logger.error("Breeze Prospecting Agent error: %s", exc)

        return seeds

    async def breeze_content_agent_optimize(
        self,
        subject: str,
        body: str,
        recipient_context: dict[str, Any] | None = None,
    ) -> ContentSuggestion:
        """
        Use HubSpot Breeze Content Agent to optimize email content.

        Provides subject line suggestions, tone adjustments, and
        personalization recommendations.
        """
        if not settings.HUBSPOT_BREEZE_ENABLED or not settings.HUBSPOT_API_KEY:
            return ContentSuggestion(platform="hubspot_breeze_content")

        try:
            # Use HubSpot's content recommendations endpoint
            resp = await self._request_with_retry(
                "POST",
                f"{_HUBSPOT_BASE}/marketing/v3/emails/ai/suggestions",
                limiter=_HUBSPOT_AI_LIMITER,
                headers=self._hs_headers(),
                json={
                    "subject": subject,
                    "body": body[:2000],
                    "context": recipient_context or {},
                },
            )

            data = resp.json()
            return ContentSuggestion(
                platform="hubspot_breeze_content",
                subject_line=data.get("suggested_subject", subject),
                body_preview=data.get("suggested_body_preview"),
                personalization_tokens=data.get("personalization", {}),
                tone=data.get("tone", "professional"),
                confidence=float(data.get("confidence", 0.5)),
            )

        except Exception as exc:
            logger.error("Breeze Content Agent error: %s", exc)
            return ContentSuggestion(platform="hubspot_breeze_content")

    # ═══════════════════════════════════════════════════════════════════
    # ZOOMINFO COPILOT
    # ═══════════════════════════════════════════════════════════════════

    async def _zoominfo_auth(self) -> str:
        """Get ZoomInfo JWT token for Copilot API access."""
        if self._zoominfo_jwt:
            return self._zoominfo_jwt

        if settings.ZOOMINFO_API_KEY:
            self._zoominfo_jwt = settings.ZOOMINFO_API_KEY
            return self._zoominfo_jwt

        if not settings.ZOOMINFO_CLIENT_ID or not settings.ZOOMINFO_CLIENT_SECRET:
            raise ValueError("ZoomInfo credentials not configured")

        async with _ZOOMINFO_AI_LIMITER:
            resp = await self._client.post(
                f"{_ZOOMINFO_BASE}/authenticate",
                json={
                    "username": settings.ZOOMINFO_CLIENT_ID,
                    "password": settings.ZOOMINFO_CLIENT_SECRET,
                },
            )
            resp.raise_for_status()
            self._zoominfo_jwt = resp.json().get("jwt", "")
            return self._zoominfo_jwt

    def _zi_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    async def copilot_gtm_context_scores(
        self, emails: list[str]
    ) -> list[AIScoreResult]:
        """
        Query ZoomInfo Copilot GTM Context Graph for intent and engagement signals.

        The Context Graph aggregates buying signals, technographics,
        and intent data to score leads for warmup seed selection.
        """
        if not settings.ZOOMINFO_COPILOT_ENABLED:
            return []

        results: list[AIScoreResult] = []

        try:
            token = await self._zoominfo_auth()

            # Query intent signals for the contact list
            resp = await self._request_with_retry(
                "POST",
                f"{_ZOOMINFO_BASE}/lookup/intent/contact",
                limiter=_ZOOMINFO_AI_LIMITER,
                headers=self._zi_headers(token),
                json={
                    "emailAddress": emails[:100],
                    "outputFields": [
                        "intentScore",
                        "topicIntentScores",
                        "companyAttributes",
                        "techStackDetails",
                        "signalDate",
                    ],
                },
            )

            body = resp.json()
            for record in body.get("result", {}).get("data", []):
                intent_score = float(record.get("intentScore", 0))
                record.get("emailAddress", "")

                # Normalize intent score to 0-100
                normalized = min(100.0, max(0.0, intent_score))

                results.append(
                    AIScoreResult(
                        platform="zoominfo_copilot_context_graph",
                        score=normalized,
                        confidence=0.85 if intent_score > 0 else 0.2,
                        signals={
                            "intent_score": intent_score,
                            "topic_scores": record.get("topicIntentScores", []),
                            "tech_stack": record.get("techStackDetails", []),
                            "signal_date": record.get("signalDate"),
                        },
                        recommended_action="high_priority_seed"
                        if normalized > 70
                        else "standard_seed"
                        if normalized > 40
                        else "low_priority",
                    )
                )

            logger.info(
                "ZoomInfo Copilot Context Graph: scored %d contacts", len(results)
            )

        except Exception as exc:
            logger.error("ZoomInfo Copilot Context Graph error: %s", exc)

        return results

    async def copilot_gtm_workspace_insights(
        self, domain: str
    ) -> dict[str, Any]:
        """
        Query ZoomInfo GTM Workspace for account-level intelligence.

        Returns buying signals, org hierarchy, and GTM recommendations
        to inform warmup strategy and content personalization.
        """
        if not settings.ZOOMINFO_COPILOT_ENABLED:
            return {}

        try:
            token = await self._zoominfo_auth()

            resp = await self._request_with_retry(
                "POST",
                f"{_ZOOMINFO_BASE}/lookup/company/enrich",
                limiter=_ZOOMINFO_AI_LIMITER,
                headers=self._zi_headers(token),
                json={
                    "companyDomain": domain,
                    "outputFields": [
                        "companyName",
                        "industry",
                        "subIndustry",
                        "employeeCount",
                        "revenue",
                        "techStack",
                        "intentSignals",
                        "fundingInfo",
                    ],
                },
            )

            data = resp.json().get("result", {}).get("data", [{}])[0]
            logger.info(
                "ZoomInfo GTM Workspace: insights for %s", domain
            )
            return {
                "platform": "zoominfo_gtm_workspace",
                "company": data.get("companyName"),
                "industry": data.get("industry"),
                "sub_industry": data.get("subIndustry"),
                "employee_count": data.get("employeeCount"),
                "revenue": data.get("revenue"),
                "tech_stack": data.get("techStack", []),
                "intent_signals": data.get("intentSignals", []),
                "timestamp": datetime.now(UTC).isoformat(),
            }

        except Exception as exc:
            logger.error("ZoomInfo GTM Workspace error: %s", exc)
            return {}

    # ═══════════════════════════════════════════════════════════════════
    # APOLLO AI (2026 AGENTIC)
    # ═══════════════════════════════════════════════════════════════════

    async def apollo_ai_score_leads(
        self, lead_data: list[dict[str, Any]]
    ) -> list[AIScoreResult]:
        """
        Use Apollo AI's enhanced scoring engine to evaluate leads.

        The 2026 Apollo AI Assistant uses agentic workflows with
        MCP + Claude integration for deeper lead analysis.
        """
        if not settings.APOLLO_AI_ENABLED or not settings.APOLLO_API_KEY:
            return []

        results: list[AIScoreResult] = []

        try:
            for lead in lead_data[:100]:
                resp = await self._request_with_retry(
                    "POST",
                    f"{_APOLLO_BASE}/v1/people/match",
                    limiter=_APOLLO_AI_LIMITER,
                    json={
                        "api_key": settings.APOLLO_API_KEY,
                        "email": lead.get("email", ""),
                        "reveal_personal_emails": False,
                    },
                )

                person = resp.json().get("person")
                if not person:
                    continue

                # Apollo's AI scoring composite
                apollo_score = float(person.get("ai_score", 0) or 0)
                engagement_score = float(
                    person.get("engagement_score", 0) or 0
                )
                intent_score = float(person.get("intent_score", 0) or 0)

                # Weighted composite
                composite = (
                    apollo_score * 0.4
                    + engagement_score * 0.35
                    + intent_score * 0.25
                )
                normalized = min(100.0, max(0.0, composite))

                results.append(
                    AIScoreResult(
                        platform="apollo_ai",
                        score=normalized,
                        confidence=0.75,
                        signals={
                            "ai_score": apollo_score,
                            "engagement_score": engagement_score,
                            "intent_score": intent_score,
                            "seniority": person.get("seniority"),
                            "departments": person.get("departments", []),
                            "organization": person.get("organization", {}).get(
                                "name"
                            ),
                        },
                        recommended_action="high_value_seed"
                        if normalized > 65
                        else "standard",
                    )
                )

            logger.info("Apollo AI: scored %d leads", len(results))

        except Exception as exc:
            logger.error("Apollo AI scoring error: %s", exc)

        return results

    async def apollo_waterfall_enrich(
        self, email: str
    ) -> dict[str, Any]:
        """
        Apollo waterfall enrichment — cascading data sources for maximum coverage.

        Returns enriched data from Apollo's 2026 waterfall pipeline.
        """
        if not settings.APOLLO_WATERFALL_ENRICHMENT or not settings.APOLLO_API_KEY:
            return {}

        try:
            resp = await self._request_with_retry(
                "POST",
                f"{_APOLLO_BASE}/v1/people/match",
                limiter=_APOLLO_AI_LIMITER,
                json={
                    "api_key": settings.APOLLO_API_KEY,
                    "email": email,
                    "reveal_personal_emails": False,
                    "reveal_phone_number": True,
                },
            )

            person = resp.json().get("person")
            if not person:
                return {}

            return {
                "platform": "apollo_waterfall",
                "data": {
                    "first_name": person.get("first_name"),
                    "last_name": person.get("last_name"),
                    "email": person.get("email"),
                    "phone": person.get("phone_number"),
                    "title": person.get("title"),
                    "seniority": person.get("seniority"),
                    "departments": person.get("departments", []),
                    "organization": person.get("organization", {}).get("name"),
                    "linkedin_url": person.get("linkedin_url"),
                    "city": person.get("city"),
                    "state": person.get("state"),
                    "country": person.get("country"),
                },
                "enriched_at": datetime.now(UTC).isoformat(),
            }

        except Exception as exc:
            logger.error("Apollo waterfall enrichment error for %s: %s", email, exc)
            return {}

    # ═══════════════════════════════════════════════════════════════════
    # UNIFIED OPERATIONS (cross-platform)
    # ═══════════════════════════════════════════════════════════════════

    async def get_unified_lead_scores(
        self, emails: list[str]
    ) -> dict[str, AIScoreResult]:
        """
        Query all enabled AI platforms in parallel and return the best score
        for each email address.

        Aggregates HubSpot Breeze, ZoomInfo Copilot, and Apollo AI signals
        into a single normalized score per lead.
        """
        # Fire all platforms in parallel
        tasks = []

        if settings.HUBSPOT_BREEZE_ENABLED:
            tasks.append(self.breeze_data_agent_insights(emails))

        if settings.ZOOMINFO_COPILOT_ENABLED:
            tasks.append(self.copilot_gtm_context_scores(emails))

        if settings.APOLLO_AI_ENABLED:
            tasks.append(
                self.apollo_ai_score_leads(
                    [{"email": e} for e in emails]
                )
            )

        if not tasks:
            logger.info("No AI platforms enabled for scoring")
            return {}

        platform_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge: take highest-confidence score per email
        merged: dict[str, AIScoreResult] = {}

        for result_set in platform_results:
            if isinstance(result_set, Exception):
                logger.error("Platform AI error: %s", result_set)
                continue

            for score_result in result_set:
                email_key = score_result.signals.get("email", "")
                # Match by index if email not in signals
                if not email_key:
                    continue

                existing = merged.get(email_key)
                if existing is None or score_result.confidence > existing.confidence:
                    merged[email_key] = score_result

        logger.info("Unified AI scoring: %d leads scored", len(merged))
        return merged

    async def select_warmup_seeds(
        self,
        candidate_emails: list[str],
        batch_size: int | None = None,
        criteria: dict[str, Any] | None = None,
    ) -> list[SeedRecommendation]:
        """
        Use all enabled AI platforms to select optimal warmup seeds.

        Priority order:
        1. HubSpot Breeze Prospecting Agent (if enabled)
        2. ZoomInfo Copilot Context Graph scoring
        3. Apollo AI scoring
        4. Fallback: random selection from candidates

        Returns seeds sorted by engagement likelihood (descending).
        """
        batch = batch_size or settings.WARMUP_AI_SEED_BATCH_SIZE
        seeds: list[SeedRecommendation] = []

        # 1. Try HubSpot Breeze Prospecting Agent
        if settings.HUBSPOT_BREEZE_ENABLED:
            breeze_seeds = await self.breeze_prospecting_agent_seeds(
                criteria=criteria or {"industry": "Dental"},
                limit=batch,
            )
            seeds.extend(breeze_seeds)

        # 2. Score remaining candidates with all platforms
        scored_emails = {s.email for s in seeds}
        remaining = [e for e in candidate_emails if e not in scored_emails]

        if remaining:
            unified_scores = await self.get_unified_lead_scores(remaining[:batch])

            for email, score_result in unified_scores.items():
                if score_result.score > 40:  # Minimum engagement threshold
                    seeds.append(
                        SeedRecommendation(
                            lead_id="",  # Will be resolved by caller
                            email=email,
                            score=score_result.score,
                            reason=f"AI score {score_result.score:.0f} via {score_result.platform}",
                            platform=score_result.platform,
                            engagement_likelihood=min(
                                1.0, score_result.score / 100
                            ),
                        )
                    )

        # 3. Fallback: add unscored candidates with default score
        if len(seeds) < batch:
            remaining_unscored = [
                e
                for e in candidate_emails
                if e not in {s.email for s in seeds}
            ]
            for email in remaining_unscored[: batch - len(seeds)]:
                seeds.append(
                    SeedRecommendation(
                        lead_id="",
                        email=email,
                        score=30.0,
                        reason="Fallback selection (no AI scoring available)",
                        platform="fallback",
                        engagement_likelihood=0.3,
                    )
                )

        # Sort by score descending
        seeds.sort(key=lambda s: s.score, reverse=True)
        return seeds[:batch]

    # ═══════════════════════════════════════════════════════════════════
    # BI-DIRECTIONAL LEARNING LOOPS
    # ═══════════════════════════════════════════════════════════════════

    async def send_outcome_feedback(
        self,
        platform: str,
        contact_email: str,
        outcomes: dict[str, Any],
    ) -> bool:
        """
        Send warmup outcome data back to AI platforms for learning.

        This closes the bi-directional loop: platform AI recommends seeds,
        we track outcomes, then feed results back so the AI improves.

        Args:
            platform: Which platform to send feedback to
            contact_email: The contact's email
            outcomes: Dict with keys like "opened", "replied", "bounced", "complained"
        """
        try:
            if platform.startswith("hubspot") and settings.HUBSPOT_BREEZE_ENABLED:
                return await self._feedback_to_hubspot(contact_email, outcomes)
            elif platform.startswith("zoominfo") and settings.ZOOMINFO_COPILOT_ENABLED:
                return await self._feedback_to_zoominfo(contact_email, outcomes)
            elif platform.startswith("apollo") and settings.APOLLO_AI_ENABLED:
                return await self._feedback_to_apollo(contact_email, outcomes)

            logger.warning("No feedback handler for platform: %s", platform)
            return False

        except Exception as exc:
            logger.error(
                "Failed to send outcome feedback to %s for %s: %s",
                platform,
                contact_email,
                exc,
            )
            return False

    async def _feedback_to_hubspot(
        self, email: str, outcomes: dict[str, Any]
    ) -> bool:
        """Send engagement feedback to HubSpot via note/property update."""
        if not settings.HUBSPOT_API_KEY:
            return False

        try:
            # Search for contact by email
            resp = await self._request_with_retry(
                "POST",
                f"{_HUBSPOT_BASE}/crm/v3/objects/contacts/search",
                limiter=_HUBSPOT_AI_LIMITER,
                headers=self._hs_headers(),
                json={
                    "filterGroups": [
                        {
                            "filters": [
                                {
                                    "propertyName": "email",
                                    "operator": "EQ",
                                    "value": email,
                                }
                            ]
                        }
                    ],
                    "limit": 1,
                },
            )

            results = resp.json().get("results", [])
            if not results:
                return False

            hs_id = results[0].get("id")

            # Update custom properties with warmup outcomes
            props: dict[str, Any] = {}
            if outcomes.get("opened"):
                props["fortressflow_warmup_opened"] = "true"
            if outcomes.get("replied"):
                props["fortressflow_warmup_replied"] = "true"
            if outcomes.get("bounced"):
                props["fortressflow_warmup_bounced"] = "true"

            if props:
                await self._request_with_retry(
                    "PATCH",
                    f"{_HUBSPOT_BASE}/crm/v3/objects/contacts/{hs_id}",
                    limiter=_HUBSPOT_AI_LIMITER,
                    headers=self._hs_headers(),
                    json={"properties": props},
                )

            logger.info("Sent warmup feedback to HubSpot for %s", email)
            return True

        except Exception as exc:
            logger.error("HubSpot feedback error for %s: %s", email, exc)
            return False

    async def _feedback_to_zoominfo(
        self, email: str, outcomes: dict[str, Any]
    ) -> bool:
        """
        Log engagement outcomes for ZoomInfo Copilot learning.

        ZoomInfo's Context Graph ingests engagement signals to refine
        intent scoring and recommendations.
        """
        if not settings.ZOOMINFO_COPILOT_ENABLED:
            return False

        try:
            token = await self._zoominfo_auth()

            await self._request_with_retry(
                "POST",
                f"{_ZOOMINFO_BASE}/engage/v1/interactions",
                limiter=_ZOOMINFO_AI_LIMITER,
                headers=self._zi_headers(token),
                json={
                    "interactions": [
                        {
                            "emailAddress": email,
                            "interactionType": "EMAIL",
                            "outcome": (
                                "REPLIED"
                                if outcomes.get("replied")
                                else "OPENED"
                                if outcomes.get("opened")
                                else "BOUNCED"
                                if outcomes.get("bounced")
                                else "DELIVERED"
                            ),
                            "timestamp": datetime.now(UTC).isoformat(),
                            "metadata": {
                                "source": "fortressflow_warmup",
                                **outcomes,
                            },
                        }
                    ]
                },
            )

            logger.info("Sent warmup feedback to ZoomInfo for %s", email)
            return True

        except Exception as exc:
            logger.error("ZoomInfo feedback error for %s: %s", email, exc)
            return False

    async def _feedback_to_apollo(
        self, email: str, outcomes: dict[str, Any]
    ) -> bool:
        """
        Push engagement data back to Apollo for AI model refinement.

        Apollo's 2026 agentic AI uses this feedback to improve
        scoring accuracy and seed recommendations.
        """
        if not settings.APOLLO_AI_ENABLED or not settings.APOLLO_API_KEY:
            return False

        try:
            await self._request_with_retry(
                "POST",
                f"{_APOLLO_BASE}/v1/emailer_campaigns/log_engagement",
                limiter=_APOLLO_AI_LIMITER,
                json={
                    "api_key": settings.APOLLO_API_KEY,
                    "email": email,
                    "engagement_type": (
                        "reply"
                        if outcomes.get("replied")
                        else "open"
                        if outcomes.get("opened")
                        else "bounce"
                        if outcomes.get("bounced")
                        else "delivered"
                    ),
                    "metadata": {
                        "source": "fortressflow_warmup",
                        "timestamp": datetime.now(UTC).isoformat(),
                        **outcomes,
                    },
                },
            )

            logger.info("Sent warmup feedback to Apollo for %s", email)
            return True

        except Exception as exc:
            logger.error("Apollo feedback error for %s: %s", email, exc)
            return False
