"""Deterministic claim/assessment governance. Providers never receive this service."""

import hashlib
import json
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from research_agent.application.audit_service import AuditService
from research_agent.application.research_service import ResearchTaskNotFound
from research_agent.domain.events import EventPayload, EventType
from research_agent.domain.memory import (
    AppliedMemoryChange,
    MemoryAuthority,
    MemoryChangeProposal,
    MemoryConflict,
    MemoryDenied,
    MemoryOperation,
    MemoryReversal,
    MemoryTarget,
)
from research_agent.domain.research import (
    ClaimCreate,
    ClaimSourceLink,
    ClaimStatus,
    HypothesisAssessmentCreate,
    utc_now,
)
from research_agent.persistence.models import (
    AssessmentEvidenceRecord,
    ClaimSourceRecord,
    HypothesisAssessmentRecord,
    MemoryChangeRecord,
    ResearchClaimRecord,
    ResearchCycleRecord,
    ResearchSourceRecord,
    ResearchTaskRecord,
)

KnowledgeRecord = ResearchClaimRecord | HypothesisAssessmentRecord


class MemoryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _authorize(self, authority: MemoryAuthority) -> None:
        if not authority.can_commit or authority.actor == "model":
            # A denied mutation is a security-significant attempt. Persist the
            # bounded event independently so the caller's failed transaction
            # cannot erase the trail.
            AuditService(self.session).record_failure(
                authority.task_id,
                EventType.SECURITY_EVENT,
                EventPayload(
                    operation_id=uuid4(),
                    actor=authority.actor,
                    result="rejected",
                    change_reason="unauthorized_memory_mutation",
                ),
            )
            raise MemoryDenied("Caller cannot commit memory")

    @staticmethod
    def _digest(state: dict[str, Any] | None) -> str | None:
        if state is None:
            return None
        encoded = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def _task(self, task_id: UUID) -> ResearchTaskRecord:
        task = self.session.scalar(
            select(ResearchTaskRecord)
            .where(ResearchTaskRecord.id == task_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if task is None:
            raise ResearchTaskNotFound
        return task

    def _record(self, kind: MemoryTarget, target_id: UUID) -> KnowledgeRecord | None:
        if kind == MemoryTarget.CLAIM:
            return self.session.get(ResearchClaimRecord, target_id, populate_existing=True)
        return self.session.get(HypothesisAssessmentRecord, target_id, populate_existing=True)

    def state(self, record: KnowledgeRecord) -> dict[str, Any]:
        if isinstance(record, ResearchClaimRecord):
            links = self.session.scalars(
                select(ClaimSourceRecord)
                .where(ClaimSourceRecord.claim_id == record.id)
                .order_by(ClaimSourceRecord.source_id)
            ).all()
            data = ClaimCreate(
                statement=record.statement,
                confidence=record.confidence,
                status=ClaimStatus(record.status),
                source_links=[
                    ClaimSourceLink.model_validate(link, from_attributes=True) for link in links
                ],
            ).model_dump(mode="json")
            return {"data": data, "lifecycle": record.lifecycle}
        links2 = self.session.scalars(
            select(AssessmentEvidenceRecord)
            .where(AssessmentEvidenceRecord.assessment_id == record.id)
            .order_by(AssessmentEvidenceRecord.claim_id)
        ).all()
        data = HypothesisAssessmentCreate.model_validate(
            {
                "status": record.status,
                "summary": record.summary,
                "confidence": record.confidence,
                "evidence_links": [
                    {
                        "claim_id": link.claim_id,
                        "relation": link.relation,
                        "strength": link.strength,
                    }
                    for link in links2
                ],
            }
        ).model_dump(mode="json")
        return {
            "data": data,
            "lifecycle": record.lifecycle,
            "hypothesis_id": str(record.hypothesis_id),
        }

    def _validate_state(
        self,
        task: ResearchTaskRecord,
        kind: MemoryTarget,
        target_id: UUID,
        before: dict[str, Any] | None,
        after: dict[str, Any],
        *,
        allow_provenance_removal: bool = False,
    ) -> list[str]:
        if kind == MemoryTarget.CLAIM:
            claim = ClaimCreate.model_validate(after["data"])
            ids = [link.source_id for link in claim.source_links]
            found = self.session.scalars(
                select(ResearchSourceRecord.id).where(
                    ResearchSourceRecord.task_id == task.id, ResearchSourceRecord.id.in_(ids)
                )
            ).all()
            if len(set(ids)) != len(ids) or set(found) != set(ids):
                raise ValueError("Claim requires unique sources from this investigation")
            # Never detach old provenance through an ordinary update.
            if before is not None:
                old = {(x["source_id"], x["support_type"]) for x in before["data"]["source_links"]}
                new = {(str(x.source_id), x.support_type.value) for x in claim.source_links}
                if not allow_provenance_removal and not old.issubset(new):
                    raise MemoryConflict("UPDATE cannot remove existing provenance")
                if before != after:
                    dependent = self.session.scalar(
                        select(AssessmentEvidenceRecord.claim_id)
                        .where(AssessmentEvidenceRecord.claim_id == target_id)
                        .limit(1)
                    )
                    cycle = self.session.scalar(
                        select(ResearchCycleRecord.id)
                        .where(
                            ResearchCycleRecord.task_id == task.id,
                            ResearchCycleRecord.claim_ids.contains([str(target_id)]),
                        )
                        .limit(1)
                    )
                    if dependent is not None or cycle is not None:
                        raise MemoryConflict("Dependent research requires explicit reassessment")
            return [str(x) for x in ids]
        assessment = HypothesisAssessmentCreate.model_validate(after["data"])
        hypothesis_id = after["hypothesis_id"]
        if not any(h["id"] == hypothesis_id for h in task.brief["hypotheses"]):
            raise ValueError("Hypothesis must belong to this investigation")
        existing = self.session.scalar(
            select(HypothesisAssessmentRecord.id).where(
                HypothesisAssessmentRecord.task_id == task.id,
                HypothesisAssessmentRecord.hypothesis_id == UUID(hypothesis_id),
                HypothesisAssessmentRecord.id != target_id,
            )
        )
        if existing is not None:
            raise MemoryConflict("Hypothesis already has an assessment; update or restore it")
        claim_ids = [link.claim_id for link in assessment.evidence_links]
        found_claims = self.session.scalars(
            select(ResearchClaimRecord.id).where(
                ResearchClaimRecord.task_id == task.id,
                ResearchClaimRecord.id.in_(claim_ids),
                ResearchClaimRecord.lifecycle == "active",
            )
        ).all()
        if len(set(claim_ids)) != len(claim_ids) or set(found_claims) != set(claim_ids):
            raise ValueError("Assessment requires unique active claims from this investigation")
        return [str(x) for x in claim_ids]

    def _prepare(
        self,
        proposal: MemoryChangeProposal,
        authority: MemoryAuthority,
    ) -> tuple[KnowledgeRecord | None, dict[str, Any] | None, dict[str, Any], list[str]]:
        task = self._task(authority.task_id)
        record = self._record(proposal.target_type, proposal.target_id)
        if record is not None and record.task_id != task.id:
            raise MemoryConflict("Target is not in this investigation")
        if (record is None) != (proposal.operation == MemoryOperation.CREATE):
            raise MemoryConflict(
                "CREATE needs a new target; other operations need an existing target"
            )
        if record is not None and record.version != proposal.expected_version:
            raise MemoryConflict("Stale target version")
        before = self.state(record) if record is not None else None
        if proposal.operation in (MemoryOperation.CREATE, MemoryOperation.UPDATE):
            if before is not None and before["lifecycle"] != "active":
                raise MemoryConflict("Restore inactive records before updating")
            payload = proposal.claim or proposal.assessment
            assert payload is not None
            after: dict[str, Any] = {"data": payload.model_dump(mode="json"), "lifecycle": "active"}
            if proposal.target_type == MemoryTarget.ASSESSMENT:
                after["hypothesis_id"] = (
                    str(proposal.hypothesis_id) if before is None else before["hypothesis_id"]
                )
        else:
            assert before is not None
            required = {
                MemoryOperation.ARCHIVE: {"active"},
                MemoryOperation.LOGICAL_DELETE: {"active", "archived"},
                MemoryOperation.RESTORE: {"archived", "logically_deleted"},
            }
            if before["lifecycle"] not in required[proposal.operation]:
                raise MemoryConflict("Invalid memory lifecycle transition")
            after = before | {
                "lifecycle": {
                    MemoryOperation.ARCHIVE: "archived",
                    MemoryOperation.LOGICAL_DELETE: "logically_deleted",
                    MemoryOperation.RESTORE: "active",
                }[proposal.operation]
            }
        if authority.actor in ("claim_extractor", "model"):
            if (
                proposal.operation != MemoryOperation.CREATE
                or proposal.claim is None
                or proposal.claim.status != ClaimStatus.UNVERIFIED
            ):
                raise MemoryDenied(
                    "Reasoning components may only propose unverified claim creation"
                )
            if task.status != "active":
                raise MemoryDenied("Automated claims require an active investigation")
        key = "source_links" if proposal.target_type == MemoryTarget.CLAIM else "evidence_links"
        id_key = "source_id" if proposal.target_type == MemoryTarget.CLAIM else "claim_id"
        after["data"][key] = sorted(after["data"][key], key=lambda item: item[id_key])
        provenance = self._validate_state(
            task, proposal.target_type, proposal.target_id, before, after
        )
        return record, before, after, provenance

    def validate(self, proposal: MemoryChangeProposal, authority: MemoryAuthority) -> None:
        """Read-only advisory validation; commit always repeats this under the task lock."""
        self._prepare(proposal, authority)

    def apply(
        self, proposal: MemoryChangeProposal, authority: MemoryAuthority
    ) -> AppliedMemoryChange:
        try:
            result = self.stage(proposal, authority)
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def stage(
        self,
        proposal: MemoryChangeProposal,
        authority: MemoryAuthority,
    ) -> AppliedMemoryChange:
        """Caller owns atomic transaction, including extraction batches."""
        self._authorize(authority)
        self._task(authority.task_id)
        request = proposal.model_dump(mode="json")
        prior = self.session.get(MemoryChangeRecord, proposal.change_id)
        if prior is not None:
            if (
                prior.task_id != authority.task_id
                or prior.actor != authority.actor
                or prior.request != request
            ):
                raise MemoryConflict("Change ID already used for a different request")
            return AppliedMemoryChange.model_validate(prior, from_attributes=True)
        record, before, after, provenance = self._prepare(proposal, authority)
        return self._write(
            authority,
            proposal.change_id,
            proposal.target_type,
            proposal.target_id,
            proposal.operation.value,
            proposal.reason,
            record,
            before,
            after,
            provenance,
            request,
        )

    def _write(
        self,
        authority: MemoryAuthority,
        change_id: UUID,
        kind: MemoryTarget,
        target_id: UUID,
        operation: str,
        reason: str,
        record: KnowledgeRecord | None,
        before: dict[str, Any] | None,
        after: dict[str, Any],
        provenance: list[str],
        request: dict[str, Any],
        reverses: UUID | None = None,
    ) -> AppliedMemoryChange:
        previous_version = record.version if record is not None else 0
        now = utc_now()
        data = after["data"]
        if kind == MemoryTarget.CLAIM:
            if record is None:
                record = ResearchClaimRecord(
                    id=target_id, task_id=authority.task_id, created_at=now
                )
                self.session.add(record)
            assert isinstance(record, ResearchClaimRecord)
            record.statement, record.confidence, record.status = (
                data["statement"],
                data["confidence"],
                data["status"],
            )
        else:
            if record is None:
                record = HypothesisAssessmentRecord(
                    id=target_id,
                    task_id=authority.task_id,
                    hypothesis_id=UUID(after["hypothesis_id"]),
                )
                self.session.add(record)
            assert isinstance(record, HypothesisAssessmentRecord)
            record.summary, record.confidence, record.status = (
                data["summary"],
                data["confidence"],
                data["status"],
            )
        record.version, record.lifecycle = previous_version + 1, after["lifecycle"]
        record.updated_at = now
        self.session.flush()
        if kind == MemoryTarget.CLAIM:
            self.session.execute(
                delete(ClaimSourceRecord).where(ClaimSourceRecord.claim_id == target_id)
            )
            self.session.add_all(
                ClaimSourceRecord(
                    claim_id=target_id,
                    source_id=UUID(link["source_id"]),
                    support_type=link["support_type"],
                    strength=link["strength"],
                )
                for link in data["source_links"]
            )
        else:
            self.session.execute(
                delete(AssessmentEvidenceRecord).where(
                    AssessmentEvidenceRecord.assessment_id == target_id
                )
            )
            self.session.add_all(
                AssessmentEvidenceRecord(
                    assessment_id=target_id,
                    claim_id=UUID(link["claim_id"]),
                    relation=link["relation"],
                    strength=link["strength"],
                )
                for link in data["evidence_links"]
            )
        change = MemoryChangeRecord(
            change_id=change_id,
            task_id=authority.task_id,
            target_type=kind.value,
            target_id=target_id,
            operation=operation,
            actor=authority.actor,
            timestamp=now,
            previous_version=previous_version,
            version=record.version,
            previous_state=before,
            proposed_state=after,
            resulting_state=after,
            reason=reason,
            provenance=provenance,
            request=request,
            reverses_change_id=reverses,
        )
        self.session.add(change)
        # Claim extraction retains its established claim.created audit contract;
        # the append-only memory journal still records the governed change. Operator
        # mutations additionally expose a public memory event.
        if authority.actor != "claim_extractor":
            AuditService(self.session).stage(
                authority.task_id,
                EventType.MEMORY_REVERSED if reverses else EventType.MEMORY_CHANGED,
                EventPayload.model_validate(
                    {
                        "operation_id": change_id,
                        "change_id": change_id,
                        "target_id": target_id,
                        "target_type": kind.value,
                        "actor": authority.actor,
                        "memory_operation": operation,
                        "previous_version": previous_version,
                        "version": record.version,
                        "previous_state_digest": self._digest(before),
                        "new_state_digest": self._digest(after),
                        "provenance": [UUID(item) for item in provenance],
                        "change_reason": reason,
                        "result": "committed",
                    }
                ),
            )
        self.session.flush()
        return AppliedMemoryChange.model_validate(change, from_attributes=True)

    def reverse(
        self,
        original_id: UUID,
        request: MemoryReversal,
        authority: MemoryAuthority,
    ) -> AppliedMemoryChange:
        try:
            self._authorize(authority)
            if authority.actor != "local_operator" or not request.reason.strip():
                raise MemoryDenied("Only the operator can request reversal")
            task = self._task(authority.task_id)
            original = self.session.get(MemoryChangeRecord, original_id)
            if original is None or original.task_id != task.id:
                raise MemoryConflict("Change not found in this investigation")
            if original.reverses_change_id is not None:
                raise MemoryConflict("Reversal of reversal is not supported")
            duplicate = self.session.scalar(
                select(MemoryChangeRecord).where(
                    MemoryChangeRecord.reverses_change_id == original_id
                )
            )
            if duplicate is not None:
                result = AppliedMemoryChange.model_validate(duplicate, from_attributes=True)
                self.session.commit()
                return result
            if self.session.get(MemoryChangeRecord, request.change_id) is not None:
                raise MemoryConflict("Reversal change ID is already used")
            if utc_now() >= original.timestamp + timedelta(hours=48):
                raise MemoryConflict("Reversal window expired")
            kind = MemoryTarget(original.target_type)
            record = self._record(kind, original.target_id)
            if record is None or record.task_id != task.id or record.version != original.version:
                raise MemoryConflict("Newer or missing state prevents reversal")
            before = self.state(record)
            if before != original.resulting_state:
                raise MemoryConflict("Current state no longer matches the accepted change")
            after = original.previous_state or (before | {"lifecycle": "logically_deleted"})
            # Normal updates preserve provenance; inverse operations may restore the
            # historical links, after rejecting dependent assessment/cycle changes.
            provenance = self._validate_state(
                task, kind, original.target_id, before, after, allow_provenance_removal=True
            )
            result = self._write(
                authority,
                request.change_id,
                kind,
                original.target_id,
                "REVERSE",
                request.reason,
                record,
                before,
                after,
                provenance,
                request.model_dump(mode="json"),
                original_id,
            )
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise
