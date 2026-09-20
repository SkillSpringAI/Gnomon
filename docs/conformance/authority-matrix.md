# Gnomon authority conformance matrix

Baseline: `2d786916f707f9d6eda89c4003d73942da4dc2d2`, inspected 2026-09-13.
This is an implementation inventory, not an authority certification.
Supplemental S05–S07 record the 19 September authority work; older section-wide
classifications below retain their stated limitations.

## Authority coverage

The user supplied all ten authority DOCX files on 2026-09-13. Documents 01–07 are
mapped below by every top-level section, including all subordinate requirements.
Documents 08–10 inform supplementary security, persistence and release findings.
The complete replacement Document 08, `Security, Audit & Recovery Authority.docx`,
was reviewed on 2026-09-13. It contains sections 1–50 through the final authority
statement. The earlier truncated-source flag is resolved. Document 08 remains a
supplemental review, not part of the 395 section groups mapped for Documents 01–07.

Source numbers and draft statuses come from each document's own metadata. Exact
file revisions are pinned by SHA-256 in [authority-sources.json](authority-sources.json);
no authority-set version was invented. Documents 01–04 say Foundational Draft,
05–07 say Draft / Governing Specification, and 08–10 say Governing Specification.
Document 01 takes precedence. Today's explicit deferrals determine implementation
scope, not amendment of mandatory invariants.

Run `python scripts/check_conformance.py` to check source hashes, complete section
coverage, classifications and evidence references. This is a traceability harness,
not proof of behavioral conformance.

## Classification rules

- `IMPLEMENTED`: the narrowly stated behavior exists and relevant tests pass.
- `PARTIALLY_IMPLEMENTED`: some behavior exists; the limitation is named.
- `DESIGNED_NOT_IMPLEMENTED`: described in repository design or the active roadmap,
  but no executable implementation was found.
- `MISSING`: required coverage or behavior is absent without a concrete implementation design.
- `CONFLICTING`: observed behavior contradicts the stated target; the section mapping identifies the applicable authority.
- `DEFERRED`: explicitly outside today's implementation scope; not a waiver of authority.

Paths below are relative to the repository root. Priorities identify today's slices,
not permission to skip their dependencies. “None” means no matching test found.

## Evidence-backed implementation inventory

| ID | Requirement and basis | Classification | Implementation evidence | Existing tests | Limitation / priority |
| --- | --- | --- | --- | --- | --- |
| B01 | Local API, packaging, health; roadmap Phase 0 | IMPLEMENTED | `pyproject.toml`, `api/app.py` under `src/research_agent` | `tests/unit/test_health.py` | Existing foundation |
| B02 | Durable task/cycle persistence; Phase 1 | IMPLEMENTED | `src/research_agent/persistence/repositories.py`, migrations 001, 005, 006 | `tests/integration/test_postgres_persistence.py`, `test_api_postgres.py` | Existing foundation |
| B03 | Numbered transactional migration runner; Phase 0 | IMPLEMENTED | `src/research_agent/application/migrations.py` | `tests/unit/test_migrations.py`; integration suites invoke migrations | Checksums implemented; downgrade handling deferred |
| B04 | Structured research brief; project plan §3 | PARTIALLY_IMPLEMENTED | `src/research_agent/domain/research.py` | `tests/unit/test_investigations.py` | Hypotheses/questions/methods/stopping criteria exist; explicit scope, parent-task and priority fields absent |
| B05 | Model-based structured planning; Phase 1 | PARTIALLY_IMPLEMENTED | `src/research_agent/ports/llm.py`, `application/research_service.py` | `tests/unit/test_investigations.py` | Generic protocol exists; actual planning is deterministic, not an LLM call |
| B06 | Lifecycle compare-and-set and active-only planning; architecture §5 | IMPLEMENTED | `src/research_agent/application/research_service.py`, `persistence/repositories.py` | `tests/integration/test_lifecycle.py` | Status comparison is not a record version |
| B07 | Persisted bounded gap prioritization; Phase 1 | IMPLEMENTED | `src/research_agent/application/cycle_planner.py`, migration 005 | `tests/unit/test_cycle_planner.py`, `tests/integration/test_cycle_planning.py` | Structural prioritization only |
| B08 | Explicit cycle start/outcome; Phase 1 | IMPLEMENTED | `src/research_agent/application/research_service.py`, migration 006 | `tests/unit/test_investigations.py` | No autonomous execution runner |
| B09 | Pause cancels ongoing work / gates every writer | MISSING | Lifecycle gates new cycles; manual evidence and assessment routes remain callable | No cancellation test | Define lifecycle boundary before autonomous integration; Slice 5/9 |
| B10 | Source ingestion with origin/hash/time; Phase 2 | IMPLEMENTED | `src/research_agent/application/evidence_service.py` | `tests/integration/test_snapshot.py`, `test_idempotency.py` | Hash covers stored normalized content |
| B11 | Original raw-source storage abstraction; Phase 2 | DESIGNED_NOT_IMPLEMENTED | Sources hold normalized text in PostgreSQL; no object-storage port | None | Reproduction limitation; later source work |
| B12 | Exact evidence/claim retry identity; Phase 2 | IMPLEMENTED | `src/research_agent/application/evidence_service.py` | `tests/integration/test_idempotency.py` | Application locks, not semantic deduplication |
| B13 | Domain policy before every retrieval hop; Phase 2 | IMPLEMENTED | `src/research_agent/application/source_registry.py`, `adapters/web/http.py` | `tests/unit/test_http_retriever.py`, `tests/integration/test_snapshot.py` | Registry approval is not evidence truth |
| B14 | Public IP validation, pinned connections, deadlines and sizes; Slice 5 | IMPLEMENTED | `src/research_agent/adapters/web/network.py`, `adapters/web/http.py` | `tests/unit/test_network.py`, `test_http_retriever.py` | Controlled transport tests, not deployment penetration testing |
| B15 | Entity and typed entity-relationship models; Phase 3 | DESIGNED_NOT_IMPLEMENTED | Claim-source links exist; no entity/relationship domain or tables | None | Do not confuse provenance links with entity graph |
| B16 | Claim proposals with task-local provenance; architecture §5 | IMPLEMENTED | `src/research_agent/domain/research.py`, `application/evidence_service.py` | `tests/integration/test_snapshot.py`, `test_idempotency.py` | Existence checks do not establish independent corroboration |
| B17 | Extraction proposal then atomic validated commit; architecture §2 | IMPLEMENTED | `src/research_agent/application/claim_extraction_service.py`, `adapters/llm/rule_based.py` | `tests/unit/test_http_retriever.py`, `tests/integration/test_idempotency.py`, `test_audit.py` | Sentence extraction creates unverified claims |
| B18 | Confidence/status transition governance; Phase 3 | PARTIALLY_IMPLEMENTED | Bounded enums/scores in `domain/research.py`; `application/evidence_service.py` accepts caller status | `tests/integration/test_idempotency.py` preserves existing judgments | No governed revisions or deterministic support-promotion rule; Slice 2 |
| B19 | Hypothesis assessment with claim links; Phase 1/3 | IMPLEMENTED | `src/research_agent/application/assessment_service.py`, `application/memory_service.py` | `tests/integration/test_snapshot.py`, `tests/integration/test_memory_rollback.py` | Governed versions/history exist; dependent reassessment propagation remains open |
| B20 | Task-scoped consistent snapshot and provenance report; Phase 4 | IMPLEMENTED | `src/research_agent/application/snapshot_service.py`, `report_service.py`, API routes | `tests/integration/test_snapshot.py`, `test_reports.py`, `tests/unit/test_report_service.py` | Full snapshots are unpaginated |
| B21 | Later-task memory retrieval; Phase 4 exit criterion | DESIGNED_NOT_IMPLEMENTED | Read models are task-scoped; no cross-task search service | None | Phase 4 is not complete just because reports work |
| B22 | Provider-neutral draft generation; Phase 4 | IMPLEMENTED | `src/research_agent/ports/reporting.py`, `adapters/llm/*report.py`, `application/report_generation_service.py` | `tests/unit/test_report_service.py`, `tests/integration/test_reports.py` | Local tests do not verify live Bedrock |
| B23 | Draft task/citation validation and failure mapping; Slice 5 | PARTIALLY_IMPLEMENTED | `src/research_agent/application/report_generation_service.py`, `api/routes/reports.py` | `tests/unit/test_report_service.py` | Citation membership is not factual entailment; adversarial malformed-response coverage incomplete |
| B24 | Bounded provider resource consumption; Slice 5 | PARTIALLY_IMPLEMENTED | `src/research_agent/api/routes/reports.py`, `application/provider_budget_service.py`, Bedrock adapters | `tests/integration/test_reports.py` concurrent/expiry coverage; `tests/unit/test_report_service.py` adapter parity | Persistent atomic reservations and dispatch fencing implemented; uncertain late-outcome reconciliation and monetary cost accounting remain open |
| B25 | Non-secret provider status and bounded local sessions | IMPLEMENTED | `src/research_agent/api/routes/provider.py`, `application/provider_session.py` | `tests/unit/test_provider_status.py`, `test_settings_secrets.py` | Local boundary only, not authenticated actor identity |
| M01 | MemoryChangeProposal and deterministic allowed-operation validation; Slice 2 | IMPLEMENTED | `domain/memory.py`, `application/memory_service.py`, `/memory/validate` | `tests/unit/test_memory_governance.py` plus full suite | Implemented for claims/assessments; actor is trusted application context |
| M02 | Governed CREATE; Slice 2 | IMPLEMENTED | `MemoryService.stage`, migration 007 journal/version columns | `tests/unit/test_memory_governance.py`, `tests/integration/test_idempotency.py` | Claim extraction and assessment creation use the boundary |
| M03 | Governed UPDATE; Slice 2 | IMPLEMENTED | Assessment and claim writers route through `MemoryService` | `tests/integration/test_idempotency.py`, `tests/integration/test_memory_rollback.py` | Dependent-state propagation remains bounded to conflict refusal |
| M04 | Governed ARCHIVE; Slice 2 | IMPLEMENTED | `MemoryService` lifecycle transition and `/memory/changes` API | Proposal model tests; integration coverage pending | Current snapshots exclude archived records |
| M05 | Governed LOGICAL_DELETE; Slice 2 | IMPLEMENTED | `MemoryService` lifecycle transition and migration 007 | Proposal model tests; integration coverage pending | Physical purge is not exposed |
| M06 | Governed RESTORE; Slice 2 | IMPLEMENTED | `MemoryService` lifecycle transition and reverse API seam | Proposal model tests; integration coverage pending | Full dependent restore policy is Slice 3 |
| M07 | MERGE / RETRACT / SUPERSEDE on shared mechanism | DEFERRED | Merge described; retracted claim enum exists, not a mutation workflow | None | Follow initial five operations |
| M08 | Trusted actor, reason, provenance and accepted change identity; Slice 2/3 | PARTIALLY_IMPLEMENTED | `MemoryAuthority`, proposal reason, provenance IDs, immutable change IDs and journal | `tests/unit/test_memory_governance.py`, full suite | Actor classes are local/operator/extractor; multi-user identity is deferred |
| V01 | Previous/proposed/resulting snapshots and monotonic versions; Slice 3 | IMPLEMENTED | `MemoryChangeRecord`, migration 007, `MemoryService` | `tests/integration/test_memory_rollback.py` | Scoped to claims and assessments |
| V02 | Normal rollback within 48 hours; Slice 3 | IMPLEMENTED | `MemoryService.reverse` | `tests/integration/test_memory_rollback.py` | Scoped to governed claim/assessment changes |
| V03 | Duplicate rollback idempotency; Slice 3 | IMPLEMENTED | `MemoryService.reverse` detects an existing reversal | `tests/integration/test_memory_rollback.py` | Scoped to governed claim/assessment changes |
| V04 | Stale rollback refusal; Slice 3 | IMPLEMENTED | Version and resulting-state compare before reversal | `tests/integration/test_memory_rollback.py` | Explicit conflict; no silent overwrite |
| V05 | Concurrent modification during rollback; Slice 3 | IMPLEMENTED | Task row lock plus optimistic version checks | `tests/integration/test_memory_rollback.py` | Independent transaction stress remains limited |
| V06 | Dependent knowledge during rollback; Slice 3 | PARTIALLY_IMPLEMENTED | Active assessment/cycle dependencies block claim reversal | `tests/integration/test_memory_rollback.py` | No automatic dependent reassessment propagation |
| V07 | Rollback after 48 hours; Slice 3 | IMPLEMENTED | Trusted UTC timestamp window in `MemoryService.reverse` | `tests/integration/test_memory_rollback.py` | No background recovery worker |
| V08 | Rollback conflict leaves state/history unchanged; Slice 3 | IMPLEMENTED | Reversal is atomic and preserves original journal entry | `tests/integration/test_memory_rollback.py` | Backup/restore recovery remains release-gate work |
| A01 | Redacted, coupled source/claim/extraction/lifecycle/cycle audit; Slice 4 | IMPLEMENTED | `src/research_agent/domain/events.py`, `application/audit_service.py`, writer services | `tests/integration/test_audit.py`, `test_lifecycle.py` | Narrow existing coverage |
| A02 | Task creation / first cycle audit; Slice 4 | IMPLEMENTED | `persistence/repositories.py` emits `task.created` | `tests/integration/test_audit.py`, `test_lifecycle.py` | First-cycle detail remains represented by cycle planning events |
| A03 | Assessment and source-registry mutation audit; Slice 4 | PARTIALLY_IMPLEMENTED | Assessments are journaled and exposed through memory events; source registry writes remain unaudited | `tests/integration/test_memory_rollback.py` | Add source-policy audit events |
| A04 | WHO/WHY/previous/new/provenance/result envelope; Slice 4 | PARTIALLY_IMPLEMENTED | Event payloads include actor, reason/result, state digests and provenance where applicable | `tests/integration/test_audit.py`, `test_memory_rollback.py` | Public events intentionally retain digests rather than raw state; authenticated identity remains deferred |
| A05 | Authentication/security event audit; Slice 4 | PARTIALLY_IMPLEMENTED | Rejected memory commits emit redacted `security.event`; provider-session lifecycle has no event stream | `tests/integration/test_memory_rollback.py` | Add authenticated identity and provider-session audit coverage |
| A06 | Preserve history rather than silently destroy it; target milestone | PARTIALLY_IMPLEMENTED | `memory_service.py` preserves governed change history; migration 013 restricts retained audit deletion | `tests/integration/test_memory_rollback.py`, retention/deletion integration tests | Broader dependent reassessment and backup/restore preservation remain open |
| S01 | Retrieved content cannot instruct deterministic planner; Slice 5 | IMPLEMENTED | `src/research_agent/application/cycle_planner.py` | `tests/unit/test_cycle_planner.py::test_source_content_cannot_instruct_planner` | Does not prove every adapter boundary |
| S02 | Malicious provider/retrieved content cannot gain state authority; Slice 5 | PARTIALLY_IMPLEMENTED | Providers return drafts/proposals; application services own writes | Existing extraction/citation tests | Need hostile adapter tests proving no state/tool authority |
| S03 | Credential leakage defenses; Slice 5 | PARTIALLY_IMPLEMENTED | Secret settings/session separation; output filter in `report_generation_service.py` | `tests/unit/test_settings_secrets.py`, `test_provider_status.py` | Four literal output patterns are not complete leakage protection |
| S04 | Unauthorized tool/memory requests, replay and malformed provider tests; Slice 5 | MISSING | No shared capability/replay policy for future proposals/agents | None for complete boundary contract | Slice 5, HIGH |
| S05 | Point-of-effect security capabilities; 19 September baseline | IMPLEMENTED | `application/security_capability.py`, `audit_service.py`, `source_cycle_runner.py`, `api/routes/reports.py`, `api/routes/security.py` under `src/research_agent` | `test_audit.py`, `test_source_cycle.py`, `test_provider_lifecycle.py`, `test_security_api.py` | Verified in `9c82544d`, hosted Quality #12; protected restoration remains open |
| S06 | Authority Epoch persistence and new transition attribution | IMPLEMENTED | `domain/security.py`, `application/security_state_store.py`, `security_state_service.py`, migration 023 under `src/research_agent` | `test_authority_epoch.py`, `test_security_state_store.py`, `test_security_state_transitions.py`; `scripts/verify_prototype.py` | Local scope only; historical audit is unbound; epoch replacement and execution authorization binding deferred |
| S07 | Transition actor/reason matrix and capability direction | IMPLEMENTED | `src/research_agent/application/security_transition_policy.py`, `security_state_service.py` | `test_security_transition_policy.py`, `test_security_state_transitions.py` | All 825 tuples covered; same-state no-ops retained; full restoration authority deferred |
| S08 | Bounded interruption closure and selected mutation/lockdown ordering | IMPLEMENTED | `src/research_agent/application/cycle_interruption.py`, `security_capability.py`, runner/outcome/memory/evidence services | `tests/integration/test_interruption_ordering.py` | Slice closed; five PostgreSQL paths and same-task stage composition tested. Cross-task batching unsupported; no external-call cancellation or restoration guarantee |
| S09 | Direction-aware capability policy and authority administration | IMPLEMENTED | `src/research_agent/application/security_capability.py`, `security_transition_policy.py`, `security_state_service.py`, `source_registry.py` | `tests/unit/test_security_capability.py`, `test_security_transition_policy.py`; `tests/integration/test_security_state_transitions.py` | AUTHORITY_ADMINISTRATION governs state changes and trusted-source registration/activation; containment cannot broaden, recovery purpose cannot replace actual-effect authority; no OperatorAuthorization or RecoveryContext |
| N01 | Agent/identity/capability/observation/request/message/reliability domain; Slice 6 | DESIGNED_NOT_IMPLEMENTED | Agent source/method enums only; architecture sketches AgentNetwork | None | Slice 6, after governance |
| N02 | AgentNetwork adapter and governed evidence ingestion; Slice 6 | DESIGNED_NOT_IMPLEMENTED | No executable network port or application service | None | External agent is never an authority |
| N03 | Nine deterministic honest/adversarial/failure agent modes; Slice 7 | DESIGNED_NOT_IMPLEMENTED | Active roadmap only | None | Include duplicate/replay, timeout and rate-limit assertions |
| N04 | Moltbook isolated adapter; Slice 8 | DESIGNED_NOT_IMPLEMENTED | Repository roadmap Phase 7 only | None | Depends on Slices 6/7; no live communication implied |
| N05 | Agent evidence acquisition integrated with existing planner; Slice 9 | DESIGNED_NOT_IMPLEMENTED | Planner handles persisted gaps; no acquisition runner | None | One research loop, common provenance/governance |
| R01 | Authority-to-test release gate and security/epistemic/recovery review; Slice 10 | PARTIALLY_IMPLEMENTED | Tests/lint/types pass; this baseline adds traceability | Existing suite; no authority gate | Block candidate until authority mapping and required slices pass |
| D01 | pgvector, semantic synthesis, AWS workers/queues, distributed memory, multi-user auth, cryptographic ledger, stopping reasoning, complex reputation, broad UI | DEFERRED | Explicitly deferred by today's roadmap | Not an acceptance claim | Keep outside today's scope |

