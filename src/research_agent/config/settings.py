"""Environment-backed application settings."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the application."""

    app_name: str = "research-agent"
    environment: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://research_agent:research_agent@localhost:5432/research_agent"
    llm_provider: str = "stub"
    model_id: str = "local-development"
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None
    persistence_backend: Literal["memory", "postgres"] = "postgres"
    require_trusted_sources: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
