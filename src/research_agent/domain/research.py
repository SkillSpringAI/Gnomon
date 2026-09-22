"""Domain models for open-ended research investigations."""

from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(UTC)


class TaskStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    PAUSED = "paused"
    BLOCKED = "blocked"
    CONCLUDED = "concluded"
    ABANDONED = "abandoned"
    ARCHIVED = "archived"


class CycleStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class ResearchMethod(StrEnum):
    WEB_RESEARCH = "web_research"
    SOURCE_ANALYSIS = "source_analysis"
    AGENT_DISCOVERY = "agent_discovery"
    AGENT_QUESTIONING = "agent_questioning"
    CRITIQUE = "critique"
    CASE_STUDY = "case_study"


class SourceType(StrEnum):
    WEB_PAGE = "web_page"
    PAPER = "paper"
    DOCUMENT = "document"
    USER_STATEMENT = "user_statement"
    AGENT_MESSAGE = "agent_message"
    API_RESULT = "api_result"
    INFERENCE = "inference"


class TrustedSourceStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    REVIEW = "review"


class ClaimStatus(StrEnum):
    UNVERIFIED = "unverified"
    SUPPORTED = "supported"
    CONTESTED = "contested"
    CONTRADICTED = "contradicted"
    OBSOLETE = "obsolete"
    RETRACTED = "retracted"


class HypothesisAssessmentStatus(StrEnum):
    SUPPORTED = "supported"
    WEAKENED = "weakened"
    MIXED = "mixed"
    UNRESOLVED = "unresolved"


class SupportType(StrEnum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    CONTEXT = "context"
    INFERRED = "inferred"


class Hypothesis(BaseModel):
    """A proposition that an investigation may support or weaken."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    label: str = Field(min_length=1, max_length=40)
    statement: str = Field(min_length=1, max_length=2000)


class ResearchQuestion(BaseModel):
    """A question that guides one or more research cycles."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    question: str = Field(min_length=1, max_length=2000)
    priority: Annotated[int, Field(ge=1, le=5)] = 3


class CaseStudy(BaseModel):
    """A bounded real-world context used for comparative investigation."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)


class ResearchBrief(BaseModel):
    """User-provided brief for an open-ended investigation."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=4000)
    hypotheses: list[Hypothesis] = Field(default_factory=list, max_length=20)
    questions: list[ResearchQuestion] = Field(default_factory=list, max_length=50)
    case_studies: list[CaseStudy] = Field(default_factory=list, max_length=20)
    methods: list[ResearchMethod] = Field(default_factory=list, max_length=20)
    evidence_requirements: list[str] = Field(default_factory=list, max_length=30)
    stopping_criteria: list[str] = Field(default_factory=list, max_length=20)


class InvestigationPlan(BaseModel):
    """Initial plan produced from a research brief."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    first_cycle_objectives: list[str]
    proposed_methods: list[ResearchMethod]
    open_questions: list[str]


class CyclePlanningBasis(BaseModel):
    """Stored reason and evidence identifiers for one planned objective."""

    model_config = ConfigDict(extra="forbid")

    reason: Literal[
        "contradictory_evidence",
        "missing_assessment",
        "unresolved_assessment",
        "unverified_claim",
        "unanalysed_source",
        "open_question",
        "review_stopping_criteria",
        "missing_evidence",
        "incomplete_cycle",
        "agent_contradiction",
        "agent_comparison_limit",
        "agent_corroboration",
        "source_dependence_unknown",
    ]
    hypothesis_id: UUID | None = None
    assessment_id: UUID | None = None
    claim_ids: list[UUID] = Field(default_factory=list)
    source_id: UUID | None = None
    source_ids: list[UUID] = Field(default_factory=list, max_length=100)
    evidence_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class CycleObjectiveResult(BaseModel):
    """Collection associations for a saved objective, not evidence of resolution."""

    model_config = ConfigDict(extra="forbid")

    objective_index: int = Field(ge=0, strict=True)
    source_ids: list[UUID] = Field(default_factory=list, max_length=100)
    claim_ids: list[UUID] = Field(default_factory=list, max_length=100)


class ObjectiveReviewCreate(BaseModel):
    """Operator decision against the evidence displayed for review."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    decision: Literal["completed", "unresolved"]
    rationale: str = Field(min_length=1, max_length=4000)
    source_ids: list[UUID] = Field(default_factory=list, max_length=100)
    claim_ids: list[UUID] = Field(default_factory=list, max_length=100)
    expected_revision: int = Field(ge=0, strict=True)
    expected_evidence_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class ObjectiveReview(BaseModel):
    """Append-only planning decision; does not change accepted knowledge."""

    model_config = ConfigDict(extra="forbid")
    id: UUID = Field(default_factory=uuid4)
    objective_index: int = Field(ge=0, strict=True)
    objective: str
    revision: int = Field(ge=1)
    decision: Literal["completed", "unresolved"]
    rationale: str
    source_ids: list[UUID]
    claim_ids: list[UUID]
    basis: CyclePlanningBasis
    reference_fingerprint: str
    actor: Literal["local_operator"] = "local_operator"
    created_at: datetime = Field(default_factory=utc_now)


class ResearchCycle(BaseModel):
    """A bounded iteration of an open-ended investigation."""

    model_config = ConfigDict(extra="forbid")

    number: int = Field(ge=1)
    planning_basis: list[CyclePlanningBasis] = Field(default_factory=list, max_length=3)
    objectives: list[str]
    methods: list[ResearchMethod]
    status: CycleStatus = CycleStatus.PLANNED
    progress_tracked: bool = False
    recovery_reason: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result_summary: str | None = Field(default=None, max_length=10_000)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)
    claim_ids: list[UUID] = Field(default_factory=list, max_length=100)
    unresolved_objectives: list[str] = Field(default_factory=list, max_length=50)
    attempted_objectives: list[str] = Field(default_factory=list, max_length=3)
    objective_results: list[CycleObjectiveResult] = Field(default_factory=list, max_length=3)
    objective_reviews: list[ObjectiveReview] = Field(default_factory=list, max_length=100)


