from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import delete, event, select, text

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
from research_agent.domain.security import SecurityActor, SecurityReasonCode, SecurityState
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import SecurityStateRecord, SecurityTransitionRecord


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


def test_transition_persists_state_and_authoritative_audit() -> None:
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