## Updating this matrix

Retain stable IDs. Split a row when requirements need different classifications.
For every promotion to IMPLEMENTED, cite executable behavior and a meaningful test,
record the run result, and remove or explicitly retain limitations. Preserve the
baseline SHA when adding later observations. An API returning success is insufficient
for governance, security, epistemic correctness, or recovery acceptance.

## Source-of-Truth section coverage

Each row covers **all requirements in the named section**, including its subordinate headings, lists, examples and named invariants. It is an aggregate classification: PARTIALLY_IMPLEMENTED never claims every clause is satisfied. CONFLICTING identifies a concrete violation within the group. Evidence IDs resolve to the inventory above, which names code and tests. A missing capability is not a vacuous security pass. MUST/SHOULD/MAY retain their source meaning; deferral is not an authority waiver. Split groups into narrower rows as implementation begins.

### Document 01 — Authority & Constitutional Principles

Source: [Gnomon Authority & Constitutional Principles.docx](../archive/original-authority-documents/Gnomon%20Authority%20%26%20Constitutional%20Principles.docx). SHA-256: `4342e1b10fb6dd94c5626c21c02e1bedb8f8ba4ff746e7a309a4fb7059821c71`.

| Requirement group | Source section | Classification | Evidence IDs | Gap / priority |
| --- | --- | --- | --- | --- |
| AUTH-01-01 | §1 Purpose | PARTIALLY_IMPLEMENTED | B17,S01,S02,S04,R01 | Current application boundaries exist; complete capability, actor and authority-regression enforcement is absent. Slice 2/5/10. |
| AUTH-01-02 | §2 Foundational Definition | PARTIALLY_IMPLEMENTED | B17,S01,S02,S04,R01 | Current application boundaries exist; complete capability, actor and authority-regression enforcement is absent. Slice 2/5/10. |
| AUTH-01-03 | §3 Authority Hierarchy | PARTIALLY_IMPLEMENTED | B17,S01,S02,S04,R01 | Current application boundaries exist; complete capability, actor and authority-regression enforcement is absent. Slice 2/5/10. |
| AUTH-01-04 | §4 AI Is Not the System Authority | PARTIALLY_IMPLEMENTED | B17,S01,S02,S04,R01 | Current application boundaries exist; complete capability, actor and authority-regression enforcement is absent. Slice 2/5/10. |
| AUTH-01-05 | §5 Deterministic Enforcement | PARTIALLY_IMPLEMENTED | B17,S01,S02,S04,R01 | Current application boundaries exist; complete capability, actor and authority-regression enforcement is absent. Slice 2/5/10. |
| AUTH-01-06 | §6 Separation of Knowledge and Authority | PARTIALLY_IMPLEMENTED | B04,B16,B18,B19,B20 | Typed claims and provenance exist; complete epistemic types, actor lineage and historical state do not. Slice 2/3. |
| AUTH-01-07 | §7 Epistemic Status | PARTIALLY_IMPLEMENTED | B04,B16,B18,B19,B20 | Typed claims and provenance exist; complete epistemic types, actor lineage and historical state do not. Slice 2/3. |
| AUTH-01-08 | §8 Provenance Is Authoritative | PARTIALLY_IMPLEMENTED | B04,B16,B18,B19,B20 | Typed claims and provenance exist; complete epistemic types, actor lineage and historical state do not. Slice 2/3. |
| AUTH-01-09 | §9 External Agents Are Untrusted | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03 | No external-agent boundary or adversarial adapter tests. Slice 6/7. |
| AUTH-01-10 | §10 Retrieved Content Is Untrusted Data | PARTIALLY_IMPLEMENTED | S01,S02 | Planner injection test passes; all external paths are not proven. Slice 5. |
| AUTH-01-11 | §11 Research Rules Are Separate From Research Findings | PARTIALLY_IMPLEMENTED | B17,S01,S02,S04,R01 | Current application boundaries exist; complete capability, actor and authority-regression enforcement is absent. Slice 2/5/10. |
| AUTH-01-12 | §12 Persistent Memory Is Governed State | PARTIALLY_IMPLEMENTED | B04,B16,B18,B19,B20 | Typed claims and provenance exist; complete epistemic types, actor lineage and historical state do not. Slice 2/3. |
| AUTH-01-13 | §13 Reversibility | PARTIALLY_IMPLEMENTED | V01,V02,V03,V04,V05,V06,V07,V08 | Governed 48-hour rollback exists for claims/assessments; dependent propagation and backup recovery remain open. Slice 3/recovery review. |
| AUTH-01-14 | §14 Auditability | PARTIALLY_IMPLEMENTED | A01,A02,A03,A04,A05 | Core mutation and rejected-memory security events are covered; source-policy, provider-session, and authenticated identity coverage remain open. Slice 4. |
| AUTH-01-15 | §15 No Silent Loss of Knowledge | PARTIALLY_IMPLEMENTED | A06,B19,V01,V08 | Governed assessment changes retain journal history and retained audit deletion is restricted; dependent propagation and backup/restore remain incomplete. Slice 4/recovery review. |
| AUTH-01-16 | §16 Independent Corroboration | DESIGNED_NOT_IMPLEMENTED | B12,B16 | Exact deduplication is not source-independence analysis. Slice 6/9. |
| AUTH-01-17 | §17 Uncertainty Is First-Class State | PARTIALLY_IMPLEMENTED | B04,B16,B18,B19,B20 | Typed claims and provenance exist; complete epistemic types, actor lineage and historical state do not. Slice 2/3. |
| AUTH-01-18 | §18 Failure Must Be Safer Than Success | PARTIALLY_IMPLEMENTED | B06,B14,A01,S02 | Existing transactional/failure controls cover limited services, not all governed operations. Slice 2–5. |
| AUTH-01-19 | §19 Least Authority | PARTIALLY_IMPLEMENTED | B17,S01,S02,S04,R01 | Current application boundaries exist; complete capability, actor and authority-regression enforcement is absent. Slice 2/5/10. |
| AUTH-01-20 | §20 Replaceability | PARTIALLY_IMPLEMENTED | B22,N02 | Provider-neutral reporting exists; agent/storage abstractions remain incomplete. Slice 6. |
| AUTH-01-21 | §21 Local and Degraded Operation | PARTIALLY_IMPLEMENTED | B06,B14,A01,S02 | Existing transactional/failure controls cover limited services, not all governed operations. Slice 2–5. |
| AUTH-01-22 | §22 Bounded Autonomy | DESIGNED_NOT_IMPLEMENTED | B24,N05 | Per-call limits exist; no autonomous execution envelope. Slice 5/9. |
| AUTH-01-23 | §23 State Integrity | PARTIALLY_IMPLEMENTED | B06,B14,A01,S02 | Existing transactional/failure controls cover limited services, not all governed operations. Slice 2–5. |
| AUTH-01-24 | §24 Separation of Proposal and Commitment | PARTIALLY_IMPLEMENTED | B17,S01,S02,S04,R01 | Current application boundaries exist; complete capability, actor and authority-regression enforcement is absent. Slice 2/5/10. |
| AUTH-01-25 | §25 Source-of-Truth Principle | PARTIALLY_IMPLEMENTED | B17,S01,S02,S04,R01 | Current application boundaries exist; complete capability, actor and authority-regression enforcement is absent. Slice 2/5/10. |
| AUTH-01-26 | §26 Constitutional Immutability | PARTIALLY_IMPLEMENTED | B17,S01,S02,S04,R01 | Current application boundaries exist; complete capability, actor and authority-regression enforcement is absent. Slice 2/5/10. |
| AUTH-01-27 | §27 Conformance Requirement | PARTIALLY_IMPLEMENTED | B17,S01,S02,S04,R01 | Current application boundaries exist; complete capability, actor and authority-regression enforcement is absent. Slice 2/5/10. |
| AUTH-01-28 | §28 Priority of Safety and Integrity | PARTIALLY_IMPLEMENTED | B17,S01,S02,S04,R01 | Current application boundaries exist; complete capability, actor and authority-regression enforcement is absent. Slice 2/5/10. |
| AUTH-01-29 | §29 Core Constitutional Axioms | CONFLICTING | A06,S01,B16 | Compact axioms include historical preservation, which assessment replacement violates. Other boundaries are partial. Slice 2–5. |
| AUTH-01-30 | §30 Relationship to Subsequent Authority Documents | PARTIALLY_IMPLEMENTED | R01 | Authority sources now present; full downstream behavioral conformance remains open. Slice 10. |
| AUTH-01-31 | §31 Final Constitutional Statement | PARTIALLY_IMPLEMENTED | B17,S01,S02,S04,R01 | Current application boundaries exist; complete capability, actor and authority-regression enforcement is absent. Slice 2/5/10. |

