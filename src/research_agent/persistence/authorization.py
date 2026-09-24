"""Append-only application records for bounded authorization artifacts."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from research_agent.persistence.models import Base


class OperatorAuthorizationRecord(Base):
    __tablename__ = "operator_authorizations"

    authorization_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    authority_epoch_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    security_state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    replay_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    recovery_context_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    authorization: Mapped[dict[str, Any]] = mapped_column(
        "authorization_document",
        JSONB,
        nullable=False,
    )
    command: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ExecutionAuthorizationRecord(Base):
    __tablename__ = "execution_authorizations"

    execution_authorization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True
    )
    execution_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    operator_authorization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("operator_authorizations.authorization_id"),
        nullable=False,
    )
    authority_epoch_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    security_state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    replay_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    recovery_context_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    authorization: Mapped[dict[str, Any]] = mapped_column(
        "authorization_document",
        JSONB,
        nullable=False,
    )
    command: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class AuthorizationAuditRecord(Base):
    __tablename__ = "authorization_audit"

    artifact_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    authority_epoch_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    security_state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
