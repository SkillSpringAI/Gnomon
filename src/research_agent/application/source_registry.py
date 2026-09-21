"""Application service for trusted source domains."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from research_agent.application.persistence_error_translation import translate_integrity_error
from research_agent.application.security_capability import (
    AuthorityDirection,
    SecurityCapability,
    require_capability,
    require_locked_capability,
)
from research_agent.application.security_state_store import PersistedSecurityState
from research_agent.domain.research import (
    SourceType,
    TrustedSourceCreate,
    TrustedSourcePolicyEvent,
    TrustedSourceResponse,
    TrustedSourceStatus,
)
from research_agent.persistence.models import (
    TrustedSourcePolicyEventRecord,
    TrustedSourceRecord,
)


class UntrustedSourceError(Exception):
    """Raised when a URI is not approved for controlled retrieval."""


@dataclass(frozen=True)
class SourceRegistryActor:
    """Trusted application context; request payloads cannot supply this identity."""

    actor_type: Literal["local_operator"] = "local_operator"
    actor_id: str = "api:local_operator"


class SourceRegistryService:
    """Manage and enforce the approved source-domain registry."""

    def __init__(self, session: Session, actor: SourceRegistryActor | None = None) -> None:
        self.session = session
        self.actor = actor or SourceRegistryActor()
        if self.actor.actor_type != "local_operator" or not self.actor.actor_id.strip():
            raise ValueError("Invalid trusted source actor context")

    def register(self, source: TrustedSourceCreate) -> TrustedSourceResponse:
        try:
            authority = require_locked_capability(
                self.session,
                SecurityCapability.AUTHORITY_ADMINISTRATION,
                AuthorityDirection.PRESERVE,
            )
            domain = source.domain.lower().strip().rstrip(".")
            record = TrustedSourceRecord(
                id=uuid4(),
                domain=domain,
                display_name=source.display_name,
                source_type=source.source_type.value,
                verification_method=source.verification_method,
                requires_attribution=source.requires_attribution,
                status=TrustedSourceStatus.REVIEW.value,
            )
            self.session.add(record)
            self.session.flush()
            self._stage_policy_event(
                record,
                authority,
                previous_status=None,
                result="accepted",
                reason="registered",
            )
            self.session.commit()
            return self._response(record)
        except IntegrityError as exc:
            self.session.rollback()
            translate_integrity_error(exc)
        except Exception:
            self.session.rollback()
            raise

    def list_sources(self) -> list[TrustedSourceResponse]:
        records = self.session.scalars(
            select(TrustedSourceRecord).order_by(TrustedSourceRecord.domain)
        )
        return [self._response(record) for record in records]

    def list_policy_events(self, limit: int = 100) -> list[TrustedSourcePolicyEvent]:
        """Return redacted registry policy events at the audit capability boundary."""
        require_capability(self.session, SecurityCapability.READ_AUDIT)
        records = self.session.scalars(
            select(TrustedSourcePolicyEventRecord)
            .order_by(
                TrustedSourcePolicyEventRecord.created_at.desc(),
                TrustedSourcePolicyEventRecord.event_id.desc(),
            )
            .limit(limit)
        )
        return [
            TrustedSourcePolicyEvent.model_validate(record, from_attributes=True)
            for record in records
        ]

    def enable(self, domain: str) -> TrustedSourceResponse:
        """Enable a reviewed domain for controlled retrieval."""
        try:
            authority = require_locked_capability(
                self.session,
                SecurityCapability.AUTHORITY_ADMINISTRATION,
                AuthorityDirection.BROADEN,
            )
            normalized = domain.lower().strip().rstrip(".")
            record = self.session.scalar(
                select(TrustedSourceRecord)
                .where(TrustedSourceRecord.domain == normalized)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if record is None:
                raise UntrustedSourceError("Source domain is not registered")
            previous_status = TrustedSourceStatus(record.status)
            if previous_status is not TrustedSourceStatus.ENABLED:
                record.status = TrustedSourceStatus.ENABLED.value
                record.verified_at = datetime.now(UTC)
                result: Literal["accepted", "no_op"] = "accepted"
                reason: Literal["registered", "enabled", "already_enabled"] = "enabled"
            else:
                result, reason = "no_op", "already_enabled"
            self.session.flush()
            self._stage_policy_event(
                record,
                authority,
                previous_status=previous_status,
                result=result,
                reason=reason,
            )
            self.session.commit()
            return self._response(record)
        except IntegrityError as exc:
            self.session.rollback()
            translate_integrity_error(exc)
        except Exception:
            self.session.rollback()
            raise

    def require_enabled(self, uri: str) -> TrustedSourceRecord:
        hostname = (urlparse(uri).hostname or "").lower().rstrip(".")
        records = self.session.scalars(
            select(TrustedSourceRecord).where(
                TrustedSourceRecord.status == TrustedSourceStatus.ENABLED
            )
        )
        for record in records:
            if hostname == record.domain or hostname.endswith(f".{record.domain}"):
                return record
        raise UntrustedSourceError("Source domain is not enabled in the trusted-source registry")

    def _stage_policy_event(
        self,
        record: TrustedSourceRecord,
        authority: PersistedSecurityState,
        *,
        previous_status: TrustedSourceStatus | None,
        result: Literal["accepted", "no_op"],
        reason: Literal["registered", "enabled", "already_enabled"],
    ) -> None:
        """Stage redacted policy evidence in the same transaction as the write."""
        # Keep this narrow object protocol local to avoid making security state
        # persistence an input surface for the registry API.
        self.session.add(
            TrustedSourcePolicyEventRecord(
                event_id=uuid4(),
                source_id=record.id,
                operation="REGISTER" if previous_status is None else "ENABLE",
                previous_status=previous_status.value if previous_status else None,
                new_status=TrustedSourceStatus(record.status).value,
                actor_type=self.actor.actor_type,
                actor_id=self.actor.actor_id,
                authority_epoch_id=authority.authority_epoch_id.value,
                security_state_version=authority.version,
                result=result,
                reason=reason,
                created_at=datetime.now(UTC),
            )
        )

    @staticmethod
    def _response(record: TrustedSourceRecord) -> TrustedSourceResponse:
        return TrustedSourceResponse(
            id=record.id,
            domain=record.domain,
            display_name=record.display_name,
            source_type=SourceType(record.source_type),
            verification_method=record.verification_method,
            requires_attribution=record.requires_attribution,
            status=TrustedSourceStatus(record.status),
            verified_at=record.verified_at,
        )