### Document 02 — System Architecture Authority

Source: [Gnomon System Architecture Authority.docx](../archive/original-authority-documents/Gnomon%20System%20Architecture%20Authority.docx). SHA-256: `8acf648710630d59a0ab5d92ef051d9702c3beaff44011cd0f984e3e2846aabd`.

| Requirement group | Source section | Classification | Evidence IDs | Gap / priority |
| --- | --- | --- | --- | --- |
| AUTH-02-01 | §1 Purpose | PARTIALLY_IMPLEMENTED | B01,B02,B04,B15,B17,N01 | Layering and core research types exist; runtime, memory, entity and agent concepts are incomplete. Slice 2/6/9. |
| AUTH-02-02 | §2 Architectural Objective | PARTIALLY_IMPLEMENTED | B01,B02,B04,B15,B17,N01 | Layering and core research types exist; runtime, memory, entity and agent concepts are incomplete. Slice 2/6/9. |
| AUTH-02-03 | §3 Architectural Principle | PARTIALLY_IMPLEMENTED | B01,B02,B04,B15,B17,N01 | Layering and core research types exist; runtime, memory, entity and agent concepts are incomplete. Slice 2/6/9. |
| AUTH-02-04 | §4 Architectural Layers | PARTIALLY_IMPLEMENTED | B01,B02,B04,B15,B17,N01 | Layering and core research types exist; runtime, memory, entity and agent concepts are incomplete. Slice 2/6/9. |
| AUTH-02-05 | §5 Application Layer | PARTIALLY_IMPLEMENTED | B01,B02,B04,B15,B17,N01 | Layering and core research types exist; runtime, memory, entity and agent concepts are incomplete. Slice 2/6/9. |
| AUTH-02-06 | §6 Domain Layer | PARTIALLY_IMPLEMENTED | B01,B02,B04,B15,B17,N01 | Layering and core research types exist; runtime, memory, entity and agent concepts are incomplete. Slice 2/6/9. |
| AUTH-02-07 | §7 Port Layer | PARTIALLY_IMPLEMENTED | B01,B02,B04,B15,B17,N01 | Layering and core research types exist; runtime, memory, entity and agent concepts are incomplete. Slice 2/6/9. |
| AUTH-02-08 | §8 Adapter Layer | PARTIALLY_IMPLEMENTED | B22,B25,N02 | Existing provider/retrieval adapters preserve domain independence; future adapters lack contracts/tests. Slice 5/6. |
| AUTH-02-09 | §9 Infrastructure Layer | PARTIALLY_IMPLEMENTED | B22,B25,N02 | Existing provider/retrieval adapters preserve domain independence; future adapters lack contracts/tests. Slice 5/6. |
| AUTH-02-10 | §10 Model Boundary | PARTIALLY_IMPLEMENTED | B22,B25,N02 | Existing provider/retrieval adapters preserve domain independence; future adapters lack contracts/tests. Slice 5/6. |
| AUTH-02-11 | §11 Model Role | PARTIALLY_IMPLEMENTED | B22,B25,N02 | Existing provider/retrieval adapters preserve domain independence; future adapters lack contracts/tests. Slice 5/6. |
| AUTH-02-12 | §12 Tool Boundary | DESIGNED_NOT_IMPLEMENTED | S04,N05 | No tool registry, approved-action executor or bounded autonomous runner. Slice 5/9. |
| AUTH-02-13 | §13 Tool Registry | DESIGNED_NOT_IMPLEMENTED | S04,N05 | No tool registry, approved-action executor or bounded autonomous runner. Slice 5/9. |
| AUTH-02-14 | §14 State Mutation Boundary | PARTIALLY_IMPLEMENTED | B16,B17,M01 | Claim proposals use validators; general governed mutations are missing. Slice 2. |
| AUTH-02-15 | §15 Evidence Boundary | PARTIALLY_IMPLEMENTED | B16,B17,M01 | Claim proposals use validators; general governed mutations are missing. Slice 2. |
| AUTH-02-16 | §16 Agent Network Boundary | DESIGNED_NOT_IMPLEMENTED | N01,N02 | AgentNetwork and AgentObservation are design-only. Slice 6. |
| AUTH-02-17 | §17 Agent Observation Boundary | DESIGNED_NOT_IMPLEMENTED | N01,N02 | AgentNetwork and AgentObservation are design-only. Slice 6. |
| AUTH-02-18 | §18 Research Orchestrator | DESIGNED_NOT_IMPLEMENTED | S04,N05 | No tool registry, approved-action executor or bounded autonomous runner. Slice 5/9. |
| AUTH-02-19 | §19 Autonomous Research Loop | DESIGNED_NOT_IMPLEMENTED | S04,N05 | No tool registry, approved-action executor or bounded autonomous runner. Slice 5/9. |
| AUTH-02-20 | §20 Bounded Execution | DESIGNED_NOT_IMPLEMENTED | S04,N05 | No tool registry, approved-action executor or bounded autonomous runner. Slice 5/9. |
| AUTH-02-21 | §21 Research State Is Persistent | IMPLEMENTED | B02,B20 | Persisted task/evidence snapshots survive fresh sessions; scope is stored research, not an autonomous runtime. |
| AUTH-02-22 | §22 Memory Retrieval Boundary | PARTIALLY_IMPLEMENTED | B20,B21 | Task-scoped retrieval exists; cross-task, access-controlled bounded memory search absent. Slice 2/5. |
| AUTH-02-23 | §23 Semantic Memory | DEFERRED | D01 | Semantic retrieval explicitly deferred; canonical state remains relational. |
| AUTH-02-24 | §24 PostgreSQL and Persistent Storage | PARTIALLY_IMPLEMENTED | B02,B06,B16,A01,V01,A06 | Current PostgreSQL and transactional paths exist; complete historical integrity does not. Slice 2–4. |
| AUTH-02-25 | §25 Storage Authority | PARTIALLY_IMPLEMENTED | B02,B06,B16,A01,V01,A06 | Current PostgreSQL and transactional paths exist; complete historical integrity does not. Slice 2–4. |
| AUTH-02-26 | §26 Transactional Integrity | PARTIALLY_IMPLEMENTED | B02,B06,B16,A01,V01,A06 | Current PostgreSQL and transactional paths exist; complete historical integrity does not. Slice 2–4. |
| AUTH-02-27 | §27 Concurrency | PARTIALLY_IMPLEMENTED | B02,B06,B16,A01,V01,A06 | Current PostgreSQL and transactional paths exist; complete historical integrity does not. Slice 2–4. |
| AUTH-02-28 | §28 Event and Audit Architecture | PARTIALLY_IMPLEMENTED | B02,B06,B16,A01,V01,A06 | Current PostgreSQL and transactional paths exist; complete historical integrity does not. Slice 2–4. |
| AUTH-02-29 | §29 Deployment Independence | PARTIALLY_IMPLEMENTED | B01,B22,N02 | Local operation works without cloud calls; fake network and deployment verification incomplete. Slice 6/10. |
| AUTH-02-30 | §30 Reference Deployment | PARTIALLY_IMPLEMENTED | B01,B22,N02 | Local operation works without cloud calls; fake network and deployment verification incomplete. Slice 6/10. |
| AUTH-02-31 | §31 Degraded Operation | PARTIALLY_IMPLEMENTED | B14,B25,S01,S02,S03 | HTTP protections/local services exist; explicit degradation state machine and universal boundary tests absent. Slice 5. |
| AUTH-02-32 | §32 Security Boundary | PARTIALLY_IMPLEMENTED | B14,B25,S01,S02,S03 | HTTP protections/local services exist; explicit degradation state machine and universal boundary tests absent. Slice 5. |
| AUTH-02-33 | §33 Network Egress | PARTIALLY_IMPLEMENTED | B14,B25,S01,S02,S03 | HTTP protections/local services exist; explicit degradation state machine and universal boundary tests absent. Slice 5. |
| AUTH-02-34 | §34 Prompt-Injection Boundary | PARTIALLY_IMPLEMENTED | B14,B25,S01,S02,S03 | HTTP protections/local services exist; explicit degradation state machine and universal boundary tests absent. Slice 5. |
| AUTH-02-35 | §35 Failure Isolation | PARTIALLY_IMPLEMENTED | B14,B25,S01,S02,S03 | HTTP protections/local services exist; explicit degradation state machine and universal boundary tests absent. Slice 5. |
| AUTH-02-36 | §36 Testing Architecture | PARTIALLY_IMPLEMENTED | B14,B17,R01,N03 | Existing controlled tests pass; mandatory runtime/network/rollback properties remain untested. Slice 3/5/7. |
| AUTH-02-37 | §37 Existing Gnomon Architecture | PARTIALLY_IMPLEMENTED | B01,M01,N02 | Existing services retained; future extensions not yet implemented. Slice 2 onward. |
| AUTH-02-38 | §38 Architectural Evolution | PARTIALLY_IMPLEMENTED | B01,M01,N02 | Existing services retained; future extensions not yet implemented. Slice 2 onward. |
| AUTH-02-39 | §39 Prohibited Architectural Patterns | PARTIALLY_IMPLEMENTED | B16,B17,S01,S04,V01,N05 | Prohibited paths are not exposed by existing providers; full canonical runtime and recovery evidence absent. Slice 2–10. |
| AUTH-02-40 | §40 Canonical Authority Flow | PARTIALLY_IMPLEMENTED | B16,B17,S01,S04,V01,N05 | Prohibited paths are not exposed by existing providers; full canonical runtime and recovery evidence absent. Slice 2–10. |
| AUTH-02-41 | §41 Canonical Research Execution | PARTIALLY_IMPLEMENTED | B16,B17,S01,S04,V01,N05 | Prohibited paths are not exposed by existing providers; full canonical runtime and recovery evidence absent. Slice 2–10. |
| AUTH-02-42 | §42 Architectural Invariants | PARTIALLY_IMPLEMENTED | B16,B17,S01,S04,V01,N05 | Prohibited paths are not exposed by existing providers; full canonical runtime and recovery evidence absent. Slice 2–10. |
| AUTH-02-43 | §43 Architectural Test of Correctness | PARTIALLY_IMPLEMENTED | B16,B17,S01,S04,V01,N05 | Prohibited paths are not exposed by existing providers; full canonical runtime and recovery evidence absent. Slice 2–10. |
| AUTH-02-44 | §44 Relationship to Document 01 | PARTIALLY_IMPLEMENTED | B16,B17,S01,S04,V01,N05 | Prohibited paths are not exposed by existing providers; full canonical runtime and recovery evidence absent. Slice 2–10. |
| AUTH-02-45 | §45 Final Architectural Statement | PARTIALLY_IMPLEMENTED | B16,B17,S01,S04,V01,N05 | Prohibited paths are not exposed by existing providers; full canonical runtime and recovery evidence absent. Slice 2–10. |

