from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/fortressflow"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_database_url_scheme(cls, v: str) -> str:
        """Railway provides postgresql:// but we need postgresql+asyncpg://"""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    REDIS_URL: str = "redis://localhost:6379/0"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    SECRET_KEY: str = "change-in-production"
    UNSUBSCRIBE_HMAC_KEY: str = "change-in-production"
    DAILY_EMAIL_LIMIT: int = 100
    DAILY_SMS_LIMIT: int = 30
    DAILY_LINKEDIN_LIMIT: int = 25

    # HubSpot
    HUBSPOT_API_KEY: str = ""
    HUBSPOT_APP_ID: str = ""
    HUBSPOT_CLIENT_SECRET: str = ""  # Used for webhook signature validation

    # ZoomInfo
    ZOOMINFO_CLIENT_ID: str = ""
    ZOOMINFO_CLIENT_SECRET: str = ""
    ZOOMINFO_API_KEY: str = ""

    # Apollo
    APOLLO_API_KEY: str = ""

    # CORS
    CORS_ORIGINS: str = ""  # Comma-separated allowed origins for production

    # Sentry
    SENTRY_DSN: str = ""
    ENVIRONMENT: str = "development"

    # Enrichment
    ENRICHMENT_TTL_DAYS: int = 90
    ZOOMINFO_RATE_LIMIT: int = 25
    APOLLO_RATE_LIMIT: int = 50

    # Twilio SMS
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""

    # AWS SES
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    SES_FROM_EMAIL: str = ""

    # Sequence engine
    SEQUENCE_ENGINE_INTERVAL_MINUTES: int = 15

    # ── Phase 3: Deliverability Fortress ────────────────────────────────
    # Sending infrastructure
    SENDING_SUBDOMAIN: str = ""  # e.g. "mail.gengyveusa.com"
    DEDICATED_IP_POOL: str = ""  # SES dedicated IP pool name
    MAX_SENDING_IDENTITIES: int = 10  # Rotate 5-10 identities
    DAILY_WARMUP_VOLUME_CAP: int = 400  # 300-400 email touches/day target
    WARMUP_DURATION_WEEKS: int = 6  # 4-6 week warmup ramp

    # SES Configuration Set for tracking
    SES_CONFIGURATION_SET: str = "fortressflow-tracking"
    SES_FEEDBACK_FORWARDING_EMAIL: str = ""

    # Reputation thresholds
    BOUNCE_RATE_PAUSE_THRESHOLD: float = 0.05  # Pause at 5% bounce rate
    SPAM_RATE_PAUSE_THRESHOLD: float = 0.001  # Pause at 0.1% spam rate
    OPEN_RATE_MIN_THRESHOLD: float = 0.15  # Alert if open rate < 15%

    # HubSpot Breeze AI
    HUBSPOT_BREEZE_ENABLED: bool = False
    HUBSPOT_BREEZE_DATA_AGENT: bool = True  # Breeze Data Agent for insights
    HUBSPOT_BREEZE_PROSPECTING_AGENT: bool = True  # Breeze Prospecting Agent
    HUBSPOT_BREEZE_CONTENT_AGENT: bool = True  # Breeze Content Agent
    HUBSPOT_BREEZE_STUDIO_ENABLED: bool = True  # Breeze Studio

    # ZoomInfo Copilot
    ZOOMINFO_COPILOT_ENABLED: bool = False
    ZOOMINFO_GTM_WORKSPACE: bool = True  # GTM Workspace
    ZOOMINFO_CONTEXT_GRAPH: bool = True  # GTM Context Graph

    # Apollo AI (2026 agentic)
    APOLLO_AI_ENABLED: bool = False
    APOLLO_AI_SCORING: bool = True  # Enhanced AI scoring
    APOLLO_WATERFALL_ENRICHMENT: bool = True  # Waterfall enrichment
    APOLLO_MCP_INTEGRATION: bool = True  # MCP + Claude integration

    # Warmup AI tuning
    WARMUP_AI_SEED_BATCH_SIZE: int = 50  # Seeds per AI request
    WARMUP_AI_LEARNING_WINDOW_DAYS: int = 7  # Look-back window for learning loops
    WARMUP_RAMP_MULTIPLIER: float = 1.15  # Daily ramp multiplier (15% increase)
    WARMUP_INITIAL_DAILY_VOLUME: int = 5  # Start at 5 emails/day per identity

    # ── Phase 5: Reply Detection + Multi-Channel ─────────────────────────
    # IMAP settings for reply detection
    IMAP_HOST: str = ""
    IMAP_USER: str = ""
    IMAP_PASSWORD: str = ""
    IMAP_FOLDER: str = "INBOX"
    IMAP_POLL_INTERVAL_MINUTES: int = 5
    REPLY_WEBHOOK_SECRET: str = ""

    # LinkedIn OAuth/Proxy
    LINKEDIN_OAUTH_CLIENT_ID: str = ""
    LINKEDIN_OAUTH_CLIENT_SECRET: str = ""
    LINKEDIN_OAUTH_REDIRECT_URI: str = ""
    LINKEDIN_PROXY_ENDPOINT: str = ""  # Cloud automation proxy URL

    # Phantombuster (LinkedIn automation)
    PHANTOMBUSTER_API_KEY: str = ""
    PHANTOMBUSTER_CONNECT_AGENT_ID: str = ""
    PHANTOMBUSTER_MESSAGE_AGENT_ID: str = ""

    # Channel orchestrator
    GLOBAL_DAILY_EMAIL_LIMIT: int = 400  # 300-400 target
    GLOBAL_DAILY_SMS_LIMIT: int = 30
    GLOBAL_DAILY_LINKEDIN_LIMIT: int = 25
    MAX_TOUCH_RETRIES: int = 3
    RETRY_BACKOFF_MINUTES: int = 30

    # ── Phase 7: AI Chatbot Assistant ────────────────────────────────────
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"  # Fast + capable
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"  # Fallback — cheap + fast
    CHAT_MAX_TOKENS: int = 1024
    CHAT_RATE_LIMIT_PER_MINUTE: int = 30
    CHAT_HISTORY_RETENTION_DAYS: int = 90

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
