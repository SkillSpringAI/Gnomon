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
from research_agent.domain.memory import (
    MemoryAuthority,
    MemoryChangeProposal,
    MemoryConflict,
    MemoryReversal,
)
from research_agent.domain.research import (
    ClaimCreate,
    ClaimSourceLink,
    CycleOutcomeCreate,
    ObjectiveReview,
    ResearchBrief,
    SourceCreate,
    SourceType,
)
from research_agent.domain.security import SecurityActor, SecurityReasonCode, SecurityState
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import (
    MemoryChangeRecord,
    ResearchClaimRecord,
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


def retained_state(work):
    """Snapshot every retained task artifact that bounded closure must not rewrite."""
    task_id = work[0]
    with engine.connect() as connection:
        task = connection.execute(
            text("SELECT to_jsonb(t) FROM research_tasks t WHERE id=:id"), {"id": task_id}
        ).scalar_one()
        cycle = connection.execute(
            text("SELECT to_jsonb(c) FROM research_cycles c WHERE task_id=:id"), {"id": task_id}
        ).scalar_one()
        attempts = connection.execute(
            text(
                "SELECT to_jsonb(a) FROM research_cycle_attempts a "
                "WHERE task_id=:id ORDER BY started_at,id"
            ),
            {"id": task_id},
        ).scalars().all()
        sources = connection.execute(
            text(
                "SELECT to_jsonb(s) FROM research_sources s "
                "WHERE task_id=:id ORDER BY observed_at,id"
            ),
            {"id": task_id},
        ).scalars().all()
        claims = connection.execute(
            text(
                "SELECT to_jsonb(c) FROM research_claims c "
                "WHERE task_id=:id ORDER BY created_at,id"
            ),
            {"id": task_id},
        ).scalars().all()
        provenance = connection.execute(
            text(
                "SELECT to_jsonb(cs) FROM claim_sources cs "
                "JOIN research_claims c ON c.id=cs.claim_id "
                "WHERE c.task_id=:id ORDER BY cs.claim_id,cs.source_id"
            ),
            {"id": task_id},
        ).scalars().all()
        history = connection.execute(
            text(
                "SELECT to_jsonb(m) FROM memory_changes m "
                "WHERE task_id=:id ORDER BY timestamp,change_id"
            ),
            {"id": task_id},
        ).scalars().all()
        events = connection.execute(
            text(
                "SELECT to_jsonb(e) FROM research_events e "
                "WHERE task_id=:id ORDER BY created_at,id"
            ),
            {"id": task_id},
        ).scalars().all()
    return {
        "task": task,
        "cycle": cycle,
        "attempts": attempts,
        "sources": sources,
        "claims": claims,
        "provenance": provenance,
        "history": history,
        "events": events,
    }


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
        cycle.attempted_objectives = [cycle.objectives[0]]
        cycle.unresolved_objectives = list(cycle.objectives)
        cycle.objective_results = [
            {
                "objective_index": 0,
                "source_ids": [str(work[2])],
                "claim_ids": [str(work[3])],
            }
        ]
        cycle.objective_reviews = [
            ObjectiveReview(
                objective_index=0,
                objective=cycle.objectives[0],
                revision=1,
                decision="unresolved",
                rationale="Retain this review",
                source_ids=[work[2]],
                claim_ids=[work[3]],
                basis={"reason": "unverified_claim", "claim_ids": [work[3]]},
                reference_fingerprint="0" * 64,
            ).model_dump(mode="json")
        ]
        attempt = session.get(ResearchCycleAttemptRecord, work[1])
        attempt.stage = "EXTRACTING_CLAIMS"
        attempt.evidence_ids = [str(work[2])]
        attempt.claim_ids = [str(work[3])]
        session.commit()
    before = retained_state(work)
    authority = lockdown()
    assert close(work).cycles[0].status.value == "blocked"
    after = retained_state(work)
    cycle_allowed = {"status", "completed_at", "result_summary", "recovery_reason"}
    attempt_allowed = {"status", "stage", "finished_at", "recovery_reason"}
    task_allowed = {"updated_at"}
    assert {k: v for k, v in before["cycle"].items() if k not in cycle_allowed} == {
        k: v for k, v in after["cycle"].items() if k not in cycle_allowed
    }
    assert {k: v for k, v in before["attempts"][0].items() if k not in attempt_allowed} == {
        k: v for k, v in after["attempts"][0].items() if k not in attempt_allowed
    }
    assert {k: v for k, v in before["task"].items() if k not in task_allowed} == {
        k: v for k, v in after["task"].items() if k not in task_allowed
    }
    for key in ("sources", "claims", "provenance", "history"):
        assert after[key] == before[key]
    assert after["events"][:-1] == before["events"]
    assert after["attempts"][0]["status"] == after["attempts"][0]["stage"] == "INTERRUPTED"
    audit = after["events"][-1]
    assert audit["event_type"] == EventType.CYCLE_SECURITY_INTERRUPTED.value
    assert audit["payload"]["attempt_id"] == str(work[1])
    assert audit["payload"]["actor"] == "source_runner"
    assert audit["payload"]["authority_epoch_id"] == str(authority.authority_epoch_id.value)
    assert audit["payload"]["security_state_version"] == 2
    close(work)
    assert retained_state(work) == after
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
    before = retained_state(work)

    def fail(mapper, connection, target):
        if target.event_type == EventType.CYCLE_SECURITY_INTERRUPTED.value:
            raise RuntimeError("audit failure")

    event.listen(ResearchEventRecord, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="audit failure"):
            close(work)
    finally:
        event.remove(ResearchEventRecord, "before_insert", fail)
    assert retained_state(work) == before


def test_missing_authority_does_not_claim_closure(work):
    before = retained_state(work)
    with engine.begin() as connection:
        connection.execute(delete(SecurityStateRecord))
    with pytest.raises(SecurityCapabilityDenied):
        close(work)
    assert retained_state(work) == before


@pytest.mark.parametrize("state", list(SecurityState)[1:])
def test_exact_closure_is_available_in_every_restrictive_state(work, state):
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE security_state SET state=:state, version=2"), {"state": state.value}
        )
    result = close(work)
    assert result.cycles[0].status.value == "blocked"
    cycle, attempt, audit = persisted(work)
    assert cycle["status"] == "blocked"
    assert attempt["status"] == attempt["stage"] == "INTERRUPTED"
    assert audit[0]["security_state"] == state.value
    assert audit[0]["security_state_version"] == 2


