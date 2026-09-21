"""Read models for a persisted investigation's evidence chain."""

from typing import Literal

from pydantic import BaseModel

from research_agent.domain.research import (
    ClaimResponse,
    Hypothesis,
    HypothesisAssessmentResponse,
    ResearchTask,
    SourceDependenceProjection,
    SourceResponse,
)


class HypothesisSnapshot(BaseModel):
    hypothesis: Hypothesis
    assessment_state: Literal["assessed", "not_assessed"]
    assessment: HypothesisAssessmentResponse | None


class InvestigationSnapshot(BaseModel):
    """Stored evidence and uncertainty; no generated conclusions."""

    task: ResearchTask
    hypotheses: list[HypothesisSnapshot]
    claims: list[ClaimResponse]
    sources: list[SourceResponse]
    open_questions: list[str]
    source_dependence: SourceDependenceProjection | None = None
