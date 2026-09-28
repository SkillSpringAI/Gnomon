"""M2.5 database reconstruction service behavior before recovery startup."""

import shutil
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from subprocess import CalledProcessError, CompletedProcess
from threading import Event
from uuid import uuid4

import pytest
from m2_reconstruction_equivalence import assert_reconstruction_equivalent
from m2_reconstruction_fixture import seed_canonical_reconstruction_fixture
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
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
    DUMP_FILENAME,
    MANIFEST_FILENAME,
    BackupCreationError,
    BackupCreationService,
)
from research_agent.application.backup_state_inspection_service import (
    BackupStateInspectionService,
)
from research_agent.application.database_reconstruction_service import (
    DatabaseReconstructionError,
    DatabaseReconstructionService,
)
from research_agent.application.migrations import run_migrations
from research_agent.application.recovery_context_service import (
    RecoveryContextConflict,
    RecoveryContextService,
)
from research_agent.application.recovery_reconciliation_service import RecoveryReconciliationService
from research_agent.application.recovery_restoration_service import (
    ProtectedRestorationDenied,
    RecoveryRestorationService,
)
from research_agent.application.restore_preflight_service import RestorePreflightService
from research_agent.application.security_capability import (
    SecurityCapability,
    SecurityCapabilityDenied,
    require_capability,
)
from research_agent.application.security_state_store import SecurityStateStore
from research_agent.config.settings import get_settings
from research_agent.domain.authorization import (
    AuthorizationBasisReference,
    AuthorizationCapability,
    AuthorizationScopeItem,
    IssueExecutionAuthorization,
    IssueOperatorAuthorization,
    OperatorPrincipal,
)
from research_agent.domain.backup import BackupIntegrityMetadata, BackupManifest
from research_agent.domain.recovery import (
    CaptureRecoveryContext,
    PrepareProtectedRestoration,
    RecoveryOperationDisposition,
)
from research_agent.domain.security import SecurityReasonCode, SecurityState
from research_agent.persistence.authorization import ExecutionAuthorizationRecord
from research_agent.persistence.database import engine

SOURCE_REVISION = "316c90bf1816743ce73571e907b5c24e4da6cdec"
DUMP_BYTES = b"pg-restore-custom-bytes"
TEST_ARCHIVE_LISTING = "3; 0 103 TABLE DATA public research_tasks owner\n"


@pytest.fixture
def reconstruction_target_db():
    schema = "database_reconstruction_test_" + uuid4().hex
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


def manifest_from_target(db) -> BackupManifest:
    inspection = BackupStateInspectionService(db).inspect(
        application_version="0.1.0",
        source_revision=SOURCE_REVISION,
    )
    return BackupManifest(
        backup_id=uuid4(),
        created_at=datetime(2026, 9, 25, tzinfo=UTC),
        database=inspection.database,
        application=inspection.application,
        schema_metadata=inspection.schema_metadata,
        authority=inspection.authority,
        integrity=BackupIntegrityMetadata(dump_sha256=sha256(DUMP_BYTES).hexdigest()),
    )


def write_backup(tmp_path, manifest: BackupManifest, dump: bytes = DUMP_BYTES):
    backup = tmp_path / "backup-set"
    backup.mkdir()
    (backup / DUMP_FILENAME).write_bytes(dump)
    (backup / MANIFEST_FILENAME).write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return backup