### Document 03 — Epistemic & Evidence Authority

Source: [Gnomon Epistemic & Evidence Authority.docx](../archive/original-authority-documents/Gnomon%20Epistemic%20%26%20Evidence%20Authority.docx). SHA-256: `f5cc576da120fc13f1bd8a9106bcadcc12ba1ff630f6a170eaeeecd2f3b627fb`.

| Requirement group | Source section | Classification | Evidence IDs | Gap / priority |
| --- | --- | --- | --- | --- |
| AUTH-03-01 | §1 Purpose | PARTIALLY_IMPLEMENTED | B04,B10,B15,B16,B18,B19 | Source/claim/assessment types exist; complete observations, inferences, lineage, context and revisions absent. Slice 2/3/9. |
| AUTH-03-02 | §2 Foundational Epistemic Principle | PARTIALLY_IMPLEMENTED | B04,B10,B15,B16,B18,B19 | Source/claim/assessment types exist; complete observations, inferences, lineage, context and revisions absent. Slice 2/3/9. |
| AUTH-03-03 | §3 Epistemic Objects | PARTIALLY_IMPLEMENTED | B04,B10,B15,B16,B18,B19 | Source/claim/assessment types exist; complete observations, inferences, lineage, context and revisions absent. Slice 2/3/9. |
| AUTH-03-04 | §4 Source | PARTIALLY_IMPLEMENTED | B04,B10,B15,B16,B18,B19 | Source/claim/assessment types exist; complete observations, inferences, lineage, context and revisions absent. Slice 2/3/9. |
| AUTH-03-05 | §5 Observation | PARTIALLY_IMPLEMENTED | B04,B10,B15,B16,B18,B19 | Source/claim/assessment types exist; complete observations, inferences, lineage, context and revisions absent. Slice 2/3/9. |
| AUTH-03-06 | §6 Evidence | PARTIALLY_IMPLEMENTED | B04,B10,B15,B16,B18,B19 | Source/claim/assessment types exist; complete observations, inferences, lineage, context and revisions absent. Slice 2/3/9. |
| AUTH-03-07 | §7 Claim | PARTIALLY_IMPLEMENTED | B04,B10,B15,B16,B18,B19 | Source/claim/assessment types exist; complete observations, inferences, lineage, context and revisions absent. Slice 2/3/9. |
| AUTH-03-08 | §8 Claim Does Not Mean Fact | IMPLEMENTED | B16,B17,B20 | Unverified claims persist without promotion; source reliability and claim confidence are distinct fields and survive reporting. |
| AUTH-03-09 | §9 Claim Provenance | PARTIALLY_IMPLEMENTED | B04,B10,B15,B16,B18,B19 | Source/claim/assessment types exist; complete observations, inferences, lineage, context and revisions absent. Slice 2/3/9. |
| AUTH-03-10 | §10 Inference | PARTIALLY_IMPLEMENTED | B04,B10,B15,B16,B18,B19 | Source/claim/assessment types exist; complete observations, inferences, lineage, context and revisions absent. Slice 2/3/9. |
| AUTH-03-11 | §11 Hypothesis | PARTIALLY_IMPLEMENTED | B04,B10,B15,B16,B18,B19 | Source/claim/assessment types exist; complete observations, inferences, lineage, context and revisions absent. Slice 2/3/9. |
| AUTH-03-12 | §12 Hypothesis Assessment | PARTIALLY_IMPLEMENTED | B04,B10,B15,B16,B18,B19 | Source/claim/assessment types exist; complete observations, inferences, lineage, context and revisions absent. Slice 2/3/9. |
| AUTH-03-13 | §13 Conclusion | DESIGNED_NOT_IMPLEMENTED | B16,B21 | No conclusion/inference model or source-independence evaluation. Slice 6/9; advanced synthesis deferred. |
| AUTH-03-14 | §14 Epistemic Status | PARTIALLY_IMPLEMENTED | B04,B10,B15,B16,B18,B19 | Source/claim/assessment types exist; complete observations, inferences, lineage, context and revisions absent. Slice 2/3/9. |
| AUTH-03-15 | §15 Confidence | PARTIALLY_IMPLEMENTED | B04,B10,B15,B16,B18,B19 | Source/claim/assessment types exist; complete observations, inferences, lineage, context and revisions absent. Slice 2/3/9. |
| AUTH-03-16 | §16 Source Reliability vs Claim Confidence | IMPLEMENTED | B16,B17,B20 | Unverified claims persist without promotion; source reliability and claim confidence are distinct fields and survive reporting. |
| AUTH-03-17 | §17 Evidence Quality | PARTIALLY_IMPLEMENTED | B04,B10,B15,B16,B18,B19 | Source/claim/assessment types exist; complete observations, inferences, lineage, context and revisions absent. Slice 2/3/9. |
| AUTH-03-18 | §18 Corroboration | DESIGNED_NOT_IMPLEMENTED | B16,B21 | No conclusion/inference model or source-independence evaluation. Slice 6/9; advanced synthesis deferred. |
| AUTH-03-19 | §19 Source Independence | DESIGNED_NOT_IMPLEMENTED | B16,B21 | No conclusion/inference model or source-independence evaluation. Slice 6/9; advanced synthesis deferred. |
| AUTH-03-20 | §20 Contradiction | PARTIALLY_IMPLEMENTED | B07,B16,B19 | Conflicting links/states coexist; evidence-quality conflict resolution incomplete. Slice 9. |
| AUTH-03-21 | §21 Contested Knowledge | PARTIALLY_IMPLEMENTED | B07,B16,B19 | Conflicting links/states coexist; evidence-quality conflict resolution incomplete. Slice 9. |
| AUTH-03-22 | §22 Agent-Sourced Evidence | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03 | Agent identity, observations and epistemic evaluation absent. Slice 6/7/9. |
| AUTH-03-23 | §23 Unknown Agents | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03 | Agent identity, observations and epistemic evaluation absent. Slice 6/7/9. |
| AUTH-03-24 | §24 Agent Reputation Is Not Authority | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03 | Agent identity, observations and epistemic evaluation absent. Slice 6/7/9. |
| AUTH-03-25 | §25 Agent Recommendations | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03 | Agent identity, observations and epistemic evaluation absent. Slice 6/7/9. |
| AUTH-03-26 | §26 Agent-to-Agent Consensus | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03 | Agent identity, observations and epistemic evaluation absent. Slice 6/7/9. |
| AUTH-03-27 | §27 Web and Document Evidence | PARTIALLY_IMPLEMENTED | B10,B13,B16 | Sources and reliability metadata exist; primary/derivative lineage and explainable weighting absent. Slice 9. |
| AUTH-03-28 | §28 Primary and Secondary Sources | PARTIALLY_IMPLEMENTED | B10,B13,B16 | Sources and reliability metadata exist; primary/derivative lineage and explainable weighting absent. Slice 9. |
| AUTH-03-29 | §29 Evidence Weighting | PARTIALLY_IMPLEMENTED | B10,B13,B16 | Sources and reliability metadata exist; primary/derivative lineage and explainable weighting absent. Slice 9. |
| AUTH-03-30 | §30 Temporal Validity | DESIGNED_NOT_IMPLEMENTED | B18 | No explicit temporal/population/quantitative/causal/forecast semantics or corresponding validation tests. Slice 9/release gap. |
| AUTH-03-31 | §31 Context | DESIGNED_NOT_IMPLEMENTED | B18 | No explicit temporal/population/quantitative/causal/forecast semantics or corresponding validation tests. Slice 9/release gap. |
| AUTH-03-32 | §32 Quantitative Evidence | DESIGNED_NOT_IMPLEMENTED | B18 | No explicit temporal/population/quantitative/causal/forecast semantics or corresponding validation tests. Slice 9/release gap. |
| AUTH-03-33 | §33 Causal Claims | DESIGNED_NOT_IMPLEMENTED | B18 | No explicit temporal/population/quantitative/causal/forecast semantics or corresponding validation tests. Slice 9/release gap. |
| AUTH-03-34 | §34 Forecasts | DESIGNED_NOT_IMPLEMENTED | B18 | No explicit temporal/population/quantitative/causal/forecast semantics or corresponding validation tests. Slice 9/release gap. |
| AUTH-03-35 | §35 Predictions by Agents | DESIGNED_NOT_IMPLEMENTED | B18 | No explicit temporal/population/quantitative/causal/forecast semantics or corresponding validation tests. Slice 9/release gap. |
| AUTH-03-36 | §36 Self-Generated Knowledge | DESIGNED_NOT_IMPLEMENTED | V06,N05 | No inference graph, retraction propagation or dependent reassessment. Slice 3/9. |
| AUTH-03-37 | §37 Dependency Tracking | DESIGNED_NOT_IMPLEMENTED | V06,N05 | No inference graph, retraction propagation or dependent reassessment. Slice 3/9. |
| AUTH-03-38 | §38 Retraction | DESIGNED_NOT_IMPLEMENTED | V06,N05 | No inference graph, retraction propagation or dependent reassessment. Slice 3/9. |
| AUTH-03-39 | §39 Evidence Updates | CONFLICTING | B19,A06 | Assessment replacement destroys previous epistemic state instead of retaining historical transitions. Slice 2/3. |
| AUTH-03-40 | §40 Research State vs Epistemic State | IMPLEMENTED | B06,B16,B20 | Task status and claim/assessment status remain separate; snapshots/reports preserve distinctions. |
| AUTH-03-41 | §41 Stopping Criteria | PARTIALLY_IMPLEMENTED | B04,B06,B08 | Stopping criteria and manual statuses exist; structured stopping reasons and autonomous evaluator absent. Slice 9; reasoning deferred. |
| AUTH-03-42 | §42 Negative Evidence | PARTIALLY_IMPLEMENTED | A01,B07 | Retrieval failures do not promote contradictory claims; complete search-coverage reasoning and targeted tests absent. Slice 5/9. |
| AUTH-03-43 | §43 Search Failure | PARTIALLY_IMPLEMENTED | A01,B07 | Retrieval failures do not promote contradictory claims; complete search-coverage reasoning and targeted tests absent. Slice 5/9. |
| AUTH-03-44 | §44 Research Coverage | PARTIALLY_IMPLEMENTED | B07 | Gap and contradiction priorities exist; source diversity, active search and quality evaluation absent. Slice 9. |
| AUTH-03-45 | §45 Evidence Saturation | PARTIALLY_IMPLEMENTED | B07 | Gap and contradiction priorities exist; source diversity, active search and quality evaluation absent. Slice 9. |
| AUTH-03-46 | §46 Adversarial Evidence Gathering | PARTIALLY_IMPLEMENTED | B07 | Gap and contradiction priorities exist; source diversity, active search and quality evaluation absent. Slice 9. |
| AUTH-03-47 | §47 Model Agreement | DESIGNED_NOT_IMPLEMENTED | N02,N05 | No agent/model consensus evaluation or agent discovery pipeline. Slice 6/9. |
| AUTH-03-48 | §48 Source Ranking | PARTIALLY_IMPLEMENTED | B07 | Gap and contradiction priorities exist; source diversity, active search and quality evaluation absent. Slice 9. |
| AUTH-03-49 | §49 Agent Evidence as Discovery Infrastructure | DESIGNED_NOT_IMPLEMENTED | N02,N05 | No agent/model consensus evaluation or agent discovery pipeline. Slice 6/9. |
| AUTH-03-50 | §50 Epistemic Memory | CONFLICTING | B19,A06 | Assessment replacement destroys previous epistemic state instead of retaining historical transitions. Slice 2/3. |
| AUTH-03-51 | §51 Knowledge Decay | PARTIALLY_IMPLEMENTED | B07,B18 | Review states and conflict priorities exist; temporal decay and complete resolution process absent. Slice 9. |
| AUTH-03-52 | §52 Epistemic Conflict Resolution | PARTIALLY_IMPLEMENTED | B07,B18 | Review states and conflict priorities exist; temporal decay and complete resolution process absent. Slice 9. |
| AUTH-03-53 | §53 No Retroactive Certainty | CONFLICTING | B19,A06 | Assessment replacement destroys previous epistemic state instead of retaining historical transitions. Slice 2/3. |
| AUTH-03-54 | §54 Research Report Requirements | PARTIALLY_IMPLEMENTED | B20,B22,B23 | Structured report preserves uncertainty; provider prose entailment and qualifier preservation not guaranteed. Slice 5/9. |
| AUTH-03-55 | §55 Epistemic Integrity Under Compression | PARTIALLY_IMPLEMENTED | B20,B22,B23 | Structured report preserves uncertainty; provider prose entailment and qualifier preservation not guaranteed. Slice 5/9. |
| AUTH-03-56 | §56 Vector and Semantic Retrieval | DEFERRED | D01 | Embeddings deferred; keep relational records authoritative when introduced. |
| AUTH-03-57 | §57 Epistemic Integrity of Embeddings | DEFERRED | D01 | Embeddings deferred; keep relational records authoritative when introduced. |
| AUTH-03-58 | §58 User-Provided Information | PARTIALLY_IMPLEMENTED | B10,B16,S02 | User/inference source classes exist; full ambiguity/authority classification missing. Slice 2/5. |
| AUTH-03-59 | §59 Epistemic Safety Rule | PARTIALLY_IMPLEMENTED | B10,B16,S02 | User/inference source classes exist; full ambiguity/authority classification missing. Slice 2/5. |
| AUTH-03-60 | §60 Mandatory Epistemic Invariants | CONFLICTING | A06,B16,B20 | Mandatory invariant E9 is violated by lost assessment history; others vary from implemented to absent. Slice 2/3. |
| AUTH-03-61 | §61 Epistemic Integrity Test | PARTIALLY_IMPLEMENTED | B20,B23,V01 | Current provenance reports answer some questions; independent evidence, historical and conclusion dependencies absent. Slice 3/9. |
| AUTH-03-62 | §62 Relationship to Previous Authority Documents | PARTIALLY_IMPLEMENTED | B20,B23,V01 | Current provenance reports answer some questions; independent evidence, historical and conclusion dependencies absent. Slice 3/9. |
| AUTH-03-63 | §63 Final Epistemic Statement | PARTIALLY_IMPLEMENTED | B20,B23,V01 | Current provenance reports answer some questions; independent evidence, historical and conclusion dependencies absent. Slice 3/9. |

