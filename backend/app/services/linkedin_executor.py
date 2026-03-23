"""
LinkedIn Execution Layer — Phantombuster API integration.

Provides an abstraction for executing LinkedIn automation actions:
- PhantombusterExecutor: Real execution via Phantombuster pre-configured phantoms
- ManualExecutor: Fallback that marks items for CSV export
- Factory function get_executor() that selects based on configuration
"""

import abc
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_PHANTOMBUSTER_API_BASE = "https://api.phantombuster.com/api/v2"


class ExecutionStatus(str, Enum):
    success = "success"
    failed = "failed"
    rate_limited = "rate_limited"
    manual = "manual"


@dataclass
class ExecutionResult:
    """Result of a LinkedIn action execution."""

    status: ExecutionStatus
    message: str
    container_id: str | None = None
    executed_at: datetime | None = None
    raw_response: dict | None = None


class LinkedInExecutor(abc.ABC):
    """Abstract base class for LinkedIn action execution."""

    @abc.abstractmethod
    async def send_connection_request(
        self, profile_url: str, note: str
    ) -> ExecutionResult:
        """Send a LinkedIn connection request."""

    @abc.abstractmethod
    async def send_message(
        self, profile_url: str, message: str
    ) -> ExecutionResult:
        """Send a LinkedIn direct message to an existing connection."""

    @abc.abstractmethod
    async def view_profile(self, profile_url: str) -> ExecutionResult:
        """View a LinkedIn profile (warming action)."""

    @abc.abstractmethod
    def is_automated(self) -> bool:
        """Return True if this executor performs real automation."""


class PhantombusterExecutor(LinkedInExecutor):
    """
    Execute LinkedIn actions via Phantombuster pre-configured phantoms.

    Requires environment variables:
    - PHANTOMBUSTER_API_KEY
    - PHANTOMBUSTER_CONNECT_AGENT_ID (phantom for connection requests)
    - PHANTOMBUSTER_MESSAGE_AGENT_ID (phantom for messages)
    """

    def __init__(self) -> None:
        self._api_key = settings.PHANTOMBUSTER_API_KEY
        self._connect_agent_id = settings.PHANTOMBUSTER_CONNECT_AGENT_ID
        self._message_agent_id = settings.PHANTOMBUSTER_MESSAGE_AGENT_ID
        self._client = httpx.AsyncClient(
            base_url=_PHANTOMBUSTER_API_BASE,
            headers={
                "X-Phantombuster-Key": self._api_key,
                "Content-Type": "application/json",
            },
            timeout=30,
        )

    async def send_connection_request(
        self, profile_url: str, note: str
    ) -> ExecutionResult:
        if not self._connect_agent_id:
            return ExecutionResult(
                status=ExecutionStatus.failed,
                message="PHANTOMBUSTER_CONNECT_AGENT_ID not configured",
            )
        return await self._launch_agent(
            self._connect_agent_id,
            {"profileUrl": profile_url, "message": note},
        )

    async def send_message(
        self, profile_url: str, message: str
    ) -> ExecutionResult:
        if not self._message_agent_id:
            return ExecutionResult(
                status=ExecutionStatus.failed,
                message="PHANTOMBUSTER_MESSAGE_AGENT_ID not configured",
            )
        return await self._launch_agent(
            self._message_agent_id,
            {"profileUrl": profile_url, "message": message},
        )

    async def view_profile(self, profile_url: str) -> ExecutionResult:
        # Profile viewing uses the connect agent with view-only argument
        agent_id = self._connect_agent_id or self._message_agent_id
        if not agent_id:
            return ExecutionResult(
                status=ExecutionStatus.failed,
                message="No Phantombuster agent configured for profile viewing",
            )
        return await self._launch_agent(
            agent_id,
            {"profileUrl": profile_url, "onlyView": True},
        )

    def is_automated(self) -> bool:
        return True

    async def _launch_agent(
        self, agent_id: str, argument: dict
    ) -> ExecutionResult:
        """Launch a Phantombuster agent with the given argument payload."""
        try:
            resp = await self._client.post(
                "/agents/launch",
                json={"id": agent_id, "argument": argument},
            )

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After", "60")
                logger.warning(
                    "Phantombuster rate limited, retry after %ss", retry_after
                )
                return ExecutionResult(
                    status=ExecutionStatus.rate_limited,
                    message=f"Phantombuster rate limited. Retry after {retry_after}s.",
                )

            resp.raise_for_status()
            data = resp.json()
            container_id = data.get("containerId", "")

            logger.info(
                "Phantombuster agent %s launched, container %s",
                agent_id,
                container_id,
            )

            return ExecutionResult(
                status=ExecutionStatus.success,
                message="Agent launched successfully",
                container_id=container_id,
                executed_at=datetime.now(UTC),
                raw_response=data,
            )

        except httpx.HTTPStatusError as exc:
            logger.error(
                "Phantombuster HTTP error for agent %s: %s", agent_id, exc
            )
            return ExecutionResult(
                status=ExecutionStatus.failed,
                message=f"Phantombuster HTTP {exc.response.status_code}",
            )
        except Exception as exc:
            logger.error(
                "Phantombuster execution error for agent %s: %s", agent_id, exc
            )
            return ExecutionResult(
                status=ExecutionStatus.failed,
                message=str(exc),
            )


class ManualExecutor(LinkedInExecutor):
    """
    Fallback executor — marks items for CSV export when no automation is configured.

    No real LinkedIn actions are performed. Items are flagged for manual execution
    via browser extension tools (Expandi, Dux-Soup, etc.).
    """

    async def send_connection_request(
        self, profile_url: str, note: str
    ) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.manual,
            message="Queued for CSV export — no automation configured",
        )

    async def send_message(
        self, profile_url: str, message: str
    ) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.manual,
            message="Queued for CSV export — no automation configured",
        )

    async def view_profile(self, profile_url: str) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.manual,
            message="Queued for CSV export — no automation configured",
        )

    def is_automated(self) -> bool:
        return False


def get_executor() -> LinkedInExecutor:
    """
    Factory: return PhantombusterExecutor if credentials are configured,
    otherwise fall back to ManualExecutor.
    """
    api_key = getattr(settings, "PHANTOMBUSTER_API_KEY", "")
    connect_id = getattr(settings, "PHANTOMBUSTER_CONNECT_AGENT_ID", "")
    message_id = getattr(settings, "PHANTOMBUSTER_MESSAGE_AGENT_ID", "")

    if api_key and (connect_id or message_id):
        logger.info("LinkedIn executor: Phantombuster (automated)")
        return PhantombusterExecutor()

    logger.info("LinkedIn executor: Manual (CSV export fallback)")
    return ManualExecutor()
