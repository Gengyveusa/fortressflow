"""
Twilio Communication Agent — Full platform agent wrapping the existing sms_service.

Provides SMS (single + bulk), voice calls, OTP verification, phone lookup,
number management, messaging services, and usage analytics.
All methods are async. The synchronous Twilio SDK is wrapped with asyncio.to_thread().
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.api_key_service import get_api_key
from app.services.sms_service import send_sms as sms_service_send, SMSResult

logger = logging.getLogger(__name__)


class TwilioAgent:
    """Full Twilio communication agent. Wraps sms_service and adds voice, verify, lookup, etc."""

    def __init__(self) -> None:
        self._account_sid: str | None = None
        self._auth_token: str | None = None
        self._client = None  # Lazy-loaded twilio.rest.Client

    async def _resolve_api_key(self, user_id: UUID | None) -> tuple[str, str]:
        """Resolve Twilio credentials: DB first (JSON blob), then env fallback.

        Returns (account_sid, auth_token).
        """
        if user_id:
            async with AsyncSessionLocal() as db:
                raw_key = await get_api_key(db, "twilio", user_id)
                if raw_key:
                    # DB stores as JSON: {"account_sid": "...", "auth_token": "..."}
                    try:
                        creds = json.loads(raw_key)
                        sid = creds.get("account_sid", "")
                        token = creds.get("auth_token", "")
                        if sid and token:
                            return sid, token
                    except (json.JSONDecodeError, AttributeError):
                        # Treat plain string as auth_token paired with env SID
                        if settings.TWILIO_ACCOUNT_SID:
                            return settings.TWILIO_ACCOUNT_SID, raw_key

        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            return settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN

        raise ValueError(
            "Twilio credentials not configured — set via Settings or "
            "TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN env vars"
        )

    def _get_client(self, account_sid: str, auth_token: str):
        """Get or create the Twilio REST client (synchronous SDK)."""
        if (
            self._client is None
            or self._account_sid != account_sid
            or self._auth_token != auth_token
        ):
            from twilio.rest import Client

            self._client = Client(account_sid, auth_token)
            self._account_sid = account_sid
            self._auth_token = auth_token
        return self._client

    async def _get_twilio(self, user_id: UUID | None = None):
        """Resolve credentials and return the Twilio client."""
        sid, token = await self._resolve_api_key(user_id)
        return self._get_client(sid, token)

    # ── SMS ────────────────────────────────────────────────────────────────

    async def send_sms(
        self,
        to: str,
        body: str,
        from_: str | None = None,
        media_url: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Send a single SMS/MMS message."""
        client = await self._get_twilio(user_id)
        from_number = from_ or settings.TWILIO_PHONE_NUMBER

        if not from_number:
            return {"success": False, "error": "No from number configured"}

        kwargs: dict = {"body": body, "from_": from_number, "to": to}
        if media_url:
            kwargs["media_url"] = [media_url]

        try:
            message = await asyncio.to_thread(client.messages.create, **kwargs)
            return {
                "success": True,
                "sid": message.sid,
                "status": message.status,
                "to": to,
            }
        except Exception as exc:
            logger.error("Twilio send_sms error: %s", exc)
            return {"success": False, "error": str(exc)}

    async def bulk_send_sms(
        self, messages: list[dict], user_id: UUID | None = None
    ) -> list[dict]:
        """Send multiple SMS messages. Each dict: {to, body, from_(optional), media_url(optional)}."""
        results = []
        for msg in messages:
            result = await self.send_sms(
                to=msg["to"],
                body=msg["body"],
                from_=msg.get("from_"),
                media_url=msg.get("media_url"),
                user_id=user_id,
            )
            results.append(result)
        return results

    async def get_message(
        self, sid: str, user_id: UUID | None = None
    ) -> dict:
        """Get details of a specific message by SID."""
        client = await self._get_twilio(user_id)
        try:
            msg = await asyncio.to_thread(client.messages(sid).fetch)
            return {
                "sid": msg.sid,
                "to": msg.to,
                "from_": msg.from_,
                "body": msg.body,
                "status": msg.status,
                "date_sent": str(msg.date_sent) if msg.date_sent else None,
                "num_segments": msg.num_segments,
                "price": msg.price,
            }
        except Exception as exc:
            logger.error("Twilio get_message error: %s", exc)
            return {"error": str(exc)}

    async def list_messages(
        self,
        date_sent_after=None,
        to: str | None = None,
        from_: str | None = None,
        limit: int = 20,
        user_id: UUID | None = None,
    ) -> list[dict]:
        """List messages with optional filters."""
        client = await self._get_twilio(user_id)
        kwargs: dict = {"limit": limit}
        if date_sent_after:
            kwargs["date_sent_after"] = date_sent_after
        if to:
            kwargs["to"] = to
        if from_:
            kwargs["from_"] = from_

        try:
            messages = await asyncio.to_thread(client.messages.list, **kwargs)
            return [
                {
                    "sid": m.sid,
                    "to": m.to,
                    "from_": m.from_,
                    "body": m.body,
                    "status": m.status,
                    "date_sent": str(m.date_sent) if m.date_sent else None,
                }
                for m in messages
            ]
        except Exception as exc:
            logger.error("Twilio list_messages error: %s", exc)
            return []

    # ── Voice ──────────────────────────────────────────────────────────────

    async def make_call(
        self,
        to: str,
        from_: str,
        twiml: str | None = None,
        url: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Make an outbound voice call with TwiML or a URL."""
        client = await self._get_twilio(user_id)
        kwargs: dict = {"to": to, "from_": from_}
        if twiml:
            kwargs["twiml"] = twiml
        elif url:
            kwargs["url"] = url
        else:
            return {"success": False, "error": "Either twiml or url is required"}

        try:
            call = await asyncio.to_thread(client.calls.create, **kwargs)
            return {
                "success": True,
                "sid": call.sid,
                "status": call.status,
                "to": to,
            }
        except Exception as exc:
            logger.error("Twilio make_call error: %s", exc)
            return {"success": False, "error": str(exc)}

    async def get_call(
        self, sid: str, user_id: UUID | None = None
    ) -> dict:
        """Get details of a specific call."""
        client = await self._get_twilio(user_id)
        try:
            call = await asyncio.to_thread(client.calls(sid).fetch)
            return {
                "sid": call.sid,
                "to": call.to,
                "from_": call.from_,
                "status": call.status,
                "duration": call.duration,
                "start_time": str(call.start_time) if call.start_time else None,
                "end_time": str(call.end_time) if call.end_time else None,
                "price": call.price,
            }
        except Exception as exc:
            logger.error("Twilio get_call error: %s", exc)
            return {"error": str(exc)}

    async def list_calls(
        self,
        date_after=None,
        to: str | None = None,
        limit: int = 20,
        user_id: UUID | None = None,
    ) -> list[dict]:
        """List calls with optional filters."""
        client = await self._get_twilio(user_id)
        kwargs: dict = {"limit": limit}
        if date_after:
            kwargs["start_time_after"] = date_after
        if to:
            kwargs["to"] = to

        try:
            calls = await asyncio.to_thread(client.calls.list, **kwargs)
            return [
                {
                    "sid": c.sid,
                    "to": c.to,
                    "from_": c.from_,
                    "status": c.status,
                    "duration": c.duration,
                    "start_time": str(c.start_time) if c.start_time else None,
                }
                for c in calls
            ]
        except Exception as exc:
            logger.error("Twilio list_calls error: %s", exc)
            return []

    # ── Verify (OTP) ───────────────────────────────────────────────────────

    async def send_verification(
        self, to: str, channel: str = "sms", user_id: UUID | None = None
    ) -> dict:
        """Send a verification code via SMS, call, or email."""
        client = await self._get_twilio(user_id)

        verify_sid = getattr(settings, "TWILIO_VERIFY_SERVICE_SID", None)
        if not verify_sid:
            return {"success": False, "error": "TWILIO_VERIFY_SERVICE_SID not configured"}

        try:
            verification = await asyncio.to_thread(
                client.verify.v2.services(verify_sid).verifications.create,
                to=to,
                channel=channel,
            )
            return {
                "success": True,
                "sid": verification.sid,
                "status": verification.status,
                "channel": channel,
                "to": to,
            }
        except Exception as exc:
            logger.error("Twilio send_verification error: %s", exc)
            return {"success": False, "error": str(exc)}

    async def check_verification(
        self, to: str, code: str, user_id: UUID | None = None
    ) -> dict:
        """Check a verification code."""
        client = await self._get_twilio(user_id)

        verify_sid = getattr(settings, "TWILIO_VERIFY_SERVICE_SID", None)
        if not verify_sid:
            return {"success": False, "error": "TWILIO_VERIFY_SERVICE_SID not configured"}

        try:
            check = await asyncio.to_thread(
                client.verify.v2.services(verify_sid).verification_checks.create,
                to=to,
                code=code,
            )
            return {
                "success": check.status == "approved",
                "status": check.status,
                "to": to,
            }
        except Exception as exc:
            logger.error("Twilio check_verification error: %s", exc)
            return {"success": False, "error": str(exc)}

    # ── Lookup ─────────────────────────────────────────────────────────────

    async def lookup_phone(
        self, phone_number: str, user_id: UUID | None = None
    ) -> dict:
        """Lookup phone number info: carrier, type, caller name."""
        client = await self._get_twilio(user_id)
        try:
            result = await asyncio.to_thread(
                client.lookups.v2.phone_numbers(phone_number).fetch,
            )
            return {
                "phone_number": result.phone_number,
                "country_code": result.country_code,
                "national_format": result.national_format,
                "valid": result.valid,
                "calling_country_code": result.calling_country_code,
            }
        except Exception as exc:
            logger.error("Twilio lookup_phone error: %s", exc)
            return {"error": str(exc)}

    async def validate_phone(
        self, phone_number: str, user_id: UUID | None = None
    ) -> dict:
        """Validate a phone number and return formatting details."""
        client = await self._get_twilio(user_id)
        try:
            result = await asyncio.to_thread(
                client.lookups.v2.phone_numbers(phone_number).fetch,
            )
            return {
                "phone_number": result.phone_number,
                "valid": result.valid,
                "country_code": result.country_code,
                "national_format": result.national_format,
            }
        except Exception as exc:
            logger.error("Twilio validate_phone error: %s", exc)
            return {"phone_number": phone_number, "valid": False, "error": str(exc)}

    # ── Number Management ──────────────────────────────────────────────────

    async def list_phone_numbers(
        self, user_id: UUID | None = None
    ) -> list[dict]:
        """List all phone numbers on the account."""
        client = await self._get_twilio(user_id)
        try:
            numbers = await asyncio.to_thread(
                client.incoming_phone_numbers.list
            )
            return [
                {
                    "sid": n.sid,
                    "phone_number": n.phone_number,
                    "friendly_name": n.friendly_name,
                    "capabilities": {
                        "voice": n.capabilities.get("voice", False),
                        "sms": n.capabilities.get("sms", False),
                        "mms": n.capabilities.get("mms", False),
                    },
                    "sms_url": n.sms_url,
                    "voice_url": n.voice_url,
                }
                for n in numbers
            ]
        except Exception as exc:
            logger.error("Twilio list_phone_numbers error: %s", exc)
            return []

    async def buy_phone_number(
        self,
        area_code: str | None = None,
        country: str = "US",
        user_id: UUID | None = None,
    ) -> dict:
        """Purchase a new phone number."""
        client = await self._get_twilio(user_id)
        try:
            # Search for available numbers
            search_kwargs: dict = {"limit": 1}
            if area_code:
                search_kwargs["area_code"] = area_code

            available = await asyncio.to_thread(
                client.available_phone_numbers(country).local.list,
                **search_kwargs,
            )
            if not available:
                return {"success": False, "error": f"No numbers available for area code {area_code}"}

            phone_number = available[0].phone_number

            # Purchase it
            number = await asyncio.to_thread(
                client.incoming_phone_numbers.create,
                phone_number=phone_number,
            )
            return {
                "success": True,
                "sid": number.sid,
                "phone_number": number.phone_number,
                "friendly_name": number.friendly_name,
            }
        except Exception as exc:
            logger.error("Twilio buy_phone_number error: %s", exc)
            return {"success": False, "error": str(exc)}

    async def configure_number(
        self,
        sid: str,
        sms_url: str | None = None,
        voice_url: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Configure webhooks for a phone number."""
        client = await self._get_twilio(user_id)
        kwargs: dict = {}
        if sms_url is not None:
            kwargs["sms_url"] = sms_url
        if voice_url is not None:
            kwargs["voice_url"] = voice_url

        try:
            number = await asyncio.to_thread(
                client.incoming_phone_numbers(sid).update,
                **kwargs,
            )
            return {
                "sid": number.sid,
                "phone_number": number.phone_number,
                "sms_url": number.sms_url,
                "voice_url": number.voice_url,
            }
        except Exception as exc:
            logger.error("Twilio configure_number error: %s", exc)
            return {"error": str(exc)}

    async def release_number(
        self, sid: str, user_id: UUID | None = None
    ) -> bool:
        """Release (delete) a phone number."""
        client = await self._get_twilio(user_id)
        try:
            await asyncio.to_thread(
                client.incoming_phone_numbers(sid).delete,
            )
            return True
        except Exception as exc:
            logger.error("Twilio release_number error: %s", exc)
            return False

    # ── Messaging Services ─────────────────────────────────────────────────

    async def create_messaging_service(
        self, name: str, user_id: UUID | None = None
    ) -> dict:
        """Create a new messaging service."""
        client = await self._get_twilio(user_id)
        try:
            service = await asyncio.to_thread(
                client.messaging.v1.services.create,
                friendly_name=name,
            )
            return {
                "sid": service.sid,
                "friendly_name": service.friendly_name,
                "date_created": str(service.date_created) if service.date_created else None,
            }
        except Exception as exc:
            logger.error("Twilio create_messaging_service error: %s", exc)
            return {"error": str(exc)}

    async def add_sender_to_service(
        self, service_sid: str, phone_sid: str, user_id: UUID | None = None
    ) -> bool:
        """Add a phone number sender to a messaging service."""
        client = await self._get_twilio(user_id)
        try:
            await asyncio.to_thread(
                client.messaging.v1.services(service_sid).phone_numbers.create,
                phone_number_sid=phone_sid,
            )
            return True
        except Exception as exc:
            logger.error("Twilio add_sender_to_service error: %s", exc)
            return False

    # ── Analytics ──────────────────────────────────────────────────────────

    async def get_usage(
        self,
        category: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        user_id: UUID | None = None,
    ) -> list[dict]:
        """Get usage records for the account."""
        client = await self._get_twilio(user_id)
        kwargs: dict = {}
        if category:
            kwargs["category"] = category
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date

        try:
            records = await asyncio.to_thread(
                client.usage.records.list,
                **kwargs,
            )
            return [
                {
                    "category": r.category,
                    "description": r.description,
                    "count": r.count,
                    "usage": r.usage,
                    "price": r.price,
                    "start_date": str(r.start_date) if r.start_date else None,
                    "end_date": str(r.end_date) if r.end_date else None,
                }
                for r in records
            ]
        except Exception as exc:
            logger.error("Twilio get_usage error: %s", exc)
            return []

    async def get_delivery_stats(
        self, start_date: str, end_date: str, user_id: UUID | None = None
    ) -> dict:
        """Get SMS delivery statistics for a date range."""
        messages = await self.list_messages(
            date_sent_after=start_date, limit=1000, user_id=user_id,
        )

        total = len(messages)
        status_counts: dict[str, int] = {}
        for msg in messages:
            s = msg.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1

        delivered = status_counts.get("delivered", 0)
        failed = status_counts.get("failed", 0) + status_counts.get("undelivered", 0)

        return {
            "total_messages": total,
            "delivered": delivered,
            "failed": failed,
            "delivery_rate": round(delivered / total, 4) if total > 0 else 0.0,
            "failure_rate": round(failed / total, 4) if total > 0 else 0.0,
            "status_breakdown": status_counts,
            "start_date": start_date,
            "end_date": end_date,
        }

    # ── Advanced Messaging ────────────────────────────────────────────────────

    async def send_mms(
        self,
        to: str,
        body: str,
        media_urls: list[str],
        from_number: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Send an MMS with images/media attachments."""
        client = await self._get_twilio(user_id)
        from_num = from_number or settings.TWILIO_PHONE_NUMBER

        if not from_num:
            return {"success": False, "error": "No from number configured"}

        try:
            message = await asyncio.to_thread(
                client.messages.create,
                body=body,
                from_=from_num,
                to=to,
                media_url=media_urls,
            )
            return {
                "success": True,
                "sid": message.sid,
                "status": message.status,
                "to": to,
                "media_count": len(media_urls),
            }
        except Exception as exc:
            logger.error("Twilio send_mms error: %s", exc)
            return {"success": False, "error": str(exc)}


    async def send_whatsapp(
        self,
        to: str,
        body: str | None = None,
        template_sid: str | None = None,
        template_variables: dict | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Send a WhatsApp Business message."""
        client = await self._get_twilio(user_id)

        whatsapp_from = getattr(settings, "TWILIO_WHATSAPP_NUMBER", None)
        if not whatsapp_from:
            return {"success": False, "error": "TWILIO_WHATSAPP_NUMBER not configured"}

        # Ensure WhatsApp format
        wa_to = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
        wa_from = whatsapp_from if whatsapp_from.startswith("whatsapp:") else f"whatsapp:{whatsapp_from}"

        kwargs: dict = {"from_": wa_from, "to": wa_to}
        if template_sid:
            kwargs["content_sid"] = template_sid
            if template_variables:
                kwargs["content_variables"] = json.dumps(template_variables)
        elif body:
            kwargs["body"] = body
        else:
            return {"success": False, "error": "Either body or template_sid is required"}

        try:
            message = await asyncio.to_thread(client.messages.create, **kwargs)
            return {
                "success": True,
                "sid": message.sid,
                "status": message.status,
                "to": wa_to,
                "channel": "whatsapp",
            }
        except Exception as exc:
            logger.error("Twilio send_whatsapp error: %s", exc)
            return {"success": False, "error": str(exc)}


    async def schedule_message(
        self,
        to: str,
        body: str,
        send_at: str,
        from_number: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Schedule an SMS for future delivery.

        send_at: ISO 8601 datetime string (must be 15+ min in future, max 7 days)
        """
        client = await self._get_twilio(user_id)
        from_num = from_number or settings.TWILIO_PHONE_NUMBER

        messaging_service_sid = getattr(settings, "TWILIO_MESSAGING_SERVICE_SID", None)
        if not messaging_service_sid:
            return {"success": False, "error": "TWILIO_MESSAGING_SERVICE_SID required for scheduling"}

        try:
            message = await asyncio.to_thread(
                client.messages.create,
                body=body,
                messaging_service_sid=messaging_service_sid,
                to=to,
                send_at=send_at,
                schedule_type="fixed",
            )
            return {
                "success": True,
                "sid": message.sid,
                "status": message.status,
                "to": to,
                "scheduled_for": send_at,
            }
        except Exception as exc:
            logger.error("Twilio schedule_message error: %s", exc)
            return {"success": False, "error": str(exc)}


    async def create_content_template(
        self,
        name: str,
        body: str,
        variables: dict | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Create a content template for messaging."""
        client = await self._get_twilio(user_id)

        try:
            content = await asyncio.to_thread(
                client.content.v1.contents.create,
                friendly_name=name,
                types={"twilio/text": {"body": body}},
                variables=variables or {},
            )
            return {
                "sid": content.sid,
                "friendly_name": content.friendly_name,
                "date_created": str(content.date_created) if content.date_created else None,
            }
        except Exception as exc:
            logger.error("Twilio create_content_template error: %s", exc)
            return {"error": str(exc)}


    async def list_content_templates(
        self, user_id: UUID | None = None,
    ) -> list[dict]:
        """List approved content templates."""
        client = await self._get_twilio(user_id)

        try:
            templates = await asyncio.to_thread(client.content.v1.contents.list)
            return [
                {
                    "sid": t.sid,
                    "friendly_name": t.friendly_name,
                    "types": t.types,
                    "date_created": str(t.date_created) if t.date_created else None,
                }
                for t in templates
            ]
        except Exception as exc:
            logger.error("Twilio list_content_templates error: %s", exc)
            return []


    # ── Opt-out Management ────────────────────────────────────────────────────

    async def check_opt_out_status(
        self,
        phone_number: str,
        messaging_service_sid: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Check if a phone number has opted out."""
        client = await self._get_twilio(user_id)
        ms_sid = messaging_service_sid or getattr(settings, "TWILIO_MESSAGING_SERVICE_SID", None)

        if not ms_sid:
            return {"error": "Messaging service SID required"}

        try:
            result = await asyncio.to_thread(
                client.messaging.v1.services(ms_sid).phone_numbers(phone_number).fetch,
            )
            return {
                "phone_number": phone_number,
                "opted_out": False,
                "messaging_service_sid": ms_sid,
            }
        except Exception as exc:
            # 404 typically means opted out or not found
            logger.error("Twilio check_opt_out_status error: %s", exc)
            return {"phone_number": phone_number, "opted_out": True, "error": str(exc)}


    async def process_opt_out(
        self,
        phone_number: str,
        messaging_service_sid: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Process a STOP (opt-out) request for a phone number."""
        client = await self._get_twilio(user_id)
        ms_sid = messaging_service_sid or getattr(settings, "TWILIO_MESSAGING_SERVICE_SID", None)

        if not ms_sid:
            return {"success": False, "error": "Messaging service SID required"}

        try:
            # Add to opt-out list
            result = await asyncio.to_thread(
                client.messaging.v1.services(ms_sid).phone_numbers.create,
                phone_number=phone_number,
            )
            return {
                "success": True,
                "phone_number": phone_number,
                "status": "opted_out",
            }
        except Exception as exc:
            logger.error("Twilio process_opt_out error: %s", exc)
            return {"success": False, "error": str(exc)}


    async def process_opt_in(
        self,
        phone_number: str,
        messaging_service_sid: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Process a START (opt-in) request for a phone number."""
        client = await self._get_twilio(user_id)
        ms_sid = messaging_service_sid or getattr(settings, "TWILIO_MESSAGING_SERVICE_SID", None)

        if not ms_sid:
            return {"success": False, "error": "Messaging service SID required"}

        try:
            await asyncio.to_thread(
                client.messaging.v1.services(ms_sid).phone_numbers(phone_number).delete,
            )
            return {
                "success": True,
                "phone_number": phone_number,
                "status": "opted_in",
            }
        except Exception as exc:
            logger.error("Twilio process_opt_in error: %s", exc)
            return {"success": False, "error": str(exc)}


    # ── Voice (expanded) ──────────────────────────────────────────────────────

    async def create_conference(
        self,
        friendly_name: str,
        participants: list[str],
        user_id: UUID | None = None,
    ) -> dict:
        """Create a conference call and dial participants."""
        client = await self._get_twilio(user_id)
        from_number = settings.TWILIO_PHONE_NUMBER

        if not from_number:
            return {"success": False, "error": "No from number configured"}

        results = []
        for participant_number in participants:
            try:
                call = await asyncio.to_thread(
                    client.calls.create,
                    to=participant_number,
                    from_=from_number,
                    twiml=f'<Response><Dial><Conference>{friendly_name}</Conference></Dial></Response>',
                )
                results.append({
                    "participant": participant_number,
                    "call_sid": call.sid,
                    "status": call.status,
                })
            except Exception as exc:
                results.append({
                    "participant": participant_number,
                    "error": str(exc),
                })

        return {
            "success": True,
            "conference_name": friendly_name,
            "participants": results,
        }


    async def record_call(
        self, call_sid: str, user_id: UUID | None = None,
    ) -> dict:
        """Start recording an active call."""
        client = await self._get_twilio(user_id)

        try:
            recording = await asyncio.to_thread(
                client.calls(call_sid).recordings.create,
            )
            return {
                "success": True,
                "recording_sid": recording.sid,
                "call_sid": call_sid,
                "status": recording.status,
            }
        except Exception as exc:
            logger.error("Twilio record_call error: %s", exc)
            return {"success": False, "error": str(exc)}


    async def get_recording(
        self, recording_sid: str, user_id: UUID | None = None,
    ) -> dict:
        """Get recording details and URL."""
        client = await self._get_twilio(user_id)

        try:
            recording = await asyncio.to_thread(
                client.recordings(recording_sid).fetch,
            )
            return {
                "sid": recording.sid,
                "call_sid": recording.call_sid,
                "duration": recording.duration,
                "status": recording.status,
                "date_created": str(recording.date_created) if recording.date_created else None,
                "uri": recording.uri,
            }
        except Exception as exc:
            logger.error("Twilio get_recording error: %s", exc)
            return {"error": str(exc)}


    async def get_transcription(
        self, recording_sid: str, user_id: UUID | None = None,
    ) -> dict:
        """Get transcription for a recording."""
        client = await self._get_twilio(user_id)

        try:
            transcriptions = await asyncio.to_thread(
                client.recordings(recording_sid).transcriptions.list,
            )
            if not transcriptions:
                return {"recording_sid": recording_sid, "transcription": None}

            t = transcriptions[0]
            return {
                "recording_sid": recording_sid,
                "transcription_sid": t.sid,
                "status": t.status,
                "duration": t.duration,
                "date_created": str(t.date_created) if t.date_created else None,
            }
        except Exception as exc:
            logger.error("Twilio get_transcription error: %s", exc)
            return {"error": str(exc)}


    # ── Lookup (expanded) ─────────────────────────────────────────────────────

    async def get_line_type(
        self, phone_number: str, user_id: UUID | None = None,
    ) -> dict:
        """Get line type intelligence (mobile/landline/VoIP)."""
        client = await self._get_twilio(user_id)

        try:
            result = await asyncio.to_thread(
                client.lookups.v2.phone_numbers(phone_number).fetch,
                fields="line_type_intelligence",
            )
            line_info = result.line_type_intelligence or {}
            return {
                "phone_number": result.phone_number,
                "carrier_name": line_info.get("carrier_name"),
                "type": line_info.get("type"),
                "mobile_country_code": line_info.get("mobile_country_code"),
                "mobile_network_code": line_info.get("mobile_network_code"),
            }
        except Exception as exc:
            logger.error("Twilio get_line_type error: %s", exc)
            return {"phone_number": phone_number, "error": str(exc)}


    async def get_sim_swap(
        self, phone_number: str, user_id: UUID | None = None,
    ) -> dict:
        """SIM swap detection for fraud prevention."""
        client = await self._get_twilio(user_id)

        try:
            result = await asyncio.to_thread(
                client.lookups.v2.phone_numbers(phone_number).fetch,
                fields="sim_swap",
            )
            sim_swap = result.sim_swap or {}
            return {
                "phone_number": result.phone_number,
                "swapped_recently": sim_swap.get("swapped_recently"),
                "swapped_period": sim_swap.get("swapped_period"),
                "last_sim_swap": sim_swap.get("last_sim_swap", {}).get("last_sim_swap_date"),
            }
        except Exception as exc:
            logger.error("Twilio get_sim_swap error: %s", exc)
            return {"phone_number": phone_number, "error": str(exc)}


    async def get_caller_name(
        self, phone_number: str, user_id: UUID | None = None,
    ) -> dict:
        """CNAM lookup — get caller name for a phone number."""
        client = await self._get_twilio(user_id)

        try:
            result = await asyncio.to_thread(
                client.lookups.v2.phone_numbers(phone_number).fetch,
                fields="caller_name",
            )
            caller_name = result.caller_name or {}
            return {
                "phone_number": result.phone_number,
                "caller_name": caller_name.get("caller_name"),
                "caller_type": caller_name.get("caller_type"),
            }
        except Exception as exc:
            logger.error("Twilio get_caller_name error: %s", exc)
            return {"phone_number": phone_number, "error": str(exc)}


    # ── Conversations ─────────────────────────────────────────────────────────

    async def create_conversation(
        self, friendly_name: str, user_id: UUID | None = None,
    ) -> dict:
        """Create a multi-party conversation."""
        client = await self._get_twilio(user_id)

        try:
            conversation = await asyncio.to_thread(
                client.conversations.v1.conversations.create,
                friendly_name=friendly_name,
            )
            return {
                "sid": conversation.sid,
                "friendly_name": conversation.friendly_name,
                "state": conversation.state,
                "date_created": str(conversation.date_created) if conversation.date_created else None,
            }
        except Exception as exc:
            logger.error("Twilio create_conversation error: %s", exc)
            return {"error": str(exc)}


    async def add_participant(
        self,
        conversation_sid: str,
        identity_or_address: str,
        proxy_address: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Add a participant to a conversation."""
        client = await self._get_twilio(user_id)

        kwargs: dict = {}
        # Determine if it's a chat identity or SMS address
        if identity_or_address.startswith("+"):
            kwargs["messaging_binding_address"] = identity_or_address
            if proxy_address:
                kwargs["messaging_binding_proxy_address"] = proxy_address
            elif settings.TWILIO_PHONE_NUMBER:
                kwargs["messaging_binding_proxy_address"] = settings.TWILIO_PHONE_NUMBER
        else:
            kwargs["identity"] = identity_or_address

        try:
            participant = await asyncio.to_thread(
                client.conversations.v1.conversations(conversation_sid).participants.create,
                **kwargs,
            )
            return {
                "sid": participant.sid,
                "conversation_sid": conversation_sid,
                "identity": participant.identity,
            }
        except Exception as exc:
            logger.error("Twilio add_participant error: %s", exc)
            return {"error": str(exc)}


    async def send_conversation_message(
        self,
        conversation_sid: str,
        body: str,
        author: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Send a message in a conversation."""
        client = await self._get_twilio(user_id)

        kwargs: dict = {"body": body}
        if author:
            kwargs["author"] = author

        try:
            message = await asyncio.to_thread(
                client.conversations.v1.conversations(conversation_sid).messages.create,
                **kwargs,
            )
            return {
                "sid": message.sid,
                "conversation_sid": conversation_sid,
                "body": message.body,
                "author": message.author,
                "date_created": str(message.date_created) if message.date_created else None,
            }
        except Exception as exc:
            logger.error("Twilio send_conversation_message error: %s", exc)
            return {"error": str(exc)}


    # ── A2P Compliance ────────────────────────────────────────────────────────

    async def get_brand_registration_status(
        self, brand_sid: str, user_id: UUID | None = None,
    ) -> dict:
        """Check A2P brand registration status."""
        client = await self._get_twilio(user_id)

        try:
            brand = await asyncio.to_thread(
                client.messaging.v1.brand_registrations(brand_sid).fetch,
            )
            return {
                "sid": brand.sid,
                "status": brand.status,
                "brand_type": brand.brand_type,
                "a2p_profile_bundle_sid": brand.a2p_profile_bundle_sid,
                "date_created": str(brand.date_created) if brand.date_created else None,
                "date_updated": str(brand.date_updated) if brand.date_updated else None,
            }
        except Exception as exc:
            logger.error("Twilio get_brand_registration_status error: %s", exc)
            return {"brand_sid": brand_sid, "error": str(exc)}


    async def get_campaign_status(
        self, campaign_sid: str, user_id: UUID | None = None,
    ) -> dict:
        """Check A2P messaging campaign status."""
        client = await self._get_twilio(user_id)

        try:
            # Access via messaging service
            campaign = await asyncio.to_thread(
                client.messaging.v1.services.list,
                limit=1,
            )
            # Try direct US App-to-Person lookup
            us_app = await asyncio.to_thread(
                client.messaging.v1.brand_registrations.list,
                limit=10,
            )
            return {
                "campaign_sid": campaign_sid,
                "status": "check_console",
                "note": "Campaign status details are available in the Twilio Console",
            }
        except Exception as exc:
            logger.error("Twilio get_campaign_status error: %s", exc)
            return {"campaign_sid": campaign_sid, "error": str(exc)}


    async def get_toll_free_verification_status(
        self, phone_number: str, user_id: UUID | None = None,
    ) -> dict:
        """Check toll-free number verification status."""
        client = await self._get_twilio(user_id)

        try:
            # List toll-free verifications
            verifications = await asyncio.to_thread(
                client.messaging.v1.tollfree_verifications.list,
                tollfree_phone_number_sid=phone_number,
                limit=1,
            )
            if not verifications:
                return {
                    "phone_number": phone_number,
                    "status": "not_found",
                    "verified": False,
                }

            v = verifications[0]
            return {
                "phone_number": phone_number,
                "sid": v.sid,
                "status": v.status,
                "date_created": str(v.date_created) if v.date_created else None,
                "date_updated": str(v.date_updated) if v.date_updated else None,
            }
        except Exception as exc:
            logger.error("Twilio get_toll_free_verification_status error: %s", exc)
            return {"phone_number": phone_number, "error": str(exc)}

