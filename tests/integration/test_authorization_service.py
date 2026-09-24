"""Trusted authorization issuance persistence and replay in isolated schemas."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from research_agent.application.authorization_service import (
    AuthorizationConflict,
    AuthorizationService,
    AuthorizationUnavailable,
)
from research_agent.application.migrations import migration_files, run_migrations
from research_agent.domain.authorization import (
    AuthorizationBasisReference,
    AuthorizationCapability,
    AuthorizationScopeItem,
    IssueExecutionAuthorization,
    IssueOperatorAuthorization,
    OperatorPrincipal,
)
from research_agent.persistence.authorization import (
    AuthorizationAuditRecord,
    ExecutionAuthorizationRecord,
    OperatorAuthorizationRecord,
)
from research_agent.persistence.database import engine


@pytest.fixture
def authorization_db(request):
    schema = "authorization_test_" + uuid4().hex
    with engine.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    isolated = create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        if getattr(request, "param", None) == "pre034":
            with isolated.begin() as conn:
                for path in migration_files():
                    if path.name.startswith("034_"):
                        break
                    conn.exec_driver_sql(path.read_text(encoding="utf-8"))
        else:
            run_migrations(isolated)
        yield isolated
    finally:
        isolated.dispose()
        with engine.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')


def counts(db):
    with Session(db) as session:
        return tuple(
            session.scalar(select(func.count()).select_from(model))
            for model in (
                OperatorAuthorizationRecord,
                ExecutionAuthorizationRecord,
                AuthorizationAuditRecord,
            )
        )


def operator_command(service, *, recovery_context_id=None):
    context_id = recovery_context_id or uuid4()
    return IssueOperatorAuthorization(
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


def test_operator_and_execution_issue_replay_without_authority_change(authorization_db):
    service = AuthorizationService(authorization_db)
    command = operator_command(service)
    operator = service.issue_operator(command)
    assert service.issue_operator(command) == operator
    execution_request = execution_command(service, operator)
    execution = service.issue_execution(execution_request)
    assert service.issue_execution(execution_request) == execution
    assert execution.operator_authorization_id == operator.authorization_id
    assert execution.authority_epoch_id == operator.authority_epoch_id
    assert execution.scope == operator.scope
    assert counts(authorization_db) == (1, 1, 2)
    with authorization_db.connect() as conn:
        assert conn.scalar(text("SELECT state FROM security_state WHERE id=1")) == "normal"


def test_identity_reuse_with_different_command_is_rejected(authorization_db):
    service = AuthorizationService(authorization_db)
    command = operator_command(service)
    service.issue_operator(command)
    changed = command.model_copy(update={"replay_id": uuid4()})
    with pytest.raises(AuthorizationConflict, match="different request"):
        service.issue_operator(changed)
    operator = service.issue_operator(command)
    execution = execution_command(service, operator)
    service.issue_execution(execution)
    with pytest.raises(AuthorizationConflict, match="different request"):
        service.issue_execution(execution.model_copy(update={"execution_id": uuid4()}))
    assert counts(authorization_db) == (1, 1, 2)


def test_stale_epoch_expiry_and_escalating_execution_are_rejected(authorization_db):
    service = AuthorizationService(authorization_db)
    command = operator_command(service)
    with authorization_db.begin() as conn:
        conn.execute(
            text("UPDATE security_state SET authority_epoch_id=:epoch"),
            {"epoch": uuid4()},
        )
    with pytest.raises(AuthorizationConflict, match="stale"):
        service.issue_operator(command)
    fresh = operator_command(service)
    expired = fresh.model_copy(update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)})
    with pytest.raises(AuthorizationConflict, match="invalid"):
        service.issue_operator(expired)
    operator = service.issue_operator(fresh)
    execution = execution_command(service, operator)
    expanded = execution.model_copy(
        update={
            "scope": execution.scope
            + (AuthorizationScopeItem(kind="security_state"),)
        }
    )
    with pytest.raises(AuthorizationConflict, match="invalid"):
        service.issue_execution(expanded)
    assert counts(authorization_db) == (1, 0, 1)


def test_old_epoch_operator_cannot_issue_new_execution_authorization(authorization_db):
    service = AuthorizationService(authorization_db)
    operator = service.issue_operator(operator_command(service))
    with authorization_db.begin() as conn:
        conn.execute(
            text("UPDATE security_state SET authority_epoch_id=:epoch"),
            {"epoch": uuid4()},
        )
    request = execution_command(service, operator)
    with pytest.raises(AuthorizationConflict, match="invalid"):
        service.issue_execution(request)
    assert counts(authorization_db) == (1, 0, 1)


def test_current_execution_boundary_enforces_context_and_capability(authorization_db):
    service = AuthorizationService(authorization_db)
    operator = service.issue_operator(operator_command(service))
    execution = service.issue_execution(execution_command(service, operator))

    assert (
        service.require_current_execution(
            execution.execution_authorization_id,
            recovery_context_id=execution.recovery_context_id,
            required_capability=AuthorizationCapability.RECOVERY_ACTION,
        )
        == execution
    )
    with pytest.raises(AuthorizationConflict, match="not current"):
        service.require_current_execution(
            execution.execution_authorization_id,
            recovery_context_id=uuid4(),
            required_capability=AuthorizationCapability.RECOVERY_ACTION,
        )
    with pytest.raises(AuthorizationConflict, match="not current"):
        service.require_current_execution(
            execution.execution_authorization_id,
            recovery_context_id=execution.recovery_context_id,
            required_capability=AuthorizationCapability.AUTHORITY_ADMINISTRATION,
        )


def test_audit_failure_rolls_back_and_denied_replay_stays_denied(authorization_db, monkeypatch):
    from research_agent.application import authorization_service as module
    from research_agent.application.security_capability import SecurityCapabilityDenied

    service = AuthorizationService(authorization_db)
    command = operator_command(service)

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(service, "_record_audit", fail)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.issue_operator(command)
    assert counts(authorization_db) == (0, 0, 0)
    monkeypatch.undo()
    service = AuthorizationService(authorization_db)
    service.issue_operator(command)

    def deny(*args, **kwargs):
        raise SecurityCapabilityDenied("denied")

    monkeypatch.setattr(module, "require_capability", deny)
    with pytest.raises(SecurityCapabilityDenied):
        service.issue_operator(command)
    assert counts(authorization_db) == (1, 0, 1)


def test_malformed_history_is_rejected_without_repair(authorization_db):
    service = AuthorizationService(authorization_db)
    operator_request = operator_command(service)
    operator = service.issue_operator(operator_request)
    execution_request = execution_command(service, operator)
    service.issue_execution(execution_request)
    with authorization_db.begin() as conn:
        conn.execute(
            text("UPDATE operator_authorizations SET replay_id=:replay"),
            {"replay": uuid4()},
        )
    with pytest.raises(AuthorizationUnavailable, match="invalid"):
        service.issue_operator(operator_request)
    with authorization_db.begin() as conn:
        conn.execute(
            text("UPDATE execution_authorizations SET execution_id=:execution"),
            {"execution": uuid4()},
        )
    with pytest.raises(AuthorizationUnavailable, match="invalid"):
        service.issue_execution(execution_request)


def test_malformed_authorization_audit_is_rejected_without_repair(authorization_db):
    service = AuthorizationService(authorization_db)
    operator_request = operator_command(service)
    operator = service.issue_operator(operator_request)
    execution_request = execution_command(service, operator)
    service.issue_execution(execution_request)
    with pytest.raises(IntegrityError):
        with authorization_db.begin() as conn:
            conn.execute(
                text("UPDATE authorization_audit SET actor_type='authenticated_principal'"),
            )
    with authorization_db.begin() as conn:
        conn.execute(
            text(
                "UPDATE authorization_audit "
                "SET event_type='authorization.execution_issued' "
                "WHERE artifact_type='operator_authorization'"
            ),
        )
    with pytest.raises(AuthorizationUnavailable, match="invalid"):
        service.issue_operator(operator_request)


@pytest.mark.parametrize("authorization_db", ["pre034"], indirect=True)
def test_populated_upgrade_preserves_authority_and_adds_authorization_tables(authorization_db):
    with authorization_db.begin() as conn:
        before = conn.scalar(text("SELECT to_jsonb(s) FROM security_state s"))
        upgrade = next(path for path in migration_files() if path.name.startswith("034_"))
        conn.exec_driver_sql(upgrade.read_text(encoding="utf-8"))
        conn.exec_driver_sql(upgrade.read_text(encoding="utf-8"))
        assert conn.scalar(text("SELECT to_jsonb(s) FROM security_state s")) == before
        assert conn.scalar(text("SELECT count(*) FROM operator_authorizations")) == 0
    service = AuthorizationService(authorization_db)
    operator = service.issue_operator(operator_command(service))
    service.issue_execution(execution_command(service, operator))
    assert counts(authorization_db) == (1, 1, 2)
