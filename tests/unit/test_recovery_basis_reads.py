"""Characterize both recovery basis readers before their extraction."""

from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from research_agent.application.recovery_context_service import RecoveryContextService
from research_agent.application.recovery_restoration_service import RecoveryRestorationService
from research_agent.application.security_capability import SecurityCapabilityDenied
from research_agent.persistence.models import SecurityStateRecord


@pytest.mark.parametrize("reader", ["context", "restoration"])
@pytest.mark.parametrize(
    "defect",
    [
        "singleton",
        "started_at",
        "state",
        "version",
        "bad_state",
        "bad_version",
        "retained_origin",
        "equal_version",
        "naive_time",
    ],
)
def test_basis_reader_preserves_fail_closed_exception_boundary(reader, defect):
    record = SecurityStateRecord(
        id=1,
        state="normal",
        version=8,
        authority_epoch_id=uuid4(),
        recovery_bootstrap_pending=True,
        recovery_bootstrap_started_at=datetime.now(UTC),
        recovery_bootstrap_from_state="normal",
        recovery_bootstrap_from_version=7,
        reconstruction_validation_pending=False,
    )
    expected_error = SecurityCapabilityDenied
    if defect in {"started_at", "state", "version"}:
        column = {
            "started_at": "recovery_bootstrap_started_at",
            "state": "recovery_bootstrap_from_state",
            "version": "recovery_bootstrap_from_version",
        }[defect]
        setattr(record, column, None)
    elif defect == "bad_state":
        record.recovery_bootstrap_from_state = "unrecognized"
    elif defect == "bad_version":
        record.recovery_bootstrap_from_version = 0
    elif defect == "retained_origin":
        record.recovery_bootstrap_pending = False
    elif defect == "equal_version":
        record.recovery_bootstrap_from_version = record.version
        expected_error = ValidationError
    elif defect == "naive_time":
        record.recovery_bootstrap_started_at = datetime.now()
        expected_error = ValidationError
    session = Mock()
    session.scalar.return_value = session.get.return_value = (
        None if defect == "singleton" else record
    )
    with pytest.raises(expected_error):
        if reader == "context":
            RecoveryContextService._basis(session)
        else:
            RecoveryRestorationService._locked_basis(session)
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
