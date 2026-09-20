"""Integration coverage for reviewed persistence translation boundaries."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from research_agent.api.app import create_app
from research_agent.application import security_state_service
from research_agent.application.persistence_error_translation import (
    PersistenceBoundaryError,
    PersistenceErrorCategory,
)
from research_agent.application.security_state_service import SecurityStateTransitionService
from research_agent.domain.security import SecurityActor, SecurityReasonCode, SecurityState
from research_agent.persistence.database import SessionFactory, engine
from research_agent.persistence.models import (
    SecurityStateRecord,
    SecurityTransitionRecord,
    TrustedSourceRecord,
)


def driver_integrity_error(constraint_name: str) -> IntegrityError:
    driver_error = RuntimeError("private SQL detail")
    driver_error.diag = SimpleNamespace(constraint_name=constraint_name)  # type: ignore[attr-defined]
    return IntegrityError("private SQL text", {}, driver_error)


def test_duplicate_source_registration_is_translated_at_service_boundary() -> None:
    domain = f"{uuid4().hex}.example"
    app = create_app()
    with TestClient(app) as client:
        try:
            payload = {
                "domain": domain,
                "display_name": "Boundary test source",
                "verification_method": "Fixture",
            }
            assert client.post("/source-registry", json=payload).status_code == 201
            duplicate = client.post("/source-registry", json=payload)
            assert duplicate.status_code == 409
            assert duplicate.json() == {"detail": "Source domain is already registered"}
        finally:
            with engine.begin() as connection:
                connection.execute(
                    delete(TrustedSourceRecord).where(TrustedSourceRecord.domain == domain)
                )


def test_security_invariant_translation_rolls_back_transition(monkeypatch) -> None:
    with engine.begin() as connection:
        connection.execute(delete(SecurityTransitionRecord))
        connection.execute(
            text(
                "UPDATE security_state SET state = 'normal', version = 1, "
                "updated_at = now() WHERE id = 1"
            )
        )
    commit_error = driver_integrity_error("security_state_state_valid")

    try:
        with SessionFactory() as session:
            def fail_commit() -> None:
                raise commit_error

            monkeypatch.setattr(session, "commit", fail_commit)
            with pytest.raises(PersistenceBoundaryError) as raised:
                SecurityStateTransitionService(session).transition(
                    expected_version=1,
                    requested_state=SecurityState.LOCKDOWN,
                    actor_type=SecurityActor.LOCAL_OPERATOR,
                    actor_id="operator",
                    reason_code=SecurityReasonCode.OPERATOR_LOCKDOWN,
                )

            assert raised.value.category is PersistenceErrorCategory.AUTHORITY_INVARIANT_VIOLATION
            assert raised.value.__cause__ is commit_error

        with SessionFactory() as session:
            state = session.scalar(select(SecurityStateRecord).where(SecurityStateRecord.id == 1))
            assert state is not None
            assert state.state == "normal"
            assert state.version == 1
    finally:
        with engine.begin() as connection:
            connection.execute(delete(SecurityTransitionRecord))
            connection.execute(
                text(
                    "UPDATE security_state SET state = 'normal', version = 1, "
                    "updated_at = now() WHERE id = 1"
                )
            )


def test_security_invariant_api_response_is_safe_and_not_retryable(monkeypatch) -> None:
    def reject_transition(*args, **kwargs):
        raise PersistenceBoundaryError(
            PersistenceErrorCategory.AUTHORITY_INVARIANT_VIOLATION,
            "security_state_state_valid",
        )

    monkeypatch.setattr(
        security_state_service.SecurityStateTransitionService,
        "transition",
        reject_transition,
    )
    with TestClient(create_app()) as client:
        response = client.post(
            "/security/transitions",
            json={
                "expected_version": 1,
                "requested_state": "lockdown",
                "reason_code": "OPERATOR_LOCKDOWN",
            },
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Security state persistence invariant failed"}
    assert "security_state_state_valid" not in response.text
    assert "private SQL" not in response.text
