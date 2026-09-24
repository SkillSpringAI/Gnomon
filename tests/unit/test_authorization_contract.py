"""M1.2/M1.3 authorization artifacts are bounded evidence, not authority."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from research_agent.domain.authorization import (
    AuthorizationCapability,
    AuthorizationScopeItem,
    AuthorizationScopeKind,
    ExecutionAuthorization,
    OperatorAuthorization,
    validate_execution_authorization,
    validate_operator_authorization,
)


@pytest.fixture
def issued_at():
    return datetime(2026, 9, 24, 12, tzinfo=UTC)


@pytest.fixture
def recovery_context_id():
    return uuid4()


@pytest.fixture
def epoch_id():
    return uuid4()


@pytest.fixture
def operator_payload(issued_at, recovery_context_id, epoch_id):
    return {
        "authorization_id": uuid4(),
        "principal": {"kind": "local_operator", "principal_id": "local-admin"},
        "granted_capability": "recovery_action",
        "scope": [{"kind": "recovery_context", "target_id": recovery_context_id}],
        "authority_epoch_id": epoch_id,
        "issuance_basis": [{"kind": "recovery_context", "record_id": recovery_context_id}],
        "issued_at": issued_at,
        "expires_at": issued_at + timedelta(minutes=30),
        "replay_id": uuid4(),
        "recovery_context_id": recovery_context_id,
    }


def execution_payload(operator: OperatorAuthorization, issued_at: datetime):
    return {
        "execution_authorization_id": uuid4(),
        "execution_id": uuid4(),
        "operator_authorization_id": operator.authorization_id,
        "granted_capability": operator.granted_capability,
        "scope": list(operator.scope),
        "authority_epoch_id": operator.authority_epoch_id,
        "issued_at": issued_at + timedelta(minutes=1),
        "expires_at": issued_at + timedelta(minutes=10),
        "replay_id": uuid4(),
        "recovery_context_id": operator.recovery_context_id,
    }


def test_operator_authorization_roundtrip_is_immutable(operator_payload):
    authorization = OperatorAuthorization.model_validate(operator_payload)
    assert (
        OperatorAuthorization.model_validate_json(authorization.model_dump_json())
        == authorization
    )
    operator_payload["scope"].clear()
    assert len(authorization.scope) == 1
    with pytest.raises(ValidationError):
        authorization.expires_at = authorization.issued_at
    with pytest.raises(ValidationError):
        authorization.scope[0].target_id = uuid4()


@pytest.mark.parametrize(
    "field,value",
    [
        ("authorization_id", UUID(int=0)),
        ("authority_epoch_id", UUID(int=0)),
        ("replay_id", UUID(int=0)),
        ("principal", {"kind": "local_operator", "principal_id": " "}),
        ("principal", {"kind": "model", "principal_id": "model"}),
        ("granted_capability", "memory_mutation"),
        ("scope", []),
        ("scope", [{"kind": "restore_everything", "target_id": uuid4()}]),
        ("issuance_basis", []),
        ("schema_version", 2),
        ("authorization", "implicit"),
    ],
)
def test_invalid_operator_authorization_is_rejected(operator_payload, field, value):
    operator_payload[field] = value
    with pytest.raises(ValidationError):
        OperatorAuthorization.model_validate(operator_payload)


def test_recovery_context_binding_must_be_scoped_and_basis_backed(operator_payload):
    operator_payload["scope"] = [{"kind": "security_state", "target_id": None}]
    with pytest.raises(ValidationError, match="inside the authorization scope"):
        OperatorAuthorization.model_validate(operator_payload)
    operator_payload["scope"] = [
        {"kind": "recovery_context", "target_id": operator_payload["recovery_context_id"]}
    ]
    operator_payload["issuance_basis"] = [{"kind": "operator_command", "record_id": uuid4()}]
    with pytest.raises(ValidationError, match="part of the issuance basis"):
        OperatorAuthorization.model_validate(operator_payload)


def test_scope_singleton_and_non_singleton_bounds(operator_payload):
    operator_payload["scope"] = [{"kind": "task", "target_id": None}]
    with pytest.raises(ValidationError, match="identify"):
        OperatorAuthorization.model_validate(operator_payload)
    operator_payload["scope"] = [{"kind": "security_state", "target_id": uuid4()}]
    with pytest.raises(ValidationError, match="singleton"):
        OperatorAuthorization.model_validate(operator_payload)


def test_operator_authorization_rejects_stale_epoch_time_and_context(
    operator_payload, issued_at, epoch_id, recovery_context_id
):
    authorization = OperatorAuthorization.model_validate(operator_payload)
    validate_operator_authorization(
        authorization,
        current_authority_epoch_id=epoch_id,
        now=issued_at,
        recovery_context_id=recovery_context_id,
    )
    with pytest.raises(ValueError, match="stale"):
        validate_operator_authorization(
            authorization,
            current_authority_epoch_id=uuid4(),
            now=issued_at,
            recovery_context_id=recovery_context_id,
        )
    with pytest.raises(ValueError, match="not currently valid"):
        validate_operator_authorization(
            authorization,
            current_authority_epoch_id=epoch_id,
            now=authorization.expires_at,
            recovery_context_id=recovery_context_id,
        )
    with pytest.raises(ValueError, match="aware clock"):
        validate_operator_authorization(
            authorization,
            current_authority_epoch_id=epoch_id,
            now=issued_at.replace(tzinfo=None),
            recovery_context_id=recovery_context_id,
        )
    with pytest.raises(ValueError, match="not bound"):
        validate_operator_authorization(
            authorization,
            current_authority_epoch_id=epoch_id,
            now=issued_at,
            recovery_context_id=uuid4(),
        )


def test_execution_authorization_can_only_narrow_operator_grant(
    operator_payload, issued_at, epoch_id
):
    operator = OperatorAuthorization.model_validate(operator_payload)
    execution = ExecutionAuthorization.model_validate(execution_payload(operator, issued_at))
    validate_execution_authorization(
        execution,
        operator,
        current_authority_epoch_id=epoch_id,
        now=execution.issued_at,
    )
    expanded = execution.model_copy(
        update={
            "scope": execution.scope
            + (
                AuthorizationScopeItem(kind=AuthorizationScopeKind.SECURITY_STATE),
            )
        }
    )
    with pytest.raises(ValueError, match="expands"):
        validate_execution_authorization(
            expanded,
            operator,
            current_authority_epoch_id=epoch_id,
            now=execution.issued_at,
        )


@pytest.mark.parametrize(
    "change,match",
    [
        ("epoch", "stale"),
        ("operator", "not bound"),
        ("capability", "changes"),
        ("early", "exceeds"),
        ("late", "exceeds"),
        ("expired", "not currently valid"),
    ],
)
def test_execution_authorization_rejects_stale_or_escalating_artifacts(
    operator_payload, issued_at, epoch_id, change, match
):
    operator = OperatorAuthorization.model_validate(operator_payload)
    payload = execution_payload(operator, issued_at)
    if change == "epoch":
        payload["authority_epoch_id"] = uuid4()
    elif change == "operator":
        payload["operator_authorization_id"] = uuid4()
    elif change == "capability":
        payload["granted_capability"] = AuthorizationCapability.AUTHORITY_ADMINISTRATION
    elif change == "early":
        payload["issued_at"] = operator.issued_at - timedelta(seconds=1)
    elif change == "late":
        payload["expires_at"] = operator.expires_at + timedelta(seconds=1)
    elif change == "expired":
        payload["expires_at"] = issued_at + timedelta(minutes=2)
    execution = ExecutionAuthorization.model_validate(payload)
    now = execution.expires_at if change == "expired" else issued_at + timedelta(minutes=1)
    with pytest.raises(ValueError, match=match):
        validate_execution_authorization(
            execution,
            operator,
            current_authority_epoch_id=epoch_id,
            now=now,
        )


def test_execution_authorization_revalidates_copied_models(operator_payload, issued_at, epoch_id):
    operator = OperatorAuthorization.model_validate(operator_payload)
    execution = ExecutionAuthorization.model_validate(execution_payload(operator, issued_at))
    invalid = execution.model_copy(update={"expires_at": execution.issued_at})
    with pytest.raises(ValidationError):
        validate_execution_authorization(
            invalid,
            operator,
            current_authority_epoch_id=epoch_id,
            now=execution.issued_at,
        )


def test_duplicate_scope_and_basis_are_rejected(operator_payload):
    operator_payload["scope"] = operator_payload["scope"] * 2
    with pytest.raises(ValidationError, match="scope"):
        OperatorAuthorization.model_validate(operator_payload)
    operator_payload["scope"] = [operator_payload["scope"][0]]
    operator_payload["issuance_basis"] = operator_payload["issuance_basis"] * 2
    with pytest.raises(ValidationError, match="basis"):
        OperatorAuthorization.model_validate(operator_payload)


def test_authorization_basis_kind_is_bounded(operator_payload):
    operator_payload["issuance_basis"] = [{"kind": "freeform_note", "record_id": uuid4()}]
    with pytest.raises(ValidationError):
        OperatorAuthorization.model_validate(operator_payload)