def test_reconstruction_runs_restore_and_verifies_target(
    reconstruction_target_db, tmp_path
):
    manifest = manifest_from_target(reconstruction_target_db)
    backup = write_backup(tmp_path, manifest)
    task_id = uuid4()

    def runner(args, *, env, cwd=None):
        if "--list" in args:
            return CompletedProcess(args, 0, TEST_ARCHIVE_LISTING, "")
        assert "--data-only" in args
        assert "--single-transaction" in args
        assert "--use-list" in args
        assert cwd == backup
        with reconstruction_target_db.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO research_tasks (
                        id, title, objective, status, brief, plan, created_at, updated_at
                    )
                    VALUES (:id, 'Reconstructed', 'Verify reconstruction.', 'active',
                            '{}'::jsonb, '{}'::jsonb, now(), now())
                    """
                ),
                {"id": task_id},
            )

    result = DatabaseReconstructionService(
        reconstruction_target_db,
        runner=runner,
        environment={"PATH": "test"},
    ).reconstruct(backup)

    assert result.applied_migrations == ()
    assert result.recovery_context_id is not None
    with reconstruction_target_db.connect() as conn:
        assert conn.scalar(
            text("SELECT title FROM research_tasks WHERE id = :id"), {"id": task_id}
        ) == "Reconstructed"
        restored = conn.execute(
            text(
                """
                SELECT state, version, authority_epoch_id, recovery_bootstrap_pending,
                       recovery_bootstrap_from_state, recovery_bootstrap_from_version,
                       reconstruction_validation_pending
                FROM security_state WHERE id = 1
                """
            )
        ).one()
    assert restored.state == manifest.authority.security_state.value
    assert restored.version == manifest.authority.security_state_version + 1
    assert restored.authority_epoch_id == manifest.authority.authority_epoch_id
    assert restored.recovery_bootstrap_pending is True
    assert restored.recovery_bootstrap_from_state == manifest.authority.security_state.value
    assert restored.recovery_bootstrap_from_version == manifest.authority.security_state_version
    assert restored.reconstruction_validation_pending is False
    context = RecoveryContextService(reconstruction_target_db).read(result.recovery_context_id)
    assert context.authority_basis.version == manifest.authority.security_state_version + 1
    assert context.authority_basis.authority_epoch_id == manifest.authority.authority_epoch_id
    assert context.authority_basis.bootstrap_origin is not None
    assert context.authority_basis.bootstrap_origin.state is manifest.authority.security_state
    assert (
        context.authority_basis.bootstrap_origin.version
        == manifest.authority.security_state_version
    )


@pytest.mark.parametrize("stored_state", list(SecurityState))
@pytest.mark.parametrize("source_pending", [False, True])
def test_reconstruction_enters_recovery_with_new_context(
    reconstruction_target_db, tmp_path, stored_state, source_pending
):
    original = manifest_from_target(reconstruction_target_db)
    manifest = original.model_copy(
        update={
            "authority": original.authority.model_copy(
                update={
                    "security_state": stored_state,
                    "security_state_version": 7,
                    "recovery_bootstrap_pending": source_pending,
                }
            )
        }
    )
    backup = write_backup(tmp_path, manifest)
    historical_id = uuid4()

    def runner(args, *, env, cwd=None):
        if "--list" in args:
            return CompletedProcess(args, 0, TEST_ARCHIVE_LISTING, "")
        with reconstruction_target_db.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO recovery_contexts (
                        context_id, incident_id, authority_epoch_id,
                        security_state_version, created_at, expires_at,
                        context, command
                    ) VALUES (
                        :context_id, :incident_id, :epoch_id, 5,
                        now() - interval '2 hours', now() - interval '1 hour',
                        '{}'::jsonb, '{}'::jsonb
                    )
                    """
                ),
                {
                    "context_id": historical_id,
                    "incident_id": uuid4(),
                    "epoch_id": manifest.authority.authority_epoch_id,
                },
            )

    result = DatabaseReconstructionService(reconstruction_target_db, runner=runner).reconstruct(
        backup
    )
    assert result.recovery_context_id is not None
    assert result.recovery_context_id != historical_id
    with reconstruction_target_db.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT state, version, recovery_bootstrap_pending,
                       recovery_bootstrap_from_state, recovery_bootstrap_from_version
                FROM security_state WHERE id = 1
                """
            )
        ).one()
        assert conn.scalar(text("SELECT count(*) FROM recovery_contexts")) == 2
        context = conn.scalar(
            text("SELECT context FROM recovery_contexts WHERE context_id = :id"),
            {"id": result.recovery_context_id},
        )
    assert row.state == stored_state.value
    assert row.version == 8
    assert row.recovery_bootstrap_pending is True
    assert row.recovery_bootstrap_from_state == stored_state.value
    assert row.recovery_bootstrap_from_version == 7
    assert context["authority_basis"]["state"] == SecurityState.RECOVERY_REQUIRED.value
    assert context["authority_basis"]["bootstrap_origin"]["state"] == stored_state.value
    assert context["authority_basis"]["bootstrap_origin"]["version"] == 7
    assert context["authority_basis"]["version"] == 8
    assert context["authority_basis"]["authority_epoch_id"] == str(
        manifest.authority.authority_epoch_id
    )
    with Session(reconstruction_target_db) as session:
        current = AuthorityBootstrapService(session).initialize(AuthorityStartupMode.CONTINUING)
        assert current.state is SecurityState.RECOVERY_REQUIRED
        assert current.version == 8
        assert SecurityStateStore(session).load().recovery_bootstrap_pending
        with pytest.raises(SecurityCapabilityDenied):
            require_capability(session, SecurityCapability.MEMORY_MUTATION)
    assert RecoveryContextService(reconstruction_target_db).read(
        result.recovery_context_id, require_current=True
    ).context_id == result.recovery_context_id


def test_failed_pg_restore_leaves_committed_validation_pending_fence(
    reconstruction_target_db, tmp_path
):
    backup = write_backup(tmp_path, manifest_from_target(reconstruction_target_db))

    def runner(args, *, env, cwd=None):
        if "--list" in args:
            return CompletedProcess(args, 0, TEST_ARCHIVE_LISTING, "")
        raise CalledProcessError(1, args, stderr="pg_restore: error: COPY research_tasks failed")

    with pytest.raises(DatabaseReconstructionError, match="COPY research_tasks failed"):
        DatabaseReconstructionService(
            reconstruction_target_db,
            runner=runner,
        ).reconstruct(backup)

    with reconstruction_target_db.connect() as conn:
        row = conn.execute(text("SELECT * FROM security_state WHERE id=1")).one()
    assert row.recovery_bootstrap_pending is True
    assert row.reconstruction_validation_pending is True
    assert row.version == 2


def test_restart_cannot_publish_an_interrupted_reconstruction(reconstruction_target_db, tmp_path):
    backup = write_backup(tmp_path, manifest_from_target(reconstruction_target_db))

    def runner(args, *, env, cwd=None):
        if "--list" in args:
            return CompletedProcess(args, 0, TEST_ARCHIVE_LISTING, "")
        raise CalledProcessError(1, args, stderr="interrupted import")

    with pytest.raises(DatabaseReconstructionError, match="interrupted import"):
        DatabaseReconstructionService(reconstruction_target_db, runner=runner).reconstruct(backup)
    with Session(reconstruction_target_db) as session:
        for mode in (AuthorityStartupMode.CONTINUING, AuthorityStartupMode.RECOVERY):
            current = AuthorityBootstrapService(session).initialize(mode)
            assert current.state is SecurityState.RECOVERY_REQUIRED
            assert current.version == 2
            assert current.recovery_bootstrap_pending
            assert current.reconstruction_validation_pending
    contexts = RecoveryContextService(reconstruction_target_db)
    with pytest.raises(RecoveryContextConflict, match="validation is pending"):
        contexts.capture(
            CaptureRecoveryContext(
                context_id=uuid4(),
                expected_basis=contexts.current_basis(),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )


def test_restore_list_failure_leaves_pristine_authority(reconstruction_target_db, tmp_path):
    backup = write_backup(tmp_path, manifest_from_target(reconstruction_target_db))
    with reconstruction_target_db.connect() as conn:
        before = conn.scalar(text("SELECT to_jsonb(s) FROM security_state s"))

    def runner(args, *, env, cwd=None):
        assert "--list" in args
        raise CalledProcessError(1, args, stderr="listing failed")

    with pytest.raises(DatabaseReconstructionError, match="listing failed"):
        DatabaseReconstructionService(reconstruction_target_db, runner=runner).reconstruct(backup)
    with reconstruction_target_db.connect() as conn:
        assert conn.scalar(text("SELECT to_jsonb(s) FROM security_state s")) == before


def test_fence_transaction_failure_rolls_back_all_manifest_authority(
    reconstruction_target_db, tmp_path
):
    original = manifest_from_target(reconstruction_target_db)
    manifest = original.model_copy(
        update={"authority": original.authority.model_copy(update={"security_state_version": 7})}
    )
    backup = write_backup(tmp_path, manifest)
    with reconstruction_target_db.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE security_state ADD CONSTRAINT test_pristine_version "
                "CHECK (version = 1)"
            )
        )
    with reconstruction_target_db.connect() as conn:
        before = conn.scalar(text("SELECT to_jsonb(s) FROM security_state s"))
    calls = []

    def runner(args, *, env, cwd=None):
        calls.append(args)
        assert "--list" in args
        return CompletedProcess(args, 0, TEST_ARCHIVE_LISTING, "")

    with pytest.raises(DatabaseReconstructionError):
        DatabaseReconstructionService(reconstruction_target_db, runner=runner).reconstruct(backup)
    assert len(calls) == 1
    with reconstruction_target_db.connect() as conn:
        assert conn.scalar(text("SELECT to_jsonb(s) FROM security_state s")) == before


def test_context_capture_failure_keeps_reconstruction_fenced(
    reconstruction_target_db, tmp_path, monkeypatch
):
    backup = write_backup(tmp_path, manifest_from_target(reconstruction_target_db))

    def runner(args, *, env, cwd=None):
        if "--list" in args:
            return CompletedProcess(args, 0, TEST_ARCHIVE_LISTING, "")

    def fail_capture(self, request):
        raise RecoveryContextConflict("simulated capture failure")

    monkeypatch.setattr(RecoveryContextService, "capture", fail_capture)
    with pytest.raises(DatabaseReconstructionError, match="context capture failed"):
        DatabaseReconstructionService(reconstruction_target_db, runner=runner).reconstruct(backup)
    with Session(reconstruction_target_db) as session:
        state = SecurityStateStore(session).load()
    assert state.state is SecurityState.RECOVERY_REQUIRED
    assert state.recovery_bootstrap_pending
    assert not state.reconstruction_validation_pending


def test_failed_readiness_update_keeps_validation_pending(reconstruction_target_db, tmp_path):
    backup = write_backup(tmp_path, manifest_from_target(reconstruction_target_db))

    def runner(args, *, env, cwd=None):
        if "--list" in args:
            return CompletedProcess(args, 0, TEST_ARCHIVE_LISTING, "")
        with reconstruction_target_db.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE security_state ADD CONSTRAINT test_validation_pending "
                    "CHECK (reconstruction_validation_pending = true)"
                )
            )

    with pytest.raises(DatabaseReconstructionError):
        DatabaseReconstructionService(reconstruction_target_db, runner=runner).reconstruct(backup)
    with reconstruction_target_db.connect() as conn:
        row = conn.execute(text("SELECT * FROM security_state WHERE id=1")).one()
        assert row.recovery_bootstrap_pending is True
        assert row.reconstruction_validation_pending is True
        assert row.version == 2
        assert conn.scalar(text("SELECT count(*) FROM recovery_contexts")) == 0


@pytest.mark.parametrize("wrong_field", ["state", "version", "epoch"])
def test_readiness_rejects_changed_manifest_authority_basis(
    reconstruction_target_db, tmp_path, wrong_field
):
    backup = write_backup(tmp_path, manifest_from_target(reconstruction_target_db))

    def runner(args, *, env, cwd=None):
        if "--list" in args:
            return CompletedProcess(args, 0, TEST_ARCHIVE_LISTING, "")
        statement = {
            "state": "UPDATE security_state SET state='lockdown' WHERE id=1",
            "version": "UPDATE security_state SET version=version+1 WHERE id=1",
            "epoch": "UPDATE security_state SET authority_epoch_id=:epoch WHERE id=1",
        }[wrong_field]
        with reconstruction_target_db.begin() as conn:
            conn.execute(text(statement), {"epoch": uuid4()})

    with pytest.raises(DatabaseReconstructionError, match="basis mismatch"):
        DatabaseReconstructionService(reconstruction_target_db, runner=runner).reconstruct(backup)
    with reconstruction_target_db.connect() as conn:
        row = conn.execute(text("SELECT * FROM security_state WHERE id=1")).one()
        assert row.recovery_bootstrap_pending is True
        assert row.reconstruction_validation_pending is True
        assert conn.scalar(text("SELECT count(*) FROM recovery_contexts")) == 0


def test_reconstruction_rejects_malformed_restored_authority(
    reconstruction_target_db, tmp_path
):
    manifest = manifest_from_target(reconstruction_target_db)
    backup = write_backup(tmp_path, manifest)

    def runner(args, *, env, cwd=None):
        if "--list" in args:
            return CompletedProcess(args, 0, TEST_ARCHIVE_LISTING, "")
        with reconstruction_target_db.begin() as conn:
            conn.execute(text("DELETE FROM security_state"))

    with pytest.raises(DatabaseReconstructionError):
        DatabaseReconstructionService(
            reconstruction_target_db,
            runner=runner,
        ).reconstruct(backup)


@pytest.mark.skipif(
    shutil.which("pg_dump") is None or shutil.which("pg_restore") is None,
    reason="pg_dump and pg_restore are not installed",
)
@pytest.mark.parametrize("variant", ["baseline", "restrictive_unresolved"])
def test_real_pg_restore_reconstructs_task_data(tmp_path, variant):
    base_url = make_url(get_settings().database_url)
    if base_url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("real reconstruction integration requires local PostgreSQL")
    source_database = "database_reconstruction_source_" + uuid4().hex
    target_database = "database_reconstruction_target_" + uuid4().hex
    admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
    created: list[str] = []
    source = create_engine(base_url.set(database=source_database))
    target = create_engine(base_url.set(database=target_database))
    task_id = uuid4()
    try:
        try:
            with admin.connect() as conn:
                conn.exec_driver_sql(f'CREATE DATABASE "{source_database}"')
                created.append(source_database)
                conn.exec_driver_sql(f'CREATE DATABASE "{target_database}"')
                created.append(target_database)
        except SQLAlchemyError as exc:
            pytest.skip(f"cannot create disposable databases: {exc}")
        run_migrations(source)
        run_migrations(target)
        with source.begin() as conn:
            fixture = seed_canonical_reconstruction_fixture(conn, variant=variant)
            conn.execute(
                text(
                    """
                    INSERT INTO research_tasks (
                        id, title, objective, status, brief, plan, created_at, updated_at
                    )
                    VALUES (:id, 'Real restore', 'Verify pg_restore.', 'active',
                            '{}'::jsonb, '{}'::jsonb, now(), now())
                    """
                ),
                {"id": task_id},
            )
        backup = BackupCreationService(source).create(
            tmp_path / "backup-set",
            application_version="0.1.0",
            source_revision=SOURCE_REVISION,
        )
        service = DatabaseReconstructionService(target)
        verified = service._restore_verified_data(backup.backup_directory)
        with target.connect() as conn:
            assert conn.scalar(
                text("SELECT title FROM research_tasks WHERE id = :id"),
                {"id": task_id},
            ) == "Real restore"
        assert_reconstruction_equivalent(
            source, target, task_id=fixture.task_id, reconstruction_fenced=True
        )
        recovered = service._enter_recovery(verified)
        assert recovered.recovery_context_id is not None
        assert recovered.recovery_context_id != fixture.recovery_context_id
        basis = RecoveryContextService(target).current_basis()
        assert basis.state is SecurityState.RECOVERY_REQUIRED
        assert basis.bootstrap_origin is not None
        assert basis.bootstrap_origin.state.value == fixture.security_state
        assert basis.bootstrap_origin.version == fixture.security_state_version
        context_id = recovered.recovery_context_id
        reconciliation = RecoveryReconciliationService(target).reconcile(context_id)
        authorizations = AuthorizationService(target)
        operator = authorizations.issue_operator(
            IssueOperatorAuthorization(
                authorization_id=uuid4(),
                expected_authority_epoch_id=basis.authority_epoch_id,
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
        execution = authorizations.issue_execution(
            IssueExecutionAuthorization(
                execution_authorization_id=uuid4(),
                expected_authority_epoch_id=basis.authority_epoch_id,
                execution_id=uuid4(),
                operator_authorization_id=operator.authorization_id,
                scope=operator.scope,
                expires_at=datetime.now(UTC) + timedelta(minutes=30),
                replay_id=uuid4(),
                recovery_context_id=context_id,
            )
        )
        command = PrepareProtectedRestoration(
            restoration_id=uuid4(),
            context_id=context_id,
            operator_authorization_id=operator.authorization_id,
            execution_authorization_id=execution.execution_authorization_id,
            expected_authority_epoch_id=basis.authority_epoch_id,
            expected_security_state_version=basis.version,
            requested_state=SecurityState.NORMAL,
            reason_code=SecurityReasonCode.RECOVERY_VERIFIED,
        )
        restoration = RecoveryRestorationService(target)
        if variant == "restrictive_unresolved":
            assert not reconciliation.restoration_allowed
            assert any(
                operation.disposition is RecoveryOperationDisposition.UNKNOWN
                for operation in reconciliation.operations
            )
            with pytest.raises(ProtectedRestorationDenied, match="reconciliation"):
                restoration.complete(command)
            assert RecoveryContextService(target).current_basis().recovery_bootstrap_pending
        else:
            assert reconciliation.restoration_allowed
            stale = command.model_copy(
                update={
                    "operator_authorization_id": fixture.operator_authorization_id,
                    "execution_authorization_id": fixture.execution_authorization_id,
                }
            )
            with pytest.raises(ProtectedRestorationDenied):
                restoration.complete(stale)
            completed, replacement = restoration.complete_reconstruction(
                command,
                replacement_id=uuid4(),
                new_authority_epoch_id=uuid4(),
            )
            assert completed.state is SecurityState.NORMAL
            assert completed.authority_epoch_id == basis.authority_epoch_id
            assert replacement.previous_authority_epoch_id == basis.authority_epoch_id
            assert replacement.authority_epoch_id != basis.authority_epoch_id
            assert replacement.version == completed.version + 1
            assert not RecoveryContextService(target).current_basis().recovery_bootstrap_pending
            assert (
                RecoveryContextService(target).current_basis().authority_epoch_id
                == replacement.authority_epoch_id
            )
            with Session(target) as session:
                historical = session.get(
                    ExecutionAuthorizationRecord,
                    fixture.execution_authorization_id,
                )
                assert historical is not None
                assert historical.authority_epoch_id == basis.authority_epoch_id
            historical_replay = authorizations.issue_execution(
                IssueExecutionAuthorization(
                    execution_authorization_id=execution.execution_authorization_id,
                    expected_authority_epoch_id=execution.authority_epoch_id,
                    execution_id=execution.execution_id,
                    operator_authorization_id=execution.operator_authorization_id,
                    scope=execution.scope,
                    expires_at=execution.expires_at,
                    replay_id=execution.replay_id,
                    recovery_context_id=execution.recovery_context_id,
                )
            )
            assert historical_replay == execution
            with pytest.raises(AuthorizationConflict, match="not current"):
                authorizations.require_current_execution(
                    execution.execution_authorization_id,
                    recovery_context_id=context_id,
                    required_capability=AuthorizationCapability.RECOVERY_ACTION,
                )
            fresh_operator = authorizations.issue_operator(
                IssueOperatorAuthorization(
                    authorization_id=uuid4(),
                    expected_authority_epoch_id=replacement.authority_epoch_id,
                    principal=OperatorPrincipal(
                        kind="local_operator", principal_id="local-admin"
                    ),
                    granted_capability=AuthorizationCapability.RECOVERY_ACTION,
                    scope=operator.scope,
                    issuance_basis=(
                        AuthorizationBasisReference(
                            kind="recovery_context", record_id=context_id
                        ),
                    ),
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    replay_id=uuid4(),
                    recovery_context_id=context_id,
                )
            )
            fresh_execution = authorizations.issue_execution(
                IssueExecutionAuthorization(
                    execution_authorization_id=uuid4(),
                    expected_authority_epoch_id=replacement.authority_epoch_id,
                    execution_id=uuid4(),
                    operator_authorization_id=fresh_operator.authorization_id,
                    scope=fresh_operator.scope,
                    expires_at=datetime.now(UTC) + timedelta(minutes=30),
                    replay_id=uuid4(),
                    recovery_context_id=context_id,
                )
            )
            assert (
                authorizations.require_current_execution(
                    fresh_execution.execution_authorization_id,
                    recovery_context_id=context_id,
                    required_capability=AuthorizationCapability.RECOVERY_ACTION,
                )
                == fresh_execution
            )
    finally:
        source.dispose()
        target.dispose()
        for database in reversed(created):
            with admin.connect() as conn:
                conn.exec_driver_sql(f'DROP DATABASE "{database}" WITH (FORCE)')
        admin.dispose()


@pytest.mark.parametrize("stored_state", list(SecurityState))
def test_internal_boundary_has_manifest_authority_with_fence_and_no_new_grants(
    reconstruction_target_db, tmp_path, stored_state
):
    original = manifest_from_target(reconstruction_target_db)
    manifest = original.model_copy(
        update={
            "authority": original.authority.model_copy(
                update={
                    "security_state": stored_state,
                    "security_state_version": 7,
                    "recovery_bootstrap_pending": True,
                }
            )
        }
    )
    backup = write_backup(tmp_path, manifest)

    def runner(args, *, env, cwd=None):
        if "--list" in args:
            return CompletedProcess(args, 0, TEST_ARCHIVE_LISTING, "")

    result = DatabaseReconstructionService(
        reconstruction_target_db, runner=runner
    )._restore_verified_data(backup)
    assert result.recovery_context_id is None
    with reconstruction_target_db.connect() as conn:
        row = conn.execute(text("SELECT * FROM security_state WHERE id = 1")).one()
        assert row.state == stored_state.value
        assert row.version == 8
        assert row.authority_epoch_id == manifest.authority.authority_epoch_id
        assert row.recovery_bootstrap_pending is True
        assert row.reconstruction_validation_pending is False
        assert row.recovery_bootstrap_started_at is not None
        assert row.recovery_bootstrap_from_state == stored_state.value
        assert row.recovery_bootstrap_from_version == 7
        for table in (
            "recovery_contexts",
            "recovery_context_audit",
            "operator_authorizations",
            "execution_authorizations",
            "authorization_audit",
        ):
            assert conn.scalar(text(f"SELECT count(*) FROM {table}")) == 0
    with Session(reconstruction_target_db) as session:
        state = AuthorityBootstrapService(session).initialize(AuthorityStartupMode.CONTINUING)
        assert state.state is SecurityState.RECOVERY_REQUIRED
        assert state.recovery_bootstrap_pending
        with pytest.raises(SecurityCapabilityDenied):
            require_capability(session, SecurityCapability.MEMORY_MUTATION)


@pytest.mark.parametrize("failure_phase", ["migration", "inspection", "critical", "publication"])
def test_failure_after_restore_leaves_validation_pending_target_and_retry_is_denied(
    reconstruction_target_db, tmp_path, monkeypatch, failure_phase
):
    import research_agent.application.database_reconstruction_service as module

    original = manifest_from_target(reconstruction_target_db)
    manifest = original.model_copy(
        update={"authority": original.authority.model_copy(update={"security_state_version": 7})}
    )
    backup = write_backup(tmp_path, manifest)
    restores = []

    def runner(args, *, env, cwd=None):
        if "--list" in args:
            return CompletedProcess(args, 0, TEST_ARCHIVE_LISTING, "")
        restores.append(args)
        with reconstruction_target_db.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO research_tasks (
                    id, title, objective, status, brief, plan, created_at, updated_at
                ) VALUES (:id, 'Committed import', 'Characterize failure', 'active',
                          '{}'::jsonb, '{}'::jsonb, now(), now())
            """),
                {"id": uuid4()},
            )

    service = DatabaseReconstructionService(reconstruction_target_db, runner=runner)

    def fail(*args, **kwargs):
        raise DatabaseReconstructionError("injected post-import failure")

    with monkeypatch.context() as patch:
        if failure_phase == "migration":
            patch.setattr(module, "run_migrations", fail)
        elif failure_phase == "inspection":
            inspect = module.BackupStateInspectionService._migration_entries

            def fail_after_import(session):
                if restores:
                    fail()
                return inspect(session)

            patch.setattr(
                module.BackupStateInspectionService,
                "_migration_entries",
                staticmethod(fail_after_import),
            )
        elif failure_phase == "critical":
            patch.setattr(service, "_verify_critical_tables", fail)
        else:
            patch.setattr(service, "_publish_reconstruction_readiness", fail)
        with pytest.raises(DatabaseReconstructionError, match="injected"):
            service.reconstruct(backup)
    with reconstruction_target_db.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM research_tasks")) == 1
        assert conn.scalar(text("SELECT count(*) FROM recovery_contexts")) == 0
    with Session(reconstruction_target_db) as session:
        current = SecurityStateStore(session).load()
        assert current.version == 8
        assert current.recovery_bootstrap_pending
        assert current.reconstruction_validation_pending
        with pytest.raises(SecurityCapabilityDenied):
            require_capability(session, SecurityCapability.MEMORY_MUTATION)
    with pytest.raises(DatabaseReconstructionError) as exc:
        service.reconstruct(backup)
    assert "preflight failed" in str(exc.value.__cause__)
    assert len(restores) == 1


