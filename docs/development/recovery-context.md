# RecoveryContext — M1.1

Date: 24 September 2026.
Status: domain contract, trusted local snapshot collection and diagnostic persistence
implemented locally. HTTP exposure, recovery reconciliation and restoration remain
unimplemented. The first contract pass below is followed by the persistence boundary.

## Scope

The first M1.1 pass defines immutable evidence for the existing pending recovery-
bootstrap boundary. It does not describe ordinary incident recovery without that
fence. Extending the contract to other recovery entry paths requires an explicit
later design. Security capability policy and the transition graph are unchanged.

`RecoveryContext` in `src/research_agent/domain/recovery.py` is schema version 1.
It contains a non-nil context ID and incident ID, an effective authority basis,
initiating actor attribution, inspection scope, evidence references, required
reconciliation checks, unresolved operations, inventory status and validity times.
Frozen nested models and tuple collections prevent ordinary in-place mutation;
this is not tamper evidence or protection against privileged code.

## Authority binding

The basis identifies singleton security state 1, its non-nil authority epoch,
effective state and positive integer version, and pending bootstrap origin state,
version and timestamp. Pending bootstrap requires effective RECOVERY_REQUIRED and
an origin version older than the current version. Historical raw NORMAL remains
evidence; it does not become current NORMAL.

`validate_recovery_context_basis` rejects a mismatch against an independently
supplied current basis, including changed epoch, version, origin or cleared fence.
It also revalidates the structure of supplied models. This is a pure comparison:
there is no database read, lock, authorization, reference-existence check or repair.
Future consumers must obtain the basis from trusted runtime state and recheck it
under their transaction's authority lock. Caller-supplied matching values are not
proof that persisted authority is current.

## Attribution, scope and evidence

Initiating actor uses the existing SecurityActor vocabulary and a nonblank identity
of at most 100 characters. It is attribution, not authentication. A syntactically
valid context can be fabricated; a future trusted loader and separate
OperatorAuthorization are required before any recovery action.

Permitted scope is an inspection ceiling: inspect authority, inspect history, and
inventory operations. It grants none of those capabilities. Restoration, epoch
replacement and arbitrary scope strings are excluded from this first contract.

Evidence references identify security transitions, research events, memory changes,
source relationship changes or stopping decision changes by kind and non-nil UUID.
Unresolved operations identify provider or cycle attempts and retain an unknown or
unresolved outcome. No raw evidence payload, credential or free-form explanation is
part of these references. Reference existence, task ownership and semantic integrity
must be checked by a later collector; the domain model cannot establish them.

Each reference collection is capped at 100 entries. Duplicate kind/ID pairs are
rejected. A future collector must explicitly report partial inventory if discovery
exceeds the bound, retain unresolved work durably and never silently truncate while
claiming completeness. This pass defines the representation, not that collector.

Inventory is explicitly not_collected, partial or complete. Not-collected inventory
must be empty. Complete means enumeration is complete, not that outcomes are known
or reconciliation passed. All five checks remain required: authority lineage,
history integrity, evidence integrity, operation outcomes and configuration integrity.
The context contains no checked-off, verified or restoration-ready flag.

## Validity and lifecycle

All timestamps require a timezone. Creation cannot predate bootstrap, and expiry
must be strictly after creation. At validation, creation is inclusive and expiry is
exclusive. The clock must be trusted and timezone-aware. This contract requires a
finite expiry but sets no operational TTL; issuance policy belongs to the trusted
context service. Expired contexts remain historical evidence, never fresh authority.

An updated snapshot should receive a new context ID while retaining the incident
identity. Persistence will need to enforce that identity and immutable history;
there is no update, renewal, deletion or context-registration service in this pass.

## Contract-pass verification

Focused negative contracts cover stale epoch/version/origin/fence, malformed
bootstrap state, nil IDs, invalid scopes and actors, attempted authority fields,
collection bounds and duplicate references, immutable round trips, aware clocks,
expiry boundaries and copied-model revalidation. An unchanged runtime capability
guard still denies mutation and provider dispatch after a context passes validation,
even when its inventory is complete.

Local evidence for this pass: 35 focused RecoveryContext cases passed; the combined
contract, security-state, capability and PostgreSQL bootstrap selection passed 308
tests. Ruff, strict mypy (88 source files), conformance traceability and whitespace
checks passed. This pass is uncommitted and has no hosted verification claim.

## Trusted collection and persistence pass

`RecoveryContextService` accepts a database engine and owns each transaction. It is
an internal local diagnostic entry point with fixed `local_operator` attribution
and `local-recovery-diagnostics` identity. There is no HTTP/model-facing endpoint,
no caller-supplied evidence or actor, and no authenticated operator claim. Recording
this diagnostic artifact does not permit ordinary memory mutation during bootstrap.
READ_AUDIT is checked for capture, historical read and exact replay.

Capture commands contain a caller-retained context ID, expected authority basis and
finite expiry. The service loads the singleton itself and requires pending bootstrap
for a new context. A stale expected basis or past expiry is rejected before writing.
The incident UUID is deterministically derived from epoch and normalized bootstrap
origin state/version/time; refreshed contexts in the same bootstrap share it.

Each transaction uses PostgreSQL REPEATABLE READ and a security-row SHARE lock.
Inventory queries see one database snapshot, and supported authority writers cannot
change its basis before commit. No task locks are acquired, avoiding reversal of the
existing task-then-security lock order. A concurrent insert for the same context ID
may conflict; rollback is complete and an explicit identical retry returns the one
historical record. The service does not retry automatically or renew an old context.

Each of the five evidence streams is queried in UUID order with LIMIT 101. Provider
attempts other than SUCCEEDED/FAILED and cycle attempts other than
COMPLETED/FAILED/BLOCKED/INTERRUPTED are retained conservatively as unknown. Unknown
or unexpected nonterminal status values are not interpreted as success. Each attempt
stream also uses LIMIT 101. Results retain at most 100 evidence and 100 operation
references and report partial if either combined limit overflows. These are bounded
returned rows, not a guarantee of bounded physical database scanning.

Complete means enumeration of these supported streams at the transaction snapshot.
It does not cover every possible incident artifact, prove reference integrity or
resolve outcomes. Later reconciliation must enumerate original records independently;
this pass provides no continuation cursor for omitted references. All omitted source
rows remain durable and unchanged. An authority-fresh context is still a historical
inventory: evidence and attempt outcomes can change without changing authority version.

Migration 033 adds `recovery_contexts` and `recovery_context_audit`. Context, canonical
command and one redacted audit record commit together. Audit failure rolls back the
context insert. Application methods only append and read; database owners can still
rewrite rows. This is not cryptographic tamper resistance or database role separation.
No authority row, bootstrap fence, provider attempt or cycle attempt is modified.

Reads validate the domain payload against stored identity/epoch/version/time columns,
the retained command and matching audit. Malformed history fails without repair.
Historical reads and exact authorized retries can return stale or expired records;
`read(..., require_current=True)` separately rejects them. That check only establishes
authority-basis/time consistency inside its transaction and grants no downstream
permission after the transaction ends.

## Remaining milestone work

Review and commit the M1.1 implementation, then verify that exact SHA in hosted CI
before treating it as the canonical baseline. OperatorAuthorization (M1.2), epoch-bound
execution authorization (M1.3), reconciliation (M1.4), restoration (M1.5) and epoch
replacement (M1.6) remain open. This service neither clears the bootstrap fence nor
provides a path back to NORMAL. Milestone 1 remains open.
