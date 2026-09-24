"""Negative contracts before introducing recovery persistence or consumers."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from research_agent.application.security_capability import (
    SecurityCapability,
    SecurityCapabilityDenied,
    require_capability,
)
from research_agent.domain.recovery import (
    ReconciliationCheck,
    RecoveryAuthorityBasis,
    RecoveryContext,
    validate_recovery_context_basis,
)
from research_agent.persistence.models import SecurityStateRecord


@pytest.fixture
def payload():
    now = datetime(2026, 9, 24, tzinfo=UTC)
    return {
        "context_id": uuid4(),
        "incident_id": uuid4(),
        "authority_basis": {
            "security_state_id": 1,
            "authority_epoch_id": uuid4(),
            "state": "recovery_required",
            "version": 8,
            "recovery_bootstrap_pending": True,
            "bootstrap_origin": {
                "state": "normal",
                "version": 7,
                "started_at": now - timedelta(minutes=1),
            },
        },
        "initiating_actor": "local_operator",
        "initiating_actor_id": "bounded-local-operator",
        "permitted_scope": ["inspect_authority", "inspect_history", "inventory_operations"],
        "evidence_basis": [],
        "required_reconciliation": list(ReconciliationCheck),
        "unresolved_operations": [],
        "inventory_status": "not_collected",
        "created_at": now,
        "expires_at": now + timedelta(hours=1),
    }


def test_context_roundtrip_is_deeply_immutable(payload):
    context = RecoveryContext.model_validate(payload)
    assert RecoveryContext.model_validate_json(context.model_dump_json()) == context
    payload["permitted_scope"].clear()
    payload["authority_basis"]["version"] = 99
    assert len(context.permitted_scope) == 3
    assert context.authority_basis.version == 8
    with pytest.raises(ValidationError):
        context.expires_at = context.created_at
    with pytest.raises(ValidationError):
        context.authority_basis.version = 99
    with pytest.raises(ValidationError):
        context.authority_basis.bootstrap_origin.version = 99


@pytest.mark.parametrize(
    "field,value",
    [
        ("context_id", UUID(int=0)),
        ("incident_id", UUID(int=0)),
        ("initiating_actor", "external_agent"),
        ("initiating_actor", "model"),
        ("initiating_actor_id", " "),
        ("initiating_actor_id", "x" * 101),
        ("permitted_scope", []),
        ("permitted_scope", ["restore_authority"]),
        ("permitted_scope", ["inspect_authority", "inspect_authority"]),
        ("required_reconciliation", []),
        ("required_reconciliation", ["authority_lineage"] * 5),
        ("schema_version", 2),
        ("authorization", "granted"),
    ],
)
def test_invalid_or_authority_bearing_context_is_rejected(payload, field, value):
    payload[field] = value
    with pytest.raises(ValidationError):
        RecoveryContext.model_validate(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("security_state_id", 2),
        ("authority_epoch_id", UUID(int=0)),
        ("version", 0),
        ("version", True),
        ("version", "8"),
        ("version", 7),
        ("state", "normal"),
        ("recovery_bootstrap_pending", False),
        ("bootstrap_origin", None),
    ],
)
def test_invalid_bootstrap_basis_fails_closed(payload, field, value):
    payload["authority_basis"][field] = value
    with pytest.raises(ValidationError):
        RecoveryContext.model_validate(payload)


@pytest.mark.parametrize("change", ["epoch", "version", "origin", "fence_cleared"])
def test_stale_context_rejected_against_independent_current_basis(payload, change):
    context = RecoveryContext.model_validate(payload)
    current = context.authority_basis.model_dump()
    if change == "epoch":
        current["authority_epoch_id"] = uuid4()
    elif change == "version":
        current["version"] += 1
    elif change == "origin":
        current["bootstrap_origin"]["state"] = "lockdown"
    else:
        current.update(recovery_bootstrap_pending=False, bootstrap_origin=None)
    with pytest.raises(ValueError, match="stale"):
        validate_recovery_context_basis(
            context, RecoveryAuthorityBasis.model_validate(current), now=context.created_at
        )


def test_validity_is_inclusive_at_creation_and_exclusive_at_expiry(payload):
    context = RecoveryContext.model_validate(payload)
    validate_recovery_context_basis(context, context.authority_basis, now=context.created_at)
    for now in (context.created_at - timedelta(microseconds=1), context.expires_at):
        with pytest.raises(ValueError, match="not currently valid"):
            validate_recovery_context_basis(context, context.authority_basis, now=now)
    with pytest.raises(ValueError, match="aware clock"):
        validate_recovery_context_basis(
            context, context.authority_basis, now=context.created_at.replace(tzinfo=None)
        )


@pytest.mark.parametrize("field", ["created_at", "expires_at"])
def test_naive_context_dates_rejected(payload, field):
    payload[field] = payload[field].replace(tzinfo=None)
    with pytest.raises(ValidationError):
        RecoveryContext.model_validate(payload)


def test_context_cannot_predate_bootstrap_or_expire_at_creation(payload):
    payload["expires_at"] = payload["created_at"]
    with pytest.raises(ValidationError):
        RecoveryContext.model_validate(payload)
    payload["expires_at"] += timedelta(hours=1)
    payload["created_at"] -= timedelta(hours=1)
    with pytest.raises(ValidationError):
        RecoveryContext.model_validate(payload)


@pytest.mark.parametrize(
    "field,kind,id_field",
    [
        ("evidence_basis", "research_event", "record_id"),
        ("unresolved_operations", "provider_attempt", "operation_id"),
    ],
)
def test_reference_bounds_duplicates_and_uncollected_state(payload, field, kind, id_field):
    def reference():
        item = {"kind": kind, id_field: uuid4()}
        if field == "unresolved_operations":
            item["outcome"] = "unknown"
        return item

    payload[field] = [reference()]
    with pytest.raises(ValidationError, match="Uncollected"):
        RecoveryContext.model_validate(payload)
    payload["inventory_status"] = "partial"
    payload[field] = [reference() for _ in range(100)]
    context = RecoveryContext.model_validate(payload)
    assert len(getattr(context, field)) == 100
    assert context.inventory_status == "partial"
    payload[field].append(reference())
    with pytest.raises(ValidationError):
        RecoveryContext.model_validate(payload)
    payload[field] = [payload[field][0], payload[field][0]]
    with pytest.raises(ValidationError, match="repeat identities"):
        RecoveryContext.model_validate(payload)


def test_complete_inventory_is_not_resolution_or_authorization(payload):
    payload["inventory_status"] = "complete"
    payload["unresolved_operations"] = [
        {"kind": "provider_attempt", "operation_id": uuid4(), "outcome": "unknown"}
    ]
    context = RecoveryContext.model_validate(payload)
    validate_recovery_context_basis(context, context.authority_basis, now=context.created_at)
    assert context.unresolved_operations[0].outcome == "unknown"
    basis = context.authority_basis
    session = Mock()
    session.get.return_value = SecurityStateRecord(
        id=1,
        state="normal",
        version=basis.version,
        authority_epoch_id=basis.authority_epoch_id,
        recovery_bootstrap_pending=True,
        recovery_bootstrap_from_state="normal",
        recovery_bootstrap_from_version=7,
        recovery_bootstrap_started_at=basis.bootstrap_origin.started_at,
    )
    for capability in (SecurityCapability.MEMORY_MUTATION, SecurityCapability.PROVIDER_DISPATCH):
        with pytest.raises(SecurityCapabilityDenied):
            require_capability(session, capability)
    session.commit.assert_not_called()


def test_validation_rechecks_constructed_or_copied_models(payload):
    context = RecoveryContext.model_validate(payload)
    invalid = context.model_copy(update={"expires_at": context.created_at})
    with pytest.raises(ValidationError):
        validate_recovery_context_basis(invalid, context.authority_basis, now=context.created_at)
