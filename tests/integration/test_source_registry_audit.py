"""Atomic, redacted audit contracts for trusted-source policy writes."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select, text

from research_agent.api.app import create_app
from research_agent.application import source_registry as source_registry_module
from research_agent.application.persistence_error_translation import PersistenceBoundaryError
from research_agent.application.security_capability import (
    SecurityCapability,
    SecurityCapabilityDenied,
)
from research_agent.application.security_state_service import SecurityStateTransitionService
from research_agent.application.source_registry import (
    SourceRegistryActor,
    SourceRegistryService,
    UntrustedSourceError,
)
from research_agent.domain.research import TrustedSourceCreate
from research_agent.domain.security import SecurityActor, SecurityReasonCode, SecurityState
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import (
    SecurityStateRecord,
    SecurityTransitionRecord,
    TrustedSourcePolicyEventRecord,
    TrustedSourceRecord,
)


@pytest.fixture(autouse=True)
def clean_security_state():
    with engine.begin() as connection:
        connection.execute(delete(SecurityTransitionRecord))
        connection.execute(
            text(
                "UPDATE security_state SET state = 'normal', version = 1, "
                "updated_at = now() WHERE id = 1"
            )
        )
    yield
    with engine.begin() as connection:
        connection.execute(delete(SecurityTransitionRecord))
        connection.execute(
            text(
                "UPDATE security_state SET state = 'normal', version = 1, "
                "updated_at = now() WHERE id = 1"
            )
        )


def create_source(domain: str):
    with SessionFactory() as session:
        return SourceRegistryService(session).register(
            TrustedSourceCreate(
                domain=domain,
                display_name="Operator-visible source",
                verification_method="controlled test fixture",
            )
        )


def cleanup_source(source_id: UUID) -> None:
    with engine.begin() as connection:
        connection.execute(
            delete(TrustedSourcePolicyEventRecord).where(
                TrustedSourcePolicyEventRecord.source_id == source_id
            )
        )
        connection.execute(
            delete(TrustedSourceRecord).where(TrustedSourceRecord.id == source_id)
        )


def test_register_enable_and_repeat_are_audited_with_bounded_semantics():
    domain = f"audit-{uuid4().hex}.example"
    source = create_source(domain)
    source_id = source.id
    try:
        with SessionFactory() as session:
            registry = SourceRegistryService(session)
            enabled = registry.enable(domain)
            before_repeat = enabled.verified_at
            repeated = registry.enable(domain)
            events = session.scalars(
                select(TrustedSourcePolicyEventRecord)
                .where(TrustedSourcePolicyEventRecord.source_id == source_id)
                .order_by(TrustedSourcePolicyEventRecord.created_at)
            ).all()
        assert enabled.status.value == repeated.status.value == "enabled"
        assert repeated.verified_at == before_repeat
        assert [(event.operation, event.result, event.reason) for event in events] == [
            ("REGISTER", "accepted", "registered"),
            ("ENABLE", "accepted", "enabled"),
            ("ENABLE", "no_op", "already_enabled"),
        ]
        assert events[0].previous_status is None and events[0].new_status == "review"
        assert events[1].previous_status == "review" and events[1].new_status == "enabled"
        assert all(event.actor_type == "local_operator" for event in events)
        assert all(event.actor_id == "api:local_operator" for event in events)
        assert all(event.security_state_version >= 1 for event in events)
        assert all(event.authority_epoch_id is not None for event in events)
        assert all(not hasattr(event, "domain") for event in events)
        with TestClient(create_app()) as client:
            response = client.get("/source-registry/audit")
        assert response.status_code == 200
        assert domain not in response.text
        assert "Operator-visible source" not in response.text
        assert "controlled test fixture" not in response.text
        assert {item["source_id"] for item in response.json()} >= {str(source_id)}
    finally:
        cleanup_source(source_id)


def test_duplicate_registration_has_no_second_audit_event():
    domain = f"duplicate-{uuid4().hex}.example"
    source = create_source(domain)
    try:
        with SessionFactory() as session:
            with pytest.raises(PersistenceBoundaryError, match="resource already exists"):
                SourceRegistryService(session).register(
                    TrustedSourceCreate(
                        domain=domain,
                        display_name="Duplicate",
                        verification_method="test",
                    )
                )
            events = session.scalars(
                select(TrustedSourcePolicyEventRecord)
                .where(TrustedSourcePolicyEventRecord.source_id == source.id)
                .order_by(
                    TrustedSourcePolicyEventRecord.created_at,
                    TrustedSourcePolicyEventRecord.event_id,
                )
            ).all()
        assert len(events) == 1
    finally:
        cleanup_source(source.id)


def test_audit_failure_rolls_back_registration():
    domain = f"register-failure-{uuid4().hex}.example"

    def reject_event(*_: object, **__: object) -> None:
        raise RuntimeError("source policy audit unavailable")

    event.listen(TrustedSourcePolicyEventRecord, "before_insert", reject_event)
    try:
        with SessionFactory() as session:
            with pytest.raises(RuntimeError, match="source policy audit unavailable"):
                SourceRegistryService(session).register(
                    TrustedSourceCreate(
                        domain=domain,
                        display_name="Rollback",
                        verification_method="test",
                    )
                )
    finally:
        event.remove(TrustedSourcePolicyEventRecord, "before_insert", reject_event)
    with SessionFactory() as session:
        assert session.scalar(
            select(TrustedSourceRecord).where(TrustedSourceRecord.domain == domain)
        ) is None


def test_audit_failure_rolls_back_activation():
    domain = f"enable-failure-{uuid4().hex}.example"
    source = create_source(domain)

    def reject_event(*_: object, **__: object) -> None:
        raise RuntimeError("source policy audit unavailable")

    event.listen(TrustedSourcePolicyEventRecord, "before_insert", reject_event)
    try:
        with SessionFactory() as session:
            with pytest.raises(RuntimeError, match="source policy audit unavailable"):
                SourceRegistryService(session).enable(domain)
        with SessionFactory() as session:
            record = session.get(TrustedSourceRecord, source.id)
            events = session.scalars(
                select(TrustedSourcePolicyEventRecord)
                .where(TrustedSourcePolicyEventRecord.source_id == source.id)
                .order_by(
                    TrustedSourcePolicyEventRecord.created_at,
                    TrustedSourcePolicyEventRecord.event_id,
                )
            ).all()
        assert record is not None and record.status == "review"
        assert len(events) == 1
    finally:
        event.remove(TrustedSourcePolicyEventRecord, "before_insert", reject_event)
        cleanup_source(source.id)


def test_registry_audit_read_requires_read_audit(monkeypatch):
    def deny(session, capability):
        assert capability is SecurityCapability.READ_AUDIT
        raise SecurityCapabilityDenied("denied by test policy")

    monkeypatch.setattr(source_registry_module, "require_capability", deny)
    with SessionFactory() as session:
        with pytest.raises(SecurityCapabilityDenied):
            SourceRegistryService(session).list_policy_events()


def test_registry_audit_api_enforces_read_audit(monkeypatch):
    def deny(session, capability):
        assert capability is SecurityCapability.READ_AUDIT
        raise SecurityCapabilityDenied("denied by test policy")

    monkeypatch.setattr(source_registry_module, "require_capability", deny)
    with TestClient(create_app()) as client:
        response = client.get("/source-registry/audit")
    assert response.status_code == 403
    assert response.json() == {"detail": "Security policy denied capability"}


def test_registry_actor_context_is_not_blank_or_request_derived():
    with SessionFactory() as session:
        with pytest.raises(ValueError, match="trusted source actor"):
            SourceRegistryService(session, SourceRegistryActor(actor_id=" "))


def test_missing_source_activation_has_no_policy_event():
    with SessionFactory() as session:
        with pytest.raises(UntrustedSourceError):
            SourceRegistryService(session).enable(f"missing-{uuid4().hex}.example")


def test_activation_wins_before_lockdown_and_commits_policy_event(monkeypatch):
    domain = f"race-activation-{uuid4().hex}.example"
    source = create_source(domain)
    entered = Event()
    release = Event()
    original_stage = SourceRegistryService._stage_policy_event

    def pause_after_policy_write(self, *args, **kwargs):
        entered.set()
        assert release.wait(timeout=10)
        return original_stage(self, *args, **kwargs)

    monkeypatch.setattr(SourceRegistryService, "_stage_policy_event", pause_after_policy_write)

    def activate():
        try:
            with SessionFactory() as session:
                return SourceRegistryService(session).enable(domain)
        except Exception as exc:  # assert the exact result below
            return exc

    def lockdown():
        try:
            with SessionFactory() as session:
                return SecurityStateTransitionService(session).transition(
                    expected_version=1,
                    requested_state=SecurityState.LOCKDOWN,
                    actor_type=SecurityActor.LOCAL_OPERATOR,
                    actor_id="race-lockdown",
                    reason_code=SecurityReasonCode.OPERATOR_LOCKDOWN,
                )
        except Exception as exc:
            return exc

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            activation_future = pool.submit(activate)
            assert entered.wait(timeout=10)
            lockdown_future = pool.submit(lockdown)
            release.set()
            activation_result = activation_future.result(timeout=10)
            lockdown_result = lockdown_future.result(timeout=10)
        assert not isinstance(activation_result, Exception)
        assert not isinstance(lockdown_result, Exception)
        with SessionFactory() as session:
            record = session.get(TrustedSourceRecord, source.id)
            events = session.scalars(
                select(TrustedSourcePolicyEventRecord).where(
                    TrustedSourcePolicyEventRecord.source_id == source.id
                )
            ).all()
            state = session.get(SecurityStateRecord, 1)
        assert record is not None and record.status == "enabled"
        assert [item.reason for item in events] == ["registered", "enabled"]
        assert state is not None and state.state == "lockdown"
    finally:
        cleanup_source(source.id)


def test_lockdown_wins_before_activation_acquires_security_lock(monkeypatch):
    domain = f"race-lockdown-{uuid4().hex}.example"
    source = create_source(domain)
    started = Event()
    original_require = source_registry_module.require_locked_capability

    def mark_before_lock(*args, **kwargs):
        started.set()
        return original_require(*args, **kwargs)

    monkeypatch.setattr(source_registry_module, "require_locked_capability", mark_before_lock)

    def activate():
        try:
            with SessionFactory() as session:
                SourceRegistryService(session).enable(domain)
        except Exception as exc:
            return exc
        return None

    try:
        with SessionFactory() as blocker:
            blocker.scalar(
                select(SecurityStateRecord)
                .where(SecurityStateRecord.id == 1)
                .with_for_update()
            )
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(activate)
                assert started.wait(timeout=10)
                SecurityStateTransitionService(blocker).transition(
                    expected_version=1,
                    requested_state=SecurityState.LOCKDOWN,
                    actor_type=SecurityActor.LOCAL_OPERATOR,
                    actor_id="race-lockdown",
                    reason_code=SecurityReasonCode.OPERATOR_LOCKDOWN,
                )
                result = future.result(timeout=10)
        assert isinstance(result, SecurityCapabilityDenied)
        with SessionFactory() as session:
            record = session.get(TrustedSourceRecord, source.id)
            events = session.scalars(
                select(TrustedSourcePolicyEventRecord).where(
                    TrustedSourcePolicyEventRecord.source_id == source.id
                )
            ).all()
        assert record is not None and record.status == "review"
        assert [item.reason for item in events] == ["registered"]
    finally:
        cleanup_source(source.id)
