"""
Application configuration loaded from environment variables.

Uses pydantic-settings to read values from a `.env` file in the project root.
All fields are required — the app will fail to start if any are missing.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PG_DB: str  # PostgreSQL connection string
    GROQ_API_KEY: str  # API key for the Groq LLM service
    TELEGRAM_BOT_KEY: str  # Telegram Bot API token from @BotFather
    WEBHOOK_SECRET_TOKEN: (
        str  # Secret used to verify incoming Telegram webhook requests
    )
    BASE_URL: str  # Public URL prefix (e.g. https://yourdomain.com)
    API_SECRET_KEY: str  # Secret key for authenticating API requests (custom header)
    model_config = SettingsConfigDict(
        env_file=".env",
    )


# Singleton settings instance used throughout the app
settings = Settings()
