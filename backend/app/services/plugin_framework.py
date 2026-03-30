"""Plugin framework for extending FortressFlow with third-party integrations."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Callable, Optional, Protocol
from uuid import uuid4

logger = logging.getLogger(__name__)


class PluginType(str, Enum):
    AGENT = "agent"
    DATA_SOURCE = "data_source"
    VISUALIZATION = "visualization"
    WORKFLOW = "workflow"
    ANALYTICS = "analytics"
    INTEGRATION = "integration"


class PluginStatus(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    SUSPENDED = "suspended"


class PluginInterface(Protocol):
    """Protocol that all plugins must implement."""

    name: str
    version: str
    plugin_type: PluginType

    def initialize(self, config: dict) -> bool: ...
    def execute(self, action: str, params: dict) -> dict: ...
    def get_capabilities(self) -> list[str]: ...
    def shutdown(self) -> None: ...


@dataclass
class PluginManifest:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    version: str = "1.0.0"
    author: str = ""
    description: str = ""
    plugin_type: PluginType = PluginType.AGENT
    entry_point: str = ""  # module.path:ClassName
    required_permissions: list[str] = field(default_factory=list)
    config_schema: dict = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: PluginStatus = PluginStatus.DRAFT
    rating: float = 0.0
    install_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class PluginInstance:
    plugin_id: str
    user_id: str
    config: dict = field(default_factory=dict)
    enabled: bool = True
    installed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    instance: Optional[Any] = None


@dataclass
class ContextMessage:
    """Message for inter-plugin communication."""

    source_plugin: str
    target_plugin: Optional[str] = None  # None = broadcast
    action: str = ""
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class PluginRegistry:
    """Central registry and marketplace for plugins."""

    def __init__(self):
        self._manifests: dict[str, PluginManifest] = {}
        self._instances: dict[str, dict[str, PluginInstance]] = {}  # user_id -> {plugin_id -> instance}
        self._context_handlers: dict[str, list[Callable]] = {}  # action -> [handlers]
        self._seed_marketplace()

    def _seed_marketplace(self):
        """Seed with example plugins."""
        examples = [
            PluginManifest(
                name="Slack Notifier",
                author="FortressFlow",
                description="Send notifications to Slack channels on key events",
                plugin_type=PluginType.INTEGRATION,
                status=PluginStatus.PUBLISHED,
                rating=4.5,
                install_count=234,
            ),
            PluginManifest(
                name="Custom Dashboard Widgets",
                author="FortressFlow",
                description="Create custom visualization widgets for the super-dashboard",
                plugin_type=PluginType.VISUALIZATION,
                status=PluginStatus.PUBLISHED,
                rating=4.2,
                install_count=156,
            ),
            PluginManifest(
                name="Salesforce Sync",
                author="Community",
                description="Bi-directional sync with Salesforce CRM",
                plugin_type=PluginType.DATA_SOURCE,
                status=PluginStatus.PUBLISHED,
                rating=4.7,
                install_count=412,
            ),
            PluginManifest(
                name="AI Content Reviewer",
                author="Community",
                description="Automated content quality and compliance review",
                plugin_type=PluginType.WORKFLOW,
                status=PluginStatus.PUBLISHED,
                rating=4.0,
                install_count=89,
            ),
            PluginManifest(
                name="Predictive Lead Scoring",
                author="FortressFlow",
                description="ML-powered lead scoring with custom models",
                plugin_type=PluginType.ANALYTICS,
                status=PluginStatus.PUBLISHED,
                rating=4.8,
                install_count=567,
            ),
        ]
        for p in examples:
            self._manifests[p.id] = p

    def register_plugin(self, manifest: PluginManifest) -> PluginManifest:
        """Register a new plugin in the marketplace."""
        manifest.status = PluginStatus.REVIEW
        manifest.updated_at = datetime.now(UTC)
        self._manifests[manifest.id] = manifest
        logger.info("Plugin registered: %s v%s by %s", manifest.name, manifest.version, manifest.author)
        return manifest

    def get_marketplace(
        self, plugin_type: Optional[PluginType] = None, search: Optional[str] = None
    ) -> list[PluginManifest]:
        """Browse the plugin marketplace."""
        plugins = [p for p in self._manifests.values() if p.status == PluginStatus.PUBLISHED]
        if plugin_type:
            plugins = [p for p in plugins if p.plugin_type == plugin_type]
        if search:
            search_lower = search.lower()
            plugins = [p for p in plugins if search_lower in p.name.lower() or search_lower in p.description.lower()]
        return sorted(plugins, key=lambda p: -p.rating)

    def install_plugin(self, user_id: str, plugin_id: str, config: dict = None) -> Optional[PluginInstance]:
        """Install a plugin for a user."""
        manifest = self._manifests.get(plugin_id)
        if not manifest or manifest.status != PluginStatus.PUBLISHED:
            return None
        if user_id not in self._instances:
            self._instances[user_id] = {}
        instance = PluginInstance(plugin_id=plugin_id, user_id=user_id, config=config or {})
        self._instances[user_id][plugin_id] = instance
        manifest.install_count += 1
        logger.info("Plugin %s installed for user %s", manifest.name, user_id)
        return instance

    def uninstall_plugin(self, user_id: str, plugin_id: str) -> bool:
        """Remove a plugin installation."""
        if user_id in self._instances and plugin_id in self._instances[user_id]:
            inst = self._instances[user_id].pop(plugin_id)
            if inst.instance and hasattr(inst.instance, "shutdown"):
                inst.instance.shutdown()
            return True
        return False

    def get_user_plugins(self, user_id: str) -> list[dict]:
        """Get all installed plugins for a user."""
        if user_id not in self._instances:
            return []
        result = []
        for plugin_id, instance in self._instances[user_id].items():
            manifest = self._manifests.get(plugin_id)
            if manifest:
                result.append({"manifest": manifest, "instance": instance})
        return result

    def send_context(self, message: ContextMessage) -> list[dict]:
        """Send a context message to plugins (inter-plugin communication)."""
        responses = []
        handlers = self._context_handlers.get(message.action, [])
        for handler in handlers:
            try:
                result = handler(message)
                responses.append({"handler": str(handler), "result": result})
            except Exception as e:
                logger.error("Context handler failed: %s", e)
                responses.append({"handler": str(handler), "error": str(e)})
        return responses

    def register_context_handler(self, action: str, handler: Callable) -> None:
        """Register a handler for context messages."""
        if action not in self._context_handlers:
            self._context_handlers[action] = []
        self._context_handlers[action].append(handler)

    def get_marketplace_stats(self) -> dict:
        published = [p for p in self._manifests.values() if p.status == PluginStatus.PUBLISHED]
        return {
            "total_plugins": len(published),
            "total_installs": sum(p.install_count for p in published),
            "avg_rating": round(sum(p.rating for p in published) / len(published), 1) if published else 0,
            "by_type": {t.value: sum(1 for p in published if p.plugin_type == t) for t in PluginType},
        }
