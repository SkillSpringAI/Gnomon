from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, select, text

from research_agent.application.evidence_service import EvidenceService
from research_agent.application.security_capability import (
    SecurityCapability,
    SecurityCapabilityDenied,
    require_capability,
)
from research_agent.application.security_state_service import (
    SecurityStateConflict,
    SecurityStateTransitionService,
    SecurityTransitionDenied,
)
from research_agent.application.security_state_store import SecurityStateStore
from research_agent.domain.research import SourceCreate, SourceType
from research_agent.domain.security import SecurityActor, SecurityReasonCode, SecurityState
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import (
    ResearchSourceRecord,
    SecurityStateRecord,
    SecurityTransitionRecord,
)


def reset_security_state() -> None:
    with engine.begin() as connection:
        connection.execute(delete(SecurityTransitionRecord))
        connection.execute(
            text(
                "UPDATE security_state SET state = 'normal', version = 1, "
                "updated_at = now() WHERE id = 1"
            )
        )


@pytest.fixture(autouse=True)
def clean_security_state():
    reset_security_state()
    yield
    reset_security_state()


def transition(**kwargs):
    with SessionFactory() as session:
        return SecurityStateTransitionService(session).transition(**kwargs)


def test_cached_normal_state_cannot_authorize_after_lockdown():
    with SessionFactory() as session:
        cached = session.get(SecurityStateRecord, 1)
        assert cached.state == "normal"
        transition(
            expected_version=1,
            requested_state=SecurityState.LOCKDOWN,
            actor_type=SecurityActor.LOCAL_OPERATOR,
            actor_id="operator",
            reason_code=SecurityReasonCode.OPERATOR_LOCKDOWN,
        )
        # Hold the ORM object strongly so the identity map retains the stale snapshot.
        assert cached.state == "normal"
        with pytest.raises(SecurityCapabilityDenied):
            require_capability(session, SecurityCapability.PROVIDER_DISPATCH)
        assert cached.state == "lockdown"
        assert cached.version == 2


def test_locked_transition_refreshes_cached_state_before_version_check():
    with SessionFactory() as session:
        cached = session.get(SecurityStateRecord, 1)
        first = transition(
            expected_version=1,
            requested_state=SecurityState.LOCKDOWN,
            actor_type=SecurityActor.LOCAL_OPERATOR,
            actor_id="operator",
            reason_code=SecurityReasonCode.OPERATOR_LOCKDOWN,
        )
        assert cached.state == "normal"
        with pytest.raises(SecurityStateConflict):
            SecurityStateTransitionService(session).transition(
                expected_version=1,
                requested_state=SecurityState.DEGRADED,
                actor_type=SecurityActor.LOCAL_OPERATOR,
                actor_id="stale-operator",
                reason_code=SecurityReasonCode.OPERATOR_DEGRADED_MODE,
            )
        assert cached.state == "lockdown"
    with SessionFactory() as session:
        state = SecurityStateStore(session).load()
        assert state.identity == (first.authority_epoch_id, 2)
        assert state.state is SecurityState.LOCKDOWN
        assert len(session.scalars(select(SecurityTransitionRecord)).all()) == 1


def test_transition_persists_state_and_authoritative_audit() -> None:
    with SessionFactory() as session:
        initial = SecurityStateStore(session).load()
    result = transition(
        expected_version=1,
        requested_state=SecurityState.LOCKDOWN,
        actor_type=SecurityActor.LOCAL_OPERATOR,
        actor_id="operator-1",
        reason_code=SecurityReasonCode.OPERATOR_LOCKDOWN,
    )

    with SessionFactory() as session:
        state = session.get(SecurityStateRecord, 1)
        audit = session.get(SecurityTransitionRecord, result.transition_id)
    assert result.state is SecurityState.LOCKDOWN
    assert result.version == 2
    assert state is not None and state.state == "lockdown" and state.version == 2
    assert audit is not None
    assert audit.previous_state == "normal"
    assert audit.new_state == "lockdown"
    assert audit.security_state_version == 2
    assert result.authority_epoch_id == initial.authority_epoch_id
    assert state.authority_epoch_id == audit.authority_epoch_id == initial.authority_epoch_id.value
    # Drop pooled connections to exercise durable reload across engine restart.
    engine.dispose()
    with SessionFactory() as session:
        restarted = SecurityStateStore(session).load()
    assert restarted.identity == (initial.authority_epoch_id, 2)


