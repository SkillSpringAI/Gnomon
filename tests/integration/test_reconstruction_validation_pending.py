"""C3a persisted readiness and narrow recovery-entry denial."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from research_agent.application.authority_bootstrap import (
    AuthorityBootstrapService,
    AuthorityStartupMode,
)
from research_agent.application.authorization_service import (
    AuthorizationConflict,
    AuthorizationService,
)
from research_agent.application.backup_creation_service import (
    BackupCreationError,
    BackupCreationService,
)
from research_agent.application.backup_state_inspection_service import (
    BackupStateInspectionService,
    BackupStateInspectionUnavailable,
)
from research_agent.application.migrations import migration_files, run_migrations
from research_agent.application.recovery_context_service import (
    RecoveryContextConflict,
    RecoveryContextService,
)
from research_agent.application.recovery_restoration_service import (
    ProtectedRestorationDenied,
    RecoveryRestorationService,
)
from research_agent.application.security_state_service import (
    SecurityStateTransitionService,
    SecurityTransitionDenied,
)
from research_agent.application.security_state_store import (
    SecurityStateStore,
    SecurityStateUnavailable,
)
from research_agent.domain.authorization import (
    AuthorizationBasisReference,
    AuthorizationCapability,
    AuthorizationScopeItem,
    IssueExecutionAuthorization,
    IssueOperatorAuthorization,
    OperatorPrincipal,
)
from research_agent.domain.recovery import CaptureRecoveryContext, PrepareProtectedRestoration
from research_agent.domain.security import SecurityActor, SecurityReasonCode, SecurityState
from research_agent.persistence.database import engine


@pytest.fixture
def readiness_db():
    schema = "reconstruction_readiness_test_" + uuid4().hex
    with engine.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    isolated = create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        run_migrations(isolated)
        yield isolated
    finally:
        isolated.dispose()
        with engine.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')


def fence(db):
    with Session(db) as session:
        return AuthorityBootstrapService(session).initialize(AuthorityStartupMode.RECOVERY)


def block_validation(db):
    with db.begin() as conn:
        conn.execute(text("UPDATE security_state SET reconstruction_validation_pending=true"))


def context_command(service, context_id=None):
    return CaptureRecoveryContext(
        context_id=context_id or uuid4(),
        expected_basis=service.current_basis(),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def operator_command(service, context_id):
    return IssueOperatorAuthorization(
        authorization_id=uuid4(),
        expected_authority_epoch_id=service.current_authority_epoch_id(),
        principal=OperatorPrincipal(kind="local_operator", principal_id="local-admin"),
        granted_capability=AuthorizationCapability.RECOVERY_ACTION,
        scope=(AuthorizationScopeItem(kind="recovery_context", target_id=context_id),),
        issuance_basis=(
            AuthorizationBasisReference(kind="recovery_context", record_id=context_id),
        ),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        replay_id=uuid4(),
        recovery_context_id=context_id,
    )


def execution_command(service, operator):
    return IssueExecutionAuthorization(
        execution_authorization_id=uuid4(),
        expected_authority_epoch_id=service.current_authority_epoch_id(),
        execution_id=uuid4(),
        operator_authorization_id=operator.authorization_id,
        scope=operator.scope,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        replay_id=uuid4(),
        recovery_context_id=operator.recovery_context_id,
    )


@pytest.mark.parametrize("source_pending", [False, True])
def test_upgrade_defaults_existing_valid_authority_to_not_validation_pending(source_pending):
    schema = "readiness_upgrade_test_" + uuid4().hex
    with engine.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    isolated = create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        with isolated.begin() as conn:
            for path in migration_files():
                if path.name.startswith("035_"):
                    break
                conn.exec_driver_sql(path.read_text(encoding="utf-8"))
            if source_pending:
                conn.execute(
                    text("""
                    UPDATE security_state
                    SET state='lockdown', version=8, recovery_bootstrap_pending=true,
                        recovery_bootstrap_started_at=now(),
                        recovery_bootstrap_from_state='lockdown',
                        recovery_bootstrap_from_version=7
                """)
                )
            before = conn.execute(
                text("""
                SELECT state, version, authority_epoch_id, recovery_bootstrap_pending,
                       recovery_bootstrap_from_state, recovery_bootstrap_from_version
                FROM security_state WHERE id=1
            """)
            ).one()
            upgrade = next(path for path in migration_files() if path.name.startswith("035_"))
            conn.exec_driver_sql(upgrade.read_text(encoding="utf-8"))
            conn.exec_driver_sql(upgrade.read_text(encoding="utf-8"))
            after = conn.execute(
                text("""
                SELECT state, version, authority_epoch_id, recovery_bootstrap_pending,
                       recovery_bootstrap_from_state, recovery_bootstrap_from_version
                FROM security_state WHERE id=1
            """)
            ).one()
            assert after == before
            assert (
                conn.scalar(
                    text("""
                SELECT reconstruction_validation_pending FROM security_state WHERE id=1
            """)
                )
                is False
            )
        with Session(isolated) as session:
            current = SecurityStateStore(session).load()
        assert current.reconstruction_validation_pending is False
        assert current.recovery_bootstrap_pending is source_pending
    finally:
        isolated.dispose()
        with engine.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')


def test_pending_round_trip_requires_a_valid_bootstrap_and_survives_continuing_startup(
    readiness_db,
):
    with Session(readiness_db) as session:
        current = SecurityStateStore(session).load()
    assert current.reconstruction_validation_pending is False
    with pytest.raises(IntegrityError):
        block_validation(readiness_db)
    fence(readiness_db)
    block_validation(readiness_db)
    with Session(readiness_db) as session:
        current = AuthorityBootstrapService(session).initialize(AuthorityStartupMode.CONTINUING)
    assert current.state is SecurityState.RECOVERY_REQUIRED
    assert current.recovery_bootstrap_pending
    assert current.reconstruction_validation_pending
    with pytest.raises(IntegrityError):
        with readiness_db.begin() as conn:
            conn.execute(
                text("""
                UPDATE security_state SET version=recovery_bootstrap_from_version
            """)
            )
    with pytest.raises(IntegrityError):
        with readiness_db.begin() as conn:
            conn.execute(
                text("""
                UPDATE security_state SET recovery_bootstrap_pending=false,
                    recovery_bootstrap_started_at=NULL,
                    recovery_bootstrap_from_state=NULL,
                    recovery_bootstrap_from_version=NULL
            """)
            )
    with Session(readiness_db) as session:
        assert SecurityStateStore(session).load().reconstruction_validation_pending
    assert run_migrations(readiness_db) == []
    with Session(readiness_db) as session:
        assert SecurityStateStore(session).load().reconstruction_validation_pending


def test_loader_rejects_invalid_pending_shape_if_database_constraint_is_missing(readiness_db):
    with readiness_db.begin() as conn:
        conn.execute(
            text("""
            ALTER TABLE security_state
            DROP CONSTRAINT security_state_reconstruction_validation_pending_shape
        """)
        )
        conn.execute(
            text("""
            UPDATE security_state SET reconstruction_validation_pending=true
        """)
        )
    with Session(readiness_db) as session:
        with pytest.raises(SecurityStateUnavailable, match="reconstruction-validation"):
            SecurityStateStore(session).load()


def test_capture_and_current_read_reject_pending_even_for_historical_replay(readiness_db):
    fence(readiness_db)
    service = RecoveryContextService(readiness_db)
    request = context_command(service)
    context = service.capture(request)
    block_validation(readiness_db)
    with pytest.raises(RecoveryContextConflict, match="validation is pending"):
        service.capture(request)
    with pytest.raises(RecoveryContextConflict, match="validation is pending"):
        service.capture(context_command(service))
    assert service.read(context.context_id) == context
    with pytest.raises(RecoveryContextConflict, match="validation is pending"):
        service.read(context.context_id, require_current=True)
    with readiness_db.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM recovery_contexts")) == 1


def test_security_transition_and_protected_restoration_cannot_clear_gate(readiness_db):
    fence(readiness_db)
    contexts = RecoveryContextService(readiness_db)
    context = contexts.capture(context_command(contexts))
    authorizations = AuthorizationService(readiness_db)
    operator = authorizations.issue_operator(operator_command(authorizations, context.context_id))
    execution = authorizations.issue_execution(execution_command(authorizations, operator))
    block_validation(readiness_db)
    with Session(readiness_db) as session:
        with pytest.raises(SecurityTransitionDenied, match="pending"):
            SecurityStateTransitionService(session).transition(
                expected_version=2,
                requested_state=SecurityState.LOCKDOWN,
                actor_type=SecurityActor.LOCAL_OPERATOR,
                actor_id="operator",
                reason_code=SecurityReasonCode.OPERATOR_LOCKDOWN,
            )
    with pytest.raises(ProtectedRestorationDenied, match="validation is pending"):
        RecoveryRestorationService(readiness_db).prepare(
            PrepareProtectedRestoration(
                restoration_id=uuid4(),
                context_id=context.context_id,
                operator_authorization_id=operator.authorization_id,
                execution_authorization_id=execution.execution_authorization_id,
                expected_authority_epoch_id=context.authority_basis.authority_epoch_id,
                expected_security_state_version=context.authority_basis.version,
                requested_state=SecurityState.NORMAL,
                reason_code=SecurityReasonCode.RECOVERY_VERIFIED,
            )
        )
    with Session(readiness_db) as session:
        assert SecurityStateStore(session).load().reconstruction_validation_pending


def test_new_recovery_bound_authorizations_are_denied_while_pending(readiness_db):
    fence(readiness_db)
    service = AuthorizationService(readiness_db)
    operator_request = operator_command(service, uuid4())
    operator = service.issue_operator(operator_request)
    execution_request = execution_command(service, operator)
    execution = service.issue_execution(execution_request)
    block_validation(readiness_db)
    assert service.issue_operator(operator_request) == operator
    assert service.issue_execution(execution_request) == execution
    with pytest.raises(AuthorizationConflict, match="validation is pending"):
        service.issue_operator(operator_command(service, uuid4()))
    with pytest.raises(AuthorizationConflict, match="validation is pending"):
        service.issue_execution(execution_command(service, operator))
    with readiness_db.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM operator_authorizations")) == 1
        assert conn.scalar(text("SELECT count(*) FROM execution_authorizations")) == 1


def test_validation_pending_target_is_not_a_backup_source(readiness_db, tmp_path):
    fence(readiness_db)
    block_validation(readiness_db)
    with pytest.raises(BackupStateInspectionUnavailable, match="validation is pending"):
        BackupStateInspectionService(readiness_db).inspect(
            application_version="0.1.0", source_revision="316c90bf1816743ce73571e907b5c24e4da6cdec"
        )
    calls = []

    def runner(args, *, env, cwd=None):
        calls.append(args)

    with pytest.raises(BackupCreationError):
        BackupCreationService(readiness_db, runner=runner).create(
            tmp_path / "blocked-backup",
            application_version="0.1.0",
            source_revision="316c90bf1816743ce73571e907b5c24e4da6cdec",
        )
    assert not calls
    assert not (tmp_path / "blocked-backup").exists()


def test_backup_does_not_publish_when_validation_becomes_pending_during_dump(
    readiness_db, tmp_path
):
    fence(readiness_db)

    def runner(args, *, env, cwd=None):
        Path(args[args.index("--file") + 1]).write_bytes(b"simulated dump")
        block_validation(readiness_db)

    target = tmp_path / "interrupted-backup"
    with pytest.raises(BackupCreationError):
        BackupCreationService(readiness_db, runner=runner).create(
            target,
            application_version="0.1.0",
            source_revision="316c90bf1816743ce73571e907b5c24e4da6cdec",
        )
    assert not target.exists()
