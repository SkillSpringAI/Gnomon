"""Populated pre-031 stopping rows retain their historical meaning on upgrade."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from test_stopping_decisions import _cleanup, _new_task, _request

from research_agent.api.app import create_app
from research_agent.application.migrations import migration_files
from research_agent.application.stopping_decision_service import (
    StoppingDecisionConflict,
    StoppingDecisionService,
)
from research_agent.domain.research import StoppingDecisionCreate
from research_agent.persistence.database import engine
from research_agent.persistence.models import StoppingDecisionChangeRecord, StoppingDecisionRecord


def test_populated_pre_031_stopping_upgrade_preserves_legacy_reads():
    with TestClient(create_app()) as client:
        task, ready = _new_task(client)
        body = _request(ready)
        try:
            response = client.post(f"/investigations/{task}/stopping-decision", json=body)
            assert response.status_code == 201
            schema = "stopping_upgrade_" + uuid4().hex
            with engine.connect() as connection:
                transaction = connection.begin()
                try:
                    origin = connection.scalar(text("SELECT current_schema()"))
                    quoted = connection.dialect.identifier_preparer.quote(origin)
                    connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
                    connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
                    files = migration_files()
                    for path in files:
                        if path.name < "031_":
                            connection.exec_driver_sql(path.read_text(encoding="utf-8"))
                    for table, key in (
                        ("research_tasks", "id"),
                        ("stopping_decisions", "task_id"),
                        ("stopping_decision_changes", "task_id"),
                    ):
                        connection.execute(
                            text(
                                f'INSERT INTO "{schema}".{table} '
                                f'SELECT (jsonb_populate_record(NULL::"{schema}".{table}, '
                                f"to_jsonb(original))).* FROM {quoted}.{table} original "
                                f"WHERE original.{key} = :task"
                            ),
                            {"task": task},
                        )
                    connection.exec_driver_sql(
                        "UPDATE stopping_decision_changes SET resulting_state = "
                        "resulting_state - 'objective_cycle_number'"
                    )
                    before = connection.scalar(
                        text("SELECT resulting_state FROM stopping_decision_changes")
                    )
                    for _ in range(2):
                        for path in files:
                            if path.name >= "031_":
                                connection.exec_driver_sql(path.read_text(encoding="utf-8"))
                        with Session(
                            bind=connection, join_transaction_mode="create_savepoint"
                        ) as session:
                            service = StoppingDecisionService(session)
                            record = session.scalar(select(StoppingDecisionRecord))
                            change = session.scalar(select(StoppingDecisionChangeRecord))
                            assert (
                                service._decision_from_record(record).objective_cycle_number is None
                            )
                            assert (
                                service._change_from_record(
                                    change
                                ).resulting_state.objective_cycle_number
                                is None
                            )
                            assert change.resulting_state == before
                            assert change.command_request is None
                            with pytest.raises(StoppingDecisionConflict):
                                service._retry_or_conflict(
                                    change, task, StoppingDecisionCreate.model_validate(body)
                                )
                finally:
                    transaction.rollback()
        finally:
            _cleanup(task)