def test_invalid_stale_and_unauthorized_requests_do_not_change_state() -> None:
    with pytest.raises(SecurityTransitionDenied):
        transition(
            expected_version=1,
            requested_state=SecurityState.RECOVERY_REQUIRED,
            actor_type=SecurityActor.LOCAL_OPERATOR,
            actor_id="operator-1",
            reason_code=SecurityReasonCode.RECOVERY_STARTED,
        )
    transition(
        expected_version=1,
        requested_state=SecurityState.DEGRADED,
        actor_type=SecurityActor.SECURITY_DETECTOR,
        actor_id="detector-1",
        reason_code=SecurityReasonCode.SECURITY_DEPENDENCY_DEGRADED,
    )
    with pytest.raises(SecurityTransitionDenied):
        transition(
            expected_version=2,
            requested_state=SecurityState.NORMAL,
            actor_type=SecurityActor.SECURITY_DETECTOR,
            actor_id="detector-1",
            reason_code=SecurityReasonCode.RECOVERY_VERIFIED,
        )
    with pytest.raises(SecurityStateConflict):
        transition(
            expected_version=1,
            requested_state=SecurityState.LOCKDOWN,
            actor_type=SecurityActor.LOCAL_OPERATOR,
            actor_id="operator-1",
            reason_code=SecurityReasonCode.OPERATOR_LOCKDOWN,
        )
    with SessionFactory() as session:
        state = session.get(SecurityStateRecord, 1)
    assert state is not None and state.state == "degraded" and state.version == 2


def test_same_state_is_idempotent_only_for_matching_version() -> None:
    result = transition(
        expected_version=1,
        requested_state=SecurityState.NORMAL,
        actor_type=SecurityActor.LOCAL_OPERATOR,
        actor_id="operator-1",
        reason_code=SecurityReasonCode.OPERATOR_DEGRADED_MODE,
    )
    assert result.transition_id is None and result.version == 1
    with SessionFactory() as session:
        assert session.scalars(select(SecurityTransitionRecord)).all() == []


def test_concurrent_transitions_cannot_consume_one_version_twice() -> None:
    barrier = Barrier(2)

    def attempt() -> object:
        barrier.wait()
        try:
            return transition(
                expected_version=1,
                requested_state=SecurityState.DEGRADED,
                actor_type=SecurityActor.SECURITY_DETECTOR,
                actor_id="detector-1",
                reason_code=SecurityReasonCode.SECURITY_DEPENDENCY_DEGRADED,
            )
        except Exception as exc:  # assert the exact outcome below
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, SecurityStateConflict) for result in results) == 1
    with SessionFactory() as session:
        assert len(session.scalars(select(SecurityTransitionRecord)).all()) == 1


def test_state_and_audit_roll_back_together_on_audit_failure() -> None:
    def reject_audit(*_: object, **__: object) -> None:
        raise RuntimeError("audit sink unavailable")

    event.listen(SecurityTransitionRecord, "before_insert", reject_audit)
    try:
        with pytest.raises(RuntimeError, match="audit sink unavailable"):
            transition(
                expected_version=1,
                requested_state=SecurityState.LOCKDOWN,
                actor_type=SecurityActor.LOCAL_OPERATOR,
                actor_id="operator-1",
                reason_code=SecurityReasonCode.OPERATOR_LOCKDOWN,
            )
    finally:
        event.remove(SecurityTransitionRecord, "before_insert", reject_audit)
    with SessionFactory() as session:
        state = session.get(SecurityStateRecord, 1)
        audits = session.scalars(select(SecurityTransitionRecord)).all()
    assert state is not None and state.state == "normal" and state.version == 1
    assert audits == []


def test_lockdown_denies_provider_dispatch_but_allows_diagnostics() -> None:
    transition(
        expected_version=1,
        requested_state=SecurityState.LOCKDOWN,
        actor_type=SecurityActor.LOCAL_OPERATOR,
        actor_id="operator-1",
        reason_code=SecurityReasonCode.OPERATOR_LOCKDOWN,
    )
    with SessionFactory() as session:
        with pytest.raises(SecurityCapabilityDenied):
            require_capability(session, SecurityCapability.PROVIDER_DISPATCH)
        assert require_capability(session, SecurityCapability.DIAGNOSTICS) is SecurityState.LOCKDOWN


def test_restrictive_transition_blocks_in_flight_result_persistence() -> None:
    transition(
        expected_version=1,
        requested_state=SecurityState.LOCKDOWN,
        actor_type=SecurityActor.LOCAL_OPERATOR,
        actor_id="operator-1",
        reason_code=SecurityReasonCode.OPERATOR_LOCKDOWN,
    )
    with SessionFactory() as session:
        before = len(session.scalars(select(ResearchSourceRecord)).all())
        with pytest.raises(SecurityCapabilityDenied):
            EvidenceService(session).create_source(
                uuid4(),
                SourceCreate(
                    source_type=SourceType.WEB_PAGE,
                    title="Result returned after lockdown",
                    content="This must not be persisted.",
                ),
            )
        assert len(session.scalars(select(ResearchSourceRecord)).all()) == before


