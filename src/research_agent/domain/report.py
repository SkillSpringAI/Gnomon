"""Structured, evidence-aware report read models."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from research_agent.domain.agent_comparison import AgentObservationComparison
from research_agent.domain.research import (
    ClaimResponse,
    CycleObjectiveResult,
    CycleStatus,
    HypothesisAssessmentStatus,
    ObjectiveReview,
    SourceDependenceProjection,
    SourceType,
    TaskStatus,
)


class ReportStoppingDecision(BaseModel):
    """Decision provenance shown with the structured report."""

    model_config = ConfigDict(extra="forbid")

    decision_id: UUID | None = None
    reason: Literal[
        "evidence_sufficient",
        "resource_limited",
        "evidence_unavailable",
        "operator_stopped",
        "unspecified",
    ]
    rationale: str | None = None
    evidence_fingerprint: str | None = None
    stale: bool = False
    limitations: list[str] = Field(default_factory=list)


class ReportSource(BaseModel):
    """Citation metadata without duplicating full source content."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    source_type: SourceType
    title: str
    uri: str | None
    publisher: str | None
    observed_at: datetime


class ReportHypothesis(BaseModel):
    """A hypothesis with its current assessment or explicit uncertainty."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    label: str
    statement: str
    assessment_status: HypothesisAssessmentStatus | None
    assessment_summary: str | None
    confidence: float | None
    claim_ids: list[UUID] = Field(default_factory=list)


class ReportCycle(BaseModel):
    """A compact cycle outcome suitable for a report timeline."""

    model_config = ConfigDict(extra="forbid")

    number: int
    status: CycleStatus
    started_at: datetime | None = None
    progress_tracked: bool = False
    recovery_fingerprint: str | None = None
    objectives: list[str]
    result_summary: str | None
    unresolved_objectives: list[str]
    attempted_objectives: list[str] = Field(default_factory=list)
    objective_results: list[CycleObjectiveResult] = Field(default_factory=list)
    objective_reviews: list[ObjectiveReview] = Field(default_factory=list)
    stale_review_ids: list[UUID] = Field(default_factory=list)
    evidence_ids: list[UUID]
    claim_ids: list[UUID]


class InvestigationReport(BaseModel):
    """Read-only report assembled from persisted evidence and uncertainty."""

    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    review_evidence_fingerprint: str = ""
    title: str
    objective: str
    task_status: TaskStatus
    summary: str
    hypotheses: list[ReportHypothesis]
    claims: list[ClaimResponse]
    sources: list[ReportSource]
    cycles: list[ReportCycle]
    open_questions: list[str]
    unresolved_objectives: list[str]
    limitations: list[str]
    agent_comparison: AgentObservationComparison | None = None
    source_dependence: SourceDependenceProjection | None = None
    stopping_decision: ReportStoppingDecision


class ReportUsage(BaseModel):
    """Provider-reported usage metadata without prompts, responses, or credentials."""

    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class ReportDraft(BaseModel):
    """Generated prose with explicit provider metadata and cited record IDs."""

    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    provider: str
    model: str
    generated_at: datetime
    content: str = Field(min_length=1, max_length=50_000)
    cited_source_ids: list[UUID] = Field(default_factory=list)
    cited_claim_ids: list[UUID] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    usage: ReportUsage | None = None
