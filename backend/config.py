from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PG_DB: str
    GROQ_API_KEY: str
    TELEGRAM_BOT_KEY: str
    WEBHOOK_SECRET_TOKEN: str
    TELEGRAM_WEBHOOK_URL: str
    model_config = SettingsConfigDict(
        env_file=".env",
    )


settings = Settings()
