"""Controlled PostgreSQL interleavings for the provider lifecycle."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event
from time import monotonic, sleep
from uuid import UUID, uuid4

import pytest
from conftest import purge_test_tasks
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from research_agent.adapters.llm.rule_based_report import RuleBasedReportDraftGenerator
from research_agent.api.app import create_app
from research_agent.api.routes.reports import get_report_generator
from research_agent.application.audit_service import AuditService
from research_agent.application.provider_budget_service import (
    ProviderAttemptConflict,
    ProviderBudgetExceeded,
    ProviderBudgetService,
)
from research_agent.application.report_generation_service import ReportGenerationService
from research_agent.config.settings import get_settings
from research_agent.domain.events import EventType
from research_agent.persistence.database import SessionFactory, engine, get_session
from research_agent.persistence.models import ReportGenerationAttemptRecord, ResearchEventRecord


@pytest.fixture
def provider_task(monkeypatch):
    monkeypatch.setenv("LLM_MAX_DRAFTS_PER_TASK", "1")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        task_id = UUID(
            client.post(
                "/investigations",
                json={"title": "Provider lifecycle", "objective": "Bound execution."},
            ).json()["task"]["id"]
        )
        try:
            yield app, client, task_id
        finally:
            app.dependency_overrides.clear()
            with engine.begin() as connection:
                purge_test_tasks(connection, [task_id])
            get_settings.cache_clear()


def admit(task_id, operation_id, dispatched=True):
    with SessionFactory() as session:
        service = ProviderBudgetService(session)
        service.reserve(task_id, operation_id, 1, 60)
        if dispatched:
            service.dispatch(operation_id)


def overdue(operation_id):
    with SessionFactory() as session:
        attempt = session.get(ReportGenerationAttemptRecord, operation_id)
        attempt.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()


def saved(operation_id):
    with SessionFactory() as session:
        attempt = session.get(ReportGenerationAttemptRecord, operation_id)
        events = session.scalars(
            select(ResearchEventRecord).where(
                ResearchEventRecord.payload["operation_id"].astext == str(operation_id)
            )
        ).all()
        return attempt, [item.event_type for item in events]


@pytest.mark.parametrize("winner", ["expiry", "dispatch"])
def test_expiry_and_dispatch_share_the_task_lock(provider_task, monkeypatch, winner):
    _, _, task_id = provider_task
    first_id, next_id = uuid4(), uuid4()
    admit(task_id, first_id, dispatched=False)
    if winner == "expiry":
        overdue(first_id)
    entered, release, competing = Event(), Event(), Event()
    competing_pid = []
    original = ProviderBudgetService._audit

    def pause(service, attempt, event, payload=None):
        original(service, attempt, event, payload)
        expected = (
            EventType.REPORT_DRAFT_EXPIRED
            if winner == "expiry"
            else EventType.REPORT_DRAFT_DISPATCHED
        )
        if attempt.operation_id == first_id and event == expected:
            if winner == "dispatch":
                attempt.expires_at = datetime.now(UTC) - timedelta(minutes=1)
            entered.set()
            assert release.wait(10)

    monkeypatch.setattr(ProviderBudgetService, "_audit", pause)

    def dispatch():
        with SessionFactory() as session:
            # Preload stale PENDING state, then race with expiry.
            session.get(ReportGenerationAttemptRecord, first_id)
            if winner == "expiry":
                competing_pid.append(session.scalar(text("SELECT pg_backend_pid()")))
                competing.set()
            try:
                ProviderBudgetService(session).dispatch(first_id)
                return "dispatched"
            except ProviderAttemptConflict:
                return "conflict"

    def reserve():
        with SessionFactory() as session:
            if winner == "dispatch":
                competing_pid.append(session.scalar(text("SELECT pg_backend_pid()")))
                competing.set()
            try:
                ProviderBudgetService(session).reserve(task_id, next_id, 1, 60)
                return "reserved"
            except ProviderBudgetExceeded:
                return "full"

    with ThreadPoolExecutor(max_workers=2) as pool:
        leading = pool.submit(reserve if winner == "expiry" else dispatch)
        try:
            assert entered.wait(10)
            trailing = pool.submit(dispatch if winner == "expiry" else reserve)
            assert competing.wait(10)
            # Confirm actual PostgreSQL lock contention before releasing the winner.
            deadline = monotonic() + 5
            with engine.connect() as observer:
                while not observer.scalar(
                    text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"),
                    {"pid": competing_pid[0]},
                ):
                    assert monotonic() < deadline, "Competing writer never waited on a DB lock"
                    sleep(0.01)
        finally:
            release.set()
        assert leading.result(timeout=10) == ("reserved" if winner == "expiry" else "dispatched")
        assert trailing.result(timeout=10) == ("conflict" if winner == "expiry" else "full")
    assert saved(first_id)[0].status == ("EXPIRED" if winner == "expiry" else "DISPATCHED")


@pytest.mark.parametrize("other", ["SUCCEEDED", "FAILED"])
def test_concurrent_finalizers_refresh_state_and_emit_one_terminal_event(provider_task, other):
    _, _, task_id = provider_task
    operation_id = uuid4()
    admit(task_id, operation_id)
    barrier = Barrier(2)

    def finish(status):
        with SessionFactory() as session:
            stale = session.get(ReportGenerationAttemptRecord, operation_id)
            assert stale.status == "DISPATCHED"
            barrier.wait(timeout=10)
            try:
                ProviderBudgetService(session).finish(operation_id, status)
                return "ok"
            except ProviderAttemptConflict:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(finish, status) for status in ("SUCCEEDED", other)]
        outcomes = sorted(future.result(timeout=10) for future in futures)
    assert outcomes == (["ok", "ok"] if other == "SUCCEEDED" else ["conflict", "ok"])
    attempt, events = saved(operation_id)
    assert attempt.status in {"SUCCEEDED", other}
    assert sum(event in {"report.draft_generated", "report.draft_failed"} for event in events) == 1


def test_live_expiry_recovery_and_late_success_keep_capacity(provider_task):
    app, client, task_id = provider_task
    operation_id = uuid4()
    entered, release = Event(), Event()
    sessions = []

    def session_dependency():
        with SessionFactory() as session:
            sessions.append(session)
            yield session

    class Delayed:
        def generate(self, report):
            assert not sessions[0].in_transaction()
            entered.set()
            assert release.wait(10)
            return RuleBasedReportDraftGenerator().generate(report)

    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[get_report_generator] = lambda: ReportGenerationService(Delayed())
    url = f"/investigations/{task_id}/report"
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            client.post, url + "/draft", headers={"Idempotency-Key": str(operation_id)}
        )
        try:
            assert entered.wait(10)
            assert client.post(f"{url}/attempts/{operation_id}/recover").status_code == 409
            overdue(operation_id)
            assert client.post(url + "/draft").status_code == 429
            for _ in range(2):
                assert client.post(f"{url}/attempts/{operation_id}/recover").status_code == 204
            current = client.get(f"{url}/attempts/{operation_id}").json()
            assert current["status"] == "UNKNOWN" and current["finished_at"] is None
            assert client.post(url + "/draft").status_code == 429
        finally:
            release.set()
        assert future.result(timeout=10).status_code == 200
    attempt, events = saved(operation_id)
    assert attempt.status == "SUCCEEDED"
    assert events.count("report.draft_uncertain") == 1
    assert events.count("report.draft_generated") == 1
    assert client.post(url + "/draft").status_code == 429
    assert client.post(f"{url}/attempts/{operation_id}/recover").status_code == 409
    assert (
        client.get(f"/investigations/{uuid4()}/report/attempts/{operation_id}").status_code == 404
    )


@pytest.mark.parametrize("failure", ["transport", "validation", "input"])
def test_failures_preserve_budget_semantics_and_atomic_audit(provider_task, monkeypatch, failure):
    app, client, task_id = provider_task
    operation_id = uuid4()
    calls = []

    class Invalid:
        def generate(self, report):
            calls.append(report.task_id)
            if failure == "transport":
                raise TimeoutError("private transport detail")
            draft = RuleBasedReportDraftGenerator().generate(report)
            return draft.model_copy(update={"cited_claim_ids": [uuid4()]})

    app.dependency_overrides[get_report_generator] = lambda: ReportGenerationService(Invalid())
    if failure == "input":
        monkeypatch.setenv("LLM_MAX_REPORT_CHARS", "1")
        get_settings.cache_clear()
    response = client.post(
        f"/investigations/{task_id}/report/draft", headers={"Idempotency-Key": str(operation_id)}
    )
    assert response.status_code == (413 if failure == "input" else 502)
    attempt, events = saved(operation_id)
    assert attempt.status == ("UNKNOWN" if failure == "transport" else "FAILED")
    assert len(calls) == (0 if failure == "input" else 1)
    assert (
        events.count("report.draft_uncertain" if failure == "transport" else "report.draft_failed")
        == 1
    )
    assert "private transport detail" not in response.text
    with SessionFactory() as session:
        service = ProviderBudgetService(session)
        if failure == "transport":
            with pytest.raises(ProviderBudgetExceeded):
                service.reserve(task_id, uuid4(), 1, 60)
        else:
            service.reserve(task_id, uuid4(), 1, 60)


def test_crash_after_provider_return_rolls_back_final_state_and_audit(provider_task, monkeypatch):
    _, client, task_id = provider_task
    operation_id = uuid4()
    original = AuditService.stage

    def fail(service, task_id, event, payload):
        original(service, task_id, event, payload)
        if event == EventType.REPORT_DRAFT_GENERATED:
            service.session.flush()
            raise RuntimeError("injected finalization failure")

    monkeypatch.setattr(AuditService, "stage", fail)
    with pytest.raises(RuntimeError, match="injected finalization failure"):
        client.post(
            f"/investigations/{task_id}/report/draft",
            headers={"Idempotency-Key": str(operation_id)},
        )
    attempt, events = saved(operation_id)
    assert attempt.status == "DISPATCHED"
    assert "report.draft_generated" not in events
    monkeypatch.setattr(AuditService, "stage", original)
    overdue(operation_id)
    with SessionFactory() as session:
        service = ProviderBudgetService(session)
        service.recover(task_id, operation_id)
        service.finish(operation_id, "SUCCEEDED")
        service.finish(operation_id, "SUCCEEDED")
    assert saved(operation_id)[1].count("report.draft_generated") == 1


@pytest.mark.parametrize("target", ["FAILED", "UNKNOWN"])
def test_failure_and_recovery_audit_errors_roll_back(provider_task, monkeypatch, target):
    _, _, task_id = provider_task
    operation_id = uuid4()
    admit(task_id, operation_id)
    overdue(operation_id)
    original = AuditService.stage

    def fail(service, task_id, event, payload):
        original(service, task_id, event, payload)
        service.session.flush()
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditService, "stage", fail)
    with SessionFactory() as session:
        with pytest.raises(RuntimeError, match="audit unavailable"):
            service = ProviderBudgetService(session)
            if target == "UNKNOWN":
                service.recover(task_id, operation_id)
            else:
                service.finish(operation_id, target)
    attempt, events = saved(operation_id)
    assert attempt.status == "DISPATCHED"
    assert "report.draft_failed" not in events and "report.draft_uncertain" not in events


def test_expired_admission_cannot_dispatch_or_finish_successfully(provider_task):
    _, _, task_id = provider_task
    operation_id = uuid4()
    admit(task_id, operation_id, dispatched=False)
    overdue(operation_id)
    with SessionFactory() as session:
        service = ProviderBudgetService(session)
        with pytest.raises(ProviderAttemptConflict):
            service.dispatch(operation_id)
        with pytest.raises(ProviderAttemptConflict):
            service.finish(operation_id, "SUCCEEDED")
        service.reserve(task_id, uuid4(), 1, 60)
    attempt, events = saved(operation_id)
    assert attempt.status == "EXPIRED"
    assert events.count("report.draft_expired") == 1


def test_cross_task_concurrent_operation_reuse_returns_conflict(provider_task, monkeypatch):
    _, client, task_id = provider_task
    other_id = UUID(
        client.post(
            "/investigations", json={"title": "Other task", "objective": "Do not reuse operations."}
        ).json()["task"]["id"]
    )
    operation_id = uuid4()
    barrier = Barrier(2)
    original = ProviderBudgetService._audit

    def synchronize(service, attempt, event, payload=None):
        if event == EventType.REPORT_DRAFT_RESERVED:
            barrier.wait(timeout=10)
        original(service, attempt, event, payload)

    monkeypatch.setattr(ProviderBudgetService, "_audit", synchronize)

    def reserve(task):
        with SessionFactory() as session:
            try:
                ProviderBudgetService(session).reserve(task, operation_id, 1, 60)
                return "reserved"
            except ProviderAttemptConflict:
                return "conflict"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(reserve, task) for task in (task_id, other_id)]
            assert sorted(future.result(timeout=10) for future in futures) == [
                "conflict",
                "reserved",
            ]
        assert saved(operation_id)[1].count("report.draft_reserved") == 1
    finally:
        with engine.begin() as connection:
            purge_test_tasks(connection, [other_id])
