"""SQLAlchemy engine and session configuration."""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from research_agent.config.settings import get_settings


def create_database_engine() -> Engine:
    """Create the SQLAlchemy engine from application settings."""
    return create_engine(get_settings().database_url, pool_pre_ping=True)


engine = create_database_engine()
SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    """Yield a database session for dependency injection."""
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()