class CycleAttemptProgress(BaseModel):
    """Read-only durable progress for one persisted cycle execution attempt."""

    model_config = ConfigDict(extra="forbid")

    attempt_id: UUID
    cycle_number: int = Field(ge=1)
    attempt_status: Literal["RUNNING", "COMPLETED", "BLOCKED", "FAILED", "INTERRUPTED"]
    last_durable_stage: Literal[
        "CREATED",
        "STARTED",
        "QUESTIONING",
        "EVIDENCE_RECORDED",
        "EXTRACTING_CLAIMS",
        "FINALIZING",
        "COMPLETED",
        "BLOCKED",
        "FAILED",
        "INTERRUPTED",
    ]
    started_at: datetime
    finished_at: datetime | None = None
    recovery_reason: str | None = None
    retained_evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)
    retained_claim_ids: list[UUID] = Field(default_factory=list, max_length=100)
    attempted_objectives: list[str] = Field(default_factory=list, max_length=3)
    unresolved_objectives: list[str] = Field(default_factory=list, max_length=50)
    cycle_status: CycleStatus
    cycle_active: bool


class CycleRecoveryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=1, max_length=4000)
    expected_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


def recovery_fingerprint(status: TaskStatus, cycle: ResearchCycle) -> str:
    return sha256((status.value + cycle.model_dump_json()).encode()).hexdigest()


class ResearchTask(BaseModel):
    """Persistent state for an investigation."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    brief: ResearchBrief
    plan: InvestigationPlan
    status: TaskStatus = TaskStatus.PLANNED
    cycles: list[ResearchCycle] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    revision: int = Field(default=1, ge=1)


class ResearchTaskResponse(BaseModel):
    """Response returned after creating or retrieving a task."""

    task: ResearchTask


class SourceCreate(BaseModel):
    """Raw evidence submitted to an investigation."""

    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    title: str = Field(min_length=1, max_length=500)
    uri: str | None = Field(default=None, max_length=2000)
    publisher: str | None = Field(default=None, max_length=300)
    content: str = Field(min_length=1, max_length=500_000)
    reliability_score: Annotated[float, Field(ge=0, le=1)] = 0.5
    source_metadata: dict[str, str] = Field(default_factory=dict, max_length=20)


class SourceResponse(BaseModel):
    """Stored source evidence."""

    id: UUID
    task_id: UUID
    source_type: SourceType
    title: str
    uri: str | None
    publisher: str | None
    content: str
    reliability_score: float
    observed_at: datetime
    source_metadata: dict[str, str] = Field(default_factory=dict)


class SourceDependenceKind(StrEnum):
    DERIVED_FROM = "derived_from"
    COMMON_ORIGIN = "common_origin"


class SourceRelationshipLifecycle(StrEnum):
    ACTIVE = "active"
    RETRACTED = "retracted"


class SourceRelationship(BaseModel):
    """Canonical current source-dependence relationship."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relationship_id: UUID
    task_id: UUID
    source_low_id: UUID
    source_high_id: UUID
    kind: SourceDependenceKind
    direction: Literal["low_to_high", "high_to_low", "none"]
    lifecycle: SourceRelationshipLifecycle
    revision: int = Field(ge=1)
    latest_change_id: UUID
    updated_at: datetime


