"""Operator-only database connection for migration and complete reconstruction."""

from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class OwnerDatabaseConfigurationError(RuntimeError):
    """The operator database credential is missing or malformed."""


class _OwnerDatabaseSettings(BaseSettings):
    owner_database_url: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


def create_owner_database_engine() -> Engine:
    """Build an ephemeral engine only inside an operator command."""
    try:
        configured = _OwnerDatabaseSettings().owner_database_url
        if configured is None:
            raise OwnerDatabaseConfigurationError(
                "OWNER_DATABASE_URL must name a PostgreSQL psycopg database"
            )
        raw_url = configured.get_secret_value()
        url = make_url(raw_url)
    except (ValidationError, ArgumentError, ValueError):
        raise OwnerDatabaseConfigurationError(
            "OWNER_DATABASE_URL must name a PostgreSQL psycopg database"
        ) from None
    if url.drivername != "postgresql+psycopg" or not url.database or not url.username:
        raise OwnerDatabaseConfigurationError(
            "OWNER_DATABASE_URL must name a PostgreSQL psycopg database"
        )
    try:
        return create_engine(url, pool_pre_ping=True)
    except (ArgumentError, ValueError):
        raise OwnerDatabaseConfigurationError(
            "OWNER_DATABASE_URL must name a PostgreSQL psycopg database"
        ) from None
