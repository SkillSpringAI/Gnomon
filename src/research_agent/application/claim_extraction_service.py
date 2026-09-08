"""Application service for claim extraction from stored sources."""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.adapters.llm.rule_based import RuleBasedClaimExtractor
from research_agent.application.audit_service import AuditService
from research_agent.application.evidence_service import EvidenceService
from research_agent.domain.events import EventPayload, EventType
from research_agent.domain.research import ClaimResponse, SourceResponse, SourceType
from research_agent.persistence.models import ResearchSourceRecord
from research_agent.ports.claim_extraction import ClaimExtractor


class SourceNotFound(Exception):
    """Raised when a source is not part of the requested task."""


class ClaimExtractionService:
    """Extract and persist claims while preserving source provenance."""

    def __init__(self, session: Session, extractor: ClaimExtractor | None = None) -> None:
        self.session = session
        self.extractor = extractor or RuleBasedClaimExtractor()

    def extract_for_source(self, task_id: UUID, source_id: UUID) -> list[ClaimResponse]:
        source = self.session.scalar(
            select(ResearchSourceRecord).where(
                ResearchSourceRecord.id == source_id,
                ResearchSourceRecord.task_id == task_id,
            )
        )
        if source is None:
            raise SourceNotFound

        source_response = SourceResponse(
            id=source.id,
            task_id=source.task_id,
            source_type=SourceType(source.source_type),
            title=source.title,
            uri=source.uri,
            publisher=source.publisher,
            content=source.content,
            reliability_score=source.reliability_score,
            observed_at=source.observed_at,
        )
        # Extraction may be slow or external in the future: propose before taking
        # the task lock, then validate and commit all proposals in one transaction.
        operation_id = uuid4()
        try:
            proposals = self.extractor.extract(source_response)
            evidence_service = EvidenceService(self.session, operation_id)
            evidence_service.require_task(task_id, lock=True)
            claims: list[ClaimResponse] = []
            seen: set[UUID] = set()
            for proposal in proposals:
                if {link.source_id for link in proposal.source_links} != {source_id}:
                    raise ValueError("Extracted claims must cite only the requested source")
                claim = evidence_service.stage_claim(task_id, proposal)
                if claim.id not in seen:
                    claims.append(claim)
                    seen.add(claim.id)
            AuditService(self.session).stage(
                task_id,
                EventType.EXTRACTION_COMPLETED,
                EventPayload(
                    operation_id=operation_id, source_id=source_id, claim_count=len(claims)
                ),
            )
            self.session.commit()
            return claims
        except Exception:
            AuditService(self.session).record_failure(
                task_id,
                EventType.EXTRACTION_FAILED,
                EventPayload(
                    operation_id=operation_id, source_id=source_id, reason="extraction_failed"
                ),
            )
            raise