class SourceRelationshipChange(BaseModel):
    """Immutable source-dependence relationship change."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    change_id: UUID
    operation_id: UUID
    relationship_id: UUID
    task_id: UUID
    previous_revision: int = Field(ge=0)
    revision: int = Field(ge=1)
    operation: Literal["CREATE", "SET", "RETRACT", "REVERSE"]
    previous_state: SourceRelationship | None
    resulting_state: SourceRelationship
    actor_type: Literal["local_operator"]
    actor_id: str
    reason: str = Field(min_length=1, max_length=255)
    authority_epoch_id: UUID
    security_state_version: int = Field(ge=1)
    reverses_change_id: UUID | None
    created_at: datetime


class SourceRelationshipCreate(BaseModel):
    """Operator assertion of a source relationship."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    derived_source_id: UUID | None = None
    upstream_source_id: UUID | None = None
    source_a_id: UUID | None = None
    source_b_id: UUID | None = None
    kind: SourceDependenceKind
    reason: str = Field(min_length=1, max_length=255)
    operation_id: UUID = Field(default_factory=uuid4)


class SourceRelationshipMutation(BaseModel):
    """Versioned correction or retraction of a relationship."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    relationship_id: UUID
    expected_revision: int = Field(ge=1, strict=True)
    operation: Literal["SET", "RETRACT"]
    lifecycle: SourceRelationshipLifecycle | None = None
    direction: Literal["low_to_high", "high_to_low", "none"] | None = None
    reason: str = Field(min_length=1, max_length=255)
    operation_id: UUID = Field(default_factory=uuid4)


class SourceRelationshipReversal(BaseModel):
    """Bounded reversal of an eligible accepted relationship change."""

    relationship_id: UUID
    change_id: UUID
    expected_revision: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=255)
    operation_id: UUID = Field(default_factory=uuid4)


class SourceDependenceLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_roots: int = 100
    max_visited_sources: int = 100
    max_examined_relationships: int = 500
    max_hops: int = 8
    max_frontier_sources: int = 100


class SourceDependenceProjection(BaseModel):
    """Bounded source-dependence read, never an independence judgment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: UUID
    complete: bool
    truncated: bool
    limits: SourceDependenceLimits
    visited_source_ids: list[UUID]
    examined_relationships: list[SourceRelationship]
    frontier_source_ids: list[UUID]
    frontier_omitted: bool = False
    overflow_reason: Literal["node_limit", "edge_limit", "depth_limit"] | None = None
    invalid: bool = False
    invalid_reason: Literal["directed_cycle"] | None = None
    unknown_dependence: bool = True
    note: str = (
        "Declared relationships describe dependence only. Missing or partial graph "
        "data remains unknown and does not establish independence."
    )


class SourceFetchRequest(BaseModel):
    """Request to retrieve and store a source from a URI."""

    model_config = ConfigDict(extra="forbid")

    uri: str = Field(min_length=1, max_length=2000)
    source_type: SourceType = SourceType.WEB_PAGE
    reliability_score: Annotated[float, Field(ge=0, le=1)] = 0.5


class TrustedSourceCreate(BaseModel):
    """Registry entry for an approved source domain."""

    model_config = ConfigDict(extra="forbid")

    domain: str = Field(min_length=1, max_length=253)
    display_name: str = Field(min_length=1, max_length=300)
    source_type: SourceType = SourceType.WEB_PAGE
    verification_method: str = Field(min_length=1, max_length=500)
    requires_attribution: bool = True


class TrustedSourceResponse(TrustedSourceCreate):
    """Registry entry returned by the API."""

    id: UUID
    status: TrustedSourceStatus
    verified_at: datetime | None


