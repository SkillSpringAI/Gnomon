"""Unit contracts for the bounded persistence error translator."""

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from research_agent.application.persistence_error_translation import (
    PersistenceBoundaryError,
    PersistenceErrorCategory,
    translate_integrity_error,
)


def integrity_error(constraint_name: str | None) -> IntegrityError:
    driver_error = RuntimeError("private SQL detail")
    if constraint_name is not None:
        driver_error.diag = SimpleNamespace(constraint_name=constraint_name)  # type: ignore[attr-defined]
    return IntegrityError("private SQL text", {}, driver_error)


@pytest.mark.parametrize(
    ("constraint_name", "category", "safe_message"),
    [
        (
            "report_generation_attempts_pkey",
            PersistenceErrorCategory.DUPLICATE_OPERATION,
            "The operation identity has already been used",
        ),
        (
            "trusted_sources_domain_key",
            PersistenceErrorCategory.DUPLICATE_RESOURCE,
            "The resource already exists",
        ),
        (
            "security_state_state_valid",
            PersistenceErrorCategory.AUTHORITY_INVARIANT_VIOLATION,
            "Persisted authority state violates a protected invariant",
        ),
    ],
)
def test_known_constraint_maps_to_safe_stable_error(
    constraint_name: str,
    category: PersistenceErrorCategory,
    safe_message: str,
) -> None:
    error = integrity_error(constraint_name)
    with pytest.raises(PersistenceBoundaryError) as raised:
        translate_integrity_error(error)

    translated = raised.value
    assert translated.category is category
    assert translated.constraint_name == constraint_name
    assert str(translated) == safe_message
    assert "private SQL" not in str(translated)
    assert raised.value.__cause__ is error


@pytest.mark.parametrize("constraint_name", ["unknown_constraint", None])
def test_unknown_or_undiagnosed_failure_is_reraised_unchanged(constraint_name: str | None) -> None:
    error = integrity_error(constraint_name)
    with pytest.raises(IntegrityError) as raised:
        translate_integrity_error(error)

    assert raised.value is error