def test_recovery_requires_explicit_path_and_survives_reload() -> None:
    transition(
        expected_version=1,
        requested_state=SecurityState.LOCKDOWN,
        actor_type=SecurityActor.LOCAL_OPERATOR,
        actor_id="operator-1",
        reason_code=SecurityReasonCode.OPERATOR_LOCKDOWN,
    )
    transition(
        expected_version=2,
        requested_state=SecurityState.RECOVERY_REQUIRED,
        actor_type=SecurityActor.SECURITY_RECOVERY_SERVICE,
        actor_id="recovery-1",
        reason_code=SecurityReasonCode.RECOVERY_STARTED,
    )
    with SessionFactory() as session:
        persisted = SecurityStateStore(session).load()
    assert persisted.state is SecurityState.RECOVERY_REQUIRED
    assert persisted.version == 3
    with pytest.raises(SecurityTransitionDenied):
        transition(
            expected_version=3,
            requested_state=SecurityState.NORMAL,
            actor_type=SecurityActor.SECURITY_DETECTOR,
            actor_id="detector-1",
            reason_code=SecurityReasonCode.RECOVERY_VERIFIED,
        )
    result = transition(
        expected_version=3,
        requested_state=SecurityState.NORMAL,
        actor_type=SecurityActor.SECURITY_RECOVERY_SERVICE,
        actor_id="recovery-1",
        reason_code=SecurityReasonCode.RECOVERY_VERIFIED,
    )
    assert result.state is SecurityState.NORMAL and result.version == 4


def test_transition_service_applies_centralized_recovery_capability_policy() -> None:
    transition(
        expected_version=1,
        requested_state=SecurityState.DEGRADED,
        actor_type=SecurityActor.SECURITY_DETECTOR,
        actor_id="detector-1",
        reason_code=SecurityReasonCode.SECURITY_DEPENDENCY_DEGRADED,
    )
    result = transition(
        expected_version=2,
        requested_state=SecurityState.NORMAL,
        actor_type=SecurityActor.SECURITY_RECOVERY_SERVICE,
        actor_id="recovery-1",
        reason_code=SecurityReasonCode.RECOVERY_VERIFIED,
    )
    assert result.state is SecurityState.NORMAL


@pytest.mark.parametrize(
    "actor,requested,reason",
    [
        (
            SecurityActor.SECURITY_DETECTOR,
            SecurityState.LOCKDOWN,
            SecurityReasonCode.OPERATOR_LOCKDOWN,
        ),
        (
            SecurityActor.SECURITY_DETECTOR,
            SecurityState.DEGRADED,
            SecurityReasonCode.RECOVERY_VERIFIED,
        ),
        (
            SecurityActor.LOCAL_OPERATOR,
            SecurityState.COMPROMISED_SUSPECTED,
            SecurityReasonCode.OPERATOR_DEGRADED_MODE,
        ),
        (
            SecurityActor.SECURITY_RECOVERY_SERVICE,
            SecurityState.DEGRADED,
            SecurityReasonCode.RECOVERY_PARTIAL,
        ),
    ],
)
def test_unrelated_reasons_cannot_mutate_state_or_append_audit(actor, requested, reason):
    with SessionFactory() as session:
        before = SecurityStateStore(session).load()
    with pytest.raises(SecurityTransitionDenied):
        transition(
            expected_version=1,
            requested_state=requested,
            actor_type=actor,
            actor_id="test",
            reason_code=reason,
        )
    with SessionFactory() as session:
        assert SecurityStateStore(session).load() == before
        assert session.scalars(select(SecurityTransitionRecord)).all() == []


def test_detector_integrity_finding_can_contain_with_epoch_audit():
    result = transition(
        expected_version=1,
        requested_state=SecurityState.COMPROMISED_SUSPECTED,
        actor_type=SecurityActor.SECURITY_DETECTOR,
        actor_id="detector",
        reason_code=SecurityReasonCode.INTEGRITY_CHECK_FAILED,
    )
    with SessionFactory() as session:
        audit = session.get(SecurityTransitionRecord, result.transition_id)
        assert audit.reason_code == SecurityReasonCode.INTEGRITY_CHECK_FAILED
        assert audit.authority_epoch_id == result.authority_epoch_id.value


def test_noop_response_keeps_observed_identity_after_releasing_lock(monkeypatch):
    with SessionFactory() as session:
        rollback = session.rollback

        def rollback_then_concurrent_transition():
            rollback()
            transition(
                expected_version=1,
                requested_state=SecurityState.LOCKDOWN,
                actor_type=SecurityActor.LOCAL_OPERATOR,
                actor_id="concurrent",
                reason_code=SecurityReasonCode.OPERATOR_LOCKDOWN,
            )

        monkeypatch.setattr(session, "rollback", rollback_then_concurrent_transition)
        result = SecurityStateTransitionService(session).transition(
            expected_version=1,
            requested_state=SecurityState.NORMAL,
            actor_type=SecurityActor.LOCAL_OPERATOR,
            actor_id="noop",
            reason_code=SecurityReasonCode.OPERATOR_DEGRADED_MODE,
        )
        assert result.state is SecurityState.NORMAL
        assert result.version == 1
        assert result.transition_id is None
    with SessionFactory() as session:
        current = SecurityStateStore(session).load()
        assert current.state is SecurityState.LOCKDOWN
        assert current.identity == (result.authority_epoch_id, 2)