class TrustedSourcePolicyEvent(BaseModel):
    """Redacted configuration audit evidence for trusted-source policy changes."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    source_id: UUID
    operation: Literal["REGISTER", "ENABLE"]
    previous_status: TrustedSourceStatus | None
    new_status: TrustedSourceStatus
    actor_type: Literal["local_operator"]
    actor_id: str
    authority_epoch_id: UUID
    security_state_version: int = Field(ge=1)
    result: Literal["accepted", "no_op"]
    reason: Literal["registered", "enabled", "already_enabled"]
    created_at: datetime


class ClaimSourceLink(BaseModel):
    """Provenance relationship between a claim and a source."""

    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    support_type: SupportType
    strength: Annotated[float, Field(ge=0, le=1)] = 0.5


class ClaimCreate(BaseModel):
    """Claim proposal that must carry provenance links."""

    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=1, max_length=5000)
    confidence: Annotated[float, Field(ge=0, le=1)] = 0.5
    status: ClaimStatus = ClaimStatus.UNVERIFIED
    source_links: list[ClaimSourceLink] = Field(min_length=1, max_length=50)


class ClaimResponse(BaseModel):
    """Stored claim with provenance."""

    version: int = 1
    lifecycle: Literal["active", "archived", "logically_deleted"] = "active"
    id: UUID
    task_id: UUID
    statement: str
    confidence: float
    status: ClaimStatus
    source_links: list[ClaimSourceLink]
    created_at: datetime


class AssessmentEvidenceLink(BaseModel):
    """Link between a hypothesis assessment and a claim."""

    model_config = ConfigDict(extra="forbid")

    claim_id: UUID
    relation: SupportType
    strength: Annotated[float, Field(ge=0, le=1)] = 0.5


class HypothesisAssessmentCreate(BaseModel):
    """Assessment of one hypothesis based on current evidence."""

    model_config = ConfigDict(extra="forbid")

    status: HypothesisAssessmentStatus
    summary: str = Field(min_length=1, max_length=5000)
    confidence: Annotated[float, Field(ge=0, le=1)] = 0.5
    evidence_links: list[AssessmentEvidenceLink] = Field(min_length=1, max_length=100)


class HypothesisAssessmentResponse(BaseModel):
    """Stored hypothesis assessment with evidence links."""

    version: int = 1
    lifecycle: Literal["active", "archived", "logically_deleted"] = "active"
    id: UUID
    task_id: UUID
    hypothesis_id: UUID
    status: HypothesisAssessmentStatus
    summary: str
    confidence: float
    evidence_links: list[AssessmentEvidenceLink]
    updated_at: datetime


class TaskStatusChange(BaseModel):
    """Compare-and-set lifecycle request; exact retries are harmless."""

    model_config = ConfigDict(extra="forbid")

    status: TaskStatus
    expected_status: TaskStatus


class StoppingDecisionReason(StrEnum):
    EVIDENCE_SUFFICIENT = "evidence_sufficient"
    RESOURCE_LIMITED = "resource_limited"
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"
    OPERATOR_STOPPED = "operator_stopped"


class StoppingDecisionCreate(BaseModel):
    """Operator-controlled request to conclude with an evidence basis."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: StoppingDecisionReason
    rationale: str = Field(min_length=1, max_length=4000)
    expected_status: TaskStatus
    expected_revision: int = Field(ge=1, strict=True)
    expected_evidence_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_ids: list[UUID] = Field(default_factory=list, max_length=100)
    claim_ids: list[UUID] = Field(default_factory=list, max_length=100)
    objective_indices: list[int] = Field(default_factory=list, max_length=50)
    review_ids: list[UUID] = Field(default_factory=list, max_length=100)
    limitations: list[str] = Field(default_factory=list, max_length=20)
    runtime_limit_evidence: list[str] = Field(default_factory=list, max_length=20)
    operation_id: UUID = Field(default_factory=uuid4)


class StoppingDecision(BaseModel):
    """Current or historical accepted stopping decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: UUID
    task_id: UUID
    revision: int = Field(ge=1)
    operation_id: UUID
    reason: StoppingDecisionReason
    rationale: str
    source_ids: list[UUID]
    claim_ids: list[UUID]
    objective_indices: list[int]
    review_ids: list[UUID]
    limitations: list[str]
    evidence_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_limit_evidence: list[str]
    actor_type: Literal["local_operator"]
    actor_id: str
    created_at: datetime


class StoppingDecisionChange(BaseModel):
    """Immutable accepted stopping-decision history."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    change_id: UUID
    decision_id: UUID
    task_id: UUID
    operation_id: UUID
    previous_revision: int = Field(ge=0)
    revision: int = Field(ge=1)
    resulting_state: StoppingDecision
    actor_type: Literal["local_operator"]
    actor_id: str
    created_at: datetime


class StoppingReadinessItem(BaseModel):
    """Read-only advisory stopping checklist item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: Literal[
        "unresolved_objectives",
        "missing_assessment",
        "mixed_assessment",
        "contradictory_claims",
        "dependence_unknown",
        "active_attempt",
    ]
    status: Literal["satisfied", "attention", "unknown"]
    detail: str
    source_ids: list[UUID] = Field(default_factory=list)
    claim_ids: list[UUID] = Field(default_factory=list)


class StoppingReadiness(BaseModel):
    """Advisory checklist; never a semantic conclusion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: UUID
    task_status: TaskStatus
    task_revision: int
    evidence_fingerprint: str
    items: list[StoppingReadinessItem]
    current_decision: StoppingDecision | None = None
    note: str = (
        "This checklist supports operator review only. It does not establish truth, "
        "sufficiency, independence, or claim status."
    )


class CycleOutcomeCreate(BaseModel):
    """Bounded, provenance-linked result for a started research cycle."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "blocked", "failed"]
    result_summary: str = Field(min_length=1, max_length=10_000)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)
    claim_ids: list[UUID] = Field(default_factory=list, max_length=100)
    unresolved_objectives: list[str] = Field(default_factory=list, max_length=50)
    attempted_objectives: list[str] = Field(default_factory=list, max_length=3)
    objective_results: list[CycleObjectiveResult] = Field(default_factory=list, max_length=3)
