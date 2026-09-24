"""M1.4 recovery reconciliation verdicts are deterministic and read-only."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from research_agent.application.authority_bootstrap import (
    AuthorityBootstrapService,
    AuthorityStartupMode,
)
from research_agent.application.migrations import run_migrations
from research_agent.application.recovery_context_service import RecoveryContextService
from research_agent.application.recovery_reconciliation_service import (
    RecoveryReconciliationService,
)
from research_agent.domain.recovery import (
    CaptureRecoveryContext,
    ReconciliationCheck,
    ReconciliationOutcome,
    RecoveryOperationDisposition,
)
from research_agent.persistence.database import engine
from research_agent.persistence.models import (
    ReportGenerationAttemptRecord,
    ResearchCycleAttemptRecord,
    ResearchCycleRecord,
    ResearchEventRecord,
    ResearchTaskRecord,
)
from research_agent.persistence.recovery import RecoveryContextAuditRecord, RecoveryContextRecord


@pytest.fixture
def recovery_db():
    schema = "recovery_reconciliation_test_" + uuid4().hex
    with engine.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    isolated = create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        run_migrations(isolated)
        with Session(isolated) as session:
            AuthorityBootstrapService(session).initialize(AuthorityStartupMode.RECOVERY)
        yield isolated
    finally:
        isolated.dispose()
        with engine.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')


def command(service):
    return CaptureRecoveryContext(
        context_id=uuid4(),
        expected_basis=service.current_basis(),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def seed_unresolved(db):
    now = datetime.now(UTC)
    task_id, cycle_id = uuid4(), uuid4()
    provider_id, attempt_id = uuid4(), uuid4()
    event_id = uuid4()
    with Session(db) as session, session.begin():
        session.add(
            ResearchTaskRecord(
                id=task_id,
                title="Recovery reconciliation fixture",
                objective="Reconcile retained work",
                status="active",
                brief={},
                plan={},
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()
        session.add(
            ResearchCycleRecord(
                id=cycle_id,
                task_id=task_id,
                cycle_number=1,
                objectives=[],
                methods=[],
                status="active",
                created_at=now,
            )
        )
        session.flush()
        session.add(
            ResearchEventRecord(
                id=event_id,
                task_id=task_id,
                event_type="fixture",
                payload={},
                created_at=now,
            )
        )
        session.add(
            ReportGenerationAttemptRecord(
                operation_id=provider_id,
                task_id=task_id,
                status="UNKNOWN",
                started_at=now,
                expires_at=now + timedelta(hours=1),
            )
        )
        session.add(
            ResearchCycleAttemptRecord(
                id=attempt_id,
                task_id=task_id,
                cycle_id=cycle_id,
                status="RUNNING",
                stage="CREATED",
                started_at=now,
            )
        )
    return task_id, provider_id, attempt_id, event_id


def finish_operations(db, provider_id, attempt_id):
    with db.begin() as conn:
        conn.execute(
            text(
                "UPDATE report_generation_attempts "
                "SET status='SUCCEEDED', finished_at=:now "
                "WHERE operation_id=:id"
            ),
            {"id": provider_id, "now": datetime.now(UTC)},
        )
        conn.execute(
            text(
                "UPDATE research_cycle_attempts "
                "SET status='COMPLETED', finished_at=:now "
                "WHERE id=:id"
            ),
            {"id": attempt_id, "now": datetime.now(UTC)},
        )


def check_map(reconciliation):
    return {item.check: item.outcome for item in reconciliation.checks}


def recovery_counts(db):
    with Session(db) as session:
        return tuple(
            session.scalar(select(func.count()).select_from(model))
            for model in (RecoveryContextRecord, RecoveryContextAuditRecord)
        )


def test_reconciliation_passes_after_unknown_operations_become_terminal(recovery_db):
    _, provider_id, attempt_id, _ = seed_unresolved(recovery_db)
    context_service = RecoveryContextService(recovery_db)
    context = context_service.capture(command(context_service))
    finish_operations(recovery_db, provider_id, attempt_id)
    before = recovery_counts(recovery_db)

    reconciliation = RecoveryReconciliationService(recovery_db).reconcile(context.context_id)

    assert reconciliation.restoration_allowed is True
    assert check_map(reconciliation) == {
        check: ReconciliationOutcome.PASSED for check in ReconciliationCheck
    }
    assert {item.disposition for item in reconciliation.operations} == {
        RecoveryOperationDisposition.COMMITTED
    }
    assert recovery_counts(recovery_db) == before


def test_reconciliation_blocks_while_operations_remain_unknown(recovery_db):
    _, _, _, _ = seed_unresolved(recovery_db)
    context_service = RecoveryContextService(recovery_db)
    context = context_service.capture(command(context_service))

    reconciliation = RecoveryReconciliationService(recovery_db).reconcile(context.context_id)

    assert reconciliation.restoration_allowed is False
    assert check_map(reconciliation)[ReconciliationCheck.OPERATION_OUTCOMES] == (
        ReconciliationOutcome.UNKNOWN
    )
    assert {item.disposition for item in reconciliation.operations} == {
        RecoveryOperationDisposition.UNKNOWN
    }


def test_reconciliation_detects_evidence_added_after_context_capture(recovery_db):
    task_id, provider_id, attempt_id, _ = seed_unresolved(recovery_db)
    context_service = RecoveryContextService(recovery_db)
    context = context_service.capture(command(context_service))
    finish_operations(recovery_db, provider_id, attempt_id)
    with Session(recovery_db) as session, session.begin():
        session.add(
            ResearchEventRecord(
                id=uuid4(),
                task_id=task_id,
                event_type="later",
                payload={},
                created_at=datetime.now(UTC),
            )
        )

    reconciliation = RecoveryReconciliationService(recovery_db).reconcile(context.context_id)

    assert reconciliation.restoration_allowed is False
    assert check_map(reconciliation)[ReconciliationCheck.EVIDENCE_INTEGRITY] == (
        ReconciliationOutcome.FAILED
    )


def test_reconciliation_detects_missing_captured_history_without_repair(recovery_db):
    _, provider_id, attempt_id, event_id = seed_unresolved(recovery_db)
    context_service = RecoveryContextService(recovery_db)
    context = context_service.capture(command(context_service))
    finish_operations(recovery_db, provider_id, attempt_id)
    with recovery_db.begin() as conn:
        conn.execute(text("DELETE FROM research_events WHERE id=:id"), {"id": event_id})

    reconciliation = RecoveryReconciliationService(recovery_db).reconcile(context.context_id)

    assert reconciliation.restoration_allowed is False
    outcomes = check_map(reconciliation)
    assert outcomes[ReconciliationCheck.HISTORY_INTEGRITY] == ReconciliationOutcome.FAILED
    assert outcomes[ReconciliationCheck.EVIDENCE_INTEGRITY] == ReconciliationOutcome.FAILED


def test_reconciliation_reports_stale_authority_basis(recovery_db):
    _, provider_id, attempt_id, _ = seed_unresolved(recovery_db)
    context_service = RecoveryContextService(recovery_db)
    context = context_service.capture(command(context_service))
    finish_operations(recovery_db, provider_id, attempt_id)
    with recovery_db.begin() as conn:
        conn.execute(text("UPDATE security_state SET version=version+1"))

    reconciliation = RecoveryReconciliationService(recovery_db).reconcile(context.context_id)

    assert reconciliation.restoration_allowed is False
    assert check_map(reconciliation)[ReconciliationCheck.AUTHORITY_LINEAGE] == (
        ReconciliationOutcome.FAILED
    )
