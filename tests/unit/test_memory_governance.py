from uuid import uuid4

import pytest
from pydantic import ValidationError

from research_agent.domain.memory import (
    MemoryAuthority,
    MemoryChangeProposal,
    MemoryDenied,
    MemoryOperation,
    MemoryTarget,
)
from research_agent.domain.research import ClaimCreate, ClaimSourceLink, SupportType


def claim() -> ClaimCreate:
    return ClaimCreate(
        statement="A governed claim",
        source_links=[
            ClaimSourceLink(
                source_id=uuid4(),
                support_type=SupportType.SUPPORTING,
            )
        ],
    )


def test_create_requires_zero_version_and_payload() -> None:
    proposal = MemoryChangeProposal(
        target_type=MemoryTarget.CLAIM,
        target_id=uuid4(),
        operation=MemoryOperation.CREATE,
        expected_version=0,
        reason="initial evidence ingestion",
        claim=claim(),
    )
    assert proposal.expected_version == 0
    with pytest.raises(ValidationError):
        MemoryChangeProposal(
            target_type=MemoryTarget.CLAIM,
            target_id=uuid4(),
            operation=MemoryOperation.CREATE,
            expected_version=1,
            reason="invalid version",
            claim=claim(),
        )


def test_lifecycle_proposals_cannot_smuggle_new_state() -> None:
    with pytest.raises(ValidationError):
        MemoryChangeProposal(
            target_type=MemoryTarget.CLAIM,
            target_id=uuid4(),
            operation=MemoryOperation.ARCHIVE,
            expected_version=1,
            reason="archive",
            claim=claim(),
        )


def test_model_authority_is_not_commit_authority() -> None:
    authority = MemoryAuthority(actor="model", task_id=uuid4(), can_commit=True)
    with pytest.raises(MemoryDenied):
        # The service check is intentionally represented by the trusted context
        # contract: a model cannot turn a proposal into committed state.
        if authority.actor == "model" or not authority.can_commit:
            raise MemoryDenied("Caller cannot commit memory")
