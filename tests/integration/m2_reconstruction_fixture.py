"""Canonical M2.6 reconstruction fixture data for backup/restore coverage."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid5

from sqlalchemy import Connection, text

FixtureVariant = Literal["baseline", "restrictive_unresolved"]

_NAMESPACE = UUID("f46adfd2-7f50-4b56-a3a8-0d3f3f4f4c62")
_BASE_TIME = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)

CANONICAL_RECONSTRUCTION_TABLES = (
    "research_tasks",
    "research_cycles",
    "research_cycle_attempts",
    "research_sources",
    "research_claims",
    "claim_sources",
    "hypothesis_assessments",
    "assessment_evidence",
    "source_relationships",
    "source_relationship_changes",
    "memory_changes",
    "stopping_decisions",
    "stopping_decision_changes",
    "report_generation_attempts",
    "security_state_transitions",
    "recovery_contexts",
    "recovery_context_audit",
    "operator_authorizations",
    "execution_authorizations",
    "authorization_audit",
    "research_events",
    "trusted_sources",
    "trusted_source_policy_events",
    "provider_session_events",
)


@dataclass(frozen=True)
class CanonicalReconstructionFixture:
    variant: FixtureVariant
    task_id: UUID
    cycle_ids: tuple[UUID, UUID]
    source_ids: tuple[UUID, UUID]
    claim_ids: tuple[UUID, UUID]
    assessment_id: UUID
    relationship_id: UUID
    recovery_context_id: UUID
    operator_authorization_id: UUID
    execution_authorization_id: UUID
    authority_epoch_id: UUID
    security_state: str
    security_state_version: int
    provider_attempt_status: str
    cycle_attempt_status: str


def seed_canonical_reconstruction_fixture(
    connection: Connection,
    *,
    variant: FixtureVariant = "baseline",
) -> CanonicalReconstructionFixture:
    """Populate one compact source database fixture for M2 reconstruction tests."""
    ids = _fixture_ids(variant)
    authority_epoch_id = connection.execute(
        text("SELECT authority_epoch_id FROM security_state WHERE id = 1")
    ).scalar_one()
    security_state, security_state_version = _seed_security_history(
        connection,
        ids=ids,
        variant=variant,
        authority_epoch_id=authority_epoch_id,
    )
    provider_attempt_status = "UNKNOWN" if variant == "restrictive_unresolved" else "SUCCEEDED"
    cycle_attempt_status = "INTERRUPTED" if variant == "restrictive_unresolved" else "COMPLETED"

    _seed_research_graph(connection, ids=ids, cycle_attempt_status=cycle_attempt_status)
    _seed_source_dependence(
        connection,
        ids=ids,
        authority_epoch_id=authority_epoch_id,
        security_state_version=security_state_version,
    )
    _seed_memory_history(connection, ids=ids)
    _seed_stopping_history(connection, ids=ids)
    _seed_provider_attempt(
        connection,
        ids=ids,
        provider_attempt_status=provider_attempt_status,
    )
    _seed_configuration_audit(
        connection,
        ids=ids,
        authority_epoch_id=authority_epoch_id,
        security_state_version=security_state_version,
    )
    _seed_recovery_and_authorization(
        connection,
        ids=ids,
        variant=variant,
        authority_epoch_id=authority_epoch_id,
        security_state_version=security_state_version,
    )

    return CanonicalReconstructionFixture(
        variant=variant,
        task_id=ids["task"],
        cycle_ids=(ids["cycle_1"], ids["cycle_2"]),
        source_ids=(ids["source_low"], ids["source_high"]),
        claim_ids=(ids["claim_1"], ids["claim_2"]),
        assessment_id=ids["assessment"],
        relationship_id=ids["relationship"],
        recovery_context_id=ids["recovery_context"],
        operator_authorization_id=ids["operator_authorization"],
        execution_authorization_id=ids["execution_authorization"],
        authority_epoch_id=authority_epoch_id,
        security_state=security_state,
        security_state_version=security_state_version,
        provider_attempt_status=provider_attempt_status,
        cycle_attempt_status=cycle_attempt_status,
    )


def canonical_fixture_table_counts(connection: Connection) -> dict[str, int]:
    """Return deterministic per-table coverage counts for the M2 fixture."""
    return {
        table_name: int(
            connection.execute(text(f'SELECT count(*) FROM "{table_name}"')).scalar_one()
        )
        for table_name in CANONICAL_RECONSTRUCTION_TABLES
    }


def _fixture_ids(variant: FixtureVariant) -> dict[str, UUID]:
    ids = {
        name: uuid5(_NAMESPACE, f"m2.6:{variant}:{name}")
        for name in (
            "task",
            "cycle_1",
            "cycle_2",
            "cycle_attempt",
            "source_low",
            "source_high",
            "claim_1",
            "claim_2",
            "assessment",
            "relationship",
            "relationship_change",
            "relationship_operation",
            "memory_change",
            "stopping_decision",
            "stopping_decision_change",
            "stopping_operation",
            "provider_attempt",
            "trusted_source",
            "trusted_source_event",
            "provider_session_event",
            "security_transition_1",
            "security_transition_2",
            "security_transition_3",
            "recovery_context",
            "incident",
            "operator_authorization",
            "execution_authorization",
            "execution",
            "operator_replay",
            "execution_replay",
            "research_event",
            "hypothesis",
            "review_1",
            "review_2",
        )
    }
    if ids["source_low"] > ids["source_high"]:
        ids["source_low"], ids["source_high"] = ids["source_high"], ids["source_low"]
    return ids


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True)


def _seed_security_history(
    connection: Connection,
    *,
    ids: dict[str, UUID],
    variant: FixtureVariant,
    authority_epoch_id: UUID,
) -> tuple[str, int]:
    transitions = [
        (
            ids["security_transition_1"],
            "normal",
            "degraded",
            "OPERATOR_DEGRADED_MODE",
            "local_operator",
            "fixture-operator",
            2,
            _BASE_TIME + timedelta(minutes=1),
        ),
        (
            ids["security_transition_2"],
            "degraded",
            "normal",
            "RECOVERY_VERIFIED",
            "security_recovery_service",
            "fixture-recovery",
            3,
            _BASE_TIME + timedelta(minutes=2),
        ),
    ]
    final_state = "normal"
    final_version = 3
    if variant == "restrictive_unresolved":
        transitions.append(
            (
                ids["security_transition_3"],
                "normal",
                "lockdown",
                "AUTHORITY_BOUNDARY_VIOLATION",
                "local_operator",
                "fixture-operator",
                4,
                _BASE_TIME + timedelta(minutes=3),
            )
        )
        final_state = "lockdown"
        final_version = 4
    for transition in transitions:
        connection.execute(
            text(
                """
                INSERT INTO security_state_transitions (
                    transition_id, previous_state, new_state, reason_code,
                    actor_type, actor_id, created_at, security_state_version,
                    related_event_ids, authority_epoch_id
                )
                VALUES (
                    :transition_id, :previous_state, :new_state, :reason_code,
                    :actor_type, :actor_id, :created_at, :security_state_version,
                    CAST(:related_event_ids AS jsonb), :authority_epoch_id
                )
                """
            ),
            {
                "transition_id": transition[0],
                "previous_state": transition[1],
                "new_state": transition[2],
                "reason_code": transition[3],
                "actor_type": transition[4],
                "actor_id": transition[5],
                "security_state_version": transition[6],
                "created_at": transition[7],
                "related_event_ids": _json([str(ids["research_event"])]),
                "authority_epoch_id": authority_epoch_id,
            },
        )
    connection.execute(
        text(
            """
            UPDATE security_state
            SET state = :state,
                version = :version,
                updated_at = :updated_at,
                authority_epoch_id = :authority_epoch_id,
                recovery_bootstrap_pending = false,
                recovery_bootstrap_started_at = NULL,
                recovery_bootstrap_from_state = NULL,
                recovery_bootstrap_from_version = NULL
            WHERE id = 1
            """
        ),
        {
            "state": final_state,
            "version": final_version,
            "updated_at": _BASE_TIME + timedelta(minutes=4),
            "authority_epoch_id": authority_epoch_id,
        },
    )
    return final_state, final_version


def _seed_research_graph(
    connection: Connection,
    *,
    ids: dict[str, UUID],
    cycle_attempt_status: str,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO research_tasks (
                id, title, objective, status, brief, plan, created_at, updated_at, revision
            )
            VALUES (
                :id, 'M2 canonical reconstruction fixture',
                'Exercise every restore-relevant persistence family.',
                'active', CAST(:brief AS jsonb), CAST(:plan AS jsonb),
                :created_at, :updated_at, 2
            )
            """
        ),
        {
            "id": ids["task"],
            "brief": _json(
                {
                    "hypotheses": [
                        {
                            "id": str(ids["hypothesis"]),
                            "label": "H1",
                            "statement": "Fixture data survives reconstruction.",
                        }
                    ],
                    "questions": [],
                    "case_studies": [],
                    "methods": ["web_research", "source_analysis"],
                    "evidence_requirements": ["At least two fixture sources."],
                    "stopping_criteria": ["Review restored state equivalence."],
                }
            ),
            "plan": _json(
                {
                    "summary": "Seed canonical M2 reconstruction data.",
                    "first_cycle_objectives": ["objective-1"],
                    "proposed_methods": ["web_research", "source_analysis"],
                    "open_questions": ["Which restored records differ?"],
                }
            ),
            "created_at": _BASE_TIME,
            "updated_at": _BASE_TIME + timedelta(minutes=20),
        },
    )
    for number, cycle_id, status in (
        (1, ids["cycle_1"], "completed"),
        (2, ids["cycle_2"], "active"),
    ):
        connection.execute(
            text(
                """
                INSERT INTO research_cycles (
                    id, task_id, cycle_number, planning_basis, objectives, methods,
                    status, created_at, started_at, completed_at, result_summary,
                    evidence_ids, claim_ids, unresolved_objectives,
                    attempted_objectives, objective_results, objective_reviews,
                    progress_tracked, recovery_reason
                )
                VALUES (
                    :id, :task_id, :cycle_number, CAST(:planning_basis AS jsonb),
                    CAST(:objectives AS jsonb), CAST(:methods AS jsonb), :status,
                    :created_at, :started_at, :completed_at, :result_summary,
                    CAST(:evidence_ids AS jsonb), CAST(:claim_ids AS jsonb),
                    CAST(:unresolved_objectives AS jsonb),
                    CAST(:attempted_objectives AS jsonb),
                    CAST(:objective_results AS jsonb),
                    CAST(:objective_reviews AS jsonb),
                    true, :recovery_reason
                )
                """
            ),
            {
                "id": cycle_id,
                "task_id": ids["task"],
                "cycle_number": number,
                "planning_basis": _json(
                    [
                        {
                            "reason": "open_question",
                            "source_ids": [str(ids["source_low"])],
                            "evidence_fingerprint": "d" * 64,
                        }
                    ]
                ),
                "objectives": _json([f"objective-{number}"]),
                "methods": _json(["web_research", "source_analysis"]),
                "status": status,
                "created_at": _BASE_TIME + timedelta(minutes=number),
                "started_at": _BASE_TIME + timedelta(minutes=number + 1),
                "completed_at": (
                    _BASE_TIME + timedelta(minutes=number + 5) if number == 1 else None
                ),
                "result_summary": "Fixture cycle completed." if number == 1 else None,
                "evidence_ids": _json([str(ids["source_low"]), str(ids["source_high"])]),
                "claim_ids": _json([str(ids["claim_1"]), str(ids["claim_2"])]),
                "unresolved_objectives": _json([] if number == 1 else ["objective-2"]),
                "attempted_objectives": _json([f"objective-{number}"]),
                "objective_results": _json(
                    [
                        {
                            "objective_index": 0,
                            "source_ids": [str(ids["source_low"])],
                            "claim_ids": [str(ids["claim_1"])],
                        }
                    ]
                ),
                "objective_reviews": _json(
                    [
                        {
                            "id": str(ids[f"review_{number}"]),
                            "objective_index": 0,
                            "objective": f"objective-{number}",
                            "revision": 1,
                            "decision": "completed" if number == 1 else "unresolved",
                            "rationale": f"Fixture review {number}.",
                            "source_ids": [str(ids["source_low"])],
                            "claim_ids": [str(ids["claim_1"])],
                            "basis": {
                                "reason": "open_question",
                                "source_ids": [str(ids["source_low"])],
                                "evidence_fingerprint": "d" * 64,
                            },
                            "reference_fingerprint": "e" * 64,
                            "actor": "local_operator",
                            "created_at": (
                                _BASE_TIME + timedelta(minutes=number + 6)
                            ).isoformat(),
                        }
                    ]
                ),
                "recovery_reason": None if number == 1 else "fixture active cycle",
            },
        )
    connection.execute(
        text(
            """
            INSERT INTO research_sources (
                id, task_id, source_type, title, uri, publisher, content,
                content_hash, reliability_score, observed_at, metadata
            )
            VALUES
                (
                    :source_low, :task_id, 'web_page', 'Fixture primary source',
                    'https://example.test/primary', 'Example Test',
                    'Primary fixture content.', :hash_a, 0.9, :observed_at,
                    CAST(:metadata_a AS jsonb)
                ),
                (
                    :source_high, :task_id, 'agent_message', 'Fixture agent observation',
                    NULL, 'local-agent', 'Agent fixture content.',
                    :hash_b, 0.7, :observed_at, CAST(:metadata_b AS jsonb)
                )
            """
        ),
        {
            "source_low": ids["source_low"],
            "source_high": ids["source_high"],
            "task_id": ids["task"],
            "hash_a": "a" * 64,
            "hash_b": "b" * 64,
            "observed_at": _BASE_TIME + timedelta(minutes=6),
            "metadata_a": _json({"fixture": "primary"}),
            "metadata_b": _json({"fixture": "agent"}),
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO research_claims (
                id, task_id, statement, confidence, status, created_at,
                updated_at, version, lifecycle
            )
            VALUES
                (
                    :claim_1, :task_id, 'Fixture claim one is supported.',
                    0.72, 'supported', :created_at, :updated_at, 2, 'active'
                ),
                (
                    :claim_2, :task_id, 'Fixture claim two remains uncertain.',
                    0.42, 'unverified', :created_at, :updated_at, 1, 'active'
                )
            """
        ),
        {
            "claim_1": ids["claim_1"],
            "claim_2": ids["claim_2"],
            "task_id": ids["task"],
            "created_at": _BASE_TIME + timedelta(minutes=7),
            "updated_at": _BASE_TIME + timedelta(minutes=9),
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO claim_sources (claim_id, source_id, support_type, strength)
            VALUES
                (:claim_1, :source_low, 'supporting', 0.8),
                (:claim_2, :source_high, 'context', 0.5)
            """
        ),
        {
            "claim_1": ids["claim_1"],
            "claim_2": ids["claim_2"],
            "source_low": ids["source_low"],
            "source_high": ids["source_high"],
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO hypothesis_assessments (
                id, task_id, hypothesis_id, status, summary, confidence,
                updated_at, version, lifecycle
            )
            VALUES (
                :assessment, :task_id, :hypothesis_id, 'mixed',
                'Fixture assessment with mixed evidence.', 0.61, :updated_at, 2, 'active'
            )
            """
        ),
        {
            "assessment": ids["assessment"],
            "task_id": ids["task"],
            "hypothesis_id": ids["hypothesis"],
            "updated_at": _BASE_TIME + timedelta(minutes=10),
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO assessment_evidence (assessment_id, claim_id, relation, strength)
            VALUES
                (:assessment, :claim_1, 'supporting', 0.8),
                (:assessment, :claim_2, 'context', 0.3)
            """
        ),
        {
            "assessment": ids["assessment"],
            "claim_1": ids["claim_1"],
            "claim_2": ids["claim_2"],
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO research_cycle_attempts (
                id, task_id, cycle_id, status, stage, started_at, finished_at,
                recovery_reason, evidence_ids, claim_ids
            )
            VALUES (
                :id, :task_id, :cycle_id, :status, :stage, :started_at, :finished_at,
                :recovery_reason, CAST(:evidence_ids AS jsonb), CAST(:claim_ids AS jsonb)
            )
            """
        ),
        {
            "id": ids["cycle_attempt"],
            "task_id": ids["task"],
            "cycle_id": ids["cycle_2"],
            "status": cycle_attempt_status,
            "stage": "INTERRUPTED" if cycle_attempt_status == "INTERRUPTED" else "COMPLETED",
            "started_at": _BASE_TIME + timedelta(minutes=11),
            "finished_at": (
                None
                if cycle_attempt_status == "INTERRUPTED"
                else _BASE_TIME + timedelta(minutes=12)
            ),
            "recovery_reason": (
                "fixture unresolved cycle" if cycle_attempt_status == "INTERRUPTED" else None
            ),
            "evidence_ids": _json([str(ids["source_low"])]),
            "claim_ids": _json([str(ids["claim_1"])]),
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO research_events (id, task_id, event_type, payload, created_at)
            VALUES (
                :id, :task_id, 'fixture.seeded', CAST(:payload AS jsonb), :created_at
            )
            """
        ),
        {
            "id": ids["research_event"],
            "task_id": ids["task"],
            "payload": _json({"fixture": "m2.6", "sources": 2, "claims": 2}),
            "created_at": _BASE_TIME + timedelta(minutes=13),
        },
    )