def test_restore_runner_observes_final_fenced_target_before_import(
    reconstruction_target_db, tmp_path
):
    backup = write_backup(tmp_path, manifest_from_target(reconstruction_target_db))
    observed = []

    def runner(args, *, env, cwd=None):
        if "--list" in args:
            return CompletedProcess(args, 0, TEST_ARCHIVE_LISTING, "")
        with reconstruction_target_db.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT state, version, authority_epoch_id, recovery_bootstrap_pending, "
                    "reconstruction_validation_pending, recovery_bootstrap_from_state, "
                    "recovery_bootstrap_from_version "
                    "FROM security_state WHERE id = 1"
                )
            ).one()
            observed.append(row)
        raise CalledProcessError(1, args, stderr="injected before import")

    with pytest.raises(DatabaseReconstructionError, match="injected before import"):
        DatabaseReconstructionService(reconstruction_target_db, runner=runner).reconstruct(backup)
    assert len(observed) == 1
    assert observed[0].state == SecurityState.NORMAL.value
    assert observed[0].version == 2
    assert observed[0].recovery_bootstrap_pending is True
    assert observed[0].reconstruction_validation_pending is True
    assert observed[0].recovery_bootstrap_from_state == SecurityState.NORMAL.value
    assert observed[0].recovery_bootstrap_from_version == 1


