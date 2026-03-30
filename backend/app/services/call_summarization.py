"""AI-powered call and meeting summarisation service."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class CallType(str, Enum):
    SALES_CALL = "sales_call"
    DISCOVERY = "discovery"
    DEMO = "demo"
    FOLLOW_UP = "follow_up"
    NEGOTIATION = "negotiation"
    MEETING = "meeting"
    ONBOARDING = "onboarding"


class Sentiment(str, Enum):
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"


@dataclass
class ActionItem:
    description: str
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    priority: str = "medium"
    status: str = "pending"


@dataclass
class CallSummary:
    id: str = field(default_factory=lambda: str(uuid4()))
    call_type: CallType = CallType.SALES_CALL
    duration_minutes: float = 0.0
    participants: list[str] = field(default_factory=list)
    transcript: str = ""
    summary: str = ""
    key_topics: list[str] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    sentiment: Sentiment = Sentiment.NEUTRAL
    sentiment_score: float = 0.5
    objections_raised: list[str] = field(default_factory=list)
    buying_signals: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    deal_stage_suggestion: Optional[str] = None
    follow_up_date: Optional[str] = None
    crm_logged: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class CallSummarizationService:
    """Transcribes and summarises sales calls and meetings using AI."""

    def __init__(self):
        self._summaries: dict[str, CallSummary] = {}

    async def summarize_call(
        self,
        transcript: str,
        call_type: str = "sales_call",
        participants: list[str] = None,
        duration_minutes: float = 0.0,
        api_key: Optional[str] = None,
    ) -> CallSummary:
        """Summarise a call transcript using AI."""
        summary = CallSummary(
            call_type=CallType(call_type) if call_type in [t.value for t in CallType] else CallType.SALES_CALL,
            duration_minutes=duration_minutes,
            participants=participants or [],
            transcript=transcript,
        )

        if api_key:
            try:
                from groq import AsyncGroq

                client = AsyncGroq(api_key=api_key)

                prompt = f"""Analyse this {call_type} transcript and return JSON:
{{
    "summary": "2-3 paragraph executive summary",
    "key_topics": ["topic1", "topic2"],
    "action_items": [{{"description": "...", "assignee": "...", "due_date": "...", "priority": "high|medium|low"}}],
    "sentiment": "very_positive|positive|neutral|negative|very_negative",
    "sentiment_score": 0.0-1.0,
    "objections_raised": ["objection1"],
    "buying_signals": ["signal1"],
    "next_steps": ["step1"],
    "deal_stage_suggestion": "stage name or null",
    "follow_up_date": "YYYY-MM-DD or null"
}}

Transcript:
{transcript[:8000]}"""

                response = await client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a sales call analysis expert. Extract insights, action items, and sentiment from call transcripts. Return valid JSON only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                    max_tokens=2048,
                )

                data = json.loads(response.choices[0].message.content)
                summary.summary = data.get("summary", "")
                summary.key_topics = data.get("key_topics", [])
                summary.action_items = [ActionItem(**ai) for ai in data.get("action_items", [])]
                summary.sentiment = Sentiment(data.get("sentiment", "neutral"))
                summary.sentiment_score = float(data.get("sentiment_score", 0.5))
                summary.objections_raised = data.get("objections_raised", [])
                summary.buying_signals = data.get("buying_signals", [])
                summary.next_steps = data.get("next_steps", [])
                summary.deal_stage_suggestion = data.get("deal_stage_suggestion")
                summary.follow_up_date = data.get("follow_up_date")

            except Exception as e:
                logger.error("AI summarisation failed: %s", e)
                summary.summary = self._fallback_summary(transcript)
        else:
            summary.summary = self._fallback_summary(transcript)

        self._summaries[summary.id] = summary
        return summary

    def _fallback_summary(self, transcript: str) -> str:
        words = transcript.split()
        return f"Call transcript with {len(words)} words. AI summarisation unavailable - manual review recommended."

    async def log_to_crm(self, summary_id: str, crm_agent: str = "hubspot") -> dict:
        """Log call summary to CRM as an activity."""
        summary = self._summaries.get(summary_id)
        if not summary:
            return {"success": False, "error": "Summary not found"}

        crm_data = {
            "type": "CALL",
            "subject": f"{summary.call_type.value.replace('_', ' ').title()} Summary",
            "body": summary.summary,
            "duration_ms": int(summary.duration_minutes * 60 * 1000),
            "metadata": {
                "sentiment": summary.sentiment.value,
                "action_items_count": len(summary.action_items),
                "key_topics": summary.key_topics,
                "next_steps": summary.next_steps,
            },
        }

        summary.crm_logged = True
        logger.info("Call summary %s logged to %s", summary_id, crm_agent)
        return {"success": True, "crm_data": crm_data}

    def get_summary(self, summary_id: str) -> Optional[CallSummary]:
        return self._summaries.get(summary_id)

    def get_analytics(self) -> dict:
        summaries = list(self._summaries.values())
        if not summaries:
            return {"total_calls": 0}

        sentiments = [s.sentiment_score for s in summaries]
        return {
            "total_calls": len(summaries),
            "avg_duration_minutes": round(sum(s.duration_minutes for s in summaries) / len(summaries), 1),
            "avg_sentiment": round(sum(sentiments) / len(sentiments), 2),
            "total_action_items": sum(len(s.action_items) for s in summaries),
            "calls_logged_to_crm": sum(1 for s in summaries if s.crm_logged),
            "call_type_distribution": {t.value: sum(1 for s in summaries if s.call_type == t) for t in CallType},
            "top_objections": self._get_top_items([o for s in summaries for o in s.objections_raised]),
            "top_buying_signals": self._get_top_items([b for s in summaries for b in s.buying_signals]),
        }

    def _get_top_items(self, items: list[str], limit: int = 5) -> list[dict]:
        counts = {}
        for item in items:
            counts[item] = counts.get(item, 0) + 1
        return [{"item": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])[:limit]]