def new_claim_proposal(work, *, change_id=None, statement="Staged claim"):
    return MemoryChangeProposal(
        **({"change_id": change_id} if change_id is not None else {}),
        target_type="claim",
        target_id=uuid4(),
        operation="CREATE",
        expected_version=0,
        reason="same-task outer transaction test",
        claim=ClaimCreate(
            statement=statement,
            confidence=0.5,
            source_links=[ClaimSourceLink(source_id=work[2], support_type="supporting")],
        ),
    )


def test_multiple_same_task_stages_commit_under_one_outer_transaction(work):
    authority = MemoryAuthority(task_id=work[0], actor="local_operator", can_commit=True)
    first = new_claim_proposal(work, statement="First outer-transaction claim")
    second = new_claim_proposal(work, statement="Second outer-transaction claim")
    with SessionFactory() as session:
        service = MemoryService(session)
        first_result = service.stage(first, authority)
        second_result = service.stage(second, authority)
        with engine.connect() as observer:
            visible = observer.scalar(
                select(MemoryChangeRecord.change_id).where(
                    MemoryChangeRecord.change_id.in_([first.change_id, second.change_id])
                )
            )
            assert visible is None
        session.commit()
    with SessionFactory() as session:
        committed = set(
            session.scalars(
                select(MemoryChangeRecord.change_id).where(
                    MemoryChangeRecord.change_id.in_([first.change_id, second.change_id])
                )
            ).all()
        )
    assert committed == {first_result.change_id, second_result.change_id}


def test_later_same_task_stage_failure_rolls_back_earlier_stage(work):
    authority = MemoryAuthority(task_id=work[0], actor="local_operator", can_commit=True)
    reused_change_id = uuid4()
    first = new_claim_proposal(
        work, change_id=reused_change_id, statement="Must roll back with the batch"
    )
    conflicting = new_claim_proposal(
        work, change_id=reused_change_id, statement="Conflicting later stage"
    )
    with SessionFactory() as session:
        service = MemoryService(session)
        service.stage(first, authority)
        with pytest.raises(MemoryConflict, match="Change ID already used"):
            service.stage(conflicting, authority)
        session.rollback()
    with SessionFactory() as session:
        assert session.get(MemoryChangeRecord, reused_change_id) is None
        assert session.get(ResearchClaimRecord, first.target_id) is None


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


