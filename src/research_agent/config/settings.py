"""Environment-backed application settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the application."""

    app_name: str = "research-agent"
    environment: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://research_agent:research_agent@localhost:5432/research_agent"
    llm_provider: Literal["stub", "bedrock"] = "stub"
    model_id: str = "local-development"
    aws_region: str = "us-east-1"
    llm_timeout_seconds: int = Field(default=30, gt=0)
    llm_max_output_tokens: int = Field(default=3000, gt=0)
    llm_max_report_chars: int = Field(default=100_000, gt=0)
    llm_max_drafts_per_task: int = Field(default=20, ge=0)
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None
    provider_session_enabled: bool = False
    persistence_backend: Literal["memory", "postgres"] = "postgres"
    authority_startup_mode: Literal["fresh", "continuing", "recovery"] = "continuing"
    require_trusted_sources: bool = True

    @field_validator("llm_provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

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
