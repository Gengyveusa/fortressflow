"""
AI Feedback Loop Service — Phase 5.

Closes the learning loop: after sequence completion or reply,
aggregate metrics and push back to all AI platforms.

Feeds performance data (reply rates, meeting booked, unsubscribes)
back to HubSpot Breeze, ZoomInfo Copilot, and Apollo AI for
future sequence generation refinement.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.lead import Lead
from app.models.sequence import EnrollmentStatus, SequenceEnrollment
from app.models.touch_log import TouchAction, TouchLog
from app.services.platform_ai_service import PlatformAIService

logger = logging.getLogger(__name__)


class AIFeedbackService:
    """
    Closes the AI learning loop by aggregating sequence performance metrics
    and pushing them back to HubSpot Breeze, ZoomInfo Copilot, and Apollo AI.

    Designed to be called:
    - After sequence completion (push_completion_feedback)
    - After reply detection (push_reply_feedback)
    - On a scheduled basis for sequence reporting (generate_learning_report)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._ai = PlatformAIService()

    # ── Sequence Metrics Aggregation ───────────────────────────────────────

    async def aggregate_sequence_metrics(self, sequence_id: UUID) -> dict[str, Any]:
        """
        Compute comprehensive performance metrics for a sequence.

        Metrics:
        - reply_rate: fraction of enrolled leads who replied
        - open_rate: fraction of enrolled leads who opened at least one email
        - bounce_rate: fraction of enrolled leads that bounced
        - meeting_booked_rate: fraction where sentiment was positive + reply
        - unsubscribe_rate: fraction who unsubscribed
        - avg_steps_before_reply: average step number at first reply
        - best_performing_channel: channel with highest reply rate
        - best_performing_template: template_id with highest reply correlation

        Returns a metrics dict.
        """
        try:
            # Total enrollments for this sequence
            total_result = await self.db.execute(
                select(func.count(SequenceEnrollment.id)).where(
                    SequenceEnrollment.sequence_id == sequence_id
                )
            )
            total_enrolled = total_result.scalar() or 0

            if total_enrolled == 0:
                return {"error": "no_enrollments", "sequence_id": str(sequence_id)}

            # Completed enrollments
            completed_result = await self.db.execute(
                select(func.count(SequenceEnrollment.id)).where(
                    and_(
                        SequenceEnrollment.sequence_id == sequence_id,
                        SequenceEnrollment.status == EnrollmentStatus.completed,
                    )
                )
            )
            total_completed = completed_result.scalar() or 0

            # Count unique leads with replies
            replied_result = await self.db.execute(
                select(func.count(func.distinct(TouchLog.lead_id))).where(
                    and_(
                        TouchLog.sequence_id == sequence_id,
                        TouchLog.action == TouchAction.replied,
                    )
                )
            )
            total_replied = replied_result.scalar() or 0

            # Count unique leads with opens
            opened_result = await self.db.execute(
                select(func.count(func.distinct(TouchLog.lead_id))).where(
                    and_(
                        TouchLog.sequence_id == sequence_id,
                        TouchLog.action == TouchAction.opened,
                    )
                )
            )
            total_opened = opened_result.scalar() or 0

            # Count bounces
            bounced_result = await self.db.execute(
                select(func.count(func.distinct(TouchLog.lead_id))).where(
                    and_(
                        TouchLog.sequence_id == sequence_id,
                        TouchLog.action == TouchAction.bounced,
                    )
                )
            )
            total_bounced = bounced_result.scalar() or 0

            # Count unsubscribes
            unsub_result = await self.db.execute(
                select(func.count(func.distinct(TouchLog.lead_id))).where(
                    and_(
                        TouchLog.sequence_id == sequence_id,
                        TouchLog.action == TouchAction.unsubscribed,
                    )
                )
            )
            total_unsubscribed = unsub_result.scalar() or 0

            # Avg steps before reply (step_number of first reply touch)
            avg_steps = await self._avg_steps_before_reply(sequence_id)

            # Best performing channel
            best_channel = await self._best_performing_channel(sequence_id)

            # Best performing template
            best_template = await self._best_performing_template(sequence_id)

            # Meeting booked approximation: positive sentiment replies
            meeting_rate = await self._meeting_booked_rate(sequence_id, total_replied)

            metrics = {
                "sequence_id": str(sequence_id),
                "computed_at": datetime.now(UTC).isoformat(),
                "total_enrolled": total_enrolled,
                "total_completed": total_completed,
                "total_replied": total_replied,
                "total_opened": total_opened,
                "total_bounced": total_bounced,
                "total_unsubscribed": total_unsubscribed,
                "reply_rate": round(total_replied / total_enrolled, 4),
                "open_rate": round(total_opened / total_enrolled, 4),
                "bounce_rate": round(total_bounced / total_enrolled, 4),
                "unsubscribe_rate": round(total_unsubscribed / total_enrolled, 4),
                "meeting_booked_rate": round(meeting_rate, 4),
                "completion_rate": round(total_completed / total_enrolled, 4),
                "avg_steps_before_reply": avg_steps,
                "best_performing_channel": best_channel,
                "best_performing_template": best_template,
            }

            logger.info(
                "Aggregated metrics for sequence %s: reply_rate=%.2f%% open_rate=%.2f%%",
                sequence_id,
                metrics["reply_rate"] * 100,
                metrics["open_rate"] * 100,
            )

            return metrics

        except Exception as exc:
            logger.error(
                "Failed to aggregate metrics for sequence %s: %s", sequence_id, exc
            )
            return {"error": str(exc), "sequence_id": str(sequence_id)}

    async def _avg_steps_before_reply(self, sequence_id: UUID) -> float:
        """Compute average step number at which the first reply occurred."""
        try:
            result = await self.db.execute(
                select(func.avg(TouchLog.step_number)).where(
                    and_(
                        TouchLog.sequence_id == sequence_id,
                        TouchLog.action == TouchAction.replied,
                        TouchLog.step_number.is_not(None),
                    )
                )
            )
            avg = result.scalar()
            return round(float(avg), 2) if avg is not None else 0.0
        except Exception:
            return 0.0

    async def _best_performing_channel(self, sequence_id: UUID) -> str | None:
        """Identify the channel with the highest reply rate for this sequence."""
        try:
            # Count replies per channel
            result = await self.db.execute(
                select(TouchLog.channel, func.count(TouchLog.id).label("reply_count"))
                .where(
                    and_(
                        TouchLog.sequence_id == sequence_id,
                        TouchLog.action == TouchAction.replied,
                    )
                )
                .group_by(TouchLog.channel)
                .order_by(func.count(TouchLog.id).desc())
                .limit(1)
            )
            row = result.first()
            return row[0] if row else None
        except Exception:
            return None

    async def _best_performing_template(self, sequence_id: UUID) -> str | None:
        """
        Find the template_id most correlated with replies.

        Looks at touch_log metadata for template_id, correlates with replies.
        """
        try:
            # Get sent touches with template_id in metadata
            result = await self.db.execute(
                select(
                    TouchLog.extra_metadata["template_id"].astext.label("template_id"),
                    func.count(TouchLog.id).label("sent_count"),
                )
                .where(
                    and_(
                        TouchLog.sequence_id == sequence_id,
                        TouchLog.action == TouchAction.sent,
                        TouchLog.extra_metadata["template_id"].astext.is_not(None),
                    )
                )
                .group_by(TouchLog.extra_metadata["template_id"].astext)
                .order_by(func.count(TouchLog.id).desc())
                .limit(5)
            )
            templates = result.all()

            if not templates:
                return None

            best_template_id = None
            best_ratio = 0.0

            for template_id, sent_count in templates:
                if not template_id or sent_count == 0:
                    continue

                # Count replies where this template was used
                reply_result = await self.db.execute(
                    select(func.count(TouchLog.id)).where(
                        and_(
                            TouchLog.sequence_id == sequence_id,
                            TouchLog.action == TouchAction.replied,
                            TouchLog.lead_id.in_(
                                select(TouchLog.lead_id).where(
                                    and_(
                                        TouchLog.sequence_id == sequence_id,
                                        TouchLog.extra_metadata["template_id"].astext == template_id,
                                    )
                                )
                            ),
                        )
                    )
                )
                reply_count = reply_result.scalar() or 0
                ratio = reply_count / sent_count

                if ratio > best_ratio:
                    best_ratio = ratio
                    best_template_id = template_id

            return best_template_id

        except Exception as exc:
            logger.debug("Best template lookup error: %s", exc)
            return None

    async def _meeting_booked_rate(
        self, sequence_id: UUID, total_replied: int
    ) -> float:
        """
        Approximate meeting booked rate from reply_logs sentiment.

        Counts positive sentiment replies as potential meeting bookings.
        """
        if total_replied == 0:
            return 0.0

        try:
            total_enrolled_result = await self.db.execute(
                select(func.count(SequenceEnrollment.id)).where(
                    SequenceEnrollment.sequence_id == sequence_id
                )
            )
            total_enrolled = total_enrolled_result.scalar() or 1

            # Count positive sentiment replies from reply_logs
            from sqlalchemy import text

            result = await self.db.execute(
                text(
                    """
                    SELECT COUNT(*) FROM reply_logs
                    WHERE matched_sequence_id = :seq_id
                    AND sentiment = 'positive'
                    """
                ),
                {"seq_id": str(sequence_id)},
            )
            positive_replies = result.scalar() or 0
            return positive_replies / total_enrolled

        except Exception:
            # Fallback: assume 30% of replies are positive
            total_enrolled = 1
            try:
                r = await self.db.execute(
                    select(func.count(SequenceEnrollment.id)).where(
                        SequenceEnrollment.sequence_id == sequence_id
                    )
                )
                total_enrolled = r.scalar() or 1
            except Exception:
                pass
            return total_replied * 0.3 / total_enrolled

    # ── Platform Feedback Push ─────────────────────────────────────────────

    async def push_metrics_to_platforms(
        self, sequence_id: UUID, metrics: dict[str, Any]
    ) -> dict[str, int]:
        """
        Push aggregated sequence metrics to all 3 AI platforms in parallel.

        For each enrolled lead, calls PlatformAIService.send_outcome_feedback.
        This allows each platform's AI to learn from the sequence performance.

        Returns {platform: success_count} dict.
        """
        # Fetch all enrolled lead emails for this sequence
        result = await self.db.execute(
            select(Lead.email)
            .join(SequenceEnrollment, SequenceEnrollment.lead_id == Lead.id)
            .where(SequenceEnrollment.sequence_id == sequence_id)
        )
        lead_emails = [row[0] for row in result.all()]

        if not lead_emails:
            logger.info("No leads found for sequence %s — skipping metrics push", sequence_id)
            return {"hubspot": 0, "zoominfo": 0, "apollo": 0}

        outcomes = {
            "sequence_id": str(sequence_id),
            "reply_rate": metrics.get("reply_rate", 0),
            "open_rate": metrics.get("open_rate", 0),
            "bounce_rate": metrics.get("bounce_rate", 0),
            "meeting_booked_rate": metrics.get("meeting_booked_rate", 0),
            "unsubscribe_rate": metrics.get("unsubscribe_rate", 0),
            "best_channel": metrics.get("best_performing_channel"),
        }

        success_counts: dict[str, int] = {"hubspot": 0, "zoominfo": 0, "apollo": 0}

        # Process in batches of 50 to avoid overwhelming APIs
        batch_size = 50
        for i in range(0, len(lead_emails), batch_size):
            batch = lead_emails[i : i + batch_size]

            tasks = []
            for email in batch:
                for platform in ("hubspot", "zoominfo", "apollo"):
                    tasks.append(
                        self._push_to_platform(platform, email, outcomes)
                    )

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Tally results
            task_idx = 0
            for email in batch:
                for platform in ("hubspot", "zoominfo", "apollo"):
                    r = results[task_idx]
                    if isinstance(r, bool) and r:
                        success_counts[platform] += 1
                    elif isinstance(r, Exception):
                        logger.debug(
                            "Platform push error (%s, %s): %s", platform, email, r
                        )
                    task_idx += 1

        logger.info(
            "Metrics push complete for sequence %s: %s",
            sequence_id, success_counts,
        )

        return success_counts

    async def _push_to_platform(
        self, platform: str, email: str, outcomes: dict[str, Any]
    ) -> bool:
        """Push outcome data for a single contact to a single platform."""
        return await self._ai.send_outcome_feedback(
            platform=f"{platform}_sequence_feedback",
            contact_email=email,
            outcomes=outcomes,
        )

    # ── Reply Feedback ─────────────────────────────────────────────────────

    async def push_reply_feedback(
        self,
        lead_email: str,
        reply_sentiment: str,
        sequence_id: UUID,
    ) -> dict[str, Any]:
        """
        Immediate feedback push on reply detection.

        Called by ReplyService after processing a reply. Sends reply signal
        to all 3 platforms immediately (not batched).

        Returns {platform: bool} success map.
        """
        outcomes = {
            "replied": True,
            "sentiment": reply_sentiment,
            "sequence_id": str(sequence_id),
            "source": "fortressflow_reply_detection",
            "timestamp": datetime.now(UTC).isoformat(),
        }

        tasks = {
            "hubspot": self._ai.send_outcome_feedback(
                "hubspot_breeze_data_agent", lead_email, outcomes
            ),
            "zoominfo": self._ai.send_outcome_feedback(
                "zoominfo_copilot", lead_email, outcomes
            ),
            "apollo": self._ai.send_outcome_feedback(
                "apollo_ai", lead_email, outcomes
            ),
        }

        platform_results = await asyncio.gather(
            *tasks.values(), return_exceptions=True
        )

        result: dict[str, Any] = {}
        for platform, outcome in zip(tasks.keys(), platform_results):
            if isinstance(outcome, Exception):
                result[platform] = False
                logger.warning(
                    "Reply feedback push failed (%s, %s): %s",
                    platform, lead_email, outcome,
                )
            else:
                result[platform] = bool(outcome)

        logger.info(
            "Reply feedback pushed for %s (sentiment=%s): %s",
            lead_email, reply_sentiment, result,
        )

        return result

    # ── Completion Feedback ────────────────────────────────────────────────

    async def push_completion_feedback(self, sequence_id: UUID) -> dict[str, Any]:
        """
        Full metrics push when a sequence completes.

        1. Aggregates sequence metrics
        2. Pushes to all 3 platforms
        3. Returns combined report

        Designed to be called by the sequence executor when all enrollments complete.
        """
        logger.info("Pushing completion feedback for sequence %s", sequence_id)

        # Aggregate metrics
        metrics = await self.aggregate_sequence_metrics(sequence_id)

        if "error" in metrics:
            logger.warning(
                "Cannot push completion feedback for sequence %s: %s",
                sequence_id, metrics["error"],
            )
            return metrics

        # Push to platforms
        platform_success = await self.push_metrics_to_platforms(sequence_id, metrics)

        return {
            **metrics,
            "platform_push": platform_success,
            "pushed_at": datetime.now(UTC).isoformat(),
        }

    # ── Template Performance ───────────────────────────────────────────────

    async def get_template_performance(self, template_id: UUID) -> dict[str, Any]:
        """
        Get performance metrics for a specific template.

        Used by AI sequence generation to learn which templates perform best.
        Queries touch_logs where template_id appears in metadata.

        Returns metrics dict with reply_rate, open_rate, bounce_rate, etc.
        """
        try:
            template_id_str = str(template_id)

            # Total sends with this template
            sent_result = await self.db.execute(
                select(func.count(TouchLog.id)).where(
                    and_(
                        TouchLog.action == TouchAction.sent,
                        TouchLog.extra_metadata["template_id"].astext == template_id_str,
                    )
                )
            )
            total_sent = sent_result.scalar() or 0

            if total_sent == 0:
                return {
                    "template_id": template_id_str,
                    "total_sent": 0,
                    "message": "no_data",
                }

            # Gets all leads who received this template
            leads_result = await self.db.execute(
                select(func.distinct(TouchLog.lead_id)).where(
                    and_(
                        TouchLog.extra_metadata["template_id"].astext == template_id_str,
                        TouchLog.action == TouchAction.sent,
                    )
                )
            )
            lead_ids = [row[0] for row in leads_result.all()]
            unique_recipients = len(lead_ids)

            # Opens for these leads
            opened_result = await self.db.execute(
                select(func.count(func.distinct(TouchLog.lead_id))).where(
                    and_(
                        TouchLog.lead_id.in_(lead_ids),
                        TouchLog.action == TouchAction.opened,
                    )
                )
            )
            total_opened = opened_result.scalar() or 0

            # Replies for these leads
            replied_result = await self.db.execute(
                select(func.count(func.distinct(TouchLog.lead_id))).where(
                    and_(
                        TouchLog.lead_id.in_(lead_ids),
                        TouchLog.action == TouchAction.replied,
                    )
                )
            )
            total_replied = replied_result.scalar() or 0

            # Bounces
            bounced_result = await self.db.execute(
                select(func.count(func.distinct(TouchLog.lead_id))).where(
                    and_(
                        TouchLog.lead_id.in_(lead_ids),
                        TouchLog.action == TouchAction.bounced,
                    )
                )
            )
            total_bounced = bounced_result.scalar() or 0

            # Channel breakdown
            channel_result = await self.db.execute(
                select(TouchLog.channel, func.count(TouchLog.id))
                .where(
                    and_(
                        TouchLog.extra_metadata["template_id"].astext == template_id_str,
                        TouchLog.action == TouchAction.sent,
                    )
                )
                .group_by(TouchLog.channel)
            )
            channels = {row[0]: row[1] for row in channel_result.all()}

            return {
                "template_id": template_id_str,
                "total_sent": total_sent,
                "unique_recipients": unique_recipients,
                "total_opened": total_opened,
                "total_replied": total_replied,
                "total_bounced": total_bounced,
                "open_rate": round(total_opened / unique_recipients, 4) if unique_recipients > 0 else 0.0,
                "reply_rate": round(total_replied / unique_recipients, 4) if unique_recipients > 0 else 0.0,
                "bounce_rate": round(total_bounced / unique_recipients, 4) if unique_recipients > 0 else 0.0,
                "channel_breakdown": channels,
                "computed_at": datetime.now(UTC).isoformat(),
            }

        except Exception as exc:
            logger.error(
                "Failed to get template performance for %s: %s", template_id, exc
            )
            return {
                "template_id": str(template_id),
                "error": str(exc),
            }

    # ── Learning Report ────────────────────────────────────────────────────

    async def generate_learning_report(self, sequence_id: UUID) -> dict[str, Any]:
        """
        Generate a comprehensive AI learning report for a sequence.

        Includes:
        - Full sequence metrics
        - Template performance breakdown
        - Channel performance comparison
        - Optimal send time analysis
        - AI platform recommendations
        - Actionable insights for next sequence generation

        Returns a structured report dict suitable for AI sequence generation input.
        """
        logger.info("Generating learning report for sequence %s", sequence_id)

        # Base metrics
        metrics = await self.aggregate_sequence_metrics(sequence_id)

        if "error" in metrics:
            return {"error": metrics["error"], "sequence_id": str(sequence_id)}

        # Channel comparison
        channel_perf = await self._analyze_channel_performance(sequence_id)

        # Optimal send time analysis
        send_time_analysis = await self._analyze_send_times(sequence_id)

        # Step funnel analysis
        step_funnel = await self._analyze_step_funnel(sequence_id)

        # AI recommendations
        recommendations = self._generate_recommendations(
            metrics, channel_perf, step_funnel
        )

        report = {
            "sequence_id": str(sequence_id),
            "generated_at": datetime.now(UTC).isoformat(),
            "summary_metrics": {
                "reply_rate": metrics.get("reply_rate"),
                "open_rate": metrics.get("open_rate"),
                "bounce_rate": metrics.get("bounce_rate"),
                "meeting_booked_rate": metrics.get("meeting_booked_rate"),
                "completion_rate": metrics.get("completion_rate"),
            },
            "channel_performance": channel_perf,
            "optimal_send_times": send_time_analysis,
            "step_funnel": step_funnel,
            "best_template": metrics.get("best_performing_template"),
            "best_channel": metrics.get("best_performing_channel"),
            "avg_steps_before_reply": metrics.get("avg_steps_before_reply"),
            "ai_recommendations": recommendations,
        }

        logger.info(
            "Learning report generated for sequence %s: "
            "reply_rate=%.1f%% best_channel=%s",
            sequence_id,
            (metrics.get("reply_rate") or 0) * 100,
            metrics.get("best_performing_channel"),
        )

        return report

    async def _analyze_channel_performance(
        self, sequence_id: UUID
    ) -> dict[str, Any]:
        """Analyze per-channel performance for a sequence."""
        channel_data: dict[str, Any] = {}

        for channel in ("email", "sms", "linkedin"):
            try:
                sent_r = await self.db.execute(
                    select(func.count(func.distinct(TouchLog.lead_id))).where(
                        and_(
                            TouchLog.sequence_id == sequence_id,
                            TouchLog.channel == channel,
                            TouchLog.action == TouchAction.sent,
                        )
                    )
                )
                sent = sent_r.scalar() or 0

                replied_r = await self.db.execute(
                    select(func.count(func.distinct(TouchLog.lead_id))).where(
                        and_(
                            TouchLog.sequence_id == sequence_id,
                            TouchLog.channel == channel,
                            TouchLog.action == TouchAction.replied,
                        )
                    )
                )
                replied = replied_r.scalar() or 0

                channel_data[channel] = {
                    "sent": sent,
                    "replied": replied,
                    "reply_rate": round(replied / sent, 4) if sent > 0 else 0.0,
                }
            except Exception as exc:
                logger.debug("Channel perf error for %s: %s", channel, exc)
                channel_data[channel] = {"error": str(exc)}

        return channel_data

    async def _analyze_send_times(self, sequence_id: UUID) -> dict[str, Any]:
        """
        Analyze which send hours correlated with replies.

        Returns bucketed analysis by hour of day.
        """
        try:
            # Get hour distribution of sent touches that led to replies
            result = await self.db.execute(
                select(
                    func.extract("hour", TouchLog.created_at).label("send_hour"),
                    func.count(TouchLog.id).label("reply_count"),
                )
                .where(
                    and_(
                        TouchLog.sequence_id == sequence_id,
                        TouchLog.action == TouchAction.replied,
                    )
                )
                .group_by(func.extract("hour", TouchLog.created_at))
                .order_by(func.count(TouchLog.id).desc())
            )
            rows = result.all()

            hour_distribution = {int(row[0]): row[1] for row in rows}
            peak_hours = sorted(
                hour_distribution.keys(),
                key=lambda h: hour_distribution[h],
                reverse=True,
            )[:3]

            return {
                "hour_distribution": hour_distribution,
                "peak_reply_hours": peak_hours,
                "recommendation": (
                    f"Best send hours: {', '.join(f'{h:02d}:00' for h in peak_hours)}"
                    if peak_hours
                    else "Insufficient data"
                ),
            }
        except Exception as exc:
            logger.debug("Send time analysis error: %s", exc)
            return {"error": str(exc)}

    async def _analyze_step_funnel(self, sequence_id: UUID) -> list[dict[str, Any]]:
        """
        Analyze drop-off at each sequence step.

        Returns list of {step: int, sent: int, replied: int, drop_off_rate: float}.
        """
        try:
            result = await self.db.execute(
                select(
                    TouchLog.step_number,
                    func.count(func.distinct(TouchLog.lead_id)).label("unique_leads"),
                )
                .where(
                    and_(
                        TouchLog.sequence_id == sequence_id,
                        TouchLog.action == TouchAction.sent,
                        TouchLog.step_number.is_not(None),
                    )
                )
                .group_by(TouchLog.step_number)
                .order_by(TouchLog.step_number)
            )
            steps = result.all()

            funnel: list[dict[str, Any]] = []
            prev_leads = None

            for step_num, unique_leads in steps:
                drop_off = (
                    round(1.0 - unique_leads / prev_leads, 4)
                    if prev_leads and prev_leads > 0
                    else 0.0
                )
                funnel.append(
                    {
                        "step": step_num,
                        "unique_leads_reached": unique_leads,
                        "drop_off_from_prev": drop_off,
                    }
                )
                prev_leads = unique_leads

            return funnel

        except Exception as exc:
            logger.debug("Step funnel analysis error: %s", exc)
            return []

    def _generate_recommendations(
        self,
        metrics: dict[str, Any],
        channel_perf: dict[str, Any],
        step_funnel: list[dict[str, Any]],
    ) -> list[str]:
        """
        Generate actionable recommendations for next sequence generation.

        Based on metrics, channel performance, and step funnel data.
        """
        recommendations: list[str] = []

        reply_rate = metrics.get("reply_rate", 0)
        open_rate = metrics.get("open_rate", 0)
        bounce_rate = metrics.get("bounce_rate", 0)
        best_channel = metrics.get("best_performing_channel")

        # Reply rate recommendations
        if reply_rate < 0.05:
            recommendations.append(
                "Reply rate is below 5% — test more personalized subject lines "
                "and shorten email body (aim for <150 words)."
            )
        elif reply_rate > 0.15:
            recommendations.append(
                f"Strong reply rate ({reply_rate:.1%}) — replicate subject line "
                f"patterns and timing from this sequence."
            )

        # Open rate
        if open_rate < 0.15:
            recommendations.append(
                "Open rate below 15% — A/B test subject lines; "
                "consider personalization tokens (first name, company)."
            )

        # Bounce rate
        if bounce_rate > 0.05:
            recommendations.append(
                "Bounce rate exceeds 5% threshold — validate lead list "
                "quality and run email validator before next sequence."
            )

        # Channel recommendations
        email_reply = channel_perf.get("email", {}).get("reply_rate", 0)
        linkedin_reply = channel_perf.get("linkedin", {}).get("reply_rate", 0)
        sms_reply = channel_perf.get("sms", {}).get("reply_rate", 0)

        if linkedin_reply > email_reply and channel_perf.get("linkedin", {}).get("sent", 0) > 0:
            recommendations.append(
                "LinkedIn outperformed email in reply rate — "
                "consider leading with LinkedIn connection in next sequence."
            )

        if sms_reply > email_reply and channel_perf.get("sms", {}).get("sent", 0) > 0:
            recommendations.append(
                "SMS nudges showed higher reply rate — "
                "add SMS touch earlier in the sequence flow."
            )

        # Step funnel drop-off
        if step_funnel:
            high_dropoff = [
                s for s in step_funnel if s.get("drop_off_from_prev", 0) > 0.30
            ]
            if high_dropoff:
                steps_str = ", ".join(str(s["step"]) for s in high_dropoff[:3])
                recommendations.append(
                    f"High drop-off detected at step(s) {steps_str} (>30%) — "
                    f"review content quality and delays at those steps."
                )

        # Average steps before reply
        avg_steps = metrics.get("avg_steps_before_reply", 0)
        if avg_steps > 4:
            recommendations.append(
                f"Leads typically reply at step {avg_steps:.1f} — "
                "consider adding a stronger CTA at steps 2-3 to accelerate."
            )
        elif 0 < avg_steps <= 2:
            recommendations.append(
                f"Most replies happen early (step {avg_steps:.1f}) — "
                "sequence length may be longer than needed; consider shortening."
            )

        if not recommendations:
            recommendations.append(
                "Sequence performance is within normal parameters. "
                "Continue monitoring and A/B test subject lines for optimization."
            )

        return recommendations