def _seed_source_dependence(
    connection: Connection,
    *,
    ids: dict[str, UUID],
    authority_epoch_id: UUID,
    security_state_version: int,
) -> None:
    resulting_state = {
        "kind": "derived_from",
        "direction": "low_to_high",
        "lifecycle": "active",
        "revision": 1,
    }
    connection.execute(
        text(
            """
            INSERT INTO source_relationships (
                relationship_id, task_id, source_low_id, source_high_id, kind,
                direction, lifecycle, revision, latest_change_id, updated_at
            )
            VALUES (
                :relationship_id, :task_id, :source_low_id, :source_high_id,
                'derived_from', 'low_to_high', 'active', 1, :latest_change_id, :updated_at
            )
            """
        ),
        {
            "relationship_id": ids["relationship"],
            "task_id": ids["task"],
            "source_low_id": ids["source_low"],
            "source_high_id": ids["source_high"],
            "latest_change_id": ids["relationship_change"],
            "updated_at": _BASE_TIME + timedelta(minutes=14),
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO source_relationship_changes (
                change_id, operation_id, relationship_id, task_id,
                previous_revision, revision, operation, previous_state,
                resulting_state, command_request, actor_type, actor_id,
                reason, authority_epoch_id, security_state_version,
                reverses_change_id, created_at
            )
            VALUES (
                :change_id, :operation_id, :relationship_id, :task_id,
                0, 1, 'CREATE', NULL, CAST(:resulting_state AS jsonb),
                CAST(:command_request AS jsonb), 'local_operator',
                'fixture-operator', 'fixture relationship',
                :authority_epoch_id, :security_state_version, NULL, :created_at
            )
            """
        ),
        {
            "change_id": ids["relationship_change"],
            "operation_id": ids["relationship_operation"],
            "relationship_id": ids["relationship"],
            "task_id": ids["task"],
            "resulting_state": _json(resulting_state),
            "command_request": _json({"operation_id": str(ids["relationship_operation"])}),
            "authority_epoch_id": authority_epoch_id,
            "security_state_version": security_state_version,
            "created_at": _BASE_TIME + timedelta(minutes=14),
        },
    )


def _seed_memory_history(connection: Connection, *, ids: dict[str, UUID]) -> None:
    previous = {"statement": "Fixture claim one is preliminary.", "version": 1}
    resulting = {"statement": "Fixture claim one is supported.", "version": 2}
    connection.execute(
        text(
            """
            INSERT INTO memory_changes (
                change_id, task_id, target_type, target_id, operation, actor,
                timestamp, previous_version, version, previous_state,
                proposed_state, resulting_state, reason, provenance, request,
                reverses_change_id
            )
            VALUES (
                :change_id, :task_id, 'claim', :target_id, 'UPDATE',
                'fixture-operator', :timestamp, 1, 2, CAST(:previous_state AS jsonb),
                CAST(:proposed_state AS jsonb), CAST(:resulting_state AS jsonb),
                'fixture governed update', CAST(:provenance AS jsonb),
                CAST(:request AS jsonb), NULL
            )
            """
        ),
        {
            "change_id": ids["memory_change"],
            "task_id": ids["task"],
            "target_id": ids["claim_1"],
            "timestamp": _BASE_TIME + timedelta(minutes=15),
            "previous_state": _json(previous),
            "proposed_state": _json(resulting),
            "resulting_state": _json(resulting),
            "provenance": _json([str(ids["source_low"])]),
            "request": _json({"reason": "fixture governed update"}),
        },
    )


def _seed_stopping_history(connection: Connection, *, ids: dict[str, UUID]) -> None:
    resulting_state = {
        "reason": "resource_limited",
        "revision": 1,
        "limitations": ["fixture runtime limit"],
    }
    connection.execute(
        text(
            """
            INSERT INTO stopping_decisions (
                decision_id, task_id, revision, operation_id, reason, rationale,
                source_ids, claim_ids, objective_cycle_number, objective_indices,
                review_ids, limitations, evidence_fingerprint,
                runtime_limit_evidence, actor_type, actor_id, created_at
            )
            VALUES (
                :decision_id, :task_id, 1, :operation_id, 'resource_limited',
                'Fixture stopping decision for reconstruction coverage.',
                CAST(:source_ids AS jsonb), CAST(:claim_ids AS jsonb), 2,
                CAST(:objective_indices AS jsonb), CAST(:review_ids AS jsonb),
                CAST(:limitations AS jsonb), :evidence_fingerprint,
                CAST(:runtime_limit_evidence AS jsonb), 'local_operator',
                'fixture-operator', :created_at
            )
            """
        ),
        {
            "decision_id": ids["stopping_decision"],
            "task_id": ids["task"],
            "operation_id": ids["stopping_operation"],
            "source_ids": _json([str(ids["source_low"])]),
            "claim_ids": _json([str(ids["claim_1"])]),
            "objective_indices": _json([0]),
            "review_ids": _json(["review-2"]),
            "limitations": _json(["fixture runtime limit"]),
            "evidence_fingerprint": "c" * 64,
            "runtime_limit_evidence": _json(["operator_budget"]),
            "created_at": _BASE_TIME + timedelta(minutes=16),
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO stopping_decision_changes (
                change_id, decision_id, task_id, operation_id, previous_revision,
                revision, resulting_state, command_request, actor_type, actor_id,
                created_at
            )
            VALUES (
                :change_id, :decision_id, :task_id, :operation_id, 0, 1,
                CAST(:resulting_state AS jsonb), CAST(:command_request AS jsonb),
                'local_operator', 'fixture-operator', :created_at
            )
            """
        ),
        {
            "change_id": ids["stopping_decision_change"],
            "decision_id": ids["stopping_decision"],
            "task_id": ids["task"],
            "operation_id": ids["stopping_operation"],
            "resulting_state": _json(resulting_state),
            "command_request": _json({"operation_id": str(ids["stopping_operation"])}),
            "created_at": _BASE_TIME + timedelta(minutes=16),
        },
    )


