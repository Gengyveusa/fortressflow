"""
Amazon SES infrastructure service.

Handles domain/identity verification, DKIM setup, configuration sets,
dedicated IP management, and reputation monitoring. This is the control-plane
companion to email_service.py (which handles actual send operations).

All methods are async-safe; boto3 calls run via asyncio.to_thread for non-blocking I/O.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


def _get_sesv2_client():
    """Lazy-load SES v2 client (used for identity/domain management)."""
    import boto3

    return boto3.client(
        "sesv2",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def _get_ses_client():
    """Lazy-load SES v1 client (used for some operations not yet in v2)."""
    import boto3

    return boto3.client(
        "ses",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


@dataclass
class DomainVerificationResult:
    success: bool
    domain: str
    dkim_tokens: list[str] = field(default_factory=list)
    verification_token: str | None = None
    error: str | None = None


@dataclass
class IdentityVerificationResult:
    success: bool
    email: str
    identity_arn: str | None = None
    error: str | None = None


@dataclass
class ReputationMetrics:
    bounce_rate: float = 0.0
    complaint_rate: float = 0.0
    delivery_rate: float = 0.0
    send_rate: float = 0.0
    reputation_dashboard_url: str | None = None


class SESInfrastructureService:
    """
    Manages SES infrastructure: domain verification, DKIM, dedicated IPs,
    configuration sets, and reputation monitoring.
    """

    def __init__(self) -> None:
        self._sesv2 = None
        self._ses = None

    @property
    def sesv2(self):
        if self._sesv2 is None:
            self._sesv2 = _get_sesv2_client()
        return self._sesv2

    @property
    def ses(self):
        if self._ses is None:
            self._ses = _get_ses_client()
        return self._ses

    # ── Domain Verification ────────────────────────────────────────────

    async def verify_domain(self, domain: str) -> DomainVerificationResult:
        """
        Create a domain identity in SES v2 with DKIM signing enabled.

        Returns DKIM CNAME tokens that must be added to DNS.
        """
        try:
            response = await asyncio.to_thread(
                self.sesv2.create_email_identity,
                EmailIdentity=domain,
                DkimSigningAttributes={
                    "DomainSigningSelector": "fortressflow",
                    "DomainSigningPrivateKey": "",  # Let SES generate keys (EasyDKIM)
                }
                if False  # Use EasyDKIM by default
                else {},
                Tags=[
                    {"Key": "app", "Value": "fortressflow"},
                    {"Key": "type", "Value": "sending-domain"},
                ],
            )

            dkim_attrs = response.get("DkimAttributes", {})
            tokens = dkim_attrs.get("Tokens", [])

            logger.info(
                "Domain %s created in SES. DKIM tokens: %s",
                domain,
                tokens,
            )

            return DomainVerificationResult(
                success=True,
                domain=domain,
                dkim_tokens=tokens,
            )

        except Exception as exc:
            error_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if error_code == "AlreadyExistsException":
                logger.info("Domain %s already exists in SES, fetching status", domain)
                return await self.get_domain_status(domain)

            logger.error("Failed to verify domain %s: %s", domain, exc)
            return DomainVerificationResult(success=False, domain=domain, error=str(exc))

    async def get_domain_status(self, domain: str) -> DomainVerificationResult:
        """Check current verification and DKIM status for a domain."""
        try:
            response = await asyncio.to_thread(
                self.sesv2.get_email_identity,
                EmailIdentity=domain,
            )

            dkim_attrs = response.get("DkimAttributes", {})
            tokens = dkim_attrs.get("Tokens", [])
            verified = response.get("VerifiedForSendingStatus", False)

            return DomainVerificationResult(
                success=verified,
                domain=domain,
                dkim_tokens=tokens,
            )
        except Exception as exc:
            logger.error("Failed to get domain status for %s: %s", domain, exc)
            return DomainVerificationResult(success=False, domain=domain, error=str(exc))

    # ── Email Identity Verification ────────────────────────────────────

    async def verify_email_identity(self, email: str) -> IdentityVerificationResult:
        """
        Create an email identity in SES v2.
        SES sends a verification email to the address.
        """
        try:
            response = await asyncio.to_thread(
                self.sesv2.create_email_identity,
                EmailIdentity=email,
                Tags=[
                    {"Key": "app", "Value": "fortressflow"},
                    {"Key": "type", "Value": "sending-inbox"},
                ],
            )

            arn = response.get("IdentityArn", "")
            logger.info("Email identity %s created in SES, ARN: %s", email, arn)

            return IdentityVerificationResult(
                success=True,
                email=email,
                identity_arn=arn,
            )

        except Exception as exc:
            error_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if error_code == "AlreadyExistsException":
                logger.info("Email identity %s already exists in SES", email)
                return IdentityVerificationResult(success=True, email=email)

            logger.error("Failed to verify email identity %s: %s", email, exc)
            return IdentityVerificationResult(success=False, email=email, error=str(exc))

    async def check_identity_verified(self, identity: str) -> bool:
        """Check if an identity (domain or email) is verified for sending."""
        try:
            response = await asyncio.to_thread(
                self.sesv2.get_email_identity,
                EmailIdentity=identity,
            )
            return response.get("VerifiedForSendingStatus", False)
        except Exception as exc:
            logger.error("Failed to check identity %s: %s", identity, exc)
            return False

    # ── Configuration Set ──────────────────────────────────────────────

    async def ensure_configuration_set(self) -> bool:
        """
        Create the FortressFlow tracking configuration set if it doesn't exist.
        Includes event destinations for bounces, complaints, deliveries, opens, clicks.
        """
        config_set_name = settings.SES_CONFIGURATION_SET
        if not config_set_name:
            return False

        try:
            await asyncio.to_thread(
                self.sesv2.create_configuration_set,
                ConfigurationSetName=config_set_name,
                TrackingOptions={"CustomRedirectDomain": ""},
                DeliveryOptions={
                    "SendingPoolName": settings.DEDICATED_IP_POOL or "",
                    "TlsPolicy": "REQUIRE",
                },
                ReputationOptions={
                    "ReputationMetricsEnabled": True,
                    "LastFreshStart": "",
                },
                SendingOptions={"SendingEnabled": True},
                Tags=[
                    {"Key": "app", "Value": "fortressflow"},
                ],
            )
            logger.info("Created SES configuration set: %s", config_set_name)
            return True

        except Exception as exc:
            error_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if error_code == "AlreadyExistsException":
                logger.info("Configuration set %s already exists", config_set_name)
                return True

            logger.error("Failed to create configuration set: %s", exc)
            return False

    # ── Dedicated IP Pool ──────────────────────────────────────────────

    async def create_dedicated_ip_pool(self, pool_name: str) -> bool:
        """Create a dedicated IP pool for sending."""
        try:
            await asyncio.to_thread(
                self.sesv2.create_dedicated_ip_pool,
                PoolName=pool_name,
                ScalingMode="MANAGED",  # AWS manages IP allocation
                Tags=[
                    {"Key": "app", "Value": "fortressflow"},
                ],
            )
            logger.info("Created dedicated IP pool: %s", pool_name)
            return True

        except Exception as exc:
            error_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if error_code == "AlreadyExistsException":
                logger.info("Dedicated IP pool %s already exists", pool_name)
                return True

            logger.error("Failed to create dedicated IP pool: %s", exc)
            return False

    async def list_dedicated_ips(self, pool_name: str | None = None) -> list[dict]:
        """List dedicated IPs, optionally filtered by pool."""
        try:
            kwargs: dict[str, Any] = {}
            if pool_name:
                kwargs["PoolName"] = pool_name

            response = await asyncio.to_thread(
                self.sesv2.get_dedicated_ips,
                **kwargs,
            )

            ips = response.get("DedicatedIps", [])
            return [
                {
                    "ip": ip.get("Ip"),
                    "warmup_status": ip.get("WarmupStatus"),
                    "warmup_percentage": ip.get("WarmupPercentage"),
                    "pool_name": ip.get("PoolName"),
                }
                for ip in ips
            ]

        except Exception as exc:
            logger.error("Failed to list dedicated IPs: %s", exc)
            return []

    # ── Reputation Monitoring ──────────────────────────────────────────

    async def get_account_reputation(self) -> ReputationMetrics:
        """Fetch SES account-level reputation metrics."""
        try:
            response = await asyncio.to_thread(self.sesv2.get_account)

            send_quota = response.get("SendQuota", {})
            reputation = ReputationMetrics(
                send_rate=send_quota.get("SendRate", 0.0),
            )

            # Get reputation dashboard metrics if available
            enforcement = response.get("EnforcementStatus", "")
            if enforcement != "HEALTHY":
                logger.warning("SES account enforcement status: %s", enforcement)

            return reputation

        except Exception as exc:
            logger.error("Failed to get account reputation: %s", exc)
            return ReputationMetrics()

    async def get_domain_reputation(self, domain: str) -> dict[str, Any]:
        """Get reputation metrics for a specific domain identity."""
        try:
            response = await asyncio.to_thread(
                self.sesv2.get_email_identity,
                EmailIdentity=domain,
            )

            dkim = response.get("DkimAttributes", {})
            return {
                "domain": domain,
                "verified": response.get("VerifiedForSendingStatus", False),
                "dkim_status": dkim.get("Status", "NOT_STARTED"),
                "dkim_signing_enabled": dkim.get("SigningEnabled", False),
                "mail_from_status": response.get("MailFromAttributes", {}).get("MailFromDomainStatus", ""),
            }

        except Exception as exc:
            logger.error("Failed to get domain reputation for %s: %s", domain, exc)
            return {"domain": domain, "error": str(exc)}

    # ── DMARC/BIMI Helpers ─────────────────────────────────────────────

    def generate_dmarc_record(
        self,
        policy: str = "quarantine",
        rua_email: str | None = None,
        ruf_email: str | None = None,
        pct: int = 100,
    ) -> str:
        """
        Generate a DMARC TXT record value.

        Args:
            policy: "none", "quarantine", or "reject"
            rua_email: Aggregate report destination
            ruf_email: Forensic report destination
            pct: Percentage of messages subject to filtering (1-100)
        """
        record = f"v=DMARC1; p={policy}; pct={pct}"
        if rua_email:
            record += f"; rua=mailto:{rua_email}"
        if ruf_email:
            record += f"; ruf=mailto:{ruf_email}"
        record += "; adkim=s; aspf=s"  # Strict alignment
        return record

    def generate_bimi_record(
        self,
        svg_url: str,
        vmc_url: str | None = None,
    ) -> str:
        """
        Generate a BIMI TXT record value.

        Args:
            svg_url: URL to SVG logo (must be Tiny PS format)
            vmc_url: URL to Verified Mark Certificate (optional but recommended)
        """
        record = f"v=BIMI1; l={svg_url}"
        if vmc_url:
            record += f"; a={vmc_url}"
        return record

    def generate_spf_record(self, include_ses: bool = True) -> str:
        """Generate an SPF TXT record value including SES."""
        parts = ["v=spf1"]
        if include_ses:
            parts.append("include:amazonses.com")
        parts.append("-all")
        return " ".join(parts)

    # ── DNS Setup Instructions ─────────────────────────────────────────

    async def get_dns_setup_instructions(self, domain: str) -> dict[str, Any]:
        """
        Generate complete DNS record setup instructions for a domain.
        Returns all required DNS records for SPF, DKIM, DMARC, and BIMI.
        """
        # Get DKIM tokens from SES
        domain_status = await self.get_domain_status(domain)
        dkim_tokens = domain_status.dkim_tokens

        instructions: dict[str, Any] = {
            "domain": domain,
            "records": [],
        }

        # SPF
        instructions["records"].append(
            {
                "type": "TXT",
                "name": domain,
                "value": self.generate_spf_record(),
                "purpose": "SPF - Authorize SES to send on behalf of this domain",
            }
        )

        # DKIM CNAMEs
        for token in dkim_tokens:
            instructions["records"].append(
                {
                    "type": "CNAME",
                    "name": f"{token}._domainkey.{domain}",
                    "value": f"{token}.dkim.amazonses.com",
                    "purpose": f"DKIM - Signing key #{dkim_tokens.index(token) + 1}",
                }
            )

        # DMARC
        instructions["records"].append(
            {
                "type": "TXT",
                "name": f"_dmarc.{domain}",
                "value": self.generate_dmarc_record(
                    policy="quarantine",
                    rua_email=settings.SES_FEEDBACK_FORWARDING_EMAIL or f"dmarc@{domain}",
                ),
                "purpose": "DMARC - Policy for unauthenticated messages",
            }
        )

        # BIMI (placeholder)
        instructions["records"].append(
            {
                "type": "TXT",
                "name": f"default._bimi.{domain}",
                "value": "v=BIMI1; l=https://gengyveusa.com/assets/bimi-logo.svg",
                "purpose": "BIMI - Brand logo in email clients (requires SVG Tiny PS logo)",
            }
        )

        # Custom MAIL FROM
        instructions["records"].append(
            {
                "type": "MX",
                "name": f"mail.{domain}",
                "value": f"10 feedback-smtp.{settings.AWS_REGION}.amazonses.com",
                "purpose": "Custom MAIL FROM - Bounce handling via SES",
            }
        )
        instructions["records"].append(
            {
                "type": "TXT",
                "name": f"mail.{domain}",
                "value": self.generate_spf_record(),
                "purpose": "Custom MAIL FROM SPF - Authorize SES for return-path",
            }
        )

        return instructions

    # ── Suppression List ───────────────────────────────────────────────

    async def add_to_suppression_list(self, email: str, reason: str = "COMPLAINT") -> bool:
        """Add an email to the SES account-level suppression list."""
        try:
            await asyncio.to_thread(
                self.sesv2.put_suppressed_destination,
                EmailAddress=email,
                Reason=reason,  # "BOUNCE" or "COMPLAINT"
            )
            logger.info("Added %s to SES suppression list (%s)", email, reason)
            return True
        except Exception as exc:
            logger.error("Failed to add %s to suppression list: %s", email, exc)
            return False

    async def check_suppression_list(self, email: str) -> dict | None:
        """Check if an email is on the SES suppression list."""
        try:
            response = await asyncio.to_thread(
                self.sesv2.get_suppressed_destination,
                EmailAddress=email,
            )
            dest = response.get("SuppressedDestination", {})
            return {
                "email": dest.get("EmailAddress"),
                "reason": dest.get("Reason"),
                "created_at": str(dest.get("CreatedTimestamp", "")),
            }
        except Exception as exc:
            # Not found = not suppressed
            error_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if error_code == "NotFoundException":
                return None
            logger.error("Failed to check suppression for %s: %s", email, exc)
            return None
