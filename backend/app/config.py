from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables / .env file."""

    # Neon Serverless PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/finance_db?ssl=require"

    # Local Ollama LLM for entity normalization
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "phi4-mini:latest"

    # Ollama request timeout (seconds) — fallback to regex if exceeded
    OLLAMA_TIMEOUT: float = 10.0

    # kimi-k2.6 Cloud LLM (Phase 3 — Diagnostic Agent & Copilot)
    # OpenAI-compatible API. Leave KIMI_API_KEY empty to use heuristic fallback.
    KIMI_API_KEY: str = ""
    KIMI_BASE_URL: str = "https://api.moonshot.cn/v1"
    KIMI_MODEL: str = "kimi-k2-0711-preview"
    KIMI_TIMEOUT: float = 30.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