def test_context_capture_racing_readiness_publication_sees_one_committed_basis(
    reconstruction_target_db, tmp_path, monkeypatch
):
    backup = write_backup(tmp_path, manifest_from_target(reconstruction_target_db))
    imported = Event()
    allow_validation = Event()
    locked = Event()
    allow_publication = Event()

    def runner(args, *, env, cwd=None):
        if "--list" in args:
            return CompletedProcess(args, 0, TEST_ARCHIVE_LISTING, "")
        imported.set()
        assert allow_validation.wait(10)

    service = DatabaseReconstructionService(reconstruction_target_db, runner=runner)
    verify = service._verify_critical_tables

    def pause_validation(conn):
        locked.set()
        assert allow_publication.wait(10)
        return verify(conn)

    monkeypatch.setattr(service, "_verify_critical_tables", pause_validation)
    with ThreadPoolExecutor(max_workers=3) as pool:
        reconstruction = pool.submit(service._restore_verified_data, backup)
        assert imported.wait(10)
        contexts = RecoveryContextService(reconstruction_target_db)
        pending_basis = contexts.current_basis()
        assert pending_basis.recovery_bootstrap_pending
        request = CaptureRecoveryContext(
            context_id=uuid4(),
            expected_basis=pending_basis,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        authorizations = AuthorizationService(reconstruction_target_db)
        operator_request = IssueOperatorAuthorization(
            authorization_id=uuid4(),
            expected_authority_epoch_id=pending_basis.authority_epoch_id,
            principal=OperatorPrincipal(kind="local_operator", principal_id="local-admin"),
            granted_capability="recovery_action",
            scope=(AuthorizationScopeItem(kind="recovery_context", target_id=request.context_id),),
            issuance_basis=(
                AuthorizationBasisReference(kind="recovery_context", record_id=request.context_id),
            ),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            replay_id=uuid4(),
            recovery_context_id=request.context_id,
        )
        allow_validation.set()
        assert locked.wait(10)
        capture = pool.submit(contexts.capture, request)
        issue = pool.submit(authorizations.issue_operator, operator_request)
        with pytest.raises(TimeoutError):
            capture.result(timeout=0.2)
        with pytest.raises(TimeoutError):
            issue.result(timeout=0.2)
        allow_publication.set()
        reconstruction.result(timeout=10)
        try:
            context = capture.result(timeout=10)
        except RecoveryContextConflict:
            with reconstruction_target_db.connect() as conn:
                assert (
                    conn.scalar(
                        text(
                            "SELECT reconstruction_validation_pending "
                            "FROM security_state WHERE id=1"
                        )
                    )
                    is False
                )
        else:
            assert context.authority_basis == pending_basis
            with reconstruction_target_db.connect() as conn:
                assert (
                    conn.scalar(
                        text(
                            "SELECT reconstruction_validation_pending "
                            "FROM security_state WHERE id=1"
                        )
                    )
                    is False
                )
        try:
            operator = issue.result(timeout=10)
        except AuthorizationConflict:
            pass
        else:
            assert operator.authority_epoch_id == pending_basis.authority_epoch_id
            with reconstruction_target_db.connect() as conn:
                assert (
                    conn.scalar(
                        text(
                            "SELECT reconstruction_validation_pending "
                            "FROM security_state WHERE id=1"
                        )
                    )
                    is False
                )


def test_backup_publication_racing_reconstruction_fence_is_rejected(
    reconstruction_target_db, tmp_path
):
    backup = write_backup(tmp_path, manifest_from_target(reconstruction_target_db))
    preflight = RestorePreflightService(reconstruction_target_db).validate(backup)
    dumping = Event()
    finish_dump = Event()

    def runner(args, *, env, cwd=None):
        dump_path = args[args.index("--file") + 1]
        with open(dump_path, "wb") as output:
            output.write(b"simulated dump")
        dumping.set()
        assert finish_dump.wait(10)

    target = tmp_path / "competing-backup"
    creator = BackupCreationService(reconstruction_target_db, runner=runner)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending_backup = pool.submit(
            creator.create,
            target,
            application_version="0.1.0",
            source_revision=SOURCE_REVISION,
        )
        assert dumping.wait(10)
        DatabaseReconstructionService(reconstruction_target_db)._establish_reconstruction_fence(
            preflight
        )
        finish_dump.set()
        with pytest.raises(BackupCreationError):
            pending_backup.result(timeout=10)
    assert not target.exists()
    with reconstruction_target_db.connect() as conn:
        assert (
            conn.scalar(
                text("SELECT reconstruction_validation_pending FROM security_state WHERE id=1")
            )
            is True
        )


def test_early_bootstrap_creates_no_epoch_audit_but_provisional_basis_can_create_evidence(
    reconstruction_target_db,
):
    with reconstruction_target_db.connect() as conn:
        target_epoch = conn.scalar(
            text("SELECT authority_epoch_id FROM security_state WHERE id = 1")
        )
        epoch_tables = [
            row[0]
            for row in conn.execute(
                text("""
                SELECT table_name FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND column_name = 'authority_epoch_id'
                  AND table_name <> 'security_state'
                ORDER BY table_name
            """)
            )
        ]
        assert epoch_tables
        for table in epoch_tables:
            assert conn.scalar(text(f'SELECT count(*) FROM "{table}"')) == 0

    with Session(reconstruction_target_db) as session:
        provisional = AuthorityBootstrapService(session).initialize(AuthorityStartupMode.RECOVERY)
    assert provisional.state is SecurityState.RECOVERY_REQUIRED
    assert provisional.version == 2
    assert provisional.authority_epoch_id.value == target_epoch
    assert provisional.recovery_bootstrap_pending

    with reconstruction_target_db.connect() as conn:
        for table in epoch_tables:
            assert conn.scalar(text(f'SELECT count(*) FROM "{table}"')) == 0

    contexts = RecoveryContextService(reconstruction_target_db)
    basis = contexts.current_basis()
    assert basis.authority_epoch_id == target_epoch
    assert basis.bootstrap_origin is not None
    assert basis.bootstrap_origin.state is SecurityState.NORMAL
    assert basis.bootstrap_origin.version == 1
    context = contexts.capture(
        CaptureRecoveryContext(
            context_id=uuid4(),
            expected_basis=basis,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    assert context.authority_basis.authority_epoch_id == target_epoch
    authorizations = AuthorizationService(reconstruction_target_db)
    operator = authorizations.issue_operator(
        IssueOperatorAuthorization(
            authorization_id=uuid4(),
            expected_authority_epoch_id=target_epoch,
            principal=OperatorPrincipal(kind="local_operator", principal_id="local-admin"),
            granted_capability=AuthorizationCapability.RECOVERY_ACTION,
            scope=(AuthorizationScopeItem(kind="recovery_context", target_id=context.context_id),),
            issuance_basis=(
                AuthorizationBasisReference(
                    kind="recovery_context",
                    record_id=context.context_id,
                ),
            ),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            replay_id=uuid4(),
            recovery_context_id=context.context_id,
        )
    )
    execution = authorizations.issue_execution(
        IssueExecutionAuthorization(
            execution_authorization_id=uuid4(),
            expected_authority_epoch_id=target_epoch,
            execution_id=uuid4(),
            operator_authorization_id=operator.authorization_id,
            scope=operator.scope,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            replay_id=uuid4(),
            recovery_context_id=context.context_id,
        )
    )
    assert (
        authorizations.require_current_execution(
            execution.execution_authorization_id,
            recovery_context_id=context.context_id,
            required_capability=AuthorizationCapability.RECOVERY_ACTION,
        )
        == execution
    )
    with reconstruction_target_db.connect() as conn:
        for table in (
            "recovery_contexts",
            "recovery_context_audit",
            "operator_authorizations",
            "execution_authorizations",
            "authorization_audit",
        ):
            assert (
                conn.scalar(
                    text(f'SELECT count(*) FROM "{table}" WHERE authority_epoch_id = :epoch'),
                    {"epoch": target_epoch},
                )
                > 0
            )
