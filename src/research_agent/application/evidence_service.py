"""Application service for sources, claims, provenance, and retry-safe writes."""

from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.application.audit_service import AuditService
from research_agent.application.memory_service import MemoryService
from research_agent.application.research_service import ResearchTaskNotFound
from research_agent.application.security_capability import (
    SecurityCapability,
    require_capability,
)
from research_agent.domain.events import EventPayload, EventType
from research_agent.domain.memory import (
    MemoryAuthority,
    MemoryChangeProposal,
    MemoryConflict,
    MemoryOperation,
    MemoryTarget,
)
from research_agent.domain.research import (
    ClaimCreate,
    ClaimResponse,
    ClaimSourceLink,
    SourceCreate,
    SourceResponse,
    SourceType,
)
from research_agent.persistence.models import (
    ClaimSourceRecord,
    ResearchClaimRecord,
    ResearchSourceRecord,
    ResearchTaskRecord,
)
from research_agent.ports.retrieval import RetrievedSource


class EvidenceService:
    """Serialize evidence writes per task using a PostgreSQL row lock."""

    def __init__(
        self,
        session: Session,
        operation_id: UUID | None = None,
        *,
        actor: Literal["local_operator", "claim_extractor"] = "local_operator",
    ) -> None:
        self.session = session
        self.actor = actor
        self.operation_id = operation_id or uuid4()

    def require_task(self, task_id: UUID, *, lock: bool = False) -> None:
        statement = select(ResearchTaskRecord.id).where(ResearchTaskRecord.id == task_id)
        if lock:
            statement = statement.with_for_update()
        if self.session.scalar(statement) is None:
            raise ResearchTaskNotFound

    def create_source(
        self,
        task_id: UUID,
        source: SourceCreate,
        *,
        audit_event: EventType | None = None,
        audit_actor: Literal["local_operator", "agent_network"] = "local_operator",
        provenance: list[UUID] | None = None,
        before_write: Callable[[], None] | None = None,
        after_write: Callable[[SourceResponse], None] | None = None,
    ) -> SourceResponse:
        try:
            # Re-check immediately before governed persistence so an in-flight
            # retrieval/agent response cannot bypass a restrictive transition.
            require_capability(self.session, SecurityCapability.MEMORY_MUTATION)
            self.require_task(task_id, lock=True)
            if before_write is not None:
                before_write()
            content_hash = sha256(source.content.encode("utf-8")).hexdigest()
            record = self.session.scalar(
                select(ResearchSourceRecord)
                .where(
                    ResearchSourceRecord.task_id == task_id,
                    ResearchSourceRecord.source_type == source.source_type.value,
                    ResearchSourceRecord.uri == source.uri,
                    ResearchSourceRecord.content_hash == content_hash,
                    ResearchSourceRecord.content == source.content,
                )
                .order_by(ResearchSourceRecord.observed_at, ResearchSourceRecord.id)
                .limit(1)
            )
            reused = record is not None
            if record is None:
                record = ResearchSourceRecord(
                    id=uuid4(),
                    task_id=task_id,
                    source_type=source.source_type.value,
                    title=source.title,
                    uri=source.uri,
                    publisher=source.publisher,
                    content=source.content,
                    content_hash=content_hash,
                    reliability_score=source.reliability_score,
                    observed_at=datetime.now(UTC),
                    source_metadata=source.source_metadata,
                )
                self.session.add(record)
                self.session.flush()
            AuditService(self.session).stage(
                task_id,
                EventType.SOURCE_REUSED if reused else EventType.SOURCE_CREATED,
                EventPayload(
                    operation_id=self.operation_id,
                    source_id=record.id,
                    actor=audit_actor,
                    provenance=provenance,
                    result="reused" if reused else "committed",
                ),
            )
            if audit_event is not None:
                AuditService(self.session).stage(
                    task_id,
                    audit_event,
                    EventPayload(
                        operation_id=self.operation_id,
                        source_id=record.id,
                        actor=audit_actor,
                        provenance=provenance,
                        result="reused" if reused else "committed",
                    ),
                )
            response = SourceResponse.model_validate(record, from_attributes=True)
            if after_write is not None:
                after_write(response)
            self.session.commit()
            return response
        except Exception:
            self.session.rollback()
            raise

    def create_source_from_retrieval(
        self,
        task_id: UUID,
        retrieved: RetrievedSource,
        reliability_score: float,
        source_type: SourceType,
    ) -> SourceResponse:
        """Use the same identity rules for fetched and supplied sources."""
        return self.create_source(
            task_id,
            SourceCreate(
                source_type=source_type,
                title=retrieved.title,
                uri=retrieved.uri,
                publisher=retrieved.publisher,
                content=retrieved.content,
                reliability_score=reliability_score,
            ),
        )

    def create_claim(self, task_id: UUID, claim: ClaimCreate) -> ClaimResponse:
        try:
            result = self.stage_claim(task_id, claim)
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def stage_claim(self, task_id: UUID, claim: ClaimCreate) -> ClaimResponse:
        """Find or insert a claim; the caller must commit or roll back the batch."""
        self.require_task(task_id, lock=True)
        if self.actor == "claim_extractor" and claim.status.value != "unverified":
            raise ValueError("Extracted claims must remain unverified")
        source_ids = {link.source_id for link in claim.source_links}
        if len(source_ids) != len(claim.source_links):
            raise ValueError("Each source may appear only once in a claim")
        sources = self.session.scalars(
            select(ResearchSourceRecord.id).where(
                ResearchSourceRecord.id.in_(source_ids),
                ResearchSourceRecord.task_id == task_id,
            )
        ).all()
        if len(sources) != len(source_ids):
            raise ValueError("Every claim source must exist within the same investigation")

        identity = {(link.source_id, link.support_type.value) for link in claim.source_links}
        candidates = self.session.scalars(
            select(ResearchClaimRecord)
            .where(
                ResearchClaimRecord.task_id == task_id,
                ResearchClaimRecord.statement == claim.statement,
            )
            .order_by(ResearchClaimRecord.created_at, ResearchClaimRecord.id)
        ).all()
        for candidate in candidates:
            response = self.claim_response(candidate)
            if {
                (link.source_id, link.support_type.value) for link in response.source_links
            } == identity:
                if candidate.lifecycle != "active":
                    raise MemoryConflict(
                        "Matching claim is inactive; explicit restoration required"
                    )
                AuditService(self.session).stage(
                    task_id,
                    EventType.CLAIM_REUSED,
                    EventPayload(
                        operation_id=self.operation_id,
                        claim_id=candidate.id,
                        actor=self.actor,
                        result="reused",
                    ),
                )
                return response

        target_id = uuid4()
        MemoryService(self.session).stage(
            MemoryChangeProposal(
                target_type=MemoryTarget.CLAIM,
                target_id=target_id,
                operation=MemoryOperation.CREATE,
                expected_version=0,
                reason="Claim ingestion",
                claim=claim,
            ),
            MemoryAuthority(actor=self.actor, task_id=task_id, can_commit=True),
        )
        record = self.session.get(ResearchClaimRecord, target_id)
        if record is None:
            raise RuntimeError("Claim creation did not produce a governed record")
        AuditService(self.session).stage(
            task_id,
            EventType.CLAIM_CREATED,
            EventPayload(
                operation_id=self.operation_id,
                claim_id=record.id,
                actor=self.actor,
                result="committed",
            ),
        )
        return self.claim_response(record)

    def claim_response(self, record: ResearchClaimRecord) -> ClaimResponse:
        links = self.session.scalars(
            select(ClaimSourceRecord)
            .where(ClaimSourceRecord.claim_id == record.id)
            .order_by(ClaimSourceRecord.source_id)
        ).all()
        return ClaimResponse.model_validate(
            {
                "id": record.id,
                "task_id": record.task_id,
                "statement": record.statement,
                "confidence": record.confidence,
                "status": record.status,
                "created_at": record.created_at,
                "version": record.version,
                "lifecycle": record.lifecycle,
                "source_links": [
                    ClaimSourceLink.model_validate(link, from_attributes=True) for link in links
                ],
            }
        )
