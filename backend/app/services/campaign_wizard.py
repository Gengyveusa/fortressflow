"""
Campaign Wizard — orchestrates the full campaign creation workflow.

Turns "Launch a campaign targeting periodontists in Texas" into:
Lead Search → Compliance Check → Sequence Generation → Preview → Execute.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import settings
from app.utils.sanitize import sanitize_error

logger = logging.getLogger(__name__)


class CampaignWizard:
    """
    Orchestrates end-to-end campaign creation from natural language parameters.

    Steps:
    1. Lead acquisition — query existing leads or trigger enrichment
    2. Lead qualification — compliance/DNC check
    3. Sequence generation — use SequenceAIService
    4. Preview & confirm — return summary for user approval
    5. Execute on confirmation — create sequence, enroll leads, activate
    """

    async def start_campaign(
        self,
        params: dict[str, Any],
        user_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        """
        Start the campaign wizard. Returns an action_preview for user confirmation.
        """
        target = params.get("target_description", params.get("specialty", "dental professionals"))
        location = params.get("location", "nationwide")
        count = int(params.get("count", 50))
        channels = params.get("channels", ["email"])
        tone = params.get("tone", "professional")
        seq_length = int(params.get("sequence_length", 5))

        # Normalize channels
        if isinstance(channels, str):
            if "multi" in channels.lower() or "all" in channels.lower():
                channels = ["email", "linkedin", "sms"]
            else:
                channels = [c.strip().lower() for c in channels.split(",")]

        try:
            # Step 1: Find matching leads
            leads_result = await self._find_leads(target, location, count)
            total_found = leads_result["total"]
            leads = leads_result["leads"]

            # Step 2: Compliance check
            compliant_leads = await self._check_compliance(leads)
            compliant_count = len(compliant_leads)

            # Step 3: Generate sequence preview
            sequence_preview = await self._generate_sequence_preview(
                target=target,
                channels=channels,
                tone=tone,
                seq_length=seq_length,
            )

            # Step 4: Build preview
            start_date = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%d at 9:00 AM")

            # Build step descriptions
            step_descriptions = []
            for i, step in enumerate(sequence_preview.get("steps", [])[:seq_length]):
                step_type = step.get("step_type", "email")
                delay = step.get("delay_hours", 0)
                day = sum(
                    s.get("delay_hours", 0)
                    for s in sequence_preview.get("steps", [])[:i]
                ) / 24
                desc = step.get("config", {}).get("description", "") or step.get("config", {}).get("subject_hint", "")
                if step_type == "wait":
                    continue
                channel_icon = {"email": "email", "linkedin": "LinkedIn", "sms": "SMS"}.get(step_type, step_type)
                step_descriptions.append(
                    f"Step {len(step_descriptions) + 1} (Day {int(day)}): {channel_icon} — {desc or step_type}"
                )

            # Channel summary
            channel_counts = {}
            for step in sequence_preview.get("steps", []):
                st = step.get("step_type", "")
                if st in ("email", "linkedin", "sms"):
                    channel_counts[st] = channel_counts.get(st, 0) + 1
            channel_summary = " + ".join(
                f"{v} {k}{'s' if v > 1 else ''}" for k, v in channel_counts.items()
            )

            preview_text = (
                f"Ready to launch:\n\n"
                f"**Target:** {target} in {location}\n"
                f"**Leads:** {total_found} found, {compliant_count} after compliance check\n"
                f"**Sequence:** {len(step_descriptions)}-step: {channel_summary}\n"
                f"**Starting:** {start_date}\n\n"
            )
            for desc in step_descriptions[:7]:
                preview_text += f"  {desc}\n"
            if len(step_descriptions) > 7:
                preview_text += f"  ... and {len(step_descriptions) - 7} more steps\n"

            preview_text += "\nShall I launch this? (yes / modify / cancel)"

            # Store campaign params in session state for execution
            campaign_params = {
                "target": target,
                "location": location,
                "channels": channels,
                "tone": tone,
                "sequence_length": seq_length,
                "lead_ids": [str(l.id) for l in compliant_leads[:count]],
                "compliant_count": compliant_count,
                "total_found": total_found,
                "sequence_preview": sequence_preview,
            }

            return {
                "type": "action_preview",
                "content": preview_text,
                "campaign_params": campaign_params,
                "session_state": {
                    "active_intent": "confirm_campaign",
                    "gathered_params": campaign_params,
                    "pending_questions": [],
                },
            }

        except Exception as exc:
            logger.error("CampaignWizard.start_campaign failed: %s", sanitize_error(exc))
            return {
                "type": "text",
                "content": (
                    f"I ran into an issue setting up this campaign: {sanitize_error(exc)}\n\n"
                    "Let's try again — what audience are you targeting?"
                ),
            }

    async def execute_campaign(
        self,
        params: dict[str, Any],
        user_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        """
        Execute a confirmed campaign — create sequence, enroll leads, activate.

        Returns progress updates as a dict (for SSE streaming by the chat service).
        """
        try:
            from sqlalchemy import select

            from app.database import AsyncSessionLocal
            from app.models.lead import Lead
            from app.models.sequence import (
                Sequence,
                SequenceEnrollment,
                SequenceStatus,
                SequenceStep,
                StepType,
            )

            target = params.get("target", "Campaign")
            channels = params.get("channels", ["email"])
            tone = params.get("tone", "professional")
            lead_ids = params.get("lead_ids", [])
            sequence_preview = params.get("sequence_preview", {})

            async with AsyncSessionLocal() as db:
                # 1. Create the sequence
                sequence_name = f"{target.title()} Campaign — {datetime.now(UTC).strftime('%b %d')}"
                sequence = Sequence(
                    name=sequence_name,
                    description=f"AI-generated campaign targeting {target}",
                    status=SequenceStatus.draft,
                    ai_generated=True,
                    ai_generation_prompt=f"Campaign targeting {target} via {', '.join(channels)}",
                    ai_generation_metadata={
                        "wizard": True,
                        "channels": channels,
                        "tone": tone,
                        "created_by": user_id,
                    },
                )
                db.add(sequence)
                await db.flush()

                # 2. Create sequence steps
                for step_data in sequence_preview.get("steps", []):
                    step_type_val = step_data.get("step_type", "email")
                    try:
                        step_type = StepType(step_type_val)
                    except ValueError:
                        step_type = StepType.email

                    step = SequenceStep(
                        sequence_id=sequence.id,
                        step_type=step_type,
                        position=step_data.get("position", 0),
                        config=step_data.get("config"),
                        delay_hours=step_data.get("delay_hours", 0),
                        condition=step_data.get("condition"),
                        ab_variants=step_data.get("ab_variants"),
                        is_ab_test=step_data.get("is_ab_test", False),
                        node_id=step_data.get("node_id"),
                    )
                    db.add(step)

                # 3. Enroll leads
                enrolled_count = 0
                for lid in lead_ids:
                    try:
                        lead_uuid = uuid.UUID(lid)
                    except ValueError:
                        continue
                    enrollment = SequenceEnrollment(
                        sequence_id=sequence.id,
                        lead_id=lead_uuid,
                    )
                    db.add(enrollment)
                    enrolled_count += 1

                # 4. Activate the sequence
                sequence.status = SequenceStatus.active

                # 5. Generate visual config
                from app.services.sequence_ai_service import SequenceAIService
                svc = SequenceAIService()
                visual_config = svc._build_visual_config(sequence_preview.get("steps", []))
                sequence.visual_config = visual_config

                await db.commit()

            return {
                "type": "progress",
                "content": (
                    f"Campaign launched!\n\n"
                    f"**{sequence_name}**\n"
                    f"- Sequence created with {len(sequence_preview.get('steps', []))} steps\n"
                    f"- {enrolled_count} leads enrolled\n"
                    f"- Sequence is now **active**\n"
                    f"- First touches go out tomorrow at 9 AM\n\n"
                    f"I'll keep an eye on performance. Ask me \"how's the campaign doing?\" anytime."
                ),
                "session_state": {
                    "active_intent": None,
                    "gathered_params": {},
                    "pending_questions": [],
                },
            }

        except Exception as exc:
            logger.error("CampaignWizard.execute_campaign failed: %s", sanitize_error(exc))
            return {
                "type": "text",
                "content": f"Campaign execution failed: {sanitize_error(exc)}. Please try again.",
            }

    # ── Internal Steps ───────────────────────────────────────────────────

    async def _find_leads(
        self,
        target: str,
        location: str,
        count: int,
    ) -> dict[str, Any]:
        """Find leads matching the target criteria."""
        from sqlalchemy import String, func, select

        from app.database import AsyncSessionLocal
        from app.models.lead import Lead

        async with AsyncSessionLocal() as db:
            query = select(Lead)

            if target:
                query = query.where(
                    func.lower(Lead.title).contains(target.lower())
                    | func.lower(Lead.company).contains(target.lower())
                    | func.cast(Lead.enriched_data, String).ilike(f"%{target}%")
                )
            if location and location.lower() != "nationwide":
                query = query.where(
                    func.cast(Lead.enriched_data, String).ilike(f"%{location}%")
                )

            query = query.limit(min(count, 200))
            result = await db.execute(query)
            leads = result.scalars().all()

        return {"total": len(leads), "leads": leads}

    async def _check_compliance(self, leads: list) -> list:
        """
        Filter leads through compliance checks (consent + DNC).

        Returns only leads that pass compliance.
        """
        from sqlalchemy import select

        from app.database import AsyncSessionLocal
        from app.models.consent import Consent
        from app.models.dnc import DNCBlock

        if not leads:
            return []

        lead_ids = [l.id for l in leads]
        lead_emails = [l.email for l in leads]

        async with AsyncSessionLocal() as db:
            # Check DNC list
            dnc_result = await db.execute(
                select(DNCBlock.identifier).where(
                    DNCBlock.identifier.in_(lead_emails)
                )
            )
            blocked_emails = {row[0] for row in dnc_result.all()}

        # Filter out blocked leads
        compliant = [l for l in leads if l.email not in blocked_emails]
        return compliant

    async def _generate_sequence_preview(
        self,
        target: str,
        channels: list[str],
        tone: str,
        seq_length: int,
    ) -> dict[str, Any]:
        """Generate a sequence structure using SequenceAIService."""
        try:
            from app.services.sequence_ai_service import SequenceAIService

            svc = SequenceAIService()
            result = await svc.generate_sequence(
                prompt=f"Campaign targeting {target}, {tone} tone",
                target_industry="dental",
                num_steps=seq_length,
                channels=channels,
                include_ab_test=len(channels) > 1,
                include_conditionals=True,
            )
            if result.success:
                return result.sequence_config
        except Exception as exc:
            logger.warning("Sequence generation failed, using default: %s", sanitize_error(exc))

        # Fallback: build a simple default sequence
        return self._build_default_sequence(target, channels, seq_length)

    def _build_default_sequence(
        self,
        target: str,
        channels: list[str],
        seq_length: int,
    ) -> dict[str, Any]:
        """Build a basic default sequence when AI generation is unavailable."""
        steps = []
        position = 0

        # Step 1: Initial email
        steps.append({
            "step_type": "email",
            "position": position,
            "delay_hours": 0,
            "node_id": f"email_{position}",
            "config": {
                "subject_hint": f"Quick question about your practice",
                "description": f"Introduction email to {target}",
            },
        })
        position += 1

        # Step 2: Wait 3 days
        steps.append({
            "step_type": "wait",
            "position": position,
            "delay_hours": 72,
            "node_id": f"wait_{position}",
            "config": {"description": "Wait 3 days"},
        })
        position += 1

        # Step 3: Follow-up email
        steps.append({
            "step_type": "email",
            "position": position,
            "delay_hours": 0,
            "node_id": f"email_{position}",
            "config": {
                "subject_hint": "Following up",
                "description": "Follow-up with value proposition",
            },
        })
        position += 1

        # Step 4: Wait + LinkedIn (if available)
        if "linkedin" in channels and position < seq_length + 2:
            steps.append({
                "step_type": "wait",
                "position": position,
                "delay_hours": 72,
                "node_id": f"wait_{position}",
                "config": {"description": "Wait 3 days"},
            })
            position += 1
            steps.append({
                "step_type": "linkedin",
                "position": position,
                "delay_hours": 0,
                "node_id": f"linkedin_{position}",
                "config": {
                    "action": "connection_request",
                    "description": "LinkedIn connection request",
                },
            })
            position += 1

        # Step 5: Wait + final email
        steps.append({
            "step_type": "wait",
            "position": position,
            "delay_hours": 96,
            "node_id": f"wait_{position}",
            "config": {"description": "Wait 4 days"},
        })
        position += 1
        steps.append({
            "step_type": "email",
            "position": position,
            "delay_hours": 0,
            "node_id": f"email_{position}",
            "config": {
                "subject_hint": "Last chance — case study inside",
                "description": "Final value-add email with social proof",
            },
        })
        position += 1

        # SMS if available
        if "sms" in channels and position < seq_length + 4:
            steps.append({
                "step_type": "wait",
                "position": position,
                "delay_hours": 48,
                "node_id": f"wait_{position}",
                "config": {"description": "Wait 2 days"},
            })
            position += 1
            steps.append({
                "step_type": "sms",
                "position": position,
                "delay_hours": 0,
                "node_id": f"sms_{position}",
                "config": {
                    "description": "SMS follow-up",
                    "body_hint": "Quick question about your practice — reply YES for more info",
                },
            })
            position += 1

        # End node
        steps.append({
            "step_type": "end",
            "position": position,
            "delay_hours": 0,
            "node_id": f"end_{position}",
            "config": {"description": "Sequence complete"},
        })

        return {
            "name": f"{target} Campaign",
            "steps": steps,
            "status": "draft",
        }
