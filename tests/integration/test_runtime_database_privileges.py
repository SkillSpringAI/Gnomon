"""Characterize application DML with a non-owner PostgreSQL login."""

import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from research_agent import cli
from research_agent.application.assessment_service import AssessmentService
from research_agent.application.authority_bootstrap import (
    AuthorityBootstrapService,
    AuthorityStartupMode,
)
from research_agent.application.authorization_service import AuthorizationService
from research_agent.application.backup_creation_service import BackupCreationService
from research_agent.application.backup_state_inspection_service import (
    BackupStateInspectionService,
    BackupStateInspectionUnavailable,
)
from research_agent.application.database_reconstruction_service import DatabaseReconstructionService
from research_agent.application.evidence_service import EvidenceService
from research_agent.application.memory_service import MemoryService
from research_agent.application.migrations import migration_files, run_migrations
from research_agent.application.recovery_context_service import RecoveryContextService
from research_agent.application.research_service import ResearchService
from research_agent.domain.authorization import (
    AuthorizationBasisReference,
    AuthorizationScopeItem,
    IssueExecutionAuthorization,
    IssueOperatorAuthorization,
    OperatorPrincipal,
)
from research_agent.domain.memory import MemoryAuthority, MemoryChangeProposal
from research_agent.domain.recovery import CaptureRecoveryContext
from research_agent.domain.research import (
    AssessmentEvidenceLink,
    ClaimCreate,
    ClaimSourceLink,
    Hypothesis,
    HypothesisAssessmentCreate,
    HypothesisAssessmentStatus,
    ResearchBrief,
    SourceCreate,
    SourceType,
    SupportType,
    TaskStatus,
    TaskStatusChange,
)
from research_agent.persistence.database import engine as admin_engine
from research_agent.persistence.owner_database import create_owner_database_engine
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository

# This inventory is intentionally explicit: a new migration table requires a grant review.
APPLICATION_TABLES = frozenset(
    {
        "research_tasks",
        "research_cycles",
        "research_events",
        "research_sources",
        "research_claims",
        "claim_sources",
        "trusted_sources",
        "hypothesis_assessments",
        "assessment_evidence",
        "memory_changes",
        "research_cycle_attempts",
        "report_generation_attempts",
        "security_state",
        "security_state_transitions",
        "trusted_source_policy_events",
        "provider_session_events",
        "source_relationships",
        "source_relationship_changes",
        "stopping_decisions",
        "stopping_decision_changes",
        "recovery_contexts",
        "recovery_context_audit",
        "operator_authorizations",
        "execution_authorizations",
        "authorization_audit",
    }
)
INSERT_TABLES = APPLICATION_TABLES - {"security_state"}
UPDATE_TABLES = frozenset(
    {
        "research_tasks",
        "research_cycles",
        "research_claims",
        "hypothesis_assessments",
        "trusted_sources",
        "research_cycle_attempts",
        "report_generation_attempts",
        "security_state",
        "source_relationships",
    }
)
DELETE_TABLES = frozenset({"claim_sources", "assessment_evidence"})


def _grant_tables(conn, privilege: str, tables: frozenset[str], role: str) -> None:
    for table in sorted(tables):
        conn.exec_driver_sql(f'GRANT {privilege} ON TABLE "{table}" TO "{role}"')


