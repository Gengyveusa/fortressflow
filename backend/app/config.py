from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/fortressflow"
    REDIS_URL: str = "redis://localhost:6379/0"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    SECRET_KEY: str = "change-in-production"
    UNSUBSCRIBE_HMAC_KEY: str = "change-in-production"
    DAILY_EMAIL_LIMIT: int = 100
    DAILY_SMS_LIMIT: int = 30
    DAILY_LINKEDIN_LIMIT: int = 25
    HUBSPOT_API_KEY: str = ""
    HUBSPOT_APP_ID: str = ""
    ZOOMINFO_CLIENT_ID: str = ""
    ZOOMINFO_CLIENT_SECRET: str = ""
    ZOOMINFO_API_KEY: str = ""
    APOLLO_API_KEY: str = ""
    SENTRY_DSN: str = ""
    ENVIRONMENT: str = "development"
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

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
