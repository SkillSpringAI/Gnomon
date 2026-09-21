"""Durable, redacted audit for ephemeral provider credential sessions."""

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.application.security_capability import (
    AuthorityDirection,
    SecurityCapability,
    require_capability,
    require_locked_capability,
)
from research_agent.application.security_state_store import PersistedSecurityState
from research_agent.domain.provider import ProviderSessionAuditEvent
from research_agent.persistence.models import ProviderSessionEventRecord


class ProviderSessionAuditService:
    """Record and read provider-session lifecycle metadata without secrets."""

    def __init__(self, session: Session, *, actor_id: str = "api:local_operator") -> None:
        if not actor_id.strip():
            raise ValueError("Invalid trusted provider actor context")
        self.session = session
        self.actor_id = actor_id

    def authorize_create(self) -> PersistedSecurityState:
        return require_locked_capability(
            self.session,
            SecurityCapability.AUTHORITY_ADMINISTRATION,
            AuthorityDirection.BROADEN,
        )

    def authorize_delete(self) -> PersistedSecurityState:
        return require_locked_capability(
            self.session,
            SecurityCapability.AUTHORITY_ADMINISTRATION,
            AuthorityDirection.REDUCE,
        )

    def stage(
        self,
        authority: PersistedSecurityState,
        *,
        operation: Literal["CREATE", "DELETE"],
        provider: Literal["stub", "bedrock"],
        ttl_seconds: int | None,
        result: Literal["accepted", "no_op"],
        reason: Literal["created", "deleted", "already_absent"],
    ) -> None:
        self.session.add(
            ProviderSessionEventRecord(
                event_id=uuid4(),
                operation=operation,
                provider=provider,
                credential_mode="session_bearer_token",
                ttl_seconds=ttl_seconds,
                actor_type="local_operator",
                actor_id=self.actor_id,
                authority_epoch_id=authority.authority_epoch_id.value,
                security_state_version=authority.version,
                result=result,
                reason=reason,
                created_at=datetime.now(UTC),
            )
        )

    def list_events(self, limit: int = 100) -> list[ProviderSessionAuditEvent]:
        require_capability(self.session, SecurityCapability.READ_AUDIT)
        records = self.session.scalars(
            select(ProviderSessionEventRecord)
            .order_by(
                ProviderSessionEventRecord.created_at.desc(),
                ProviderSessionEventRecord.event_id.desc(),
            )
            .limit(limit)
        )
        return [
            ProviderSessionAuditEvent.model_validate(record, from_attributes=True)
            for record in records
        ]