### Document 04 — Memory & State Authority

Source: [Gnomon Memory & State Authority.docx](../archive/original-authority-documents/Gnomon%20Memory%20%26%20State%20Authority.docx). SHA-256: `7fe372dcddc65c18fded56f908c89fe800e52107c83bb8896ffdddfec3a658d5`.

| Requirement group | Source section | Classification | Evidence IDs | Gap / priority |
| --- | --- | --- | --- | --- |
| AUTH-04-01 | §1 Purpose | PARTIALLY_IMPLEMENTED | B16,B19,M01,M08 | Current typed records and create validators exist; governed operations and trusted actor context absent. Slice 2. |
| AUTH-04-02 | §2 Foundational Principle | PARTIALLY_IMPLEMENTED | B16,B19,M01,M08 | Current typed records and create validators exist; governed operations and trusted actor context absent. Slice 2. |
| AUTH-04-03 | §3 Authoritative State | PARTIALLY_IMPLEMENTED | B16,B19,M01,M08 | Current typed records and create validators exist; governed operations and trusted actor context absent. Slice 2. |
| AUTH-04-04 | §4 Memory Categories | PARTIALLY_IMPLEMENTED | B16,B19,M01,M08 | Current typed records and create validators exist; governed operations and trusted actor context absent. Slice 2. |
| AUTH-04-05 | §5 Memory Is Not a Transcript | IMPLEMENTED | B02,B20 | Fresh-session PostgreSQL snapshots reconstruct stored research without a conversation transcript. |
| AUTH-04-06 | §6 Memory Mutation | PARTIALLY_IMPLEMENTED | B16,B19,M01,M08 | Current typed records and create validators exist; governed operations and trusted actor context absent. Slice 2. |
| AUTH-04-07 | §7 Mutation Actor | PARTIALLY_IMPLEMENTED | B16,B19,M01,M08 | Current typed records and create validators exist; governed operations and trusted actor context absent. Slice 2. |
| AUTH-04-08 | §8 Versioned State | CONFLICTING | B19,A06,V01 | Current assessments are neither versioned nor historically recoverable. Slice 2/3. |
| AUTH-04-09 | §9 Immutable Historical Records | CONFLICTING | B19,A06,V01 | Current assessments are neither versioned nor historically recoverable. Slice 2/3. |
| AUTH-04-10 | §10 Event-Sourced Principles | PARTIALLY_IMPLEMENTED | A01,A04 | Events have IDs/time/correlation; actor/version/reason/history incomplete. Slice 3/4. |
| AUTH-04-11 | §11 Event Identity | PARTIALLY_IMPLEMENTED | A01,A04 | Events have IDs/time/correlation; actor/version/reason/history incomplete. Slice 3/4. |
| AUTH-04-12 | §12 Idempotency | PARTIALLY_IMPLEMENTED | B06,B12,V01 | Exact create retries and lifecycle locking exist; general mutation replay/version conflicts absent. Slice 2/3. |
| AUTH-04-13 | §13 Compare-and-Set | PARTIALLY_IMPLEMENTED | B06,B12,V01 | Exact create retries and lifecycle locking exist; general mutation replay/version conflicts absent. Slice 2/3. |
| AUTH-04-14 | §14 Concurrent Memory Changes | PARTIALLY_IMPLEMENTED | B06,B12,V01 | Exact create retries and lifecycle locking exist; general mutation replay/version conflicts absent. Slice 2/3. |
| AUTH-04-15 | §15 Merge | DEFERRED | M07 | Merge deferred until the initial five operations; future merge must preserve both identities and provenance. |
| AUTH-04-16 | §16 Merge Safety | DEFERRED | M07 | Merge deferred until the initial five operations; future merge must preserve both identities and provenance. |
| AUTH-04-17 | §17 Provenance Dependency | PARTIALLY_IMPLEMENTED | B16,B19,V06 | Source→claim→assessment links exist; broader versioned dependency graph absent. Slice 3/9. |
| AUTH-04-18 | §18 Provenance Graph | PARTIALLY_IMPLEMENTED | B16,B19,V06 | Source→claim→assessment links exist; broader versioned dependency graph absent. Slice 3/9. |
| AUTH-04-19 | §19 Rollback Principle | DESIGNED_NOT_IMPLEMENTED | V01,V02,V03,V04,V05,V06,V07,V08 | No rollback service; preserve independent evidence and reject unresolved dependency conflicts. Slice 3. |
| AUTH-04-20 | §20 48-Hour Reversible Window | DESIGNED_NOT_IMPLEMENTED | V01,V02,V03,V04,V05,V06,V07,V08 | No rollback service; preserve independent evidence and reject unresolved dependency conflicts. Slice 3. |
| AUTH-04-21 | §21 Why Logical Deletion Is Required | DESIGNED_NOT_IMPLEMENTED | V01,V02,V03,V04,V05,V06,V07,V08 | No rollback service; preserve independent evidence and reject unresolved dependency conflicts. Slice 3. |
| AUTH-04-22 | §22 Rollback Record | DESIGNED_NOT_IMPLEMENTED | V01,V02,V03,V04,V05,V06,V07,V08 | No rollback service; preserve independent evidence and reject unresolved dependency conflicts. Slice 3. |
| AUTH-04-23 | §23 Rollback Eligibility | DESIGNED_NOT_IMPLEMENTED | V01,V02,V03,V04,V05,V06,V07,V08 | No rollback service; preserve independent evidence and reject unresolved dependency conflicts. Slice 3. |
| AUTH-04-24 | §24 Dependency-Aware Rollback | DESIGNED_NOT_IMPLEMENTED | V01,V02,V03,V04,V05,V06,V07,V08 | No rollback service; preserve independent evidence and reject unresolved dependency conflicts. Slice 3. |
| AUTH-04-25 | §25 "Undo What Agent X Taught Me" | DESIGNED_NOT_IMPLEMENTED | V01,V02,V03,V04,V05,V06,V07,V08 | No rollback service; preserve independent evidence and reject unresolved dependency conflicts. Slice 3. |
| AUTH-04-26 | §26 Example: Agent Information | DESIGNED_NOT_IMPLEMENTED | V01,V02,V03,V04,V05,V06,V07,V08 | No rollback service; preserve independent evidence and reject unresolved dependency conflicts. Slice 3. |
| AUTH-04-27 | §27 Example: Derived Inference | DESIGNED_NOT_IMPLEMENTED | V01,V02,V03,V04,V05,V06,V07,V08 | No rollback service; preserve independent evidence and reject unresolved dependency conflicts. Slice 3. |
| AUTH-04-28 | §28 Reassessment vs Deletion | DESIGNED_NOT_IMPLEMENTED | V01,V02,V03,V04,V05,V06,V07,V08 | No rollback service; preserve independent evidence and reject unresolved dependency conflicts. Slice 3. |
| AUTH-04-29 | §29 Memory Pruning | DESIGNED_NOT_IMPLEMENTED | M04,M05 | No governed pruning/retention mechanism. Slice 2/3. |
| AUTH-04-30 | §30 Redundancy | PARTIALLY_IMPLEMENTED | B12 | Exact task/origin/text/provenance identity exists; semantic redundancy/context analysis absent. |
| AUTH-04-31 | §31 Archive | DESIGNED_NOT_IMPLEMENTED | M04,M06 | Archive and restore absent. Slice 2. |
| AUTH-04-32 | §32 Restore | DESIGNED_NOT_IMPLEMENTED | M04,M06 | Archive and restore absent. Slice 2. |
| AUTH-04-33 | §33 Permanent Purge | DESIGNED_NOT_IMPLEMENTED | A06,V07 | No privileged purge/retention policy; no ordinary model purge exposed. Slice 3/4; purge capability deferred. |
| AUTH-04-34 | §34 Retention | DESIGNED_NOT_IMPLEMENTED | A06,V07 | No privileged purge/retention policy; no ordinary model purge exposed. Slice 3/4; purge capability deferred. |
| AUTH-04-35 | §35 Memory Confidence Updates | CONFLICTING | B19,A06 | Assessment confidence/status replacement is not recorded historically. Slice 2/3. |
| AUTH-04-36 | §36 Knowledge Supersession | DEFERRED | M07 | Supersession/retraction workflow follows initial five operations; existing enum is insufficient. |
| AUTH-04-37 | §37 Retraction | DEFERRED | M07 | Supersession/retraction workflow follows initial five operations; existing enum is insufficient. |
| AUTH-04-38 | §38 Contradiction | IMPLEMENTED | B16,B20 | Supporting/contradicting provenance and competing claims can coexist in snapshots. |
| AUTH-04-39 | §39 State Reconstruction | DESIGNED_NOT_IMPLEMENTED | V01 | No historical state reconstruction. Slice 3. |
| AUTH-04-40 | §40 State Integrity | PARTIALLY_IMPLEMENTED | B16,B17,B20,A01 | Current transactional/provenance/context checks exist; historical state and controlled memory access incomplete. Slice 2–5. |
| AUTH-04-41 | §41 Atomic Mutations | PARTIALLY_IMPLEMENTED | B16,B17,B20,A01 | Current transactional/provenance/context checks exist; historical state and controlled memory access incomplete. Slice 2–5. |
| AUTH-04-42 | §42 Recovery From Partial Failure | PARTIALLY_IMPLEMENTED | B16,B17,B20,A01 | Current transactional/provenance/context checks exist; historical state and controlled memory access incomplete. Slice 2–5. |
| AUTH-04-43 | §43 Memory Access | PARTIALLY_IMPLEMENTED | B16,B17,B20,A01 | Current transactional/provenance/context checks exist; historical state and controlled memory access incomplete. Slice 2–5. |
| AUTH-04-44 | §44 Memory Context Integrity | PARTIALLY_IMPLEMENTED | B16,B17,B20,A01 | Current transactional/provenance/context checks exist; historical state and controlled memory access incomplete. Slice 2–5. |
| AUTH-04-45 | §45 Semantic Memory | DEFERRED | D01 | Semantic indexes/compaction deferred; future derived state must remain rebuildable. |
| AUTH-04-46 | §46 Memory Index Rebuilding | DEFERRED | D01 | Semantic indexes/compaction deferred; future derived state must remain rebuildable. |
| AUTH-04-47 | §47 Memory Compaction | DEFERRED | D01 | Semantic indexes/compaction deferred; future derived state must remain rebuildable. |
| AUTH-04-48 | §48 Memory Security | MISSING | S04 | General memory read/write authorization absent; local prototype is not a multi-user authorization system. Slice 2/5. |
| AUTH-04-49 | §49 External Communication and Memory | DESIGNED_NOT_IMPLEMENTED | N02 | No outbound disclosure validator. Slice 6/7. |
| AUTH-04-50 | §50 Memory Export | PARTIALLY_IMPLEMENTED | B20,A01,A04 | Read API preserves existing metadata; formal export and complete mutation audit absent. Slice 4. |
| AUTH-04-51 | §51 Audit and Memory | PARTIALLY_IMPLEMENTED | B20,A01,A04 | Read API preserves existing metadata; formal export and complete mutation audit absent. Slice 4. |
| AUTH-04-52 | §52 Constitutional and Policy State | PARTIALLY_IMPLEMENTED | S02,R01 | Authority documents separate from research tables; no automated protected-policy regression check yet. Slice 5/10. |
| AUTH-04-53 | §53 User Corrections | CONFLICTING | B19,A06 | User assessment corrections can overwrite prior state. Slice 2/3. |
| AUTH-04-54 | §54 Autonomous Memory Governance | DESIGNED_NOT_IMPLEMENTED | M01,V01,V02,V03,V04,V06 | Governance lifecycle, rollback conflicts and examples are not executable. Slice 2/3. |
| AUTH-04-55 | §55 Rollback Conflicts | DESIGNED_NOT_IMPLEMENTED | M01,V01,V02,V03,V04,V06 | Governance lifecycle, rollback conflicts and examples are not executable. Slice 2/3. |
| AUTH-04-56 | §56 Rollback Idempotency | DESIGNED_NOT_IMPLEMENTED | M01,V01,V02,V03,V04,V06 | Governance lifecycle, rollback conflicts and examples are not executable. Slice 2/3. |
| AUTH-04-57 | §57 Rollback Does Not Mean Historical Erasure | DESIGNED_NOT_IMPLEMENTED | M01,V01,V02,V03,V04,V06 | Governance lifecycle, rollback conflicts and examples are not executable. Slice 2/3. |
| AUTH-04-58 | §58 Memory Lifecycle | DESIGNED_NOT_IMPLEMENTED | M01,V01,V02,V03,V04,V06 | Governance lifecycle, rollback conflicts and examples are not executable. Slice 2/3. |
| AUTH-04-59 | §59 Memory Governance Example | DESIGNED_NOT_IMPLEMENTED | M01,V01,V02,V03,V04,V06 | Governance lifecycle, rollback conflicts and examples are not executable. Slice 2/3. |
| AUTH-04-60 | §60 Memory Governance Example — Bad Evidence | DESIGNED_NOT_IMPLEMENTED | M01,V01,V02,V03,V04,V06 | Governance lifecycle, rollback conflicts and examples are not executable. Slice 2/3. |
| AUTH-04-61 | §61 Memory Governance Example — Retraction | DESIGNED_NOT_IMPLEMENTED | M01,V01,V02,V03,V04,V06 | Governance lifecycle, rollback conflicts and examples are not executable. Slice 2/3. |
| AUTH-04-62 | §62 Mandatory Memory Invariants | CONFLICTING | B19,A06,V01 | Mandatory M3/M4 historical integrity is violated; rollback invariants unimplemented. Slice 2/3. |
| AUTH-04-63 | §63 Memory Integrity Test | PARTIALLY_IMPLEMENTED | B16,A01,V01 | Existing provenance/audit answers only a subset of mutation integrity questions. Slice 2–4. |
| AUTH-04-64 | §64 Relationship to Previous Authority Documents | PARTIALLY_IMPLEMENTED | B16,A01,V01 | Existing provenance/audit answers only a subset of mutation integrity questions. Slice 2–4. |
| AUTH-04-65 | §65 Final Memory Statement | PARTIALLY_IMPLEMENTED | B16,A01,V01 | Existing provenance/audit answers only a subset of mutation integrity questions. Slice 2–4. |

