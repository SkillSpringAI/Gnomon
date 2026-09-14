"""Acquire operator-selected web sources for a bounded research cycle."""

from functools import partial
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from research_agent.adapters.web.http import SourceRetrievalError
from research_agent.application.audit_service import AuditService
from research_agent.application.claim_extraction_service import ClaimExtractionService
from research_agent.application.cycle_progress import CycleProgress
from research_agent.application.evidence_service import EvidenceService
from research_agent.application.research_service import ResearchService, TaskStateConflict
from research_agent.application.source_registry import UntrustedSourceError
from research_agent.domain.events import EventPayload, EventType
from research_agent.domain.research import (
    CycleObjectiveResult,
    CycleOutcomeCreate,
    CycleStatus,
    ResearchMethod,
    ResearchTask,
    SourceCreate,
    SourceType,
    TaskStatus,
)
from research_agent.persistence.repositories import SqlAlchemyResearchTaskRepository
from research_agent.ports.retrieval import SourceRetriever, SourceTarget


class CycleSourceTarget(BaseModel):
    """One explicit URL mapped to a zero-based objective in the saved plan."""

    model_config = ConfigDict(extra="forbid")
    objective_index: int = Field(ge=0, strict=True)
    uri: str = Field(min_length=1, max_length=2000)


class SourceCycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sources: list[CycleSourceTarget] = Field(min_length=1, max_length=2)


class SourceCycleRunner:
    def __init__(self, session: Session, retriever: SourceRetriever) -> None:
        self.session = session
        self.retriever = retriever

    def run(self, task_id: UUID, cycle_number: int, request: SourceCycleRequest) -> ResearchTask:
        repository = SqlAlchemyResearchTaskRepository(self.session)
        research = ResearchService(repository)
        task = research.start_cycle(
            task_id,
            cycle_number,
            exclusive=True,
            track_progress=True,
            objective_indices=[source.objective_index for source in request.sources],
            required_method=ResearchMethod.WEB_RESEARCH,
        )
        cycle = next(item for item in task.cycles if item.number == cycle_number)
        progress = CycleProgress(self.session, task_id, cycle_number)
        attempted: list[str] = []
        results: dict[int, CycleObjectiveResult] = {}
        evidence_ids: list[UUID] = []
        claim_ids: list[UUID] = []
        progress.start()

        def guard() -> None:
            current = repository.get(task_id, for_update=True)
            current_cycle = next(item for item in current.cycles if item.number == cycle_number)
            if current.status != TaskStatus.ACTIVE or current_cycle.status != CycleStatus.ACTIVE:
                raise TaskStateConflict("Investigation or cycle stopped during retrieval")

        def checkpoint() -> None:
            try:
                guard()
            finally:
                self.session.rollback()

        def outcome(status: str) -> ResearchTask:
            progress.finish(status)
            return research.record_cycle_outcome(
                task_id,
                cycle_number,
                CycleOutcomeCreate(
                    status="completed"
                    if status == "completed"
                    else "blocked"
                    if status == "blocked"
                    else "failed",
                    result_summary=(
                        f"Source collection {status}: {len(evidence_ids)} source(s), "
                        f"{len(claim_ids)} unverified claim(s)."
                    ),
                    evidence_ids=evidence_ids,
                    claim_ids=claim_ids,
                    attempted_objectives=attempted,
                    objective_results=list(results.values()),
                    unresolved_objectives=list(cycle.objectives),
                ),
                require_active_task=status == "completed",
            )

        def recover(status: str) -> ResearchTask:
            self.session.rollback()
            try:
                return outcome(status)
            except TaskStateConflict:
                current = repository.get(task_id)
                current_cycle = next(item for item in current.cycles if item.number == cycle_number)
                if current_cycle.status not in {
                    CycleStatus.COMPLETED,
                    CycleStatus.BLOCKED,
                    CycleStatus.FAILED,
                }:
                    # A rejected recovery write is not a successfully recorded outcome.
                    raise
                return current

        try:
            for target in request.sources:
                checkpoint()
                progress.attempt([target.objective_index])
                objective = cycle.objectives[target.objective_index]
                if objective not in attempted:
                    attempted.append(objective)
                result = results.setdefault(
                    target.objective_index,
                    CycleObjectiveResult(objective_index=target.objective_index),
                )
                evidence = EvidenceService(self.session)
                try:
                    retrieved = self.retriever.fetch(SourceTarget(uri=target.uri))
                except (SourceRetrievalError, UntrustedSourceError) as error:
                    AuditService(self.session).record_failure(
                        task_id,
                        EventType.RETRIEVAL_FAILED,
                        EventPayload(
                            operation_id=evidence.operation_id,
                            reason="domain_not_enabled"
                            if isinstance(error, UntrustedSourceError)
                            else "retrieval_rejected",
                        ),
                    )
                    raise
                source = evidence.create_source(
                    task_id,
                    SourceCreate(
                        source_type=SourceType.WEB_PAGE,
                        uri=retrieved.uri,
                        title=retrieved.title,
                        publisher=retrieved.publisher,
                        content=retrieved.content,
                    ),
                    before_write=guard,
                    after_write=partial(progress.source, indices=[target.objective_index]),
                )
                if source.id not in evidence_ids:
                    evidence_ids.append(source.id)
                if source.id not in result.source_ids:
                    result.source_ids.append(source.id)
                checkpoint()
                claims = ClaimExtractionService(self.session).extract_for_source(
                    task_id,
                    source.id,
                    before_write=guard,
                    after_write=partial(progress.claims, indices=[target.objective_index]),
                )
                claim_ids.extend(claim.id for claim in claims if claim.id not in claim_ids)
                result.claim_ids.extend(
                    claim.id for claim in claims if claim.id not in result.claim_ids
                )
            return outcome("completed")
        except (SourceRetrievalError, UntrustedSourceError, TaskStateConflict, ValueError):
            return recover("blocked")
        except Exception as error:
            try:
                recover("failed")
            except Exception:
                self.session.rollback()
                error.add_note("Cycle recovery failed; operator recovery is required.")
            raise
