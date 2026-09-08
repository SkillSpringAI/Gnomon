"""Application service for trusted source domains."""

from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_agent.domain.research import (
    SourceType,
    TrustedSourceCreate,
    TrustedSourceResponse,
    TrustedSourceStatus,
)
from research_agent.persistence.models import TrustedSourceRecord


class UntrustedSourceError(Exception):
    """Raised when a URI is not approved for controlled retrieval."""


class SourceRegistryService:
    """Manage and enforce the approved source-domain registry."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def register(self, source: TrustedSourceCreate) -> TrustedSourceResponse:
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
        self.session.commit()
        return self._response(record)

    def list_sources(self) -> list[TrustedSourceResponse]:
        records = self.session.scalars(
            select(TrustedSourceRecord).order_by(TrustedSourceRecord.domain)
        )
        return [self._response(record) for record in records]

    def enable(self, domain: str) -> TrustedSourceResponse:
        """Enable a reviewed domain for controlled retrieval."""
        normalized = domain.lower().strip().rstrip(".")
        record = self.session.scalar(
            select(TrustedSourceRecord).where(TrustedSourceRecord.domain == normalized)
        )
        if record is None:
            raise UntrustedSourceError("Source domain is not registered")
        record.status = TrustedSourceStatus.ENABLED.value
        record.verified_at = datetime.now(UTC)
        self.session.commit()
        return self._response(record)

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