### Document 05 — Agent Runtime & Tool Authority

Source: [Gnomon — Agent Runtime & Tool Authority.docx](../archive/original-authority-documents/Gnomon%20%E2%80%94%20Agent%20Runtime%20%26%20Tool%20Authority.docx). SHA-256: `b402436cbf7362848d7bf27cbfacf8caa6f69c3518b2e917ac4940c0e23c1d0a`.

| Requirement group | Source section | Classification | Evidence IDs | Gap / priority |
| --- | --- | --- | --- | --- |
| AUTH-05-01 | §1 Purpose | PARTIALLY_IMPLEMENTED | B17,S01,S02 | Existing model boundary is narrow; runtime policy and capability enforcement not generalized. Slice 5. |
| AUTH-05-02 | §2 Constitutional Runtime Principle | PARTIALLY_IMPLEMENTED | B17,S01,S02 | Existing model boundary is narrow; runtime policy and capability enforcement not generalized. Slice 5. |
| AUTH-05-03 | §3 Runtime Authority Hierarchy | PARTIALLY_IMPLEMENTED | B17,S01,S02 | Existing model boundary is narrow; runtime policy and capability enforcement not generalized. Slice 5. |
| AUTH-05-04 | §4 Agent Runtime Model | DESIGNED_NOT_IMPLEMENTED | S04,N05 | No ActionProposal, tool registry, runtime state machine or autonomous runner. Slice 5/9. |
| AUTH-05-05 | §5 Runtime State Machine | DESIGNED_NOT_IMPLEMENTED | S04,N05 | No ActionProposal, tool registry, runtime state machine or autonomous runner. Slice 5/9. |
| AUTH-05-06 | §6 Reasoning Boundary | PARTIALLY_IMPLEMENTED | B17,S01,S02 | Existing model boundary is narrow; runtime policy and capability enforcement not generalized. Slice 5. |
| AUTH-05-07 | §7 Structured Action Proposals | DESIGNED_NOT_IMPLEMENTED | S04,N05 | No ActionProposal, tool registry, runtime state machine or autonomous runner. Slice 5/9. |
| AUTH-05-08 | §8 Tool Registry | DESIGNED_NOT_IMPLEMENTED | S04,N05 | No ActionProposal, tool registry, runtime state machine or autonomous runner. Slice 5/9. |
| AUTH-05-09 | §9 Capability Classes | DESIGNED_NOT_IMPLEMENTED | S04,N05 | No ActionProposal, tool registry, runtime state machine or autonomous runner. Slice 5/9. |
| AUTH-05-10 | §10 No Arbitrary Execution | PARTIALLY_IMPLEMENTED | B17,B22,S04 | Current adapters expose no arbitrary shell/SQL tool; enforcement regression test missing. Slice 5. |
| AUTH-05-11 | §11 Action Validation | DESIGNED_NOT_IMPLEMENTED | S04 | Approved-action validator/executor absent. Slice 5/9. |
| AUTH-05-12 | §12 Validation Is Not Model Reasoning | DESIGNED_NOT_IMPLEMENTED | S04 | Approved-action validator/executor absent. Slice 5/9. |
| AUTH-05-13 | §13 Execution Boundary | DESIGNED_NOT_IMPLEMENTED | S04 | Approved-action validator/executor absent. Slice 5/9. |
| AUTH-05-14 | §14 Tool Results Are Observations | PARTIALLY_IMPLEMENTED | S01,S02,B17 | Data separation exists for source extraction/reporting; generalized tool/agent trust labels absent. Slice 5/6. |
| AUTH-05-15 | §15 Prompt Injection Boundary | PARTIALLY_IMPLEMENTED | S01,S02,B17 | Data separation exists for source extraction/reporting; generalized tool/agent trust labels absent. Slice 5/6. |
| AUTH-05-16 | §16 Tool Output Separation | PARTIALLY_IMPLEMENTED | S01,S02,B17 | Data separation exists for source extraction/reporting; generalized tool/agent trust labels absent. Slice 5/6. |
| AUTH-05-17 | §17 Budgets | PARTIALLY_IMPLEMENTED | B14,B24 | HTTP limits/timeouts and per-task provider reservations implemented; hierarchical budgets and monetary cost accounting remain incomplete. Slice 5/12. |
| AUTH-05-18 | §18 Timeouts | PARTIALLY_IMPLEMENTED | B14,B24 | HTTP limits/timeouts implemented; hierarchical budgets and provider deadline parity incomplete. Slice 5. |
| AUTH-05-19 | §19 Cancellation | DESIGNED_NOT_IMPLEMENTED | B09,N05 | Runtime cancellation and independent stop/continue controls absent. Slice 5/9. |
| AUTH-05-20 | §20 Stop Conditions | DESIGNED_NOT_IMPLEMENTED | B09,N05 | Runtime cancellation and independent stop/continue controls absent. Slice 5/9. |
| AUTH-05-21 | §21 Continue Conditions | DESIGNED_NOT_IMPLEMENTED | B09,N05 | Runtime cancellation and independent stop/continue controls absent. Slice 5/9. |
| AUTH-05-22 | §22 Retries | PARTIALLY_IMPLEMENTED | B12,B24 | Database create retries safe; generalized retry classes and external effect reconciliation absent. Slice 5/6. |
| AUTH-05-23 | §23 Idempotency | PARTIALLY_IMPLEMENTED | B12,B24 | Database create retries safe; generalized retry classes and external effect reconciliation absent. Slice 5/6. |
| AUTH-05-24 | §24 Unknown Outcome | DESIGNED_NOT_IMPLEMENTED | N02 | No explicit UNKNOWN delivery/outcome reconciliation. Slice 6/7. |
| AUTH-05-25 | §25 Memory Access Boundary | PARTIALLY_IMPLEMENTED | B17,B20,M01,V01 | Controlled reports/claim proposals exist; autonomous memory governance and rollback absent. Slice 2/3. |
| AUTH-05-26 | §26 Memory Retrieval Is Not Truth | PARTIALLY_IMPLEMENTED | B17,B20,M01,V01 | Controlled reports/claim proposals exist; autonomous memory governance and rollback absent. Slice 2/3. |
| AUTH-05-27 | §27 Memory Write Limits | PARTIALLY_IMPLEMENTED | B17,B20,M01,V01 | Controlled reports/claim proposals exist; autonomous memory governance and rollback absent. Slice 2/3. |
| AUTH-05-28 | §28 External Agent Communication | DESIGNED_NOT_IMPLEMENTED | N01,N02 | Agent request/observation boundary absent. Slice 6. |
| AUTH-05-29 | §29 External Agents Remain Untrusted | DESIGNED_NOT_IMPLEMENTED | N01,N02 | Agent request/observation boundary absent. Slice 6. |
| AUTH-05-30 | §30 User Authority | PARTIALLY_IMPLEMENTED | B06,B22,B25,S02 | Local operator controls and provider separation exist; explicit security/degraded runtime incomplete. Slice 5. |
| AUTH-05-31 | §31 Model Provider Independence | PARTIALLY_IMPLEMENTED | B06,B22,B25,S02 | Local operator controls and provider separation exist; explicit security/degraded runtime incomplete. Slice 5. |
| AUTH-05-32 | §32 Local and Degraded Operation | PARTIALLY_IMPLEMENTED | B06,B22,B25,S02 | Local operator controls and provider separation exist; explicit security/degraded runtime incomplete. Slice 5. |
| AUTH-05-33 | §33 Fail-Closed Principle | PARTIALLY_IMPLEMENTED | B06,B22,B25,S02 | Local operator controls and provider separation exist; explicit security/degraded runtime incomplete. Slice 5. |
| AUTH-05-34 | §34 Failure Isolation | PARTIALLY_IMPLEMENTED | B06,B22,B25,S02 | Local operator controls and provider separation exist; explicit security/degraded runtime incomplete. Slice 5. |
| AUTH-05-35 | §35 Transactional Commit Boundary | PARTIALLY_IMPLEMENTED | B17,A01,A04,S04 | Current atomic writes/structured summaries exist; runtime audit and complete security checks absent. Slice 4/5. |
| AUTH-05-36 | §36 Audit Requirements | PARTIALLY_IMPLEMENTED | B17,A01,A04,S04 | Current atomic writes/structured summaries exist; runtime audit and complete security checks absent. Slice 4/5. |
| AUTH-05-37 | §37 Observability | PARTIALLY_IMPLEMENTED | B17,A01,A04,S04 | Current atomic writes/structured summaries exist; runtime audit and complete security checks absent. Slice 4/5. |
| AUTH-05-38 | §38 No Chain-of-Thought Dependency | PARTIALLY_IMPLEMENTED | B17,A01,A04,S04 | Current atomic writes/structured summaries exist; runtime audit and complete security checks absent. Slice 4/5. |
| AUTH-05-39 | §39 Runtime Security Boundary | PARTIALLY_IMPLEMENTED | B17,A01,A04,S04 | Current atomic writes/structured summaries exist; runtime audit and complete security checks absent. Slice 4/5. |
| AUTH-05-40 | §40 Research Scope | DESIGNED_NOT_IMPLEMENTED | S04,N05 | No complete RuntimeContext with scope/cycle/budget/communication policy. Slice 5/9. |
| AUTH-05-41 | §41 Action Selection | PARTIALLY_IMPLEMENTED | B07 | Gap priorities exist; cost/information gain and no-activity-as-progress runtime tests absent. Slice 9. |
| AUTH-05-42 | §42 No Activity-as-Progress | PARTIALLY_IMPLEMENTED | B07 | Gap priorities exist; cost/information gain and no-activity-as-progress runtime tests absent. Slice 9. |
| AUTH-05-43 | §43 Tool Composition | DESIGNED_NOT_IMPLEMENTED | S04,N05 | No governed composition, capability availability, runtime recovery or maximum autonomous envelope. Slice 5/9. |
| AUTH-05-44 | §44 Tool-to-Tool Trust | DESIGNED_NOT_IMPLEMENTED | S04,N05 | No governed composition, capability availability, runtime recovery or maximum autonomous envelope. Slice 5/9. |
| AUTH-05-45 | §45 Dynamic Tool Availability | DESIGNED_NOT_IMPLEMENTED | S04,N05 | No governed composition, capability availability, runtime recovery or maximum autonomous envelope. Slice 5/9. |
| AUTH-05-46 | §46 Recovery | DESIGNED_NOT_IMPLEMENTED | S04,N05 | No governed composition, capability availability, runtime recovery or maximum autonomous envelope. Slice 5/9. |
| AUTH-05-47 | §47 Autonomous Execution Limits | DESIGNED_NOT_IMPLEMENTED | S04,N05 | No governed composition, capability availability, runtime recovery or maximum autonomous envelope. Slice 5/9. |
| AUTH-05-48 | §48 Human Intervention | DESIGNED_NOT_IMPLEMENTED | S04,N05 | No governed composition, capability availability, runtime recovery or maximum autonomous envelope. Slice 5/9. |
| AUTH-05-49 | §49 Runtime and Research Lifecycle | PARTIALLY_IMPLEMENTED | B06,B09 | New cycles respect active task state; autonomous action boundary/cancellation absent. Slice 5/9. |
| AUTH-05-50 | §50 Relationship to Existing Gnomon Implementation | PARTIALLY_IMPLEMENTED | B07,N05 | Existing deterministic services are the foundation; conceptual runtime is not implemented. |
| AUTH-05-51 | §51 Reference Runtime Interfaces | DESIGNED_NOT_IMPLEMENTED | S04,N05 | Reference runtime/model action interfaces and complete runtime contract absent. Slice 5/9. |
| AUTH-05-52 | §52 Model Adapter Contract | DESIGNED_NOT_IMPLEMENTED | S04,N05 | Reference runtime/model action interfaces and complete runtime contract absent. Slice 5/9. |
| AUTH-05-53 | §53 Runtime Contract | DESIGNED_NOT_IMPLEMENTED | S04,N05 | Reference runtime/model action interfaces and complete runtime contract absent. Slice 5/9. |
| AUTH-05-54 | §54 Mandatory Runtime Invariants | PARTIALLY_IMPLEMENTED | B14,B17,S01,S04 | Some narrow invariant tests pass; registry/replay/rollback/agent/cancellation conformance tests absent. Slice 3/5/7. |
| AUTH-05-55 | §55 Conformance Tests | PARTIALLY_IMPLEMENTED | B14,B17,S01,S04 | Some narrow invariant tests pass; registry/replay/rollback/agent/cancellation conformance tests absent. Slice 3/5/7. |
| AUTH-05-56 | §56 Security-Critical Implementation Rule | PARTIALLY_IMPLEMENTED | B14,B17,B22 | No arbitrary model execution in current paths; automated architectural regression coverage absent. Slice 5. |
| AUTH-05-57 | §57 Reference Safe Execution Pattern | DESIGNED_NOT_IMPLEMENTED | S04,N05 | Complete safe execution pattern remains designed, not executable. Slice 5/9. |
| AUTH-05-58 | §58 Design Consequence: Gnomon Is an Agent, Not an Unrestricted Actor | DESIGNED_NOT_IMPLEMENTED | S04,N05 | Complete safe execution pattern remains designed, not executable. Slice 5/9. |
| AUTH-05-59 | §59 Relationship to Other Authority Documents | DESIGNED_NOT_IMPLEMENTED | S04,N05 | Complete safe execution pattern remains designed, not executable. Slice 5/9. |
| AUTH-05-60 | §60 Canonical Runtime Axioms | DESIGNED_NOT_IMPLEMENTED | S04,N05 | Complete safe execution pattern remains designed, not executable. Slice 5/9. |