@pytest.fixture(scope="module")
def privilege_database(tmp_path_factory):
    suffix = uuid4().hex[:20]
    owner, runtime, reader, db_name = (
        f"m3_owner_{suffix}",
        f"m3_runtime_{suffix}",
        f"m3_reader_{suffix}",
        f"m3_priv_{suffix}",
    )
    password = uuid4().hex
    admin = create_engine(admin_engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    owner_engine = runtime_engine = reader_engine = None
    created_roles: list[str] = []
    created_db = False
    try:
        with admin.connect() as conn:
            for role in (owner, runtime, reader):
                conn.exec_driver_sql(f"CREATE ROLE \"{role}\" LOGIN PASSWORD '{password}'")
                created_roles.append(role)
            conn.exec_driver_sql(f'CREATE DATABASE "{db_name}" OWNER "{owner}"')
            created_db = True
            conn.exec_driver_sql(f'REVOKE ALL ON DATABASE "{db_name}" FROM PUBLIC')

        def role_engine(role: str) -> Engine:
            return create_engine(
                admin_engine.url.set(database=db_name, username=role, password=password)
            )

        owner_engine, runtime_engine, reader_engine = (
            role_engine(owner),
            role_engine(runtime),
            role_engine(reader),
        )
        with owner_engine.begin() as conn:
            conn.exec_driver_sql("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        baseline = Path(tmp_path_factory.mktemp("m3_privilege_migrations"))
        files = migration_files()
        assert len(files) == 36
        for path in files[:-1]:
            shutil.copyfile(path, baseline / path.name)
        assert len(run_migrations(owner_engine, directory=baseline)) == 35
        with Session(owner_engine) as session:
            task = ResearchService(SqlAlchemyResearchTaskRepository(session)).create_task(
                ResearchBrief(title="Populated owner upgrade", objective="Retain this task")
            )
            session.commit()
            populated_id = task.id
        assert run_migrations(owner_engine) == [files[-1].name]
        assert run_migrations(owner_engine) == []
        with owner_engine.begin() as conn:
            assert (
                conn.scalar(
                    text("SELECT count(*) FROM research_tasks WHERE id=:id"), {"id": populated_id}
                )
                == 1
            )
            table_names = set(
                conn.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
            )
            assert table_names == APPLICATION_TABLES | {"research_agent_schema_migrations"}
            for role in (runtime, reader):
                conn.exec_driver_sql(f'GRANT CONNECT ON DATABASE "{db_name}" TO "{role}"')
                conn.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{role}"')
            _grant_tables(conn, "SELECT", APPLICATION_TABLES, runtime)
            _grant_tables(conn, "INSERT", INSERT_TABLES, runtime)
            _grant_tables(conn, "UPDATE", UPDATE_TABLES, runtime)
            _grant_tables(conn, "DELETE", DELETE_TABLES, runtime)
            _grant_tables(conn, "SELECT", table_names, reader)
        yield owner_engine, runtime_engine, reader_engine, (owner, runtime, reader, db_name)
    finally:
        for db in (reader_engine, runtime_engine, owner_engine):
            if db is not None:
                db.dispose()
        with admin.connect() as conn:
            if created_db:
                conn.exec_driver_sql(f'DROP DATABASE "{db_name}" WITH (FORCE)')
            for role in reversed(created_roles):
                conn.exec_driver_sql(f'DROP ROLE "{role}"')
        admin.dispose()


def test_owner_migration_and_runtime_privilege_inventory(privilege_database):
    owner_db, runtime_db, reader_db, (owner, runtime, reader, db_name) = privilege_database
    with owner_db.connect() as conn:
        assert (
            conn.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname=:role"), {"role": owner})
            is False
        )
        assert (
            conn.scalar(text("SELECT extname FROM pg_extension WHERE extname='pgcrypto'"))
            == "pgcrypto"
        )
        assert conn.scalar(text("SELECT count(*) FROM research_agent_schema_migrations")) == 36
    with runtime_db.connect() as conn:
        assert conn.scalar(text("SELECT current_user")) == runtime
        assert (
            conn.scalar(
                text("SELECT has_database_privilege(current_user, :db, 'CREATE')"), {"db": db_name}
            )
            is False
        )
        assert (
            conn.scalar(
                text("SELECT has_database_privilege(current_user, :db, 'TEMP')"), {"db": db_name}
            )
            is False
        )
        assert (
            conn.scalar(text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')"))
            is False
        )
        for table in APPLICATION_TABLES:
            for privilege, expected in (
                ("SELECT", True),
                ("INSERT", table in INSERT_TABLES),
                ("UPDATE", table in UPDATE_TABLES),
                ("DELETE", table in DELETE_TABLES),
            ):
                assert (
                    conn.scalar(
                        text("SELECT has_table_privilege(current_user, :table, :privilege)"),
                        {"table": f"public.{table}", "privilege": privilege},
                    )
                    is expected
                )
        assert conn.scalar(text("SELECT count(*) FROM pg_sequences WHERE schemaname='public'")) == 0
        assert conn.scalar(text("SELECT gen_random_uuid()")) is not None
    with reader_db.connect() as conn:
        assert conn.scalar(text("SELECT current_user")) == reader
        assert (
            conn.scalar(
                text("SELECT has_table_privilege(current_user, 'public.security_state', 'UPDATE')")
            )
            is False
        )


def test_configured_owner_engine_is_distinct_from_runtime(privilege_database, monkeypatch):
    owner_db, runtime_db, _, (owner, runtime, _, _) = privilege_database
    monkeypatch.setenv("OWNER_DATABASE_URL", owner_db.url.render_as_string(hide_password=False))
    operator_db = create_owner_database_engine()
    try:
        with operator_db.connect() as conn:
            assert conn.scalar(text("SELECT current_user")) == owner
        with runtime_db.connect() as conn:
            assert conn.scalar(text("SELECT current_user")) == runtime
        assert run_migrations(operator_db) == []
        monkeypatch.setattr(sys, "argv", ["research-agent", "migrate"])
        cli.main()  # Complete CLI path uses the configured owner login.
        service = DatabaseReconstructionService(operator_db)
        args, env = service._pg_restore_command(Path("database.dump"), Path("restore.list"))
        assert args[args.index("--username") + 1] == owner
        assert owner_db.url.password not in " ".join(args)
        assert env["PGPASSWORD"] == owner_db.url.password
        assert "OWNER_DATABASE_URL" not in env
    finally:
        operator_db.dispose()


def test_restricted_runtime_governed_dml_locks_and_recovery(privilege_database):
    _, runtime_db, _, _ = privilege_database
    with Session(runtime_db) as session:
        hypothesis = Hypothesis(label="H1", statement="Role writes retain evidence")
        task = ResearchService(SqlAlchemyResearchTaskRepository(session)).create_task(
            ResearchBrief(
                title="Restricted role",
                objective="Exercise governed writes",
                hypotheses=[hypothesis],
            )
        )
        session.commit()
        task_id = task.id
        changed = ResearchService(SqlAlchemyResearchTaskRepository(session)).change_status(
            task_id, TaskStatusChange(expected_status=TaskStatus.ACTIVE, status=TaskStatus.PAUSED)
        )
        session.commit()
        assert changed.status is TaskStatus.PAUSED
        source = EvidenceService(session).create_source(
            task_id,
            SourceCreate(
                source_type=SourceType.DOCUMENT,
                title="Role evidence",
                uri="https://example.test/role",
                content="Role evidence content",
            ),
        )
        claim = EvidenceService(session).create_claim(
            task_id,
            ClaimCreate(
                statement="The role can persist evidence",
                source_links=[
                    ClaimSourceLink(source_id=source.id, support_type=SupportType.SUPPORTING)
                ],
            ),
        )
        MemoryService(session).apply(
            MemoryChangeProposal(
                target_type="claim",
                target_id=claim.id,
                operation="UPDATE",
                expected_version=1,
                reason="Exercise link replacement",
                claim=ClaimCreate(
                    statement="The restricted role persists evidence",
                    source_links=[
                        ClaimSourceLink(source_id=source.id, support_type=SupportType.SUPPORTING)
                    ],
                ),
            ),
            MemoryAuthority(actor="local_operator", task_id=task_id, can_commit=True),
        )
        AssessmentService(session).save(
            task_id,
            hypothesis.id,
            HypothesisAssessmentCreate(
                status=HypothesisAssessmentStatus.SUPPORTED,
                summary="Initial assessment",
                evidence_links=[
                    AssessmentEvidenceLink(claim_id=claim.id, relation=SupportType.SUPPORTING)
                ],
            ),
        )
        AssessmentService(session).save(
            task_id,
            hypothesis.id,
            HypothesisAssessmentCreate(
                status=HypothesisAssessmentStatus.MIXED,
                summary="Revised assessment",
                evidence_links=[
                    AssessmentEvidenceLink(claim_id=claim.id, relation=SupportType.CONTRADICTING)
                ],
            ),
        )
        AuthorityBootstrapService(session).initialize(AuthorityStartupMode.RECOVERY)
    contexts = RecoveryContextService(runtime_db)
    basis = contexts.current_basis()
    context = contexts.capture(
        CaptureRecoveryContext(
            context_id=uuid4(),
            expected_basis=basis,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    authorizations = AuthorizationService(runtime_db)
    operator = authorizations.issue_operator(
        IssueOperatorAuthorization(
            authorization_id=uuid4(),
            expected_authority_epoch_id=authorizations.current_authority_epoch_id(),
            principal=OperatorPrincipal(kind="local_operator", principal_id="local-admin"),
            granted_capability="recovery_action",
            scope=(AuthorizationScopeItem(kind="recovery_context", target_id=context.context_id),),
            issuance_basis=(
                AuthorizationBasisReference(kind="recovery_context", record_id=context.context_id),
            ),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            replay_id=uuid4(),
            recovery_context_id=context.context_id,
        )
    )
    execution = authorizations.issue_execution(
        IssueExecutionAuthorization(
            execution_authorization_id=uuid4(),
            expected_authority_epoch_id=authorizations.current_authority_epoch_id(),
            execution_id=uuid4(),
            operator_authorization_id=operator.authorization_id,
            scope=operator.scope,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            replay_id=uuid4(),
            recovery_context_id=context.context_id,
        )
    )
    assert execution.operator_authorization_id == operator.authorization_id
    with runtime_db.connect() as conn:
        assert (
            conn.scalar(
                text("SELECT count(*) FROM research_events WHERE task_id=:id"), {"id": task_id}
            )
            >= 2
        )
        assert (
            conn.scalar(
                text("SELECT count(*) FROM memory_changes WHERE target_id=:id"), {"id": claim.id}
            )
            == 2
        )
        assert conn.scalar(text("SELECT count(*) FROM recovery_context_audit")) == 1
        assert conn.scalar(text("SELECT count(*) FROM authorization_audit")) == 2


@pytest.mark.parametrize(
    "statement",
    [
        "CREATE TABLE m3_forbidden (id integer)",
        "ALTER TABLE research_tasks ADD COLUMN m3_forbidden integer",
        "DROP TABLE research_tasks",
        "CREATE SCHEMA m3_forbidden",
        "ALTER SCHEMA public RENAME TO m3_forbidden",
        "CREATE EXTENSION hstore",
    ],
)
def test_restricted_runtime_cannot_manage_schema(privilege_database, statement):
    _, runtime_db, _, _ = privilege_database
    with runtime_db.begin() as conn, pytest.raises(DBAPIError) as denied:
        conn.exec_driver_sql(statement)
    assert denied.value.orig.sqlstate == "42501"


def test_restricted_runtime_cannot_run_migrations(privilege_database):
    _, runtime_db, _, _ = privilege_database
    with pytest.raises(DBAPIError) as denied:
        run_migrations(runtime_db)
    assert denied.value.orig.sqlstate == "42501"


def test_backup_inspection_requires_ledger_read_but_no_write(
    privilege_database, tmp_path, monkeypatch
):
    owner_db, runtime_db, reader_db, (_, runtime, _, _) = privilege_database
    with pytest.raises(BackupStateInspectionUnavailable):
        BackupStateInspectionService(runtime_db).inspect(
            application_version="0.1.0", source_revision="a1b2c3d"
        )
    inspection = BackupStateInspectionService(reader_db).inspect(
        application_version="0.1.0", source_revision="a1b2c3d"
    )
    assert len(inspection.schema_metadata.migrations) == 36
    if shutil.which("pg_dump"):
        backup = BackupCreationService(reader_db)
    elif shutil.which("docker"):
        containers = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}} {{.Image}}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        postgres = [line.split()[0] for line in containers if "postgres" in line.lower()]
        if len(postgres) != 1:
            pytest.skip("No unambiguous local PostgreSQL container for real pg_dump")

        def docker_pg_dump(args, *, env, cwd=None):
            output = Path(args[args.index("--file") + 1])
            command = [
                "docker",
                "exec",
                "-e",
                "PGPASSWORD",
                postgres[0],
                "pg_dump",
                "--format=custom",
                "--dbname",
                args[args.index("--dbname") + 1],
                "--no-password",
                "--username",
                args[args.index("--username") + 1],
            ]
            docker_environment = dict(os.environ)
            docker_environment["PGPASSWORD"] = env["PGPASSWORD"]
            completed = subprocess.run(
                command, check=True, capture_output=True, env=docker_environment
            )
            output.write_bytes(completed.stdout)
            return subprocess.CompletedProcess(command, 0, "", "")

        backup = BackupCreationService(reader_db, runner=docker_pg_dump)
    else:
        pytest.skip("pg_dump client is unavailable")
    with pytest.raises(DBAPIError) as denied:
        backup.create(
            tmp_path / "read-only-backup",
            application_version="0.1.0",
            source_revision="a1b2c3d",
        )
    assert denied.value.orig.sqlstate == "42501"  # Final singleton FOR SHARE lock.
    with runtime_db.connect() as conn:
        assert (
            conn.scalar(
                text(
                    "SELECT has_table_privilege(current_user, "
                    "'public.research_agent_schema_migrations', 'SELECT')"
                )
            )
            is False
        )
    with owner_db.begin() as conn:
        conn.exec_driver_sql(f'GRANT SELECT ON research_agent_schema_migrations TO "{runtime}"')
    result = BackupCreationService(
        runtime_db,
        **({"runner": docker_pg_dump} if not shutil.which("pg_dump") else {}),
    ).create(tmp_path / "runtime-backup", application_version="0.1.0", source_revision="a1b2c3d")
    assert result.dump_path.stat().st_size > 0
    assert len(result.manifest.schema_metadata.migrations) == 36
    monkeypatch.setenv("OWNER_DATABASE_URL", owner_db.url.render_as_string(hide_password=False))
    selected_owner = create_owner_database_engine()
    try:
        with selected_owner.connect() as conn:
            assert conn.scalar(text("SELECT current_user")) == owner_db.url.username
        owner_backup = BackupCreationService(
            selected_owner,
            **({"runner": docker_pg_dump} if not shutil.which("pg_dump") else {}),
        ).create(tmp_path / "owner-backup", application_version="0.1.0", source_revision="a1b2c3d")
        assert owner_backup.dump_path.stat().st_size > 0
        assert len(owner_backup.manifest.schema_metadata.migrations) == 36
    finally:
        selected_owner.dispose()
