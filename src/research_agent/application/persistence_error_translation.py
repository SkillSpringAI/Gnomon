"""Translate only recognized PostgreSQL integrity failures."""

from enum import StrEnum
from typing import NoReturn

from sqlalchemy.exc import IntegrityError


class PersistenceErrorCategory(StrEnum):
    """Stable application categories for recognized persistence failures."""

    AUTHORITY_INVARIANT_VIOLATION = "AUTHORITY_INVARIANT_VIOLATION"
    DUPLICATE_OPERATION = "DUPLICATE_OPERATION"
    DUPLICATE_RESOURCE = "DUPLICATE_RESOURCE"


class PersistenceBoundaryError(RuntimeError):
    """A recognized persistence failure with safe application semantics."""

    def __init__(self, category: PersistenceErrorCategory, constraint_name: str) -> None:
        self.category = category
        # Retained for internal diagnostics and tests; public text never includes it.
        self.constraint_name = constraint_name
        super().__init__(self._safe_message(category))

    @staticmethod
    def _safe_message(category: PersistenceErrorCategory) -> str:
        if category is PersistenceErrorCategory.DUPLICATE_OPERATION:
            return "The operation identity has already been used"
        if category is PersistenceErrorCategory.DUPLICATE_RESOURCE:
            return "The resource already exists"
        return "Persisted authority state violates a protected invariant"


_KNOWN_CONSTRAINT_CATEGORIES: dict[str, PersistenceErrorCategory] = {
    "report_generation_attempts_pkey": PersistenceErrorCategory.DUPLICATE_OPERATION,
    "trusted_sources_domain_key": PersistenceErrorCategory.DUPLICATE_RESOURCE,
    "security_state_singleton_id_valid": PersistenceErrorCategory.AUTHORITY_INVARIANT_VIOLATION,
    "security_state_state_valid": PersistenceErrorCategory.AUTHORITY_INVARIANT_VIOLATION,
    "security_state_version_positive": PersistenceErrorCategory.AUTHORITY_INVARIANT_VIOLATION,
    "security_state_epoch_non_nil": PersistenceErrorCategory.AUTHORITY_INVARIANT_VIOLATION,
    "security_state_recovery_bootstrap_shape": (
        PersistenceErrorCategory.AUTHORITY_INVARIANT_VIOLATION
    ),
    "security_state_transitions_previous_state_valid": (
        PersistenceErrorCategory.AUTHORITY_INVARIANT_VIOLATION
    ),
    "security_state_transitions_new_state_valid": (
        PersistenceErrorCategory.AUTHORITY_INVARIANT_VIOLATION
    ),
    "security_state_transitions_version_valid": (
        PersistenceErrorCategory.AUTHORITY_INVARIANT_VIOLATION
    ),
    "security_state_transitions_reason_code_check": (
        PersistenceErrorCategory.AUTHORITY_INVARIANT_VIOLATION
    ),
    "security_state_transitions_authority_epoch_id_check": (
        PersistenceErrorCategory.AUTHORITY_INVARIANT_VIOLATION
    ),
}


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    name = getattr(diagnostic, "constraint_name", None)
    return name if isinstance(name, str) and name else None


def translate_integrity_error(error: IntegrityError) -> NoReturn:
    """Raise a stable error for a registered constraint; preserve unknown failures."""
    name = _constraint_name(error)
    if name is None:
        raise error
    category = _KNOWN_CONSTRAINT_CATEGORIES.get(name)
    if category is None:
        raise error
    raise PersistenceBoundaryError(category, name) from error