### Document 06 — Research Methodology Authority

Source: [Gnomon — Research Methodology Authority.docx](../archive/original-authority-documents/Gnomon%20%E2%80%94%20Research%20Methodology%20Authority.docx). SHA-256: `6419698a7e4019583706d700ca1b02b216d8cd1fce6916c8afc7ce156f3ad0a9`.

| Requirement group | Source section | Classification | Evidence IDs | Gap / priority |
| --- | --- | --- | --- | --- |
| AUTH-06-01 | §1 Purpose | PARTIALLY_IMPLEMENTED | B04,B07 | Explicit objectives/hypotheses/questions and persisted planning exist; autonomous decomposition and full scope absent. Slice 9. |
| AUTH-06-02 | §2 Research Is an Evidence-Gathering Process | PARTIALLY_IMPLEMENTED | B04,B07 | Explicit objectives/hypotheses/questions and persisted planning exist; autonomous decomposition and full scope absent. Slice 9. |
| AUTH-06-03 | §3 Research Objective | PARTIALLY_IMPLEMENTED | B04,B07 | Explicit objectives/hypotheses/questions and persisted planning exist; autonomous decomposition and full scope absent. Slice 9. |
| AUTH-06-04 | §4 Research Question Decomposition | PARTIALLY_IMPLEMENTED | B04,B07 | Explicit objectives/hypotheses/questions and persisted planning exist; autonomous decomposition and full scope absent. Slice 9. |
| AUTH-06-05 | §5 Question Type | DESIGNED_NOT_IMPLEMENTED | B21,N05 | No question-type strategy, search service or source-independence evaluation. Slice 9. |
| AUTH-06-06 | §6 Initial Hypothesis Generation | PARTIALLY_IMPLEMENTED | B04,B07 | Explicit objectives/hypotheses/questions and persisted planning exist; autonomous decomposition and full scope absent. Slice 9. |
| AUTH-06-07 | §7 Hypothesis Diversity | PARTIALLY_IMPLEMENTED | B04,B07 | Explicit objectives/hypotheses/questions and persisted planning exist; autonomous decomposition and full scope absent. Slice 9. |
| AUTH-06-08 | §8 Research Planning | PARTIALLY_IMPLEMENTED | B04,B07 | Explicit objectives/hypotheses/questions and persisted planning exist; autonomous decomposition and full scope absent. Slice 9. |
| AUTH-06-09 | §9 Source Strategy | DESIGNED_NOT_IMPLEMENTED | B21,N05 | No question-type strategy, search service or source-independence evaluation. Slice 9. |
| AUTH-06-10 | §10 Source Diversity | DESIGNED_NOT_IMPLEMENTED | B21,N05 | No question-type strategy, search service or source-independence evaluation. Slice 9. |
| AUTH-06-11 | §11 Source Independence | DESIGNED_NOT_IMPLEMENTED | B21,N05 | No question-type strategy, search service or source-independence evaluation. Slice 9. |
| AUTH-06-12 | §12 Search Strategy | DESIGNED_NOT_IMPLEMENTED | B21,N05 | No question-type strategy, search service or source-independence evaluation. Slice 9. |
| AUTH-06-13 | §13 Search Failure | PARTIALLY_IMPLEMENTED | B10,B14,B17,B23 | Controlled retrieval and conservative extraction exist; primary verification and context/entailment tests incomplete. Slice 5/9. |
| AUTH-06-14 | §14 Evidence Acquisition | PARTIALLY_IMPLEMENTED | B10,B14,B17,B23 | Controlled retrieval and conservative extraction exist; primary verification and context/entailment tests incomplete. Slice 5/9. |
| AUTH-06-15 | §15 Source Verification | PARTIALLY_IMPLEMENTED | B10,B14,B17,B23 | Controlled retrieval and conservative extraction exist; primary verification and context/entailment tests incomplete. Slice 5/9. |
| AUTH-06-16 | §16 Claim Extraction | PARTIALLY_IMPLEMENTED | B10,B14,B17,B23 | Controlled retrieval and conservative extraction exist; primary verification and context/entailment tests incomplete. Slice 5/9. |
| AUTH-06-17 | §17 Claim Scope | PARTIALLY_IMPLEMENTED | B10,B14,B17,B23 | Controlled retrieval and conservative extraction exist; primary verification and context/entailment tests incomplete. Slice 5/9. |
| AUTH-06-18 | §18 Causal Claims | DESIGNED_NOT_IMPLEMENTED | B18 | No causal/counterfactual type or validator. Release epistemic gap; advanced synthesis deferred. |
| AUTH-06-19 | §19 Counterfactual Reasoning | DESIGNED_NOT_IMPLEMENTED | B18 | No causal/counterfactual type or validator. Release epistemic gap; advanced synthesis deferred. |
| AUTH-06-20 | §20 Adversarial Research | DESIGNED_NOT_IMPLEMENTED | N05 | Existing gap prioritization does not execute falsification/replication research. Slice 9. |
| AUTH-06-21 | §21 Falsification-Oriented Search | DESIGNED_NOT_IMPLEMENTED | N05 | Existing gap prioritization does not execute falsification/replication research. Slice 9. |
| AUTH-06-22 | §22 Replication | DESIGNED_NOT_IMPLEMENTED | N05 | Existing gap prioritization does not execute falsification/replication research. Slice 9. |
| AUTH-06-23 | §23 Contradiction Handling | PARTIALLY_IMPLEMENTED | B07,B16 | Contradictory evidence survives; quality/context-based reconciliation absent. Slice 9. |
| AUTH-06-24 | §24 Apparent Contradictions | DESIGNED_NOT_IMPLEMENTED | B18 | No contextual contradiction evaluation. Slice 9. |
| AUTH-06-25 | §25 Evidence Gaps | PARTIALLY_IMPLEMENTED | B07 | Core persisted gaps feed planning; population/independence/causal gaps not modeled. Slice 9. |
| AUTH-06-26 | §26 Agent-Assisted Research | DESIGNED_NOT_IMPLEMENTED | N01,N02 | No agent-assisted research or consensus/independence evaluation. Slice 6/9. |
| AUTH-06-27 | §27 Agent Diversity | DESIGNED_NOT_IMPLEMENTED | N01,N02 | No agent-assisted research or consensus/independence evaluation. Slice 6/9. |
| AUTH-06-28 | §28 Agent Consensus | DESIGNED_NOT_IMPLEMENTED | N01,N02 | No agent-assisted research or consensus/independence evaluation. Slice 6/9. |
| AUTH-06-29 | §29 Evidence Quality Versus Source Reputation | PARTIALLY_IMPLEMENTED | B10,B16,B19 | Reliability/claim/assessment scores distinct; factors and multidimensional uncertainty absent. Slice 9. |
| AUTH-06-30 | §30 Confidence | PARTIALLY_IMPLEMENTED | B10,B16,B19 | Reliability/claim/assessment scores distinct; factors and multidimensional uncertainty absent. Slice 9. |
| AUTH-06-31 | §31 Uncertainty Decomposition | DESIGNED_NOT_IMPLEMENTED | B18 | No structured uncertainty/context/negative-evidence/forecast reasoning contracts. Release epistemic gap. |
| AUTH-06-32 | §32 Population and Context Boundaries | DESIGNED_NOT_IMPLEMENTED | B18 | No structured uncertainty/context/negative-evidence/forecast reasoning contracts. Release epistemic gap. |
| AUTH-06-33 | §33 Negative Evidence | DESIGNED_NOT_IMPLEMENTED | B18 | No structured uncertainty/context/negative-evidence/forecast reasoning contracts. Release epistemic gap. |
| AUTH-06-34 | §34 Temporal Reasoning | DESIGNED_NOT_IMPLEMENTED | B18 | No structured uncertainty/context/negative-evidence/forecast reasoning contracts. Release epistemic gap. |
| AUTH-06-35 | §35 Forecasts | DESIGNED_NOT_IMPLEMENTED | B18 | No structured uncertainty/context/negative-evidence/forecast reasoning contracts. Release epistemic gap. |
| AUTH-06-36 | §36 Source and Agent Reliability Learning | DEFERRED | D01 | Complex reputation/learning deferred; basic reliability observations belong in Slice 6. |
| AUTH-06-37 | §37 Research Cycles | PARTIALLY_IMPLEMENTED | B07,B08 | Objectives/outcomes persisted; full action/budget/evaluation cycle absent. Slice 9. |
| AUTH-06-38 | §38 Cycle Priority | IMPLEMENTED | B07 | Deterministic planner implements the reference priority ordering and persists planning basis. |
| AUTH-06-39 | §39 Information Gain | PARTIALLY_IMPLEMENTED | B07,B12 | Bounded gaps and exact deduplication exist; expected value/source independence absent. Slice 9. |
| AUTH-06-40 | §40 Avoiding Redundant Research | PARTIALLY_IMPLEMENTED | B07,B12 | Bounded gaps and exact deduplication exist; expected value/source independence absent. Slice 9. |
| AUTH-06-41 | §41 Evidence Saturation | DEFERRED | D01 | Automated evidence-saturation/stopping reasoning explicitly deferred. |
| AUTH-06-42 | §42 Stopping Criteria | PARTIALLY_IMPLEMENTED | B04,B06,B08 | Explicit manual lifecycle exists; separate reason taxonomy and stopping evaluation absent. Slice 9. |
| AUTH-06-43 | §43 Premature Stopping | PARTIALLY_IMPLEMENTED | B04,B06,B08 | Explicit manual lifecycle exists; separate reason taxonomy and stopping evaluation absent. Slice 9. |
| AUTH-06-44 | §44 Conclusion Formation | DEFERRED | D01 | Sophisticated conclusion synthesis deferred; future traceability/uncertainty invariants still apply. |
| AUTH-06-45 | §45 Conclusion Strength | DEFERRED | D01 | Sophisticated conclusion synthesis deferred; future traceability/uncertainty invariants still apply. |
| AUTH-06-46 | §46 Synthesis | DEFERRED | D01 | Sophisticated conclusion synthesis deferred; future traceability/uncertainty invariants still apply. |
| AUTH-06-47 | §47 Report Generation | PARTIALLY_IMPLEMENTED | B20,B23 | Reports derive from persisted state; provider prose support not fully validated. Slice 5/9. |
| AUTH-06-48 | §48 Research State Versus Narrative | IMPLEMENTED | B20,B22 | Reports/drafts are derived and do not replace canonical evidence. |
| AUTH-06-49 | §49 Reproducibility | PARTIALLY_IMPLEMENTED | B10,B20,V01 | Current records reproducible by snapshot; original bytes/actions/history incomplete. Slice 3/9. |
| AUTH-06-50 | §50 Historical Epistemic State | CONFLICTING | B19,A06 | Previous assessment state is lost on replacement. Slice 2/3. |
| AUTH-06-51 | §51 Research Updates | DESIGNED_NOT_IMPLEMENTED | V06,N05 | No automated dependency-aware reassessment. Slice 3/9. |
| AUTH-06-52 | §52 Dependency-Aware Reassessment | DESIGNED_NOT_IMPLEMENTED | V06,N05 | No automated dependency-aware reassessment. Slice 3/9. |
| AUTH-06-53 | §53 Research Integrity | PARTIALLY_IMPLEMENTED | B16,B20,B23 | Current types preserve some distinctions; complete inference/synthesis semantics and tests absent. Slice 9. |
| AUTH-06-54 | §54 Model Agreement | PARTIALLY_IMPLEMENTED | B16,B20,B23 | Current types preserve some distinctions; complete inference/synthesis semantics and tests absent. Slice 9. |
| AUTH-06-55 | §55 Self-Critique | DESIGNED_NOT_IMPLEMENTED | N05 | No self-critique executor or full methodological bias controls. Slice 9. |
| AUTH-06-56 | §56 Research Bias Controls | DESIGNED_NOT_IMPLEMENTED | N05 | No self-critique executor or full methodological bias controls. Slice 9. |
| AUTH-06-57 | §57 Research Under Uncertainty | PARTIALLY_IMPLEMENTED | B08,B20,B23 | Unresolved states/limitations visible; structured stopping/resource limitation semantics incomplete. Slice 9. |
| AUTH-06-58 | §58 Research Under Resource Constraints | PARTIALLY_IMPLEMENTED | B08,B20,B23 | Unresolved states/limitations visible; structured stopping/resource limitation semantics incomplete. Slice 9. |
| AUTH-06-59 | §59 Methodological Transparency | PARTIALLY_IMPLEMENTED | B08,B20,B23 | Unresolved states/limitations visible; structured stopping/resource limitation semantics incomplete. Slice 9. |
| AUTH-06-60 | §60 Prohibited Methodological Shortcuts | CONFLICTING | A06,B19 | Prohibited silent historical assessment rewrite occurs today. Other shortcuts need explicit tests. Slice 2/3/9. |
| AUTH-06-61 | §61 Relationship to Agent Runtime | PARTIALLY_IMPLEMENTED | B17,M01,S04 | Service boundaries exist; runtime/memory proposal integration incomplete. Slice 2/5/9. |
| AUTH-06-62 | §62 Relationship to Epistemic Authority | PARTIALLY_IMPLEMENTED | B17,M01,S04 | Service boundaries exist; runtime/memory proposal integration incomplete. Slice 2/5/9. |
| AUTH-06-63 | §63 Relationship to Memory Authority | PARTIALLY_IMPLEMENTED | B17,M01,S04 | Service boundaries exist; runtime/memory proposal integration incomplete. Slice 2/5/9. |
| AUTH-06-64 | §64 Mandatory Methodological Invariants | CONFLICTING | A06,B07,B20 | Q13/history test fails by design of replacement; other invariants have partial or missing coverage. Slice 2/3/9. |
| AUTH-06-65 | §65 Conformance Tests | CONFLICTING | A06,B07,B20 | Q13/history test fails by design of replacement; other invariants have partial or missing coverage. Slice 2/3/9. |
| AUTH-06-66 | §66 Canonical Research Axioms | PARTIALLY_IMPLEMENTED | B07,B20,N05 | Methodology axioms partially reflected by planner/reporting; active adversarial research absent. Slice 9. |
| AUTH-06-67 | §67 Final Methodological Principle | PARTIALLY_IMPLEMENTED | B07,B20,N05 | Methodology axioms partially reflected by planner/reporting; active adversarial research absent. Slice 9. |

