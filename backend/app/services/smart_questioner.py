"""
Smart Questioner — conversational follow-up for ambiguous or incomplete commands.

When a command is missing required info, this service generates targeted
questions instead of guessing, then tracks gathered parameters in session state.
"""

import logging
from typing import Any

from app.config import settings
from app.utils.sanitize import sanitize_error

logger = logging.getLogger(__name__)

# ── Required/optional fields per intent ──────────────────────────────────────

INTENT_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "find_leads": {
        "required": ["specialty_or_criteria"],
        "optional": ["location", "count", "company_size"],
        "defaults": {"count": 25, "location": "nationwide"},
    },
    "create_campaign": {
        "required": ["target_description"],
        "optional": ["channels", "tone", "sequence_length", "start_date", "location", "count"],
        "defaults": {
            "channels": ["email"],
            "tone": "professional",
            "sequence_length": 5,
            "count": 50,
        },
    },
    "import_leads": {
        "required": ["source_type"],
        "optional": ["file_path"],
        "defaults": {"source_type": "csv"},
    },
    "enrich_leads": {
        "required": [],
        "optional": ["provider", "count"],
        "defaults": {"provider": "all"},
    },
    "pause_campaign": {
        "required": ["campaign_name"],
        "optional": [],
        "defaults": {},
    },
    "resume_campaign": {
        "required": ["campaign_name"],
        "optional": [],
        "defaults": {},
    },
    "check_status": {
        "required": [],
        "optional": ["campaign_name", "timeframe"],
        "defaults": {"timeframe": "7d"},
    },
    "check_deliverability": {
        "required": [],
        "optional": ["timeframe"],
        "defaults": {"timeframe": "7d"},
    },
    "configure_integration": {
        "required": ["integration_name"],
        "optional": [],
        "defaults": {},
    },
    "check_integrations": {
        "required": [],
        "optional": [],
        "defaults": {},
    },
    "get_help": {
        "required": [],
        "optional": [],
        "defaults": {},
    },
}

# ── Prompt for generating follow-up questions ────────────────────────────────

_QUESTION_PROMPT = """\
You are a helpful assistant for FortressFlow, a B2B outreach platform for dental offices.

The user wants to: {intent_description}
What they said: "{user_message}"
What we already know: {gathered_params}
What we still need: {missing_fields}
Default values available: {defaults}

Generate a brief, conversational follow-up that:
1. Acknowledges what they want (1 short sentence)
2. Asks about the missing required fields naturally (not as a numbered list)
3. Mentions relevant defaults so they can just say "yes" to use them
4. Keep it under 60 words

Be friendly and efficient — dental professionals are busy."""


