"""M1.5 pass-1 protected restoration preflight."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session

from research_agent.application.authority_bootstrap import (
    AuthorityBootstrapService,
    AuthorityStartupMode,
)
from research_agent.application.authorization_service import AuthorizationService
from research_agent.application.migrations import run_migrations
from research_agent.application.recovery_context_service import RecoveryContextService
from research_agent.application.recovery_restoration_service import (
    ProtectedRestorationDenied,
    RecoveryRestorationService,
)
from research_agent.application.security_state_store import SecurityStateStore
from research_agent.domain.authorization import (
    AuthorizationBasisReference,
    AuthorizationScopeItem,
    IssueExecutionAuthorization,
    IssueOperatorAuthorization,
    OperatorPrincipal,
)
from research_agent.domain.recovery import CaptureRecoveryContext, PrepareProtectedRestoration
from research_agent.domain.security import SecurityReasonCode, SecurityState
from research_agent.persistence.database import engine
from research_agent.persistence.models import (
    ReportGenerationAttemptRecord,
    ResearchCycleAttemptRecord,
    ResearchCycleRecord,
    ResearchEventRecord,
    ResearchTaskRecord,
    SecurityTransitionRecord,
)


@pytest.fixture
def recovery_db():
    schema = "recovery_restoration_test_" + uuid4().hex
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


def recovery_command(service):
    return CaptureRecoveryContext(
        context_id=uuid4(),
        expected_basis=service.current_basis(),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def seed_unresolved(db):
    now = datetime.now(UTC)
    task_id, cycle_id = uuid4(), uuid4()
    provider_id, attempt_id = uuid4(), uuid4()
    with Session(db) as session, session.begin():
        session.add(
            ResearchTaskRecord(
                id=task_id,
                title="Protected restoration fixture",
                objective="Prepare restoration",
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
                id=uuid4(),
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
    return provider_id, attempt_id


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


def issue_authorizations(db, context_id):
    service = AuthorizationService(db)
    operator = service.issue_operator(
        IssueOperatorAuthorization(
            authorization_id=uuid4(),
            expected_authority_epoch_id=service.current_authority_epoch_id(),
            principal=OperatorPrincipal(kind="local_operator", principal_id="local-admin"),
            granted_capability="recovery_action",
            scope=(AuthorizationScopeItem(kind="recovery_context", target_id=context_id),),
            issuance_basis=(
                AuthorizationBasisReference(kind="recovery_context", record_id=context_id),
            ),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            replay_id=uuid4(),
            recovery_context_id=context_id,
        )
    )
    execution = service.issue_execution(
        IssueExecutionAuthorization(
            execution_authorization_id=uuid4(),
            expected_authority_epoch_id=service.current_authority_epoch_id(),
            execution_id=uuid4(),
            operator_authorization_id=operator.authorization_id,
            scope=operator.scope,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            replay_id=uuid4(),
            recovery_context_id=context_id,
        )
    )
    return operator, execution


def prepare_command(context, operator, execution):
    return PrepareProtectedRestoration(
        restoration_id=uuid4(),
        context_id=context.context_id,
        operator_authorization_id=operator.authorization_id,
        execution_authorization_id=execution.execution_authorization_id,
        expected_authority_epoch_id=context.authority_basis.authority_epoch_id,
        expected_security_state_version=context.authority_basis.version,
        requested_state=SecurityState.NORMAL,
        reason_code=SecurityReasonCode.RECOVERY_VERIFIED,
    )


def assert_fence_still_pending(db):
    with db.connect() as conn:
        row = conn.execute(
            text("SELECT state, version, recovery_bootstrap_pending FROM security_state")
        ).one()
    assert row.state == "normal"
    assert row.recovery_bootstrap_pending is True


def test_prepare_protected_restoration_succeeds_without_clearing_fence(recovery_db):
    provider_id, attempt_id = seed_unresolved(recovery_db)
    context_service = RecoveryContextService(recovery_db)
    context = context_service.capture(recovery_command(context_service))
    finish_operations(recovery_db, provider_id, attempt_id)
    operator, execution = issue_authorizations(recovery_db, context.context_id)

    prepared = RecoveryRestorationService(recovery_db).prepare(
        prepare_command(context, operator, execution)
    )

    assert prepared.context_id == context.context_id
    assert prepared.incident_id == context.incident_id
    assert prepared.restoration_allowed is True
    assert prepared.requested_state is SecurityState.NORMAL
    assert_fence_still_pending(recovery_db)


def test_complete_protected_restoration_clears_fence_and_writes_audit(recovery_db):
    provider_id, attempt_id = seed_unresolved(recovery_db)
    context_service = RecoveryContextService(recovery_db)
    context = context_service.capture(recovery_command(context_service))
    finish_operations(recovery_db, provider_id, attempt_id)
    operator, execution = issue_authorizations(recovery_db, context.context_id)
    command = prepare_command(context, operator, execution)

    result = RecoveryRestorationService(recovery_db).complete(command)

    assert result.context_id == context.context_id
    assert result.incident_id == context.incident_id
    assert result.state is SecurityState.NORMAL
    assert result.version == context.authority_basis.version + 1
    with Session(recovery_db) as session:
        state = SecurityStateStore(session).load()
        audit = session.get(SecurityTransitionRecord, result.transition_id)
    assert state.state is SecurityState.NORMAL
    assert state.version == result.version
    assert state.recovery_bootstrap_pending is False
    assert audit is not None
    assert audit.previous_state == "recovery_required"
    assert audit.new_state == "normal"
    assert audit.reason_code == "RECOVERY_VERIFIED"
    assert audit.actor_type == "security_recovery_service"
    assert audit.security_state_version == result.version
    assert str(command.restoration_id) in audit.related_event_ids
    assert str(context.context_id) in audit.related_event_ids


def test_complete_protected_restoration_rolls_back_when_audit_fails(recovery_db):
    provider_id, attempt_id = seed_unresolved(recovery_db)
    context_service = RecoveryContextService(recovery_db)
    context = context_service.capture(recovery_command(context_service))
    finish_operations(recovery_db, provider_id, attempt_id)
    operator, execution = issue_authorizations(recovery_db, context.context_id)

    def reject_audit(*args, **kwargs):
        raise RuntimeError("restoration audit unavailable")

    event.listen(SecurityTransitionRecord, "before_insert", reject_audit)
    try:
        with pytest.raises(RuntimeError, match="restoration audit unavailable"):
            RecoveryRestorationService(recovery_db).complete(
                prepare_command(context, operator, execution)
            )
    finally:
        event.remove(SecurityTransitionRecord, "before_insert", reject_audit)

    assert_fence_still_pending(recovery_db)
    with Session(recovery_db) as session:
        assert session.scalars(select(SecurityTransitionRecord)).all() == []


def test_complete_protected_restoration_rejects_repeated_command_after_success(recovery_db):
    provider_id, attempt_id = seed_unresolved(recovery_db)
    context_service = RecoveryContextService(recovery_db)
    context = context_service.capture(recovery_command(context_service))
    finish_operations(recovery_db, provider_id, attempt_id)
    operator, execution = issue_authorizations(recovery_db, context.context_id)
    command = prepare_command(context, operator, execution)
    RecoveryRestorationService(recovery_db).complete(command)

    with pytest.raises(ProtectedRestorationDenied, match="not pending"):
        RecoveryRestorationService(recovery_db).complete(command)
    with Session(recovery_db) as session:
        assert len(session.scalars(select(SecurityTransitionRecord)).all()) == 1


def test_prepare_rejects_until_reconciliation_passes(recovery_db):
    seed_unresolved(recovery_db)
    context_service = RecoveryContextService(recovery_db)
    context = context_service.capture(recovery_command(context_service))
    operator, execution = issue_authorizations(recovery_db, context.context_id)

    with pytest.raises(ProtectedRestorationDenied, match="reconciliation"):
        RecoveryRestorationService(recovery_db).prepare(
            prepare_command(context, operator, execution)
        )
    assert_fence_still_pending(recovery_db)


def test_prepare_rejects_stale_expected_version(recovery_db):
    provider_id, attempt_id = seed_unresolved(recovery_db)
    context_service = RecoveryContextService(recovery_db)
    context = context_service.capture(recovery_command(context_service))
    finish_operations(recovery_db, provider_id, attempt_id)
    operator, execution = issue_authorizations(recovery_db, context.context_id)
    command = prepare_command(context, operator, execution).model_copy(
        update={"expected_security_state_version": context.authority_basis.version + 1}
    )

    with pytest.raises(ProtectedRestorationDenied, match="version"):
        RecoveryRestorationService(recovery_db).prepare(command)
    assert_fence_still_pending(recovery_db)


def test_prepare_rejects_authorization_bound_to_other_context(recovery_db):
    provider_id, attempt_id = seed_unresolved(recovery_db)
    context_service = RecoveryContextService(recovery_db)
    context = context_service.capture(recovery_command(context_service))
    finish_operations(recovery_db, provider_id, attempt_id)
    other_context_id = uuid4()
    operator, execution = issue_authorizations(recovery_db, other_context_id)

    with pytest.raises(ProtectedRestorationDenied, match="not bound"):
        RecoveryRestorationService(recovery_db).prepare(
            prepare_command(context, operator, execution)
        )
    assert_fence_still_pending(recovery_db)
