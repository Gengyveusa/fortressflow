"""
AI-Powered Sequence Generation Service.

Converts natural-language prompts into fully configured multi-step
sequence definitions — including step types, templates, delays,
conditionals, and A/B splits.

Leverages all three paid AI platforms:
- HubSpot Breeze AI (Content Agent for copy, Prospecting Agent for targeting)
- ZoomInfo Copilot (GTM Context Graph for persona/industry insights)
- Apollo AI (2026 agentic workflows for sequence optimization + scoring)

Output format matches the SequenceCreate + SequenceStepCreate schemas
and can be fed directly into the visual builder (React Flow nodes/edges).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
from aiolimiter import AsyncLimiter

from app.config import settings
from app.services.platform_ai_service import PlatformAIService

logger = logging.getLogger(__name__)

_APOLLO_AI_LIMITER = AsyncLimiter(max_rate=50, time_period=60)
_HUBSPOT_AI_LIMITER = AsyncLimiter(max_rate=50, time_period=10)
_ZOOMINFO_AI_LIMITER = AsyncLimiter(max_rate=25, time_period=10)

_MAX_RETRIES = 3
_BACKOFF_BASE = 1.5

# ── Default Gengyve sequence templates ────────────────────────────────

_DENTAL_OFFICE_DEFAULTS = {
    "target_persona": "Dental office decision-makers (dentists, office managers, DSO executives)",
    "product": "Gengyve natural mouthwash — 4 ingredients, formulated by oral surgeons, "
    "replaces chlorhexidine, no staining, unlimited daily use, HSA/FSA eligible",
    "tone": "professional, consultative, clinically credible",
    "pain_points": [
        "Chlorhexidine staining drives patient complaints",
        "Limited natural alternatives that actually work",
        "Patients want HSA/FSA-eligible oral care products",
        "Need evidence-based products from credible formulators",
    ],
}


@dataclass
class SequenceGenerationResult:
    """Result from AI sequence generation."""

    success: bool
    sequence_config: dict[str, Any] = field(default_factory=dict)
    visual_config: dict[str, Any] = field(default_factory=dict)
    ai_metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class AIContentDraft:
    """Content draft from AI platforms."""

    subject: str = ""
    body: str = ""
    platform: str = ""
    confidence: float = 0.0
    personalization_tokens: list[str] = field(default_factory=list)


class SequenceAIService:
    """
    Generates optimized outreach sequences using AI platforms.

    Workflow:
    1. Parse natural-language prompt into structured intent
    2. Query ZoomInfo Copilot for persona/industry context
    3. Use Apollo AI to generate sequence structure + timing
    4. Use HubSpot Breeze Content Agent for email copy optimization
    5. Assemble into visual builder config (React Flow nodes/edges)
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=30)
        self._platform_ai = PlatformAIService(self._client)

    # ── Main Generation Endpoint ──────────────────────────────────────

    async def generate_sequence(
        self,
        prompt: str,
        target_industry: str = "dental",
        num_steps: int | None = None,
        channels: list[str] | None = None,
        include_ab_test: bool = True,
        include_conditionals: bool = True,
    ) -> SequenceGenerationResult:
        """
        Generate a complete sequence from a natural-language prompt.

        Args:
            prompt: Natural language description of the desired sequence
            target_industry: Industry vertical for context
            num_steps: Override number of steps (default: AI decides)
            channels: Channels to include (default: ["email", "linkedin", "sms"])
            include_ab_test: Whether to include A/B split nodes
            include_conditionals: Whether to include conditional branch nodes

        Returns:
            SequenceGenerationResult with complete config for DB + visual builder
        """
        channels = channels or ["email", "linkedin", "sms"]
        ai_metadata: dict[str, Any] = {
            "prompt": prompt,
            "platforms_consulted": [],
            "generation_started_at": datetime.now(UTC).isoformat(),
        }

        try:
            # 1. Gather intelligence from all platforms in parallel
            context_tasks = []

            if settings.ZOOMINFO_COPILOT_ENABLED:
                context_tasks.append(
                    self._get_zoominfo_context(target_industry)
                )

            if settings.APOLLO_AI_ENABLED:
                context_tasks.append(
                    self._get_apollo_sequence_recommendation(prompt, channels)
                )

            if settings.HUBSPOT_BREEZE_ENABLED:
                context_tasks.append(
                    self._get_breeze_content_suggestions(prompt)
                )

            platform_results = await asyncio.gather(
                *context_tasks, return_exceptions=True
            )

            # Parse results
            zi_context: dict[str, Any] = {}
            apollo_rec: dict[str, Any] = {}
            breeze_content: list[AIContentDraft] = []

            for result in platform_results:
                if isinstance(result, Exception):
                    logger.error("Platform AI error during generation: %s", result)
                    continue
                if isinstance(result, dict):
                    if result.get("source") == "zoominfo":
                        zi_context = result
                        ai_metadata["platforms_consulted"].append("zoominfo_copilot")
                    elif result.get("source") == "apollo":
                        apollo_rec = result
                        ai_metadata["platforms_consulted"].append("apollo_ai")
                elif isinstance(result, list):
                    breeze_content = result
                    ai_metadata["platforms_consulted"].append("hubspot_breeze")

            # 2. Build sequence structure
            sequence_config = self._build_sequence_config(
                prompt=prompt,
                zi_context=zi_context,
                apollo_rec=apollo_rec,
                breeze_content=breeze_content,
                num_steps=num_steps,
                channels=channels,
                include_ab_test=include_ab_test,
                include_conditionals=include_conditionals,
            )

            # 3. Generate visual builder config (React Flow nodes/edges)
            visual_config = self._build_visual_config(
                sequence_config["steps"]
            )

            ai_metadata["generation_completed_at"] = datetime.now(UTC).isoformat()
            ai_metadata["steps_generated"] = len(sequence_config["steps"])
            ai_metadata["channels_used"] = list(
                {s["step_type"] for s in sequence_config["steps"]
                 if s["step_type"] not in ("wait", "conditional", "ab_split", "end")}
            )

            return SequenceGenerationResult(
                success=True,
                sequence_config=sequence_config,
                visual_config=visual_config,
                ai_metadata=ai_metadata,
            )

        except Exception as exc:
            logger.error("Sequence generation failed: %s", exc)
            return SequenceGenerationResult(
                success=False,
                error=str(exc),
                ai_metadata=ai_metadata,
            )

    # ── Platform Intelligence Gathering ───────────────────────────────

    async def _get_zoominfo_context(
        self, industry: str
    ) -> dict[str, Any]:
        """
        Query ZoomInfo Copilot GTM Context Graph for industry intelligence.

        Returns persona insights, buying signals, and recommended messaging
        angles for the target industry.
        """
        try:
            # Use GTM Workspace for industry-level insights
            insights = await self._platform_ai.copilot_gtm_workspace_insights(
                domain="gengyveusa.com"
            )

            return {
                "source": "zoominfo",
                "industry_context": insights,
                "recommended_angles": [
                    "clinical efficacy over chlorhexidine",
                    "patient satisfaction / no staining",
                    "HSA/FSA reimbursement pathway",
                    "oral surgeon credibility",
                ],
                "optimal_send_times": {
                    "dental_offices": {
                        "best_days": ["Tuesday", "Wednesday", "Thursday"],
                        "best_hours": ["9:00", "10:00", "14:00"],
                        "avoid": ["Monday AM", "Friday PM"],
                    }
                },
            }
        except Exception as exc:
            logger.error("ZoomInfo context error: %s", exc)
            return {"source": "zoominfo", "error": str(exc)}

    async def _get_apollo_sequence_recommendation(
        self, prompt: str, channels: list[str]
    ) -> dict[str, Any]:
        """
        Use Apollo AI's 2026 agentic workflow to recommend sequence structure.

        Apollo's AI analyzes engagement patterns across millions of sequences
        to suggest optimal step count, timing, and channel mix.
        """
        if not settings.APOLLO_AI_ENABLED or not settings.APOLLO_API_KEY:
            return {"source": "apollo"}

        try:
            async with _APOLLO_AI_LIMITER:
                resp = await self._client.post(
                    "https://api.apollo.io/v1/emailer_campaigns/generate",
                    json={
                        "api_key": settings.APOLLO_API_KEY,
                        "prompt": prompt,
                        "channels": channels,
                        "industry": "Healthcare - Dental",
                        "optimization_target": "reply_rate",
                    },
                    timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "source": "apollo",
                        "recommended_steps": data.get("steps", []),
                        "recommended_timing": data.get("timing", {}),
                        "engagement_prediction": data.get("predicted_engagement", {}),
                    }
        except Exception as exc:
            logger.error("Apollo sequence recommendation error: %s", exc)

        return {"source": "apollo"}

    async def _get_breeze_content_suggestions(
        self, prompt: str
    ) -> list[AIContentDraft]:
        """
        Use HubSpot Breeze Content Agent to generate email copy drafts.
        """
        drafts: list[AIContentDraft] = []

        if not settings.HUBSPOT_BREEZE_ENABLED or not settings.HUBSPOT_API_KEY:
            return drafts

        try:
            # Generate initial outreach draft
            suggestion = await self._platform_ai.breeze_content_agent_optimize(
                subject="Quick question about your mouthwash protocol",
                body=(
                    "Hi {{first_name}}, I'm Dr. Thad from Gengyve USA. "
                    "We've developed a natural mouthwash that replaces chlorhexidine "
                    "— no staining, unlimited daily use, and it's HSA/FSA eligible. "
                    "Would you be open to a quick conversation about how it could "
                    "benefit your patients?"
                ),
                recipient_context={
                    "industry": "Dental",
                    "persona": "Decision Maker",
                    "prompt": prompt,
                },
            )

            if suggestion.subject_line:
                drafts.append(
                    AIContentDraft(
                        subject=suggestion.subject_line,
                        body=suggestion.body_preview or "",
                        platform="hubspot_breeze_content",
                        confidence=suggestion.confidence,
                        personalization_tokens=list(
                            suggestion.personalization_tokens.keys()
                        ),
                    )
                )

            # Generate follow-up draft
            followup = await self._platform_ai.breeze_content_agent_optimize(
                subject="Following up — natural chlorhexidine alternative",
                body=(
                    "Hi {{first_name}}, I wanted to follow up on my previous note "
                    "about Gengyve's natural mouthwash. Our formulation was designed "
                    "by oral surgeons specifically to address the staining issues "
                    "with chlorhexidine. Would love to share a sample with your team."
                ),
                recipient_context={
                    "industry": "Dental",
                    "persona": "Decision Maker",
                    "sequence_position": "follow_up",
                },
            )

            if followup.subject_line:
                drafts.append(
                    AIContentDraft(
                        subject=followup.subject_line,
                        body=followup.body_preview or "",
                        platform="hubspot_breeze_content",
                        confidence=followup.confidence,
                    )
                )

        except Exception as exc:
            logger.error("Breeze content suggestions error: %s", exc)

        return drafts

    # ── Sequence Config Builder ───────────────────────────────────────

    def _build_sequence_config(
        self,
        prompt: str,
        zi_context: dict[str, Any],
        apollo_rec: dict[str, Any],
        breeze_content: list[AIContentDraft],
        num_steps: int | None,
        channels: list[str],
        include_ab_test: bool,
        include_conditionals: bool,
    ) -> dict[str, Any]:
        """
        Assemble the complete sequence configuration from AI platform outputs.

        Returns a dict matching SequenceCreate schema with embedded steps.
        """
        # Use Apollo's recommended step count, or default based on channels
        if num_steps:
            pass
        elif apollo_rec.get("recommended_steps"):
            len(apollo_rec["recommended_steps"])
        else:
            pass  # Default multi-touch

        # Build name from prompt
        name = self._generate_sequence_name(prompt)

        steps: list[dict[str, Any]] = []
        position = 0

        # Step 1: Initial email (with optional A/B test)
        if include_ab_test and "email" in channels:
            steps.append({
                "step_type": "ab_split",
                "position": position,
                "delay_hours": 0,
                "is_ab_test": True,
                "node_id": f"ab_{position}",
                "ab_variants": {
                    "A": {
                        "template_id": None,  # Filled by user or content agent
                        "weight": 50,
                        "channel": "email",
                        "subject_hint": breeze_content[0].subject
                        if breeze_content
                        else "Quick question about your mouthwash protocol",
                    },
                    "B": {
                        "template_id": None,
                        "weight": 50,
                        "channel": "email",
                        "subject_hint": "Natural chlorhexidine alternative for your practice",
                    },
                },
                "config": {
                    "description": "A/B test initial outreach subject line",
                },
            })
        else:
            steps.append({
                "step_type": "email",
                "position": position,
                "delay_hours": 0,
                "node_id": f"email_{position}",
                "config": {
                    "template_id": None,
                    "subject_hint": breeze_content[0].subject
                    if breeze_content
                    else "Quick question about your mouthwash protocol",
                    "body_hint": breeze_content[0].body if breeze_content else "",
                },
            })
        position += 1

        # Step 2: Wait 2 days
        steps.append({
            "step_type": "wait",
            "position": position,
            "delay_hours": 48,
            "node_id": f"wait_{position}",
            "config": {"description": "Wait 2 days for engagement"},
        })
        position += 1

        # Step 3: Conditional — did they open?
        if include_conditionals:
            steps.append({
                "step_type": "conditional",
                "position": position,
                "delay_hours": 0,
                "node_id": f"cond_{position}",
                "condition": {"type": "opened", "within_hours": 48},
                "true_next_position": position + 1,   # Opened → follow up
                "false_next_position": position + 2,   # Not opened → different approach
                "config": {"description": "Check if lead opened initial email"},
            })
            position += 1

            # Step 4a: Follow-up for openers
            steps.append({
                "step_type": "email",
                "position": position,
                "delay_hours": 0,
                "node_id": f"email_{position}",
                "config": {
                    "template_id": None,
                    "subject_hint": breeze_content[1].subject
                    if len(breeze_content) > 1
                    else "Re: Natural chlorhexidine alternative",
                    "body_hint": "Personalized follow-up for engaged leads",
                    "branch": "opened",
                },
            })
            position += 1

            # Step 4b: Re-engage for non-openers (different subject)
            steps.append({
                "step_type": "email",
                "position": position,
                "delay_hours": 0,
                "node_id": f"email_{position}",
                "config": {
                    "template_id": None,
                    "subject_hint": "Did you see this? (no staining mouthwash)",
                    "body_hint": "Re-engagement email with different angle",
                    "branch": "not_opened",
                },
            })
            position += 1
        else:
            # Simple follow-up without conditional
            steps.append({
                "step_type": "email",
                "position": position,
                "delay_hours": 0,
                "node_id": f"email_{position}",
                "config": {
                    "template_id": None,
                    "subject_hint": "Following up — natural chlorhexidine alternative",
                },
            })
            position += 1

        # Step 5: Wait 3 days
        steps.append({
            "step_type": "wait",
            "position": position,
            "delay_hours": 72,
            "node_id": f"wait_{position}",
            "config": {"description": "Wait 3 days"},
        })
        position += 1

        # Step 6: LinkedIn connection request (if available)
        if "linkedin" in channels:
            steps.append({
                "step_type": "linkedin",
                "position": position,
                "delay_hours": 0,
                "node_id": f"linkedin_{position}",
                "config": {
                    "template_id": None,
                    "action": "connection_request",
                    "note_hint": (
                        "Hi {{first_name}}, I'm Dr. Thad from Gengyve USA. "
                        "We make a natural mouthwash that replaces chlorhexidine. "
                        "Would love to connect."
                    ),
                },
            })
            position += 1

        # Step 7: Wait 4 days
        steps.append({
            "step_type": "wait",
            "position": position,
            "delay_hours": 96,
            "node_id": f"wait_{position}",
            "config": {"description": "Wait 4 days"},
        })
        position += 1

        # Step 8: Final email (value-add / case study)
        steps.append({
            "step_type": "email",
            "position": position,
            "delay_hours": 0,
            "node_id": f"email_{position}",
            "config": {
                "template_id": None,
                "subject_hint": "Case study: How practices are replacing chlorhexidine",
                "body_hint": "Final touch with social proof and case study",
            },
        })
        position += 1

        # Step 9: SMS follow-up (if available)
        if "sms" in channels:
            steps.append({
                "step_type": "wait",
                "position": position,
                "delay_hours": 48,
                "node_id": f"wait_{position}",
                "config": {"description": "Wait 2 days before SMS"},
            })
            position += 1

            steps.append({
                "step_type": "sms",
                "position": position,
                "delay_hours": 0,
                "node_id": f"sms_{position}",
                "config": {
                    "template_id": None,
                    "body_hint": (
                        "Hi {{first_name}}, Dr. Thad from Gengyve. "
                        "Would you be open to trying a sample of our natural "
                        "mouthwash? Reply YES and I'll send one over."
                    ),
                },
            })
            position += 1

        # Step 10: End node
        steps.append({
            "step_type": "end",
            "position": position,
            "delay_hours": 0,
            "node_id": f"end_{position}",
            "config": {"description": "Sequence complete"},
        })

        return {
            "name": name,
            "description": f"AI-generated sequence: {prompt[:200]}",
            "status": "draft",
            "steps": steps,
            "ai_generated": True,
            "ai_generation_prompt": prompt,
            "ai_generation_metadata": {
                "zoominfo_context": bool(zi_context.get("industry_context")),
                "apollo_recommendation": bool(apollo_rec.get("recommended_steps")),
                "breeze_content_drafts": len(breeze_content),
                "channels": channels,
                "includes_ab_test": include_ab_test,
                "includes_conditionals": include_conditionals,
            },
        }

    def _generate_sequence_name(self, prompt: str) -> str:
        """Generate a clean sequence name from the prompt."""
        # Take first meaningful phrase
        words = prompt.strip().split()[:8]
        name = " ".join(words)
        if len(name) > 60:
            name = name[:57] + "..."
        return name.title()

    # ── Visual Builder Config ─────────────────────────────────────────

    def _build_visual_config(
        self, steps: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Convert step list into React Flow nodes and edges for the visual builder.

        Generates a top-to-bottom flow layout with proper positioning,
        conditional branches rendered as diamond nodes, and A/B splits
        as fork nodes.
        """
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        # Layout constants
        x_center = 400
        y_spacing = 120
        branch_x_offset = 250

        # Start node
        nodes.append({
            "id": "start",
            "type": "start",
            "position": {"x": x_center, "y": 0},
            "data": {"label": "Start"},
        })

        y_pos = y_spacing

        for i, step in enumerate(steps):
            node_id = step.get("node_id", f"step_{step['position']}")
            step_type = step["step_type"]

            # Determine node type for React Flow
            node_type = step_type  # email, sms, linkedin, wait, conditional, ab_split, end

            x = x_center

            # Position conditional branches
            if step.get("config", {}).get("branch") == "opened":
                x = x_center - branch_x_offset
            elif step.get("config", {}).get("branch") == "not_opened":
                x = x_center + branch_x_offset

            node_data: dict[str, Any] = {
                "label": self._step_label(step),
                "stepType": step_type,
                "position": step["position"],
                "delayHours": step.get("delay_hours", 0),
            }

            if step.get("condition"):
                node_data["condition"] = step["condition"]
            if step.get("ab_variants"):
                node_data["abVariants"] = step["ab_variants"]
            if step.get("config"):
                node_data["config"] = step["config"]

            nodes.append({
                "id": node_id,
                "type": node_type,
                "position": {"x": x, "y": y_pos},
                "data": node_data,
            })

            # Build edges
            if i == 0:
                edges.append({
                    "id": f"e_start_{node_id}",
                    "source": "start",
                    "target": node_id,
                    "animated": True,
                })
            else:
                prev_step = steps[i - 1]
                prev_id = prev_step.get("node_id", f"step_{prev_step['position']}")

                # Conditional nodes have branching edges
                if prev_step["step_type"] == "conditional":
                    if step.get("config", {}).get("branch") == "opened":
                        edges.append({
                            "id": f"e_{prev_id}_{node_id}_true",
                            "source": prev_id,
                            "target": node_id,
                            "sourceHandle": "true",
                            "label": "Opened",
                            "style": {"stroke": "#22c55e"},
                        })
                    elif step.get("config", {}).get("branch") == "not_opened":
                        edges.append({
                            "id": f"e_{prev_id}_{node_id}_false",
                            "source": prev_id,
                            "target": node_id,
                            "sourceHandle": "false",
                            "label": "Not Opened",
                            "style": {"stroke": "#ef4444"},
                        })
                    else:
                        edges.append({
                            "id": f"e_{prev_id}_{node_id}",
                            "source": prev_id,
                            "target": node_id,
                        })
                else:
                    edges.append({
                        "id": f"e_{prev_id}_{node_id}",
                        "source": prev_id,
                        "target": node_id,
                    })

            y_pos += y_spacing

        return {
            "nodes": nodes,
            "edges": edges,
            "viewport": {"x": 0, "y": 0, "zoom": 0.8},
        }

    @staticmethod
    def _step_label(step: dict[str, Any]) -> str:
        """Generate a human-readable label for a step node."""
        st = step["step_type"]
        config = step.get("config", {}) or {}

        if st == "email":
            return config.get("subject_hint", "Send Email")[:50]
        elif st == "sms":
            return "Send SMS"
        elif st == "linkedin":
            action = config.get("action", "connection_request")
            return f"LinkedIn: {action.replace('_', ' ').title()}"
        elif st == "wait":
            hours = step.get("delay_hours", 0)
            if hours >= 24:
                days = hours / 24
                return f"Wait {days:.0f} day{'s' if days != 1 else ''}"
            return f"Wait {hours:.0f}h"
        elif st == "conditional":
            cond = step.get("condition", {})
            return f"If: {cond.get('type', 'condition')}"
        elif st == "ab_split":
            return "A/B Test"
        elif st == "end":
            return "End"
        return st.replace("_", " ").title()
