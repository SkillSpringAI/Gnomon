"""Real PostgreSQL recovery snapshots, atomicity and concurrency in isolated schemas."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from research_agent.application.authority_bootstrap import (
    AuthorityBootstrapService,
    AuthorityStartupMode,
)
from research_agent.application.migrations import migration_files, run_migrations
from research_agent.application.recovery_context_service import (
    RecoveryContextConflict,
    RecoveryContextService,
    RecoveryContextUnavailable,
)
from research_agent.application.recovery_reconciliation_service import RecoveryReconciliationService
from research_agent.application.recovery_restoration_service import RecoveryRestorationService
from research_agent.application.security_capability import SecurityCapabilityDenied
from research_agent.domain.recovery import CaptureRecoveryContext
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
def recovery_db(request):
    schema = "recovery_context_test_" + uuid4().hex
    with engine.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    isolated = create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        if getattr(request, "param", None) == "pre033":
            with isolated.begin() as conn:
                for path in migration_files():
                    if path.name.startswith("033_"):
                        break
                    conn.exec_driver_sql(path.read_text(encoding="utf-8"))
                readiness = next(path for path in migration_files() if path.name.startswith("035_"))
                conn.exec_driver_sql(readiness.read_text(encoding="utf-8"))
        else:
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


def seed(db, count=1):
    now = datetime.now(UTC)
    task_id, cycle_id = uuid4(), uuid4()
    with Session(db) as session, session.begin():
        session.add(
            ResearchTaskRecord(
                id=task_id,
                title="Recovery fixture",
                objective="Retain evidence",
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
        for _ in range(count):
            session.add(
                ResearchEventRecord(
                    id=uuid4(),
                    task_id=task_id,
                    event_type="fixture",
                    payload={},
                    created_at=now,
                )
            )
            session.add(
                ReportGenerationAttemptRecord(
                    operation_id=uuid4(),
                    task_id=task_id,
                    status="UNKNOWN",
                    started_at=now,
                    expires_at=now + timedelta(hours=1),
                )
            )
        session.add(
            ResearchCycleAttemptRecord(
                id=uuid4(),
                task_id=task_id,
                cycle_id=cycle_id,
                status="RUNNING",
                stage="CREATED",
                started_at=now,
            )
        )
    return task_id


def counts(db):
    with Session(db) as session:
        return tuple(
            session.scalar(select(func.count()).select_from(model))
            for model in (
                RecoveryContextRecord,
                RecoveryContextAuditRecord,
            )
        )


def test_capture_replay_restart_incident_and_no_authority_change(recovery_db):
    seed(recovery_db)
    service = RecoveryContextService(recovery_db)
    request = command(service)
    context = service.capture(request)
    assert context.inventory_status == "complete"
    assert len(context.evidence_basis) == 1
    assert len(context.unresolved_operations) == 2
    assert all(item.outcome == "unknown" for item in context.unresolved_operations)
    assert service.capture(request) == context
    assert (
        RecoveryContextService(recovery_db).read(context.context_id, require_current=True)
        == context
    )
    assert counts(recovery_db) == (1, 1)
    assert service.current_basis() == request.expected_basis
    second = service.capture(command(service))
    assert second.context_id != context.context_id and second.incident_id == context.incident_id
    with pytest.raises(RecoveryContextConflict, match="different request"):
        service.capture(
            request.model_copy(update={"expires_at": request.expires_at + timedelta(seconds=1)})
        )
    assert counts(recovery_db) == (2, 2)
    with recovery_db.connect() as conn:
        assert conn.scalar(text("SELECT status FROM report_generation_attempts")) == "UNKNOWN"
        assert conn.scalar(text("SELECT status FROM research_cycle_attempts")) == "RUNNING"


def test_overflow_remains_partial_and_does_not_drop_persisted_work(recovery_db):
    seed(recovery_db, 101)
    service = RecoveryContextService(recovery_db)
    context = service.capture(command(service))
    assert context.inventory_status == "partial"
    assert len(context.evidence_basis) == len(context.unresolved_operations) == 100
    with recovery_db.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM report_generation_attempts")) == 101
        assert conn.scalar(text("SELECT count(*) FROM research_events")) == 101


def test_stale_basis_expiry_and_historical_replay(recovery_db, monkeypatch):
    from research_agent.application import recovery_context_service as module

    service = RecoveryContextService(recovery_db)
    request = command(service)
    context = service.capture(request)
    with recovery_db.begin() as conn:
        conn.execute(text("UPDATE security_state SET version=version+1"))
    with pytest.raises(RecoveryContextConflict, match="stale"):
        service.capture(request.model_copy(update={"context_id": uuid4()}))
    with pytest.raises(RecoveryContextConflict, match="stale"):
        service.read(context.context_id, require_current=True)
    assert service.read(context.context_id) == service.capture(request) == context
    fresh_request = command(service)
    fresh = service.capture(fresh_request)

    class ExpiredClock:
        @staticmethod
        def now(tz):
            return fresh.expires_at

    monkeypatch.setattr(module, "datetime", ExpiredClock)
    with pytest.raises(RecoveryContextConflict, match="expired"):
        service.read(fresh.context_id, require_current=True)
    with pytest.raises(RecoveryContextConflict, match="expiry"):
        service.capture(fresh_request.model_copy(update={"context_id": uuid4()}))
    assert service.capture(fresh_request) == fresh
    assert counts(recovery_db) == (2, 2)


def test_audit_failure_rolls_back_and_denied_replay_stays_denied(recovery_db, monkeypatch):
    from research_agent.application import recovery_context_service as module

    service = RecoveryContextService(recovery_db)
    request = command(service)
    original = service._record_audit

    def fail(*args):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr(service, "_record_audit", fail)
    with pytest.raises(RuntimeError, match="Audit unavailable"):
        service.capture(request)
    assert counts(recovery_db) == (0, 0)
    monkeypatch.setattr(service, "_record_audit", original)
    service.capture(request)

    def deny(*args):
        raise SecurityCapabilityDenied("Denied")

    monkeypatch.setattr(module, "require_capability", deny)
    with pytest.raises(SecurityCapabilityDenied):
        service.capture(request)
    with pytest.raises(SecurityCapabilityDenied):
        service.read(request.context_id)
    assert counts(recovery_db) == (1, 1)


def test_malformed_history_is_rejected_without_repair(recovery_db):
    service = RecoveryContextService(recovery_db)
    request = command(service)
    service.capture(request)
    with recovery_db.begin() as conn:
        conn.execute(text("UPDATE recovery_contexts SET incident_id=:id"), {"id": uuid4()})
    with pytest.raises(RecoveryContextUnavailable, match="invalid"):
        service.read(request.context_id)
    with pytest.raises(RecoveryContextUnavailable, match="invalid"):
        service.capture(request)
    assert counts(recovery_db) == (1, 1)


def test_snapshot_excludes_commits_after_basis_read(recovery_db, monkeypatch):
    task_id = seed(recovery_db)
    service = RecoveryContextService(recovery_db)
    original = service._inventory

    def interleave(session):
        with Session(recovery_db) as writer, writer.begin():
            writer.add(
                ResearchEventRecord(
                    id=uuid4(),
                    task_id=task_id,
                    event_type="later",
                    payload={},
                    created_at=datetime.now(UTC),
                )
            )
        return original(session)

    monkeypatch.setattr(service, "_inventory", interleave)
    context = service.capture(command(service))
    assert len(context.evidence_basis) == 1
    monkeypatch.setattr(service, "_inventory", original)
    assert len(service.capture(command(service)).evidence_basis) == 2


def test_authority_lock_is_held_until_capture_commit(recovery_db, monkeypatch):
    service = RecoveryContextService(recovery_db)
    request = command(service)
    locked, release = Event(), Event()
    original = service._inventory

    def pause(session):
        locked.set()
        assert release.wait(10)
        return original(session)

    monkeypatch.setattr(service, "_inventory", pause)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(service.capture, request)
        try:
            assert locked.wait(10)
            with pytest.raises(DBAPIError) as error, recovery_db.begin() as conn:
                conn.execute(text("SET LOCAL lock_timeout='200ms'"))
                conn.execute(text("UPDATE security_state SET version=version+1"))
            assert error.value.orig.sqlstate == "55P03"
        finally:
            release.set()
        assert future.result(timeout=10).authority_basis == request.expected_basis
    assert counts(recovery_db) == (1, 1)


def test_concurrent_duplicate_capture_has_one_record_and_retry_converges(recovery_db, monkeypatch):
    service = RecoveryContextService(recovery_db)
    request = command(service)
    barrier = Barrier(2)
    original = service._inventory

    def simultaneous(session):
        barrier.wait(timeout=10)
        return original(session)

    monkeypatch.setattr(service, "_inventory", simultaneous)
    with ThreadPoolExecutor() as pool:
        futures = [pool.submit(service.capture, request) for _ in range(2)]
        results = []
        for future in futures:
            try:
                results.append(future.result(timeout=15))
            except RecoveryContextConflict:
                pass
    assert len(results) == 1
    assert counts(recovery_db) == (1, 1)
    assert service.capture(request) == results[0]


def test_upgrade_rerun_preserves_authority_and_context_history(recovery_db):
    service = RecoveryContextService(recovery_db)
    request = command(service)
    context = service.capture(request)
    upgrade = next(path for path in migration_files() if path.name.startswith("033_"))
    with recovery_db.begin() as conn:
        before = conn.scalar(text("SELECT to_jsonb(s) FROM security_state s"))
        conn.exec_driver_sql(upgrade.read_text(encoding="utf-8"))
        assert conn.scalar(text("SELECT to_jsonb(s) FROM security_state s")) == before
    assert run_migrations(recovery_db) == []
    assert service.read(request.context_id) == context


@pytest.mark.parametrize("recovery_db", ["pre033"], indirect=True)
def test_populated_upgrade_preserves_unknown_attempts_and_authority(recovery_db):
    seed(recovery_db)
    upgrade = next(path for path in migration_files() if path.name.startswith("033_"))
    with recovery_db.begin() as conn:
        tables = (
            "security_state",
            "research_events",
            "report_generation_attempts",
            "research_cycle_attempts",
        )
        before = {
            table: conn.execute(text(f"SELECT to_jsonb(r) FROM {table} r")).scalars().all()
            for table in tables
        }
        conn.exec_driver_sql(upgrade.read_text(encoding="utf-8"))
        conn.exec_driver_sql(upgrade.read_text(encoding="utf-8"))
        after = {
            table: conn.execute(text(f"SELECT to_jsonb(r) FROM {table} r")).scalars().all()
            for table in tables
        }
        assert before == after
        later = next(path for path in migration_files() if path.name.startswith("034_"))
        conn.exec_driver_sql(later.read_text(encoding="utf-8"))
    service = RecoveryContextService(recovery_db)
    context = service.capture(command(service))
    assert len(context.unresolved_operations) == 2
    assert counts(recovery_db) == (1, 1)


def test_no_capture_outside_bootstrap_and_epoch_change_rejects_old_basis(recovery_db):
    service = RecoveryContextService(recovery_db)
    request = command(service)
    with recovery_db.begin() as conn:
        conn.execute(
            text("UPDATE security_state SET authority_epoch_id=:epoch"), {"epoch": uuid4()}
        )
    with pytest.raises(RecoveryContextConflict, match="stale"):
        service.capture(request)
    with recovery_db.begin() as conn:
        conn.execute(
            text(
                "UPDATE security_state SET recovery_bootstrap_pending=false, "
                "recovery_bootstrap_from_state=NULL, recovery_bootstrap_from_version=NULL, "
                "recovery_bootstrap_started_at=NULL"
            )
        )
    with pytest.raises(RecoveryContextConflict, match="not pending"):
        service.capture(command(service))
    assert counts(recovery_db) == (0, 0)


@pytest.mark.parametrize("consumer", ["context", "reconciliation", "restoration"])
def test_basis_read_preserves_transaction_isolation_and_lock_strength(recovery_db, consumer):
    service = {
        "context": RecoveryContextService,
        "reconciliation": RecoveryReconciliationService,
        "restoration": RecoveryRestorationService,
    }[consumer](recovery_db)
    expected = RecoveryContextService(recovery_db).current_basis()
    with service._transaction() as session:
        if consumer == "restoration":
            basis, record = service._locked_basis(session)
            assert record.state == "normal"
        else:
            basis = RecoveryContextService._basis(session)
        assert basis == expected
        assert session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
        # Readers coexist; restoration excludes even another SHARE reader.
        with recovery_db.begin() as conn:
            if consumer == "restoration":
                with pytest.raises(DBAPIError) as error:
                    conn.execute(text("SELECT id FROM security_state FOR SHARE NOWAIT"))
                assert error.value.orig.sqlstate == "55P03"
            else:
                assert conn.scalar(text("SELECT id FROM security_state FOR SHARE NOWAIT")) == 1
        with recovery_db.begin() as conn:
            with pytest.raises(DBAPIError) as error:
                conn.execute(text("SELECT id FROM security_state FOR UPDATE NOWAIT"))
            assert error.value.orig.sqlstate == "55P03"
    with recovery_db.begin() as conn:
        assert conn.scalar(text("SELECT id FROM security_state FOR UPDATE NOWAIT")) == 1


def test_inventory_bound_is_aggregate_and_partial_blocks_reconciliation(recovery_db):
    task_id = seed(recovery_db, 99)
    service = RecoveryContextService(recovery_db)
    exact = service.capture(command(service))
    assert exact.inventory_status == "complete"
    assert len(exact.evidence_basis) == 99
    assert len(exact.unresolved_operations) == 100  # 99 provider + one cycle
    transition_id = uuid4()
    with recovery_db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO security_state_transitions "
                "(transition_id, previous_state, new_state, reason_code, actor_type, actor_id, "
                "created_at, security_state_version) VALUES "
                "(:id, 'normal', 'recovery_required', 'RECOVERY_STARTED', 'local_operator', "
                "'fixture', now(), 2)"
            ),
            {"id": transition_id},
        )
    exact_evidence = service.capture(command(service))
    assert exact_evidence.inventory_status == "complete"
    assert len(exact_evidence.evidence_basis) == 100
    assert exact_evidence.evidence_basis[0].record_id == transition_id
    assert exact_evidence.evidence_basis[0].kind == "security_transition"
    assert [item.record_id for item in exact_evidence.evidence_basis[1:]] == sorted(
        item.record_id for item in exact.evidence_basis
    )
    with recovery_db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO report_generation_attempts "
                "(operation_id, task_id, status, started_at, expires_at) "
                "VALUES (:id, :task, 'UNKNOWN', now(), now() + interval '1 hour')"
            ),
            {"id": uuid4(), "task": task_id},
        )
    partial = service.capture(command(service))
    assert partial.inventory_status == "partial"
    assert len(partial.evidence_basis) == len(partial.unresolved_operations) == 100
    # Aggregate overflow must be detected even though neither operation kind exceeds 100.
    verdict = RecoveryReconciliationService(recovery_db).reconcile(partial.context_id)
    outcomes = {check.check.value: check.outcome.value for check in verdict.checks}
    assert outcomes == {
        "authority_lineage": "passed",
        "history_integrity": "passed",
        "evidence_integrity": "unknown",
        "operation_outcomes": "unknown",
        "configuration_integrity": "unknown",
    }
    assert not verdict.restoration_allowed
    restoration = RecoveryRestorationService(recovery_db)
    with restoration._transaction() as session:
        basis, _ = restoration._locked_basis(session)
        assert (
            restoration._reconcile(session, partial.context_id, basis, verdict.checked_at)
            == verdict
        )
    with recovery_db.begin() as conn:
        conn.execute(text("UPDATE report_generation_attempts SET status='FAILED'"))
        conn.execute(text("UPDATE research_cycle_attempts SET status='COMPLETED'"))
    # A now-complete inventory does not make the original partial capture complete.
    later = RecoveryReconciliationService(recovery_db).reconcile(partial.context_id)
    assert later.inventory_status == "complete"
    assert {check.check.value: check.outcome.value for check in later.checks} == {
        "authority_lineage": "passed",
        "history_integrity": "passed",
        "evidence_integrity": "unknown",
        "operation_outcomes": "passed",
        "configuration_integrity": "passed",
    }
    assert not later.restoration_allowed
