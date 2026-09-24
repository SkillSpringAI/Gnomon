"""M1.6 pass-1 authority epoch replacement after protected restoration."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session

from research_agent.application.authority_bootstrap import (
    AuthorityBootstrapService,
    AuthorityStartupMode,
)
from research_agent.application.authority_epoch_replacement_service import (
    AuthorityEpochReplacementDenied,
    AuthorityEpochReplacementService,
)
from research_agent.application.authorization_service import (
    AuthorizationConflict,
    AuthorizationService,
)
from research_agent.application.migrations import run_migrations
from research_agent.application.recovery_context_service import RecoveryContextService
from research_agent.application.recovery_restoration_service import RecoveryRestorationService
from research_agent.application.security_state_store import SecurityStateStore
from research_agent.domain.authorization import (
    AuthorizationBasisReference,
    AuthorizationCapability,
    AuthorizationScopeItem,
    IssueExecutionAuthorization,
    IssueOperatorAuthorization,
    OperatorPrincipal,
    validate_execution_authorization,
)
from research_agent.domain.recovery import (
    CaptureRecoveryContext,
    PrepareProtectedRestoration,
    ReplaceAuthorityEpoch,
)
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
    schema = "authority_epoch_replacement_test_" + uuid4().hex
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
                title="Authority epoch replacement fixture",
                objective="Replace authority lineage",
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


def restored(db):
    provider_id, attempt_id = seed_unresolved(db)
    context_service = RecoveryContextService(db)
    context = context_service.capture(recovery_command(context_service))
    finish_operations(db, provider_id, attempt_id)
    operator, execution = issue_authorizations(db, context.context_id)
    command = PrepareProtectedRestoration(
        restoration_id=uuid4(),
        context_id=context.context_id,
        operator_authorization_id=operator.authorization_id,
        execution_authorization_id=execution.execution_authorization_id,
        expected_authority_epoch_id=context.authority_basis.authority_epoch_id,
        expected_security_state_version=context.authority_basis.version,
        requested_state=SecurityState.NORMAL,
        reason_code=SecurityReasonCode.RECOVERY_VERIFIED,
    )
    result = RecoveryRestorationService(db).complete(command)
    return command, result, operator, execution


def replacement_command(result, *, new_epoch=None):
    return ReplaceAuthorityEpoch(
        replacement_id=uuid4(),
        restoration_id=result.restoration_id,
        restoration_transition_id=result.transition_id,
        expected_current_epoch_id=result.authority_epoch_id,
        expected_security_state_version=result.version,
        new_authority_epoch_id=new_epoch or uuid4(),
        reason_code=SecurityReasonCode.RECOVERY_VERIFIED,
    )


def test_replace_authority_epoch_after_protected_restoration(recovery_db):
    _, restoration, operator, execution = restored(recovery_db)
    command = replacement_command(restoration)

    result = AuthorityEpochReplacementService(recovery_db).replace(command)

    assert result.previous_authority_epoch_id == restoration.authority_epoch_id
    assert result.authority_epoch_id == command.new_authority_epoch_id
    assert result.version == restoration.version + 1
    with Session(recovery_db) as session:
        state = SecurityStateStore(session).load()
        audit = session.get(SecurityTransitionRecord, result.transition_id)
    assert state.state is SecurityState.NORMAL
    assert state.authority_epoch_id.value == result.authority_epoch_id
    assert state.version == result.version
    assert audit is not None
    assert audit.previous_state == audit.new_state == "normal"
    assert audit.authority_epoch_id == result.authority_epoch_id
    assert str(command.replacement_id) in audit.related_event_ids
    with pytest.raises(ValueError, match="stale"):
        validate_execution_authorization(
            execution,
            operator,
            current_authority_epoch_id=result.authority_epoch_id,
            now=datetime.now(UTC),
        )


def test_epoch_replacement_splits_historical_replay_from_current_execution(recovery_db):
    _, restoration, _, old_execution = restored(recovery_db)
    context_id = old_execution.recovery_context_id
    assert context_id is not None
    replacement = AuthorityEpochReplacementService(recovery_db).replace(
        replacement_command(restoration)
    )
    service = AuthorizationService(recovery_db)

    historical_replay = service.issue_execution(
        IssueExecutionAuthorization(
            execution_authorization_id=old_execution.execution_authorization_id,
            expected_authority_epoch_id=old_execution.authority_epoch_id,
            execution_id=old_execution.execution_id,
            operator_authorization_id=old_execution.operator_authorization_id,
            scope=old_execution.scope,
            expires_at=old_execution.expires_at,
            replay_id=old_execution.replay_id,
            recovery_context_id=old_execution.recovery_context_id,
        )
    )

    assert historical_replay == old_execution
    with pytest.raises(AuthorizationConflict, match="not current"):
        service.require_current_execution(
            old_execution.execution_authorization_id,
            recovery_context_id=context_id,
            required_capability=AuthorizationCapability.RECOVERY_ACTION,
        )

    operator = service.issue_operator(
        IssueOperatorAuthorization(
            authorization_id=uuid4(),
            expected_authority_epoch_id=replacement.authority_epoch_id,
            principal=OperatorPrincipal(kind="local_operator", principal_id="local-admin"),
            granted_capability=AuthorizationCapability.RECOVERY_ACTION,
            scope=old_execution.scope,
            issuance_basis=(
                AuthorizationBasisReference(
                    kind="recovery_context",
                    record_id=context_id,
                ),
            ),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            replay_id=uuid4(),
            recovery_context_id=context_id,
        )
    )
    fresh_execution = service.issue_execution(
        IssueExecutionAuthorization(
            execution_authorization_id=uuid4(),
            expected_authority_epoch_id=replacement.authority_epoch_id,
            execution_id=uuid4(),
            operator_authorization_id=operator.authorization_id,
            scope=operator.scope,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            replay_id=uuid4(),
            recovery_context_id=context_id,
        )
    )

    assert (
        service.require_current_execution(
            fresh_execution.execution_authorization_id,
            recovery_context_id=context_id,
            required_capability=AuthorizationCapability.RECOVERY_ACTION,
        )
        == fresh_execution
    )


def test_replace_authority_epoch_requires_restoration_audit(recovery_db):
    _, restoration, _, _ = restored(recovery_db)
    command = replacement_command(restoration).model_copy(
        update={"restoration_transition_id": uuid4()}
    )

    with pytest.raises(AuthorityEpochReplacementDenied, match="Restoration audit"):
        AuthorityEpochReplacementService(recovery_db).replace(command)


def test_replace_authority_epoch_rejects_stale_version_and_repeated_command(recovery_db):
    _, restoration, _, _ = restored(recovery_db)
    command = replacement_command(restoration)
    AuthorityEpochReplacementService(recovery_db).replace(command)

    with pytest.raises(AuthorityEpochReplacementDenied, match="stale"):
        AuthorityEpochReplacementService(recovery_db).replace(command)
    with Session(recovery_db) as session:
        assert len(session.scalars(select(SecurityTransitionRecord)).all()) == 2


def test_replace_authority_epoch_rolls_back_when_audit_fails(recovery_db):
    _, restoration, _, _ = restored(recovery_db)
    command = replacement_command(restoration)

    def reject_audit(*args, **kwargs):
        raise RuntimeError("epoch audit unavailable")

    event.listen(SecurityTransitionRecord, "before_insert", reject_audit)
    try:
        with pytest.raises(RuntimeError, match="epoch audit unavailable"):
            AuthorityEpochReplacementService(recovery_db).replace(command)
    finally:
        event.remove(SecurityTransitionRecord, "before_insert", reject_audit)

    with Session(recovery_db) as session:
        state = SecurityStateStore(session).load()
        audits = session.scalars(select(SecurityTransitionRecord)).all()
    assert state.authority_epoch_id.value == restoration.authority_epoch_id
    assert state.version == restoration.version
    assert len(audits) == 1
