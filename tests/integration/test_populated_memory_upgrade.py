"""Verify populated claim and assessment data survives the 007 upgrade path."""

import hashlib
import json
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from research_agent.application.migrations import migration_files
from research_agent.persistence.database import engine
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository


def test_populated_claim_and_assessment_upgrade_is_preserved() -> None:
    schema = "memory_upgrade_" + uuid4().hex
    task_id = uuid4()
    hypothesis_id = uuid4()
    source_id = uuid4()
    claim_id = uuid4()
    assessment_id = uuid4()
    content = "Legacy source content retained through upgrade."

    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}", public')
            files = migration_files()
            upgrade = next(path for path in files if path.name == "007_memory_governance.sql")
            for path in files:
                if path.name < upgrade.name:
                    connection.exec_driver_sql(path.read_text(encoding="utf-8"))

            connection.execute(
                text(
                    """
                    INSERT INTO research_tasks
                        (id, title, objective, status, brief, plan, created_at, updated_at)
                    VALUES (:task, 'Legacy memory', 'Preserve governed records.', 'active',
                        CAST(:brief AS jsonb), CAST(:plan AS jsonb), now(), now())
                    """
                ),
                {
                    "task": task_id,
                    "brief": json.dumps(
                        {
                            "title": "Legacy memory",
                            "objective": "Preserve governed records.",
                            "hypotheses": [
                                {
                                    "id": str(hypothesis_id),
                                    "label": "H1",
                                    "statement": "The retained record is readable.",
                                }
                            ],
                            "questions": [],
                            "case_studies": [],
                            "methods": [],
                            "evidence_requirements": [],
                            "stopping_criteria": [],
                        }
                    ),
                    "plan": json.dumps(
                        {
                            "summary": "Legacy plan",
                            "first_cycle_objectives": ["Read retained records."],
                            "proposed_methods": [],
                            "open_questions": [],
                        }
                    ),
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO research_sources
                        (id, task_id, source_type, title, uri, content, content_hash,
                         reliability_score, observed_at, metadata)
                    VALUES (:source, :task, 'document', 'Legacy source',
                        'https://example.test/legacy', :content, :content_hash,
                        0.7, now(), '{}'::jsonb)
                    """
                ),
                {
                    "source": source_id,
                    "task": task_id,
                    "content": content,
                    "content_hash": hashlib.sha256(content.encode()).hexdigest(),
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO research_claims
                        (id, task_id, statement, confidence, status, created_at, updated_at)
                    VALUES (:claim, :task, 'The legacy claim remains readable.', 0.6,
                        'unverified', now(), now())
                    """
                ),
                {"claim": claim_id, "task": task_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO claim_sources
                        (claim_id, source_id, support_type, strength)
                    VALUES (:claim, :source, 'supporting', 0.8)
                    """
                ),
                {"claim": claim_id, "source": source_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO hypothesis_assessments
                        (id, task_id, hypothesis_id, status, summary, confidence, updated_at)
                    VALUES (:assessment, :task, :hypothesis, 'supported',
                        'Legacy assessment remains readable.', 0.6, now())
                    """
                ),
                {
                    "assessment": assessment_id,
                    "task": task_id,
                    "hypothesis": hypothesis_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO assessment_evidence
                        (assessment_id, claim_id, relation, strength)
                    VALUES (:assessment, :claim, 'supporting', 0.8)
                    """
                ),
                {"assessment": assessment_id, "claim": claim_id},
            )

            before = connection.execute(
                text(
                    """
                    SELECT
                        (SELECT to_jsonb(s) FROM research_sources s WHERE s.id = :source),
                        (SELECT to_jsonb(c) FROM research_claims c WHERE c.id = :claim),
                        (SELECT to_jsonb(a) FROM hypothesis_assessments a WHERE a.id = :assessment)
                    """
                ),
                {"source": source_id, "claim": claim_id, "assessment": assessment_id},
            ).one()

            for path in files:
                if path.name >= upgrade.name:
                    connection.exec_driver_sql(path.read_text(encoding="utf-8"))

            after = connection.execute(
                text(
                    """
                    SELECT
                        (SELECT to_jsonb(s) - 'version' - 'lifecycle'
                         FROM research_sources s WHERE s.id = :source),
                        (SELECT to_jsonb(c) - 'version' - 'lifecycle'
                         FROM research_claims c WHERE c.id = :claim),
                        (SELECT to_jsonb(a) - 'version' - 'lifecycle'
                         FROM hypothesis_assessments a WHERE a.id = :assessment)
                    """
                ),
                {"source": source_id, "claim": claim_id, "assessment": assessment_id},
            ).one()
            assert after == before

            with Session(bind=connection) as session:
                task = SqlAlchemyResearchTaskRepository(session).get(task_id)
                assert task.brief.hypotheses[0].id == hypothesis_id
                assert len(task.cycles) == 0
                claim = session.execute(
                    text("SELECT statement, confidence, status, version, lifecycle "
                         "FROM research_claims WHERE id = :claim"),
                    {"claim": claim_id},
                ).one()
                assessment = session.execute(
                    text("SELECT status, summary, confidence, version, lifecycle "
                         "FROM hypothesis_assessments WHERE id = :assessment"),
                    {"assessment": assessment_id},
                ).one()
                assert claim == (
                    "The legacy claim remains readable.", 0.6, "unverified", 1, "active"
                )
                assert assessment == (
                    "supported", "Legacy assessment remains readable.", 0.6, 1, "active"
                )
        finally:
            transaction.rollback()
