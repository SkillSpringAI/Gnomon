# Gnomon known gaps and implementation priorities

Baseline: `2d786916f707f9d6eda89c4003d73942da4dc2d2`, 2026-09-13.
Findings below are code-review observations unless a passing test is explicitly
identified in the [matrix](authority-matrix.md). They are not demonstrated exploits.

## Authority input needed

All ten documents were supplied during this review. The matrix covers every numbered
section of Documents 01–07, including subordinate clauses, with source hashes.
Document 08 was replaced with `Security, Audit & Recovery Authority.docx` and reviewed
through all 50 numbered sections on 2026-09-13. The source truncation is resolved.
Documents 08–10 provide supplementary security/persistence/release requirements;
their review does not imply full behavioral conformance or individual section mapping.

## Governance and recovery — Slices 2/3

- Slice 2 provides MemoryChangeProposal, deterministic validation, an append-only accepted-change journal, versions, actor context, and lifecycle operations for claims and hypothesis assessments. Slice 3 adds optimistic versions and 48-hour governed reversal with immutable journal entries; broader dependent-state propagation remains open.
- Assessment updates overwrite summary/status/confidence and delete previous links.
  Prior assessment state cannot be recovered through the application.
- Task status compare-and-set is vulnerable to the conceptual ABA limitation:
  returning to the same status cannot distinguish intervening revisions. Use an
  explicit version for memory rather than reusing expected_status.
- Provenance links are current references, not a historical dependency policy.
  Claim rollback currently blocks when active assessments or cycle dependencies exist;
  propagation and explicit reassessment workflows remain future work.
- Keep sensitive historical state in a governed change journal with appropriate
  access, and keep public audit payloads redacted. Adding raw previous/new text to
  the existing public events payload would contradict its current redaction rule.
- Document 04 §20/23 defines a recovery eligibility window, with eligible classes
  determined by implementation. It does not authorize automatically undoing mutations
  at age 48 hours. The repository roadmap's worker wording must be read accordingly.

The implementation should extend the existing knowledge path. A separate memory
table that leaves assessment/claim writers outside governance would not establish
the user's target authority property. Trusted actor/capability context must be
supplied by application code, never accepted as authoritative from model output.

## Audit — Slice 4

- Task creation, lifecycle, cycle, source, claim, assessment, memory, rollback and
  rejected-memory security attempts now have redacted audit coverage. Source-registry
  registration/enabling and provider-session security operations remain unaudited.
- Core events carry actor/result metadata; governed memory events also carry reason,
  provenance IDs and deterministic state digests. These digests intentionally avoid
  returning raw historical state through the public event API.
- Actor values are application roles rather than authenticated user identities, and
  security events remain task-scoped until a broader identity/audit stream exists.
- The schema permits deletion of audit history through task ON DELETE CASCADE.
  No public task-delete endpoint was found, but database deletion still destroys
  history; preserve this distinction when designing retention protection.
- Existing tests prove atomic rollback on audit failures for source/lifecycle writes,
  not for broader dependent-state recovery or backup/restore paths.

## External boundaries — Slice 5`n`n- Shared boundary guards now validate bounded external text, explicit provider data delimiters, and capability allowlists. HTTP retrieval retains redirect, private-network, content-type, byte, and deadline controls. Prompt-injection resistance is enforced by treating retrieved material as delimited data; provider/tool and agent adapters still need equivalent integration tests.

- Draft limits count successful prior events without atomic reservations. Concurrent
  requests may pass the same budget check; failed provider attempts are not charged
  to that count. Add a reservation/attempt policy and concurrent boundary tests.
- The session-bearer adapter construction does not receive the configured maximum
  output-token value passed to the standard Bedrock adapter. Check adapter parity.
- Bedrock uses connection/read timeouts and retries, but there is no shared total
  deadline equivalent to the HTTP retrieval transport's deadline.
- Draft secret filtering checks only `api_key=`, `api-key=`, `password=`, and
  `secret=`. This is a narrow heuristic, not proof against credential leakage.
  Provider/model audit metadata is string-valued; validate it as trusted metadata.
- Citation validation checks membership in a report, not whether the cited evidence
  supports the generated statement. Preserve draft uncertainty and avoid promoting
  provider prose into accepted knowledge.
- The Bedrock JSON parser can extract an object from surrounding text. Strict
  JSON-only output is therefore a stronger claim than the current implementation.
- Source-domain strings are normalized but not validated with a full domain policy.
  Enabled domains also permit subdomains. Public-IP transport checks remain separate.
- Existing injection coverage demonstrates deterministic planner isolation, not a
  universal external-boundary property. Add malicious provider and later fake-agent
  inputs that attempt tool calls, rule changes, replay and unauthorized mutations.
- Manual evidence/assessment writes are not stopped by paused/concluded task state.
  Define permitted operator behavior and autonomous behavior explicitly.

## Networking and loop integration — Slices 6–9