@pytest.mark.parametrize("runner", ["source", "agent"])
@pytest.mark.parametrize("failure", ["unavailable", "invalid", "audit"])
def test_runner_propagates_failed_closure_without_manufacturing_terminal_state(
    work, runner, failure, monkeypatch
):
    from research_agent.adapters.agents.fake import FakeAgentNetwork
    from research_agent.application.agent_cycle_runner import AgentCycleRunner
    from research_agent.application.claim_extraction_service import ClaimExtractionService
    from research_agent.application.security_state_store import (
        SecurityStateStore,
        SecurityStateUnavailable,
    )
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
    triggered = False
    original_load = SecurityStateStore.load
    original_extract = ClaimExtractionService.extract_for_source
    original_ask = FakeAgentNetwork.ask

    def load(state_store):
        if failure == "invalid" and triggered:
            raise SecurityStateUnavailable("Injected invalid authority representation")
        return original_load(state_store)

    def trigger_after_committed_progress(service, *args, **kwargs):
        nonlocal triggered
        result = original_extract(service, *args, **kwargs)
        if not triggered:
            if failure == "unavailable":
                with engine.begin() as connection:
                    connection.execute(delete(SecurityStateRecord))
            elif failure == "audit":
                lockdown()
            triggered = True
        return result

    def ask(network, question):
        calls.append(question.id)
        return original_ask(network, question)

    class Retriever:
        def fetch(self, target):
            calls.append(target.uri)
            return RetrievedSource(
                uri=target.uri,
                title="Runner source",
                content="This committed source has enough content for one retained claim.",
                content_type="text/html",
            )

    def fail_closure_audit(mapper, connection, target):
        if target.event_type == EventType.CYCLE_SECURITY_INTERRUPTED.value:
            raise RuntimeError("closure audit failure")

    monkeypatch.setattr(SecurityStateStore, "load", load)
    monkeypatch.setattr(
        ClaimExtractionService, "extract_for_source", trigger_after_committed_progress
    )
    monkeypatch.setattr(FakeAgentNetwork, "ask", ask)
    if failure == "audit":
        event.listen(ResearchEventRecord, "before_insert", fail_closure_audit)
    expected = RuntimeError if failure == "audit" else SecurityCapabilityDenied
    try:
        with SessionFactory() as session, pytest.raises(expected):
            if runner == "source":
                SourceCycleRunner(session, Retriever()).run(
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
                AgentCycleRunner(session).run(work[0], 1, max_agents=2)
    finally:
        if failure == "audit":
            event.remove(ResearchEventRecord, "before_insert", fail_closure_audit)

    with SessionFactory() as session:
        cycle = session.scalar(
            select(ResearchCycleRecord).where(ResearchCycleRecord.task_id == work[0])
        )
        attempt = session.scalar(
            select(ResearchCycleAttemptRecord).where(
                ResearchCycleAttemptRecord.task_id == work[0]
            )
        )
        interruption_audits = session.scalars(
            select(ResearchEventRecord).where(
                ResearchEventRecord.task_id == work[0],
                ResearchEventRecord.event_type == EventType.CYCLE_SECURITY_INTERRUPTED.value,
            )
        ).all()
        sources = session.scalars(
            select(ResearchSourceRecord).where(ResearchSourceRecord.task_id == work[0])
        ).all()
        changes = session.scalars(
            select(MemoryChangeRecord).where(MemoryChangeRecord.task_id == work[0])
        ).all()
    assert triggered
    assert len(calls) == 1
    assert cycle.status == "active"
    assert attempt.status == "RUNNING"
    assert attempt.stage not in {"INTERRUPTED", "BLOCKED"}
    assert interruption_audits == []
    assert len(sources) == 2  # fixture plus the one committed runner result
    assert len(changes) >= 2  # fixture plus retained runner claim history
    assert cycle.evidence_ids and cycle.claim_ids and cycle.objective_results
    assert attempt.evidence_ids and attempt.claim_ids


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
