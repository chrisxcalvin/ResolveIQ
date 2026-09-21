from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://resolveiq:resolveiq_dev_password@localhost:5432/resolveiq"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me-to-a-long-random-value"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    frontend_origin: str = "http://localhost:3000"

    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    # urgency_score below this uses the fine-tuned cheap-tier model; at or
    # above it, tickets are drafted by the strong-tier (Groq) model instead.
    cheap_tier_urgency_threshold: float = 0.5

    # Embeddings (app/kb/embeddings.py) — hosted via the Gemini API rather
    # than local sentence-transformers/torch. Not a quality choice: the
    # local model needed torch loaded in the Celery worker's memory, which
    # alone exceeded a 512MB deployment container even before the API
    # process shared it (see docs/checkpoints/phase-5.md). Free tier:
    # 1,500 requests/day, no payment method required.
    gemini_api_key: str | None = None
    gemini_embedding_model: str = "gemini-embedding-001"

    # Tracing (optional) — unset in a fresh env, tracing.py no-ops cleanly
    # when either key is missing rather than erroring or degrading requests.
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"


settings = Settings()