Agent-related enum values and architecture examples are not an implemented network.
Build neutral domain objects and a bounded fake adapter before Moltbook. Fake modes
must include honest, wrong, confidently wrong, contradictory, duplicate, malicious,
prompt-injection, unresponsive and rate-limited behavior. Verify unchanged policy,
no unauthorized writes, intact provenance and bounded communication for each.

Integrate observations as evidence in the current planner and application services.
Do not introduce a separate agent knowledge store or independent authority path.
Live outbound communication is a separate operational action requiring authorization;
implementing or testing an adapter does not require sending messages to real agents.

## Technical debt and deliberate deferrals

- Identity deduplication relies on all writers taking the application lock; direct
  SQL writers can bypass it. Exact duplicates do not measure independent evidence.
- Snapshot responses include all stored source text without pagination.
- Migrations have no checksum or downgrade support; avoid conflating schema rollback
  with governed memory rollback.
- In-memory task storage is a development implementation without durable audit.
- Raw bytes/object storage, entity canonicalization and cross-task memory retrieval
  remain open. Do not claim reproducibility or Phase 4 completion beyond stored data.
- Keep pgvector, advanced synthesis, long-running AWS infrastructure, distributed
  memory, full multi-user authentication, cryptographic ledgers, automatic stopping
  reasoning, complex reputation and broad UI work deferred as instructed.

## Next action

Use the supplied authority mappings and passing baseline to implement the
proposal/validation boundary first, followed by
versioned persistence, rollback, audit coverage and adversarial boundaries. Update
classifications only after each exit criterion has executable evidence.

## Additional authority findings

- Document 03 §53 and E9, Document 04 §9 and M3/M4, and Document 06 §50 and Q13
  make historical epistemic preservation mandatory. Assessment replacement is a
  concrete authority conflict, not merely a deferred enhancement.
- Document 08's supplied Security State Machine requires explicit NORMAL, DEGRADED,
  ISOLATED, SAFE and RECOVERY states. No such system state machine exists. Local
  deterministic operation during provider loss is only partial support.
- Document 09 §25 requires assessment history; §37–40 covers backups, verification
  and migration safety. Document 10 §86 includes a backup/recovery procedure in
  v0.1 MUST work. No documented backup/restore drill or procedure was found. Add it
  to the release recovery review; transactional tests alone are insufficient.
- Document 10 §57 permits a narrow initial capability set, but §58/68 does not permit
  silent historical rewriting. A feature deferral must not be represented as an
  exception to a mandatory invariant already violated by an existing writer.
- The requirement groups deliberately avoid treating absent agent/runtime features
  as implemented security guarantees. No networking implementation means its boundary
  still needs to be built and tested before it can be enabled.

## Complete Document 08 review

The replacement confirms and extends the security/recovery release gaps:

| Authority | Classification | Existing evidence / required work | Priority |
| --- | --- | --- | --- |
| §24–25, §30 — compromised agents, incident response, provenance remediation | DESIGNED_NOT_IMPLEMENTED | Current provenance links are a foundation; incident classification, containment and dependent reassessment workflows are absent | Slices 3/5/7 and recovery review |
| §26–28 — backup capability, verification, restoration without historical erasure | DESIGNED_NOT_IMPLEMENTED | PostgreSQL persistence exists; no documented backup/restore procedure or tested recovery path was found | Release gate; backup capability and recovery procedure are v0.1 MUST under §42 |
| §29 — attributable, reasoned, conflict-safe rollback | PARTIALLY_IMPLEMENTED | Claims and assessments have append-only versioned changes and tested 48-hour reversal; broader V01–V08 recovery and dependent propagation remain open | Slice 3/recovery review |
| §31–32 — privileged purge and outbound privacy | DESIGNED_NOT_IMPLEMENTED | No ordinary model purge exposed; no governed deletion or outbound disclosure validator | Slices 2/5/6; permanent purge stays deferred |
| §33–36 — degraded operation, explicit failures, resources and replay | PARTIALLY_IMPLEMENTED | B06/B12/B14/B24 provide local controls; security states, general budget reservations and external-effect reconciliation absent | Slices 5/7/9 |
| §37–39 — separate history classes, derived-state recovery and security observability | PARTIALLY_IMPLEMENTED | A01/B20 preserve bounded events and derived reports; security-state observability absent | Slices 3/4/5 |
| §40–44 — deterministic security tests, v0.1 priorities and mandatory invariants | PARTIALLY_IMPLEMENTED | Existing HTTP/provenance/transaction tests cover a subset; capability, isolation and broader recovery tests still required | Slices 3/5/7/10 |
| §45–50 — authority relationships, security/recovery flow and conformance | PARTIALLY_IMPLEMENTED | Existing application boundaries support the model; full validated recovery flow and incident-history preservation are unimplemented | Release gate |

Section 49 permits advanced mechanisms to remain unimplemented only when existing
behavior does not contradict authority and implemented boundaries remain fail-closed.
It does not waive the historical-state conflict already recorded in this baseline.