def _seed_provider_attempt(
    connection: Connection,
    *,
    ids: dict[str, UUID],
    provider_attempt_status: str,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO report_generation_attempts (
                operation_id, task_id, status, started_at, expires_at,
                finished_at, error_reason
            )
            VALUES (
                :operation_id, :task_id, :status, :started_at, :expires_at,
                :finished_at, :error_reason
            )
            """
        ),
        {
            "operation_id": ids["provider_attempt"],
            "task_id": ids["task"],
            "status": provider_attempt_status,
            "started_at": _BASE_TIME + timedelta(minutes=17),
            "expires_at": _BASE_TIME + timedelta(minutes=22),
            "finished_at": (
                None
                if provider_attempt_status == "UNKNOWN"
                else _BASE_TIME + timedelta(minutes=18)
            ),
            "error_reason": (
                "fixture unresolved provider result"
                if provider_attempt_status == "UNKNOWN"
                else None
            ),
        },
    )


def _seed_configuration_audit(
    connection: Connection,
    *,
    ids: dict[str, UUID],
    authority_epoch_id: UUID,
    security_state_version: int,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO trusted_sources (
                id, domain, display_name, source_type, verification_method,
                requires_attribution, status, verified_at, created_at, metadata
            )
            VALUES (
                :id, 'fixture.example', 'Fixture Source', 'web',
                'fixture verification', true, 'enabled', :verified_at,
                :created_at, CAST(:metadata AS jsonb)
            )
            """
        ),
        {
            "id": ids["trusted_source"],
            "verified_at": _BASE_TIME + timedelta(minutes=18),
            "created_at": _BASE_TIME + timedelta(minutes=18),
            "metadata": _json({"fixture": "m2.6"}),
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO trusted_source_policy_events (
                event_id, source_id, operation, previous_status, new_status,
                actor_type, actor_id, authority_epoch_id, security_state_version,
                result, reason, created_at
            )
            VALUES (
                :event_id, :source_id, 'ENABLE', 'review', 'enabled',
                'local_operator', 'fixture-operator', :authority_epoch_id,
                :security_state_version, 'accepted', 'enabled', :created_at
            )
            """
        ),
        {
            "event_id": ids["trusted_source_event"],
            "source_id": ids["trusted_source"],
            "authority_epoch_id": authority_epoch_id,
            "security_state_version": security_state_version,
            "created_at": _BASE_TIME + timedelta(minutes=18),
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO provider_session_events (
                event_id, operation, provider, credential_mode, ttl_seconds,
                actor_type, actor_id, authority_epoch_id, security_state_version,
                result, reason, created_at
            )
            VALUES (
                :event_id, 'CREATE', 'bedrock', 'session_bearer_token', 3600,
                'local_operator', 'fixture-operator', :authority_epoch_id,
                :security_state_version, 'accepted', 'created', :created_at
            )
            """
        ),
        {
            "event_id": ids["provider_session_event"],
            "authority_epoch_id": authority_epoch_id,
            "security_state_version": security_state_version,
            "created_at": _BASE_TIME + timedelta(minutes=19),
        },
    )


