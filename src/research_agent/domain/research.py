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
