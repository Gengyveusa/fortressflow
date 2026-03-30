"""
Business Intelligence Handler — "How are we doing?" query engine.

Aggregates real-time metrics from the database and generates
conversational summaries using the LLM.
"""

import logging
from typing import Any

from app.config import settings
from app.utils.sanitize import sanitize_error

logger = logging.getLogger(__name__)

_SUMMARY_PROMPT = """\
You are the FortressFlow assistant generating a performance summary for a dental outreach platform.

Here is the live data:

{metrics_json}

Generate a conversational, scannable summary using this format:
- Use bold for key numbers and campaign names
- Flag anything that needs attention (high bounce rates, declining engagement, unactioned replies)
- Highlight wins (high reply rates, improving trends)
- Keep it under 200 words
- End with "Want me to dig into any of these?"

Be specific — use the actual numbers, don't be vague."""


class BusinessIntelligence:
    """Handles analytics and status queries with real-time database metrics."""

    async def handle_query(
        self,
        intent: str,
        entities: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any]:
        """
        Handle a status/analytics query.

        Routes to the appropriate metrics aggregation based on intent.
        """
        if intent == "check_deliverability":
            metrics = await self._gather_deliverability_metrics()
            summary = await self._generate_summary(metrics, focus="deliverability")
            return {"type": "metrics", "content": summary, "data": metrics}

        # Default: full status overview
        campaign_name = entities.get("campaign_name")
        timeframe = entities.get("timeframe", "7d")

        if campaign_name:
            metrics = await self._gather_campaign_metrics(campaign_name)
        else:
            metrics = await self._gather_all_metrics(timeframe)

        summary = await self._generate_summary(metrics, focus="overview")
        return {"type": "metrics", "content": summary, "data": metrics}

    async def _gather_all_metrics(self, timeframe: str = "7d") -> dict[str, Any]:
        """Aggregate all key metrics across the platform."""
        from datetime import UTC, datetime, timedelta

        from sqlalchemy import case, func, select

        from app.database import AsyncSessionLocal
        from app.models.lead import Lead
        from app.models.reply_log import ReplyLog
        from app.models.sending_inbox import SendingInbox
        from app.models.sequence import (
            Sequence,
            SequenceEnrollment,
            SequenceStatus,
        )
        from app.models.touch_log import TouchAction, TouchLog

        days = _parse_timeframe(timeframe)
        since = datetime.now(UTC) - timedelta(days=days)

        metrics: dict[str, Any] = {"timeframe": f"{days}d"}

        async with AsyncSessionLocal() as db:
            # ── Pipeline ──
            try:
                lead_count = await db.execute(select(func.count(Lead.id)))
                metrics["total_leads"] = lead_count.scalar_one() or 0
            except Exception:
                metrics["total_leads"] = 0

            # ── Active campaigns ──
            try:
                result = await db.execute(
                    select(
                        Sequence.id,
                        Sequence.name,
                        Sequence.status,
                        Sequence.created_at,
                    )
                    .where(Sequence.status.in_([SequenceStatus.active, SequenceStatus.paused]))
                    .order_by(Sequence.created_at.desc())
                    .limit(20)
                )
                campaigns = []
                for row in result.all():
                    seq_id = row[0]
                    # Get enrollment counts
                    enrolled_result = await db.execute(
                        select(func.count(SequenceEnrollment.id)).where(SequenceEnrollment.sequence_id == seq_id)
                    )
                    enrolled = enrolled_result.scalar_one() or 0

                    # Get touch stats for this sequence
                    touch_result = await db.execute(
                        select(
                            func.count(case((TouchLog.action == TouchAction.sent, 1))),
                            func.count(case((TouchLog.action == TouchAction.opened, 1))),
                            func.count(case((TouchLog.action == TouchAction.replied, 1))),
                            func.count(case((TouchLog.action == TouchAction.bounced, 1))),
                        ).where(
                            TouchLog.sequence_id == seq_id,
                            TouchLog.created_at >= since,
                        )
                    )
                    stats = touch_result.one()
                    sent = int(stats[0])
                    opened = int(stats[1])
                    replied = int(stats[2])
                    bounced = int(stats[3])

                    campaigns.append(
                        {
                            "name": row[1],
                            "status": row[2].value if hasattr(row[2], "value") else str(row[2]),
                            "enrolled": enrolled,
                            "sent": sent,
                            "open_rate": f"{(opened / sent * 100):.1f}%" if sent > 0 else "N/A",
                            "reply_rate": f"{(replied / sent * 100):.1f}%" if sent > 0 else "N/A",
                            "bounce_rate": f"{(bounced / sent * 100):.1f}%" if sent > 0 else "N/A",
                        }
                    )

                metrics["campaigns"] = campaigns
                metrics["active_campaigns"] = sum(1 for c in campaigns if c["status"] == "active")
            except Exception as exc:
                logger.warning("Campaign metrics error: %s", exc)
                metrics["campaigns"] = []
                metrics["active_campaigns"] = 0

            # ── Overall engagement (period) ──
            try:
                touch_result = await db.execute(
                    select(
                        func.count(case((TouchLog.action == TouchAction.sent, 1))),
                        func.count(case((TouchLog.action == TouchAction.opened, 1))),
                        func.count(case((TouchLog.action == TouchAction.replied, 1))),
                        func.count(case((TouchLog.action == TouchAction.bounced, 1))),
                        func.count(case((TouchLog.action == TouchAction.complained, 1))),
                    ).where(TouchLog.created_at >= since)
                )
                overall = touch_result.one()
                total_sent = int(overall[0])
                total_opened = int(overall[1])
                total_replied = int(overall[2])
                total_bounced = int(overall[3])
                total_complaints = int(overall[4])

                metrics["engagement"] = {
                    "sent": total_sent,
                    "opened": total_opened,
                    "replied": total_replied,
                    "bounced": total_bounced,
                    "complaints": total_complaints,
                    "open_rate": f"{(total_opened / total_sent * 100):.1f}%" if total_sent > 0 else "N/A",
                    "reply_rate": f"{(total_replied / total_sent * 100):.1f}%" if total_sent > 0 else "N/A",
                    "bounce_rate": f"{(total_bounced / total_sent * 100):.1f}%" if total_sent > 0 else "N/A",
                }
            except Exception as exc:
                logger.warning("Engagement metrics error: %s", exc)
                metrics["engagement"] = {}

            # ── Unactioned replies ──
            try:
                unactioned_result = await db.execute(
                    select(func.count(ReplyLog.id)).where(
                        ReplyLog.ai_suggested_action.is_(None),
                        ReplyLog.created_at >= since,
                    )
                )
                metrics["unactioned_replies"] = unactioned_result.scalar_one() or 0
            except Exception:
                metrics["unactioned_replies"] = 0

            # ── Deliverability summary ──
            try:
                inbox_result = await db.execute(
                    select(
                        func.count(SendingInbox.id),
                        func.avg(SendingInbox.health_score),
                        func.avg(SendingInbox.bounce_rate_7d),
                        func.avg(SendingInbox.spam_rate_7d),
                        func.count(case((SendingInbox.status == "warming", 1))),
                    )
                )
                inbox_stats = inbox_result.one()
                metrics["deliverability"] = {
                    "inboxes": int(inbox_stats[0]),
                    "avg_health_score": f"{float(inbox_stats[1] or 0):.1f}",
                    "avg_bounce_rate": f"{float(inbox_stats[2] or 0) * 100:.2f}%",
                    "avg_spam_rate": f"{float(inbox_stats[3] or 0) * 100:.3f}%",
                    "warming_inboxes": int(inbox_stats[4]),
                }
            except Exception as exc:
                logger.warning("Deliverability metrics error: %s", exc)
                metrics["deliverability"] = {}

        return metrics

    async def _gather_campaign_metrics(self, campaign_name: str) -> dict[str, Any]:
        """Get detailed metrics for a specific campaign."""
        from datetime import UTC, datetime, timedelta

        from sqlalchemy import case, func, select

        from app.database import AsyncSessionLocal
        from app.models.sequence import (
            Sequence,
            SequenceEnrollment,
            EnrollmentStatus,
        )
        from app.models.touch_log import TouchAction, TouchLog

        datetime.now(UTC) - timedelta(days=30)

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Sequence).where(Sequence.name.ilike(f"%{campaign_name}%")).limit(1))
            seq = result.scalars().first()
            if not seq:
                return {"error": f"No campaign found matching '{campaign_name}'"}

            # Enrollment stats
            enrollment_result = await db.execute(
                select(
                    func.count(SequenceEnrollment.id),
                    func.count(case((SequenceEnrollment.status == EnrollmentStatus.active, 1))),
                    func.count(case((SequenceEnrollment.status == EnrollmentStatus.completed, 1))),
                    func.count(case((SequenceEnrollment.status == EnrollmentStatus.replied, 1))),
                    func.count(case((SequenceEnrollment.status == EnrollmentStatus.bounced, 1))),
                ).where(SequenceEnrollment.sequence_id == seq.id)
            )
            e_stats = enrollment_result.one()

            # Touch stats
            touch_result = await db.execute(
                select(
                    func.count(case((TouchLog.action == TouchAction.sent, 1))),
                    func.count(case((TouchLog.action == TouchAction.opened, 1))),
                    func.count(case((TouchLog.action == TouchAction.replied, 1))),
                    func.count(case((TouchLog.action == TouchAction.bounced, 1))),
                ).where(TouchLog.sequence_id == seq.id)
            )
            t_stats = touch_result.one()
            sent = int(t_stats[0])
            opened = int(t_stats[1])
            replied = int(t_stats[2])
            bounced = int(t_stats[3])

            return {
                "campaign_name": seq.name,
                "status": seq.status.value if hasattr(seq.status, "value") else str(seq.status),
                "created_at": seq.created_at.isoformat() if seq.created_at else None,
                "enrollments": {
                    "total": int(e_stats[0]),
                    "active": int(e_stats[1]),
                    "completed": int(e_stats[2]),
                    "replied": int(e_stats[3]),
                    "bounced": int(e_stats[4]),
                },
                "performance": {
                    "sent": sent,
                    "opened": opened,
                    "replied": replied,
                    "bounced": bounced,
                    "open_rate": f"{(opened / sent * 100):.1f}%" if sent > 0 else "N/A",
                    "reply_rate": f"{(replied / sent * 100):.1f}%" if sent > 0 else "N/A",
                    "bounce_rate": f"{(bounced / sent * 100):.1f}%" if sent > 0 else "N/A",
                },
            }

    async def _gather_deliverability_metrics(self) -> dict[str, Any]:
        """Get detailed deliverability health metrics."""
        from sqlalchemy import select

        from app.database import AsyncSessionLocal
        from app.models.sending_inbox import SendingInbox
        from app.models.domain import SendingDomain

        metrics: dict[str, Any] = {"focus": "deliverability"}

        async with AsyncSessionLocal() as db:
            # Inbox metrics
            try:
                result = await db.execute(
                    select(
                        SendingInbox.email_address,
                        SendingInbox.status,
                        SendingInbox.health_score,
                        SendingInbox.bounce_rate_7d,
                        SendingInbox.spam_rate_7d,
                        SendingInbox.open_rate_7d,
                        SendingInbox.reply_rate_7d,
                        SendingInbox.warmup_day,
                        SendingInbox.daily_sent,
                        SendingInbox.daily_limit,
                    )
                    .order_by(SendingInbox.health_score.asc())
                    .limit(20)
                )
                inboxes = []
                for row in result.all():
                    inboxes.append(
                        {
                            "email": row[0],
                            "status": row[1],
                            "health_score": f"{row[2]:.1f}",
                            "bounce_rate": f"{row[3] * 100:.2f}%",
                            "spam_rate": f"{row[4] * 100:.3f}%",
                            "open_rate": f"{row[5] * 100:.1f}%",
                            "reply_rate": f"{row[6] * 100:.1f}%",
                            "warmup_day": row[7],
                            "daily_usage": f"{row[8]}/{row[9]}",
                        }
                    )
                metrics["inboxes"] = inboxes
            except Exception as exc:
                logger.warning("Inbox metrics error: %s", exc)
                metrics["inboxes"] = []

            # Domain metrics
            try:
                domain_result = await db.execute(
                    select(
                        SendingDomain.domain,
                        SendingDomain.spf_verified,
                        SendingDomain.dkim_verified,
                        SendingDomain.dmarc_verified,
                        SendingDomain.health_score,
                    ).limit(10)
                )
                domains = []
                for row in domain_result.all():
                    domains.append(
                        {
                            "domain": row[0],
                            "spf": row[1],
                            "dkim": row[2],
                            "dmarc": row[3],
                            "health_score": f"{row[4]:.1f}" if row[4] else "N/A",
                        }
                    )
                metrics["domains"] = domains
            except Exception as exc:
                logger.warning("Domain metrics error: %s", exc)
                metrics["domains"] = []

        return metrics

    async def _generate_summary(self, metrics: dict[str, Any], focus: str = "overview") -> str:
        """Generate a conversational summary from metrics using LLM."""
        import json

        prompt = _SUMMARY_PROMPT.format(metrics_json=json.dumps(metrics, indent=2, default=str))

        raw = await self._call_llm(prompt)
        if raw:
            return raw

        # Fallback: build a static summary
        return self._build_static_summary(metrics, focus)

    def _build_static_summary(self, metrics: dict[str, Any], focus: str) -> str:
        """Build a summary without LLM."""
        lines = []

        if focus == "deliverability":
            lines.append("**Deliverability Health Report**\n")
            for inbox in metrics.get("inboxes", [])[:5]:
                lines.append(
                    f"- **{inbox['email']}**: {inbox['status']} | "
                    f"Health: {inbox['health_score']} | "
                    f"Bounce: {inbox['bounce_rate']} | Spam: {inbox['spam_rate']}"
                )
            if not metrics.get("inboxes"):
                lines.append("No sending inboxes configured yet.")
        else:
            lines.append(f"**Performance Overview** (last {metrics.get('timeframe', '7d')})\n")
            lines.append(f"**Pipeline:** {metrics.get('total_leads', 0)} total leads")
            lines.append(f"**Active Campaigns:** {metrics.get('active_campaigns', 0)}")

            eng = metrics.get("engagement", {})
            if eng:
                lines.append(
                    f"**Engagement:** {eng.get('sent', 0)} sent, "
                    f"{eng.get('open_rate', 'N/A')} open rate, "
                    f"{eng.get('reply_rate', 'N/A')} reply rate"
                )

            if metrics.get("unactioned_replies", 0) > 0:
                lines.append(f"\n**Action needed:** {metrics['unactioned_replies']} replies waiting")

            for campaign in metrics.get("campaigns", [])[:3]:
                lines.append(
                    f"\n- **{campaign['name']}** ({campaign['status']}): "
                    f"{campaign.get('enrolled', 0)} enrolled, "
                    f"{campaign.get('reply_rate', 'N/A')} reply rate"
                )

            deliv = metrics.get("deliverability", {})
            if deliv:
                lines.append(
                    f"\n**Deliverability:** {deliv.get('inboxes', 0)} inboxes, "
                    f"avg health {deliv.get('avg_health_score', 'N/A')}, "
                    f"bounce {deliv.get('avg_bounce_rate', 'N/A')}"
                )

        lines.append("\nWant me to dig into any of these?")
        return "\n".join(lines)

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM for summary generation."""
        groq_key = getattr(settings, "GROQ_API_KEY", "")
        if groq_key:
            try:
                from groq import AsyncGroq

                client = AsyncGroq(api_key=groq_key)
                resp = await client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a data analyst for FortressFlow, a dental outreach platform. Generate clear, actionable summaries.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.5,
                    max_tokens=400,
                )
                return resp.choices[0].message.content or ""
            except Exception as exc:
                logger.warning("BI Groq call failed: %s", sanitize_error(exc))

        openai_key = getattr(settings, "OPENAI_API_KEY", "")
        if openai_key:
            try:
                from openai import AsyncOpenAI

                client = AsyncOpenAI(api_key=openai_key)
                resp = await client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a data analyst for FortressFlow, a dental outreach platform.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.5,
                    max_tokens=400,
                )
                return resp.choices[0].message.content or ""
            except Exception as exc:
                logger.warning("BI OpenAI call failed: %s", sanitize_error(exc))

        return ""


def _parse_timeframe(timeframe: str) -> int:
    """Parse a timeframe string like '7d', '30d', 'this week' into days."""
    if not timeframe:
        return 7

    tf = timeframe.lower().strip()
    if tf in ("this week", "1w", "7d"):
        return 7
    if tf in ("this month", "30d", "1m"):
        return 30
    if tf in ("today", "1d"):
        return 1
    if tf in ("yesterday", "2d"):
        return 2
    if tf in ("this quarter", "90d", "3m"):
        return 90

    # Try to parse "Nd" format
    import re

    match = re.match(r"(\d+)d", tf)
    if match:
        return int(match.group(1))

    return 7
