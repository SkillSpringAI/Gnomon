import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from research_agent.application.research_service import ResearchService
from research_agent.domain.research import ResearchBrief
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://research_agent:research_agent@localhost:5432/research_agent",
)


def test_postgres_task_round_trip() -> None:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - environment-dependent skip
        pytest.skip(f"PostgreSQL is unavailable: {exc}")

    brief = ResearchBrief(
        title=f"Persistence test {uuid4()}",
        objective="Verify that an open-ended task survives a database round trip.",
        questions=[{"question": "Can the task be retrieved after saving?"}],
    )
    with Session(engine) as session:
        repository = SqlAlchemyResearchTaskRepository(session)
        created = ResearchService(repository).create_task(brief)
        loaded = repository.get(created.id)

    assert loaded.id == created.id
    assert loaded.brief.title == brief.title
    assert len(loaded.cycles) == 1
