"""Containment closure and real PostgreSQL mutation/lockdown interleavings."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from conftest import purge_test_tasks
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select, text

from research_agent.api.app import create_app
from research_agent.application.cycle_interruption import (
    CycleInterruptionService,
    CycleRunnerIdentity,
)
from research_agent.application.evidence_service import EvidenceService
from research_agent.application.memory_service import MemoryService
from research_agent.application.research_service import ResearchService, TaskStateConflict
from research_agent.application.security_capability import SecurityCapabilityDenied
from research_agent.application.security_state_service import SecurityStateTransitionService
from research_agent.domain.events import EventType
from research_agent.domain.memory import MemoryAuthority, MemoryChangeProposal, MemoryReversal
from research_agent.domain.research import (
    ClaimCreate,
    ClaimSourceLink,
    CycleOutcomeCreate,
    ResearchBrief,
    SourceCreate,
    SourceType,
)
from research_agent.domain.security import SecurityActor, SecurityReasonCode, SecurityState
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import (
    MemoryChangeRecord,
    ResearchCycleAttemptRecord,
    ResearchCycleRecord,
    ResearchEventRecord,
    ResearchSourceRecord,
    SecurityStateRecord,
    SecurityTransitionRecord,
)
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository


@pytest.fixture
def work():
    with engine.begin() as connection:
        original = dict(connection.execute(text("SELECT * FROM security_state")).mappings().one())
        connection.execute(text("UPDATE security_state SET state='normal', version=1"))
    with SessionFactory() as session:
        service = ResearchService(SqlAlchemyResearchTaskRepository(session))
        task = service.create_task(
            ResearchBrief(title="Ordering test", objective="Retain evidence")
        )
        attempt_id = uuid4()
        service.start_cycle(task.id, 1, exclusive=True, track_progress=True, attempt_id=attempt_id)
        source = EvidenceService(session).create_source(
            task.id,
            SourceCreate(
                source_type=SourceType.DOCUMENT,
                title="Retained",
                content="Committed evidence.",
            ),
        )
        claim = EvidenceService(session).create_claim(
            task.id,
            ClaimCreate(
                statement="Retained claim",
                confidence=0.4,
                source_links=[ClaimSourceLink(source_id=source.id, support_type="supporting")],
            ),
        )
        change = session.scalar(
            select(MemoryChangeRecord).where(MemoryChangeRecord.target_id == claim.id)
        )
        original_change = change.change_id
        session.rollback()
    try:
        yield task.id, attempt_id, source.id, claim.id, original_change
    finally:
        with engine.begin() as connection:
            purge_test_tasks(connection, [task.id])
            connection.execute(
                delete(SecurityTransitionRecord).where(
                    SecurityTransitionRecord.actor_id == "ordering-test"
                )
            )
            connection.execute(
                text("""
                INSERT INTO security_state (id,state,version,updated_at,authority_epoch_id)
                VALUES (:id,:state,:version,:updated_at,:authority_epoch_id)
                ON CONFLICT (id) DO UPDATE SET state=excluded.state, version=excluded.version,
                updated_at=excluded.updated_at, authority_epoch_id=excluded.authority_epoch_id
            """),
                original,
            )


def lockdown(session=None):
    if session is None:
        with SessionFactory() as owned:
            return lockdown(owned)
    return SecurityStateTransitionService(session).transition(
        expected_version=1,
        requested_state=SecurityState.LOCKDOWN,
        actor_type=SecurityActor.LOCAL_OPERATOR,
        actor_id="ordering-test",
        reason_code=SecurityReasonCode.OPERATOR_LOCKDOWN,
    )


def close(work, caller=CycleRunnerIdentity.SOURCE):
    with SessionFactory() as session:
        return CycleInterruptionService(session).close(work[0], 1, work[1], caller=caller)


def persisted(work):
    with engine.connect() as connection:
        cycle = connection.execute(
            text("SELECT to_jsonb(c) FROM research_cycles c WHERE task_id=:id"), {"id": work[0]}
        ).scalar_one()
        attempt = connection.execute(
            text("SELECT to_jsonb(a) FROM research_cycle_attempts a WHERE id=:id"), {"id": work[1]}
        ).scalar_one()
        audit = (
            connection.execute(
                select(ResearchEventRecord.payload).where(
                    ResearchEventRecord.task_id == work[0],
                    ResearchEventRecord.event_type == EventType.CYCLE_SECURITY_INTERRUPTED.value,
                )
            )
            .scalars()
            .all()
        )
    return cycle, attempt, audit


def test_exact_closure_is_atomic_preserves_progress_and_idempotent(work):
    # Persist real progress through the existing writer before interruption.
    from research_agent.application.cycle_progress import CycleProgress

    with SessionFactory() as session:
        progress = CycleProgress(session, work[0], 1)
        progress.attach(work[1])
        progress.attempt([0])
        cycle = session.scalar(
            select(ResearchCycleRecord).where(ResearchCycleRecord.task_id == work[0])
        )
        cycle.evidence_ids = [str(work[2])]
        cycle.claim_ids = [str(work[3])]
        session.commit()
    before, _, _ = persisted(work)
    authority = lockdown()
    assert close(work).cycles[0].status.value == "blocked"
    after, attempt, audit = persisted(work)
    allowed = {"status", "completed_at", "result_summary", "recovery_reason"}
    assert {k: v for k, v in before.items() if k not in allowed} == {
        k: v for k, v in after.items() if k not in allowed
    }
    assert attempt["status"] == attempt["stage"] == "INTERRUPTED"
    assert len(audit) == 1
    assert audit[0]["attempt_id"] == str(work[1])
    assert audit[0]["actor"] == "source_runner"
    assert audit[0]["authority_epoch_id"] == str(authority.authority_epoch_id.value)
    assert audit[0]["security_state_version"] == 2
    close(work)
    assert persisted(work) == (after, attempt, audit)
    with pytest.raises(TaskStateConflict):
        close(work, CycleRunnerIdentity.AGENT)


def test_wrong_attempt_and_finalized_cycle_are_rejected(work):
    before = persisted(work)
    with pytest.raises(TaskStateConflict):
        close((work[0], uuid4(), *work[2:]))
    assert persisted(work) == before
    with SessionFactory() as session:
        ResearchService(SqlAlchemyResearchTaskRepository(session)).record_cycle_outcome(
            work[0], 1, CycleOutcomeCreate(status="completed", result_summary="Manual completion")
        )
    terminal = persisted(work)
    with pytest.raises(TaskStateConflict):
        close(work)
    assert persisted(work) == terminal


def test_audit_failure_rolls_back_entire_closure(work):
    before = persisted(work)

    def fail(mapper, connection, target):
        if target.event_type == EventType.CYCLE_SECURITY_INTERRUPTED.value:
            raise RuntimeError("audit failure")

    event.listen(ResearchEventRecord, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="audit failure"):
            close(work)
    finally:
        event.remove(ResearchEventRecord, "before_insert", fail)
    assert persisted(work) == before


def test_missing_authority_does_not_claim_closure(work):
    before = persisted(work)
    with engine.begin() as connection:
        connection.execute(delete(SecurityStateRecord))
    with pytest.raises(SecurityCapabilityDenied):
        close(work)
    assert persisted(work) == before


def mutation(session, work, kind):
    task_id, _, source_id, claim_id, change_id = work
    if kind == "closure":
        return CycleInterruptionService(session).close(
            task_id, 1, work[1], caller=CycleRunnerIdentity.SOURCE
        )
    if kind == "source":
        return EvidenceService(session).create_source(
            task_id,
            SourceCreate(source_type=SourceType.DOCUMENT, title="New", content="New mutation"),
        )
    if kind == "outcome":
        return ResearchService(SqlAlchemyResearchTaskRepository(session)).record_cycle_outcome(
            task_id, 1, CycleOutcomeCreate(status="completed", result_summary="Normal completion")
        )
    authority = MemoryAuthority(task_id=task_id, actor="local_operator", can_commit=True)
    if kind == "reverse":
        return MemoryService(session).reverse(change_id, MemoryReversal(reason="test"), authority)
    proposal = MemoryChangeProposal(
        target_type="claim",
        target_id=claim_id,
        operation="UPDATE",
        expected_version=1,
        reason="test",
        claim=ClaimCreate(
            statement="Changed",
            confidence=0.5,
            source_links=[ClaimSourceLink(source_id=source_id, support_type="supporting")],
        ),
    )
    result = MemoryService(session).stage(proposal, authority)
    session.commit()
    return result


def wait_blocked(waiter, blocker):
    deadline = monotonic() + 5
    with engine.connect() as connection:
        while monotonic() < deadline:
            blockers = connection.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": waiter})
            if blocker in blockers:
                return
            sleep(0.01)
    raise AssertionError("Expected PostgreSQL row-lock blocking was not observed")


@pytest.mark.parametrize("kind", ["source", "outcome", "stage", "reverse", "closure"])
@pytest.mark.parametrize("winner", ["mutation", "lockdown"])
def test_real_lock_ordering(work, kind, winner):
    locked, release, other_started = Event(), Event(), Event()
    pids = {}

    def run(role):
        with SessionFactory() as session:

            def after_begin(s, tx, connection):
                pids[role] = connection.scalar(text("SELECT pg_backend_pid()"))
                if role != winner:
                    other_started.set()

                def after_sql(conn, cursor, statement, params, context, many):
                    boundary = (
                        "FOR SHARE" in statement
                        if role == "mutation"
                        else "FOR UPDATE" in statement and "security_state" in statement
                    )
                    if role == winner and boundary:
                        locked.set()
                        assert release.wait(10)

                event.listen(connection, "after_cursor_execute", after_sql)

            event.listen(session, "after_begin", after_begin)
            if role == "lockdown":
                lockdown(session)
            elif winner == "lockdown" and kind != "closure":
                with pytest.raises(SecurityCapabilityDenied):
                    mutation(session, work, kind)
                session.rollback()
            else:
                mutation(session, work, kind)

    loser = "lockdown" if winner == "mutation" else "mutation"
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, winner)
        try:
            assert locked.wait(10)
            second = pool.submit(run, loser)
            assert other_started.wait(10)
            wait_blocked(pids[loser], pids[winner])
            assert not second.done()
        finally:
            release.set()
        first.result(timeout=10)
        second.result(timeout=10)
    with SessionFactory() as session:
        assert session.get(SecurityStateRecord, 1).state == "lockdown"
        sources = session.scalars(
            select(ResearchSourceRecord).where(ResearchSourceRecord.task_id == work[0])
        ).all()
        changes = session.scalars(
            select(MemoryChangeRecord).where(MemoryChangeRecord.task_id == work[0])
        ).all()
    cycle, attempt, audit = persisted(work)
    if kind == "closure":
        assert cycle["status"] == "blocked" and attempt["status"] == "INTERRUPTED"
        assert len(audit) == 1
        assert audit[0]["security_state_version"] == (1 if winner == "mutation" else 2)
    elif kind == "source":
        assert len(sources) == (2 if winner == "mutation" else 1)
    elif kind == "outcome":
        assert cycle["status"] == ("completed" if winner == "mutation" else "active")
    else:
        assert len(changes) == (2 if winner == "mutation" else 1)


@pytest.mark.parametrize("kind", ["source", "outcome", "stage", "reverse"])
def test_lockdown_wins_and_cached_normal_cannot_authorize(work, kind):
    with SessionFactory() as session:
        cached = session.get(SecurityStateRecord, 1)
        assert cached.state == "normal"
        lockdown()
        with pytest.raises(SecurityCapabilityDenied):
            mutation(session, work, kind)
        session.rollback()
    assert persisted(work)[0]["status"] == "active"


@pytest.mark.parametrize("state", list(SecurityState)[1:])
def test_reversal_api_and_service_denied_in_restrictive_states(work, state):
    with engine.begin() as connection:
        connection.execute(text("UPDATE security_state SET state=:state"), {"state": state.value})
    with SessionFactory() as session, pytest.raises(SecurityCapabilityDenied):
        mutation(session, work, "reverse")
    with TestClient(create_app()) as client:
        response = client.post(
            f"/investigations/{work[0]}/memory/changes/{work[4]}/reverse", json={"reason": "test"}
        )
    assert response.status_code == 403


@pytest.mark.parametrize("runner", ["source", "agent"])
def test_persisted_lockdown_during_runner_retains_first_result(work, runner, monkeypatch):
    from research_agent.adapters.agents.fake import FakeAgentNetwork
    from research_agent.application.agent_cycle_runner import AgentCycleRunner
    from research_agent.application.source_cycle_runner import SourceCycleRequest, SourceCycleRunner
    from research_agent.ports.retrieval import RetrievedSource

    with SessionFactory() as session:
        session.execute(
            delete(ResearchCycleAttemptRecord).where(ResearchCycleAttemptRecord.id == work[1])
        )
        cycle = session.scalar(
            select(ResearchCycleRecord).where(ResearchCycleRecord.task_id == work[0])
        )
        cycle.status = "planned"
        session.commit()
    calls = []
    original = FakeAgentNetwork.ask

    def ask(network, question):
        result = original(network, question)
        calls.append(question.id)
        if len(calls) == 2:
            lockdown()
        return result

    monkeypatch.setattr(FakeAgentNetwork, "ask", ask)

    class Retriever:
        def fetch(self, target):
            calls.append(target.uri)
            if len(calls) == 2:
                lockdown()
            return RetrievedSource(
                uri=target.uri,
                title="Runner source",
                content="This is a committed attributable source statement.",
                content_type="text/html",
            )

    with SessionFactory() as session:
        if runner == "source":
            result = SourceCycleRunner(session, Retriever()).run(
                work[0],
                1,
                SourceCycleRequest(
                    sources=[
                        {"uri": "https://example.test/a", "objective_index": 0},
                        {"uri": "https://example.test/b", "objective_index": 0},
                    ]
                ),
            )
        else:
            result = AgentCycleRunner(session).run(work[0], 1, max_agents=2)
        cycle = result.cycles[0]
        assert cycle.status.value == "blocked"
        assert len(cycle.evidence_ids) == 1
        assert cycle.claim_ids
        assert cycle.objective_results
        attempts = session.scalars(
            select(ResearchCycleAttemptRecord).where(ResearchCycleAttemptRecord.task_id == work[0])
        ).all()
        assert len(attempts) == 1 and attempts[0].status == "INTERRUPTED"
        assert attempts[0].evidence_ids == [str(x) for x in cycle.evidence_ids]
        events = session.scalars(
            select(ResearchEventRecord).where(
                ResearchEventRecord.task_id == work[0],
                ResearchEventRecord.event_type == EventType.CYCLE_SECURITY_INTERRUPTED.value,
            )
        ).all()
        assert len(events) == 1
        assert events[0].payload["actor"] == runner + "_runner"
        assert events[0].payload["attempt_id"] == str(attempts[0].id)
        assert (
            len(
                session.scalars(
                    select(ResearchSourceRecord).where(ResearchSourceRecord.task_id == work[0])
                ).all()
            )
            == 2
        )  # fixture + first result
    assert len(calls) == 2


@pytest.mark.parametrize("winner", ["manual", "closure"])
def test_operator_outcome_race_never_rewrites_terminal_history(work, winner):
    locked, release, started = Event(), Event(), Event()
    pids = {}

    def run(role):
        with SessionFactory() as session:

            def after_begin(s, tx, conn):
                pids[role] = conn.scalar(text("SELECT pg_backend_pid()"))
                if role != winner:
                    started.set()

                def after_sql(conn, cursor, statement, params, context, many):
                    if role == winner and "FOR SHARE" in statement:
                        locked.set()
                        assert release.wait(10)

                event.listen(conn, "after_cursor_execute", after_sql)

            event.listen(session, "after_begin", after_begin)

            def invoke():
                if role == "closure":
                    mutation(session, work, "closure")
                else:
                    mutation(session, work, "outcome")

            if role == winner:
                invoke()
            else:
                with pytest.raises(TaskStateConflict):
                    invoke()

    loser = "closure" if winner == "manual" else "manual"
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, winner)
        try:
            assert locked.wait(10)
            second = pool.submit(run, loser)
            assert started.wait(10)
            wait_blocked(pids[loser], pids[winner])
        finally:
            release.set()
        first.result(timeout=10)
        second.result(timeout=10)
    cycle, attempt, audit = persisted(work)
    assert cycle["status"] == ("completed" if winner == "manual" else "blocked")
    assert attempt["status"] == ("COMPLETED" if winner == "manual" else "INTERRUPTED")
    assert len(audit) == (0 if winner == "manual" else 1)


def test_general_outcome_api_denied_after_lockdown(work):
    lockdown()
    before = persisted(work)
    with TestClient(create_app()) as client:
        response = client.post(
            f"/investigations/{work[0]}/cycles/1/outcome",
            json={"status": "completed", "result_summary": "Cannot bypass security"},
        )
    assert response.status_code == 403
    assert persisted(work) == before


def test_existing_foreign_attempt_and_untrusted_caller_are_rejected(work):
    with SessionFactory() as session:
        service = ResearchService(SqlAlchemyResearchTaskRepository(session))
        other = service.create_task(ResearchBrief(title="Other", objective="Separate scope"))
        foreign = uuid4()
        service.start_cycle(other.id, 1, exclusive=True, attempt_id=foreign)
    try:
        before = persisted(work)
        with pytest.raises(TaskStateConflict):
            close((work[0], foreign, *work[2:]))
        with pytest.raises(TaskStateConflict):
            close(work, "source_runner")
        assert persisted(work) == before
    finally:
        with engine.begin() as connection:
            purge_test_tasks(connection, [other.id])


def test_concurrent_duplicate_closure_appends_once(work):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: close(work), range(2)))
    assert all(result.cycles[0].status.value == "blocked" for result in results)
    assert len(persisted(work)[2]) == 1


def test_corrupt_authority_rejected_without_closure(work, monkeypatch):
    from research_agent.application.security_state_store import (
        SecurityStateStore,
        SecurityStateUnavailable,
    )

    before = persisted(work)

    def corrupt(self):
        raise SecurityStateUnavailable("Invalid epoch")

    monkeypatch.setattr(SecurityStateStore, "load", corrupt)
    with pytest.raises(SecurityCapabilityDenied):
        close(work)
    assert persisted(work) == before