def _seed_recovery_and_authorization(
    connection: Connection,
    *,
    ids: dict[str, UUID],
    variant: FixtureVariant,
    authority_epoch_id: UUID,
    security_state_version: int,
) -> None:
    context_payload = {
        "variant": variant,
        "unresolved_operations": (
            [
                {
                    "kind": "provider_attempt",
                    "operation_id": str(ids["provider_attempt"]),
                    "outcome": "unknown",
                }
            ]
            if variant == "restrictive_unresolved"
            else []
        ),
    }
    command_payload = {"capture": "fixture", "variant": variant}
    issued_at = _BASE_TIME + timedelta(minutes=20)
    expires_at = issued_at + timedelta(hours=1)
    connection.execute(
        text(
            """
            INSERT INTO recovery_contexts (
                context_id, incident_id, authority_epoch_id, security_state_version,
                created_at, expires_at, context, command
            )
            VALUES (
                :context_id, :incident_id, :authority_epoch_id,
                :security_state_version, :created_at, :expires_at,
                CAST(:context AS jsonb), CAST(:command AS jsonb)
            )
            """
        ),
        {
            "context_id": ids["recovery_context"],
            "incident_id": ids["incident"],
            "authority_epoch_id": authority_epoch_id,
            "security_state_version": security_state_version,
            "created_at": issued_at,
            "expires_at": expires_at,
            "context": _json(context_payload),
            "command": _json(command_payload),
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO recovery_context_audit (
                context_id, event_type, actor_type, actor_id, authority_epoch_id,
                security_state_version, created_at
            )
            VALUES (
                :context_id, 'recovery.context_recorded', 'local_operator',
                'local-recovery-diagnostics', :authority_epoch_id,
                :security_state_version, :created_at
            )
            """
        ),
        {
            "context_id": ids["recovery_context"],
            "authority_epoch_id": authority_epoch_id,
            "security_state_version": security_state_version,
            "created_at": issued_at,
        },
    )
    operator_doc = {
        "authorization_id": str(ids["operator_authorization"]),
        "scope": [{"kind": "recovery_context", "target_id": str(ids["recovery_context"])}],
        "basis": [{"kind": "recovery_context", "record_id": str(ids["recovery_context"])}],
    }
    execution_doc = {
        "execution_authorization_id": str(ids["execution_authorization"]),
        "operator_authorization_id": str(ids["operator_authorization"]),
        "execution_id": str(ids["execution"]),
        "capabilities": ["RECOVERY_RESTORATION"],
    }
    connection.execute(
        text(
            """
            INSERT INTO operator_authorizations (
                authorization_id, authority_epoch_id, security_state_version,
                issued_at, expires_at, replay_id, recovery_context_id,
                authorization_document, command
            )
            VALUES (
                :authorization_id, :authority_epoch_id, :security_state_version,
                :issued_at, :expires_at, :replay_id, :recovery_context_id,
                CAST(:authorization_document AS jsonb), CAST(:command AS jsonb)
            )
            """
        ),
        {
            "authorization_id": ids["operator_authorization"],
            "authority_epoch_id": authority_epoch_id,
            "security_state_version": security_state_version,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "replay_id": ids["operator_replay"],
            "recovery_context_id": ids["recovery_context"],
            "authorization_document": _json(operator_doc),
            "command": _json({"issue": "operator", "fixture": "m2.6"}),
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO execution_authorizations (
                execution_authorization_id, execution_id, operator_authorization_id,
                authority_epoch_id, security_state_version, issued_at, expires_at,
                replay_id, recovery_context_id, authorization_document, command
            )
            VALUES (
                :execution_authorization_id, :execution_id, :operator_authorization_id,
                :authority_epoch_id, :security_state_version, :issued_at, :expires_at,
                :replay_id, :recovery_context_id,
                CAST(:authorization_document AS jsonb), CAST(:command AS jsonb)
            )
            """
        ),
        {
            "execution_authorization_id": ids["execution_authorization"],
            "execution_id": ids["execution"],
            "operator_authorization_id": ids["operator_authorization"],
            "authority_epoch_id": authority_epoch_id,
            "security_state_version": security_state_version,
            "issued_at": issued_at + timedelta(minutes=1),
            "expires_at": expires_at,
            "replay_id": ids["execution_replay"],
            "recovery_context_id": ids["recovery_context"],
            "authorization_document": _json(execution_doc),
            "command": _json({"issue": "execution", "fixture": "m2.6"}),
        },
    )
    for artifact_id, artifact_type, event_type in (
        (
            ids["operator_authorization"],
            "operator_authorization",
            "authorization.operator_issued",
        ),
        (
            ids["execution_authorization"],
            "execution_authorization",
            "authorization.execution_issued",
        ),
    ):
        connection.execute(
            text(
                """
                INSERT INTO authorization_audit (
                    artifact_id, artifact_type, event_type, actor_type, actor_id,
                    authority_epoch_id, security_state_version, created_at
                )
                VALUES (
                    :artifact_id, :artifact_type, :event_type, 'local_operator',
                    'local-authorization-service', :authority_epoch_id,
                    :security_state_version, :created_at
                )
                """
            ),
            {
                "artifact_id": artifact_id,
                "artifact_type": artifact_type,
                "event_type": event_type,
                "authority_epoch_id": authority_epoch_id,
                "security_state_version": security_state_version,
                "created_at": issued_at + timedelta(minutes=2),
            },
        )