class SmartQuestioner:
    """Handles multi-turn question flows to gather missing command parameters."""

    async def ask_clarification(
        self,
        intent_result: Any,
        user_message: str,
        session_state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate a targeted follow-up question for missing parameters.

        Returns a structured response with type "question" and updated session state.
        """
        intent = intent_result.intent
        reqs = INTENT_REQUIREMENTS.get(intent, {"required": [], "optional": [], "defaults": {}})
        gathered = session_state.get("gathered_params", {})

        # Merge entities from classification into gathered params
        gathered.update({k: v for k, v in intent_result.entities.items() if v})

        # Determine what's still missing
        missing_required = [f for f in reqs["required"] if f not in gathered]

        if not missing_required:
            # All required fields are gathered — apply defaults and execute
            for key, default in reqs["defaults"].items():
                if key not in gathered:
                    gathered[key] = default

            return {
                "type": "ready_to_execute",
                "intent": intent,
                "params": gathered,
                "session_state": {
                    "active_intent": None,
                    "gathered_params": {},
                    "pending_questions": [],
                },
            }

        # Generate a conversational question
        question_text = await self._generate_question(
            intent=intent,
            user_message=user_message,
            gathered=gathered,
            missing=missing_required,
            defaults=reqs["defaults"],
        )

        # Build suggested options based on the missing field
        options = self._suggest_options(intent, missing_required)

        return {
            "type": "question",
            "content": question_text,
            "options": options,
            "session_state": {
                "active_intent": intent,
                "gathered_params": gathered,
                "pending_questions": missing_required,
                "intent_confidence": intent_result.confidence,
            },
        }

    async def process_answer(
        self,
        message: str,
        session_state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process a user's answer to a clarifying question.

        Attempts to extract the answer from natural language and map it
        to the pending question fields.
        """
        intent = session_state.get("active_intent", "")
        gathered = dict(session_state.get("gathered_params", {}))
        pending = list(session_state.get("pending_questions", []))

        if not intent or not pending:
            return {"type": "passthrough", "session_state": session_state}

        # Use LLM to extract answers from the user's message
        extracted = await self._extract_answers(message, pending, intent)
        gathered.update(extracted)

        # Remove answered questions
        still_pending = [q for q in pending if q not in extracted]

        if not still_pending:
            # All required fields gathered — apply defaults and execute
            reqs = INTENT_REQUIREMENTS.get(intent, {"defaults": {}})
            for key, default in reqs.get("defaults", {}).items():
                if key not in gathered:
                    gathered[key] = default

            return {
                "type": "ready_to_execute",
                "intent": intent,
                "params": gathered,
                "session_state": {
                    "active_intent": None,
                    "gathered_params": {},
                    "pending_questions": [],
                },
            }

        # Still missing — ask again
        reqs = INTENT_REQUIREMENTS.get(intent, {"defaults": {}})
        question = await self._generate_question(
            intent=intent,
            user_message=message,
            gathered=gathered,
            missing=still_pending,
            defaults=reqs.get("defaults", {}),
        )

        return {
            "type": "question",
            "content": question,
            "options": self._suggest_options(intent, still_pending),
            "session_state": {
                "active_intent": intent,
                "gathered_params": gathered,
                "pending_questions": still_pending,
            },
        }

    async def _generate_question(
        self,
        intent: str,
        user_message: str,
        gathered: dict[str, Any],
        missing: list[str],
        defaults: dict[str, Any],
    ) -> str:
        """Generate a conversational follow-up question via LLM."""
        from app.services.command_engine import INTENTS

        intent_desc = INTENTS.get(intent, intent)
        prompt = _QUESTION_PROMPT.format(
            intent_description=intent_desc,
            user_message=user_message,
            gathered_params=gathered or "nothing yet",
            missing_fields=", ".join(missing),
            defaults={k: v for k, v in defaults.items() if k in missing or k not in gathered},
        )

        raw = await self._call_llm(prompt)
        if raw:
            return raw

        # Fallback: static question
        field_questions = {
            "specialty_or_criteria": "What type of dental professional are you looking for? (e.g., periodontist, oral surgeon, general dentist)",
            "target_description": "Who should this campaign target? (e.g., periodontists in Texas, DSO decision-makers)",
            "campaign_name": "Which campaign are you referring to?",
            "location": "What location or region?",
            "count": "How many leads would you like?",
            "channels": "Which channels? (email, LinkedIn, SMS, or multi-channel)",
            "source_type": "Where are you importing from? (CSV or HubSpot)",
            "integration_name": "Which integration? (HubSpot, ZoomInfo, or Apollo)",
        }
        questions = [field_questions.get(f, f"What's the {f.replace('_', ' ')}?") for f in missing]
        return " ".join(questions)

    async def _extract_answers(
        self,
        message: str,
        pending_fields: list[str],
        intent: str,
    ) -> dict[str, Any]:
        """Use LLM to extract answers from a natural language message."""
        prompt = (
            f"The user is answering questions about their '{intent}' request.\n"
            f"Pending fields: {pending_fields}\n"
            f'User said: "{message}"\n\n'
            f"Extract values for the pending fields from the message.\n"
            f"Respond ONLY with valid JSON mapping field names to extracted values.\n"
            f"Only include fields that have clear answers in the message.\n"
            f'Example: {{"location": "Texas", "count": 50}}'
        )

        raw = await self._call_llm(prompt)
        if not raw:
            return self._fallback_extract(message, pending_fields)

        try:
            import json

            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

            data = json.loads(cleaned)
            return {k: v for k, v in data.items() if k in pending_fields and v}
        except (ValueError, TypeError):
            return self._fallback_extract(message, pending_fields)

    def _fallback_extract(self, message: str, pending_fields: list[str]) -> dict[str, Any]:
        """Simple keyword-based extraction fallback."""
        result: dict[str, Any] = {}
        msg_lower = message.lower().strip()

        if "specialty_or_criteria" in pending_fields or "target_description" in pending_fields:
            specialties = [
                "periodontist",
                "oral surgeon",
                "endodontist",
                "orthodontist",
                "prosthodontist",
                "pediatric dentist",
                "general dentist",
                "dental hygienist",
                "office manager",
                "dso",
            ]
            for s in specialties:
                if s in msg_lower:
                    key = "specialty_or_criteria" if "specialty_or_criteria" in pending_fields else "target_description"
                    result[key] = s
                    break

        if "location" in pending_fields:
            # Just use the whole message if it looks like a location answer
            if len(msg_lower.split()) <= 5:
                result["location"] = message.strip()

        if "count" in pending_fields:
            import re

            numbers = re.findall(r"\d+", message)
            if numbers:
                result["count"] = int(numbers[0])

        if "campaign_name" in pending_fields:
            # Use the message as the campaign name if it's short
            if len(message.strip()) < 100:
                result["campaign_name"] = message.strip()

        return result

    def _suggest_options(self, intent: str, missing_fields: list[str]) -> list[str]:
        """Generate suggested quick-reply options for missing fields."""
        if not missing_fields:
            return []

        field = missing_fields[0]
        options_map = {
            "specialty_or_criteria": ["Periodontists", "Oral Surgeons", "General Dentists", "Endodontists"],
            "target_description": ["Periodontists", "Oral Surgeons", "DSO Decision Makers", "General Dentists"],
            "location": ["Texas", "California", "New York", "Nationwide"],
            "count": ["25", "50", "100"],
            "channels": ["Email only", "Email + LinkedIn", "Multi-channel (all)"],
            "campaign_name": [],
            "source_type": ["CSV", "HubSpot"],
            "integration_name": ["HubSpot", "ZoomInfo", "Apollo"],
        }
        return options_map.get(field, [])

    async def _call_llm(self, prompt: str) -> str:
        """Lightweight LLM call for question generation."""
        groq_key = getattr(settings, "GROQ_API_KEY", "")
        if groq_key:
            try:
                from groq import AsyncGroq

                client = AsyncGroq(api_key=groq_key)
                resp = await client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a helpful, concise assistant for FortressFlow."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=200,
                )
                return resp.choices[0].message.content or ""
            except Exception as exc:
                logger.warning("SmartQuestioner Groq call failed: %s", sanitize_error(exc))

        openai_key = getattr(settings, "OPENAI_API_KEY", "")
        if openai_key:
            try:
                from openai import AsyncOpenAI

                client = AsyncOpenAI(api_key=openai_key)
                resp = await client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a helpful, concise assistant for FortressFlow."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=200,
                )
                return resp.choices[0].message.content or ""
            except Exception as exc:
                logger.warning("SmartQuestioner OpenAI call failed: %s", sanitize_error(exc))

        return ""
