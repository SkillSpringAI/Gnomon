"""SQLAlchemy persistence models for investigation state."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


class ResearchTaskRecord(Base):
    """Database record for an open-ended research task."""

    __tablename__ = "research_tasks"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    brief: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    cycles: Mapped[list["ResearchCycleRecord"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="ResearchCycleRecord.cycle_number",
    )


class ResearchCycleRecord(Base):
    """Database record for one bounded research cycle."""

    __tablename__ = "research_cycles"
    __table_args__ = (UniqueConstraint("task_id", "cycle_number"),)

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("research_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    planning_basis: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    objectives: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    methods: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    progress_tracked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    recovery_reason: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_summary: Mapped[str | None] = mapped_column(Text)
    evidence_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    claim_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    unresolved_objectives: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    attempted_objectives: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )

    objective_results: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )

    objective_reviews: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )

    task: Mapped[ResearchTaskRecord] = relationship(back_populates="cycles")


class ResearchSourceRecord(Base):
    """Database record for raw source evidence."""

    __tablename__ = "research_sources"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("research_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    uri: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reliability_score: Mapped[float] = mapped_column(Float, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class ResearchClaimRecord(Base):
    """Database record for a structured claim."""

    __tablename__ = "research_claims"

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    lifecycle: Mapped[str] = mapped_column(String, default="active", server_default="active")

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("research_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ClaimSourceRecord(Base):
    """Database record linking a claim to its provenance."""

    __tablename__ = "claim_sources"

    claim_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("research_claims.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("research_sources.id", ondelete="CASCADE"),
        primary_key=True,
    )
    support_type: Mapped[str] = mapped_column(String(32), nullable=False)
    strength: Mapped[float] = mapped_column(Float, nullable=False)


class TrustedSourceRecord(Base):
    """Database record for an approved source domain."""

    __tablename__ = "trusted_sources"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    domain: Mapped[str] = mapped_column(String(253), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    verification_method: Mapped[str] = mapped_column(String(500), nullable=False)
    requires_attribution: Mapped[bool] = mapped_column(nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="review")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP"
    )
    source_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class HypothesisAssessmentRecord(Base):
    """Database record for the current assessment of a hypothesis."""

    __tablename__ = "hypothesis_assessments"
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    lifecycle: Mapped[str] = mapped_column(String, default="active", server_default="active")
    __table_args__ = (UniqueConstraint("task_id", "hypothesis_id"),)

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("research_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    hypothesis_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AssessmentEvidenceRecord(Base):
    """Database record linking an assessment to a claim."""

    __tablename__ = "assessment_evidence"

    assessment_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("hypothesis_assessments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    claim_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("research_claims.id", ondelete="CASCADE"),
        primary_key=True,
    )
    relation: Mapped[str] = mapped_column(String(32), nullable=False)
    strength: Mapped[float] = mapped_column(Float, nullable=False)


class ResearchEventRecord(Base):
    """Existing research_events table, now mapped for durable audit writes."""

    __tablename__ = "research_events"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("research_tasks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MemoryChangeRecord(Base):
    """Append-only application journal, separate from redacted public events."""

    __tablename__ = "memory_changes"

    change_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    target_type: Mapped[str] = mapped_column(Text)
    target_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    operation: Mapped[str] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    previous_version: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer)
    previous_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    proposed_state: Mapped[dict[str, Any]] = mapped_column(JSONB)
    resulting_state: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text)
    provenance: Mapped[list[str]] = mapped_column(JSONB)
    request: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reverses_change_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