### Document 07 — External Agent Network Authority

Source: [Gnomon — External Agent Network Authority.docx](../archive/original-authority-documents/Gnomon%20%E2%80%94%20External%20Agent%20Network%20Authority.docx). SHA-256: `6b2d4878efd16212e47a28d9ebecdd2d8b0e4b52b33accc69c33f47c0c415b31`.

| Requirement group | Source section | Classification | Evidence IDs | Gap / priority |
| --- | --- | --- | --- | --- |
| AUTH-07-01 | §1 Purpose | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-02 | §2 Constitutional Network Principle | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-03 | §3 Network Architecture | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-04 | §4 Platform Independence | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-05 | §5 Agent Identity | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-06 | §6 Unknown Agents | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-07 | §7 Agent Identity Persistence | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-08 | §8 Agent Observation | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-09 | §9 Agent Claims | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-10 | §10 Agent Recommendations | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-11 | §11 Agent-Sourced Evidence Class | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-12 | §12 Agent Consensus | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-13 | §13 Agent Independence | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-14 | §14 Reputation | DEFERRED | D01,N01 | Complex reputation/ranking deferred; basic attributable reliability observations remain Slice 6. |
| AUTH-07-15 | §15 Reliability Dimensions | DEFERRED | D01,N01 | Complex reputation/ranking deferred; basic attributable reliability observations remain Slice 6. |
| AUTH-07-16 | §16 Reliability Must Not Become Authority | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-17 | §17 Agent Communication Request | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-18 | §18 Agent Questions | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-19 | §19 Avoiding Leading Questions | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-20 | §20 Agent Responses | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-21 | §21 Agent Prompt Injection | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-22 | §22 Agent Capability Claims | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-23 | §23 Agent Authentication | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-24 | §24 Message Integrity | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-25 | §25 Replay Protection | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-26 | §26 Rate Limits | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-27 | §27 Network Cost | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-28 | §28 Agent Discovery | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-29 | §29 Discovery Ranking | DEFERRED | D01,N01 | Complex reputation/ranking deferred; basic attributable reliability observations remain Slice 6. |
| AUTH-07-30 | §30 Agent Selection Diversity | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-31 | §31 Agent Networks as Epistemic Sensors | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-32 | §32 Agent Communication and Privacy | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-33 | §33 No Credential Disclosure | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-34 | §34 No Policy Negotiation | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-35 | §35 Cross-Agent Collaboration | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-36 | §36 Agent-to-Agent Evidence Graph | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-37 | §37 Agent-Originated Source Discovery | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-38 | §38 Agent Criticism | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-39 | §39 Agent Red-Team Mode | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-40 | §40 Malicious Agents | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-41 | §41 Coordinated Manipulation | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-42 | §42 Reputation Gaming | DEFERRED | D01,N01 | Complex reputation/ranking deferred; basic attributable reliability observations remain Slice 6. |
| AUTH-07-43 | §43 Agent Isolation | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-44 | §44 Network Degraded States | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-45 | §45 Network Failure | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-46 | §46 Agent Message Retention | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-47 | §47 Agent Memory | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-48 | §48 Time-Dependent Reputation | DEFERRED | D01,N01 | Complex reputation/ranking deferred; basic attributable reliability observations remain Slice 6. |
| AUTH-07-49 | §49 Reputation and Rollback | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-50 | §50 Provenance-Aware Network Rollback | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-51 | §51 Agent-Sourced Memory | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-52 | §52 External Agent → Model → Memory | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-53 | §53 Agent Message as Instruction | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-54 | §54 Agent Network and User Intent | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-55 | §55 Agent Network and Research Scope | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-56 | §56 External Communication as a Side Effect | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-57 | §57 Message Safety | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-58 | §58 Agent Network as Replaceable Infrastructure | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-59 | §59 Security Boundary Summary | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-60 | §60 Mandatory Network Invariants | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-61 | §61 Conformance Tests | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-62 | §62 Canonical Agent-Network Model | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-63 | §63 Canonical Agent Axioms | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
| AUTH-07-64 | §64 Final Network Principle | DESIGNED_NOT_IMPLEMENTED | N01,N02,N03,N04,N05 | No executable agent-network domain/adapter/policy pipeline or tests. Slice 6/7/9; Moltbook only after fake gate. |
