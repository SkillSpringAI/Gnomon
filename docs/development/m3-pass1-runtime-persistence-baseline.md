# M3 Pass 1 — Runtime and persistence baseline

Date: 28 September 2026. Baseline: clean local `main` at
`e70b337bc5a8dddc80e819cc92a8aa33aa9e19d6`, one commit ahead of
`origin/main`. This is characterization only; no M3 production change is made.
The C3 closure and its characterization test are included in this HEAD.

## A. Database authority and entry points

`persistence/database.py` constructs one process-global engine and SessionFactory
from `Settings.database_url`; the default and `.env`/`DATABASE_URL` use the same
setting for every command. Docker Compose and Quality use `POSTGRES_USER=research_agent`.
That bootstrap user is the development/test database owner and PostgreSQL
superuser; current credential sharing is deployment convenience, not a demonstrated
requirement for normal application writes. No runtime/migration/backup/restore DSN
separation or SQL grants appear in the repository.

| Entry | Engine/session, work and required authority | DDL/owner need |
|---|---|---|
| HTTP API and startup | `SessionFactory`; reads and DML for task, cycle, evidence, memory, source/trust, stopping, security, provider-attempt, recovery and audit tables. Startup locks singleton; `RECOVERY` mode may update it. Task/authority row locks and selected REPEATABLE READ transactions. | No runtime DDL or superuser operation found. Runtime needs SELECT/INSERT/UPDATE on used tables and DELETE on claim-source and assessment-evidence links. |
| Source/agent/provider cycle workers | They receive the HTTP/runtime Session and use the same credential. External retrieval/provider dispatch happens around durable attempt and progress commits; no separate worker engine. | No DDL. |
| `python -m research_agent.cli migrate` | Global engine; advisory transaction lock, migration-ledger create/alter/read/write, ordered schema SQL, per-migration commits. | Schema CREATE and ownership/ALTER authority on existing objects. Fresh migration 001 installs trusted `pgcrypto`, requiring CREATE on the database; no production migration requires superuser. |
| `scripts/backup_postgres.py` | New engine from the same setting; read-only inspection under REPEATABLE READ, `pg_dump` custom archive, final singleton SHARE lock before publication. | No DDL; `pg_dump` needs schema visibility and SELECT on dumped tables. No owner/superuser requirement shown. |
| `scripts/restore_postgres.py` | Global engine plus `pg_restore` credentials derived from its URL; preflight, metadata/row reads, singleton UPDATE, data-only INSERT/COPY, migrations, publication, recovery context INSERT. | The current complete workflow **calls `run_migrations`**, so the restore operator currently also needs migration/owner capability. Database creation in tests is separate test-admin convenience. |
| Recovery/context/authorization/restoration | API or trusted service receives an engine; locked singleton and recovery evidence reads, context/authorization/audit INSERT, restoration singleton UPDATE. | No DDL or superuser need. |
| Verification scripts | `verify_prototype.py`/`verify_wheel.py` create/drop disposable databases and migrate them; smoke uses the global engine. | Admin privileges are test harness requirements, not normal deployment requirements. |

The restore and migration commands can use different credentials only after the
complete restore flow is accounted for. A read-only backup role is plausible but
not required to establish the first runtime/owner separation.

## B. Grouped governed-mutation inventory

All listed database writes commit at `Session.commit()` or the owning `session.begin()`/
`engine.begin()` exit. Task-scoped writers normally lock the task row; authority
writers lock the singleton, often with REPEATABLE READ. Staged audit joins the
governed transaction except where explicitly noted below. A generated ID is not
a reliable retry handle unless the caller received or retained it before failure.
Repository, evidence, memory, provider-budget, source-dependence, stopping and
security-transition Sessions use the database's ordinary isolation setting
(READ COMMITTED in the supported PostgreSQL deployment); context, authorization,
reconciliation, restoration and epoch-replacement services explicitly select
REPEATABLE READ. The precise row-lock protocol belongs to each service and is not
made uniform by sharing a SessionFactory.

| Pattern and owner | Durable identity, audit and duplicate behavior | Unknown-commit recovery |
|---|---|---|
| `SqlAlchemyResearchTaskRepository.save/edit`; `ResearchService` lifecycle/planning/cycle writes | Task UUID and revision; task row FOR UPDATE on edit; cycle `(task, number)` unique. Audit staged in same session. Task/audit operation IDs often generated inside the attempt; same-state starts/status changes can no-op. | Read task/revision/cycle history, but a blind new create or command retry may duplicate intent; no universal exact command replay. |
| `EvidenceService.create_source/create_claim`, extraction and agent evidence | Task lock, content/URI or claim/link equivalence lookup; generated source/claim IDs and optional operation ID; source/claim audit in same transaction. | Some equal-content retries converge, but audit may add a reuse event and provenance differs; inspect authoritative rows before retry. |
| `MemoryService.apply/stage/reverse`, `AssessmentService.save` | Proposal/reversal `change_id` is caller-suppliable but defaults to `uuid4`; target/version unique journal and task lock; current projection, journal and public audit commit together. Link tables are deleted/reinserted within the transaction. | Preserved change ID/version can identify outcome; a request that regenerated its ID is not generally safe to repeat without reading history. |
| `SourceDependenceService.create/mutate/reverse`, `StoppingDecisionService.decide` | Caller-supplied `operation_id` is unique in change history; task lock, expected revision/fingerprint and normalized command replay; current state, history and audit commit together. | Exact unchanged retry is designed to return historical result; changed command conflicts. Strongest current ambiguous-commit candidates. |
| `SourceRegistryService.register/enable` | Domain unique; trust row and policy audit commit together under authority checks/locks; repeated enable can record a no-op audit. | Domain/current status can reconcile, but a repeated call is not always the same event. |
| `SecurityStateTransitionService.transition` and startup bootstrap | Singleton FOR UPDATE, expected version; transition UUID minted inside transaction; state/version and transition audit commit together. Startup recovery is idempotent when already pending. | Read state/version/audit; lost acknowledgement is not resolved by automatic retry, which may see a stale expected version. |
| Provider budget `reserve/dispatch/finish`; cycle attempt/progress | Caller-held provider operation ID and status rows, task then attempt locks, event audit commits with status. Equal terminal `finish` is a no-op; dispatch is a durable fence before external work. Cycle attempt IDs may be caller-held, while some progress IDs are generated internally. | Read attempt/progress and reconcile UNKNOWN/external effect; do not automatically re-dispatch after uncertain commit or remote call. |
| RecoveryContext capture, operator/execution authorization issuance | Caller-supplied context/authorization IDs, exact persisted command replay, singleton SHARE lock and REPEATABLE READ; artifact and audit commit together. | Exact unchanged identity can be read/replayed after uncertainty; changed command conflicts. |
| Protected restoration and epoch replacement | Caller-supplied restoration/replacement IDs, expected basis/version/epoch; singleton FOR UPDATE, transition audit in one transaction; `complete_reconstruction()` composes restoration and rotation atomically. Transition UUIDs are generated internally and caller IDs are embedded in audit JSON, not unique relational keys. | A stale retry can fail after a successful commit; inspect canonical epoch/state and transition audit before further action. No blind retry. |
| Reconstruction/backup/migration | Fence and readiness use separate singleton transactions; `pg_restore` is data-only single-transaction; each migration commits separately; recovery capture follows. Backup publishes files after final state check. | Partial reconstruction is discarded/recreated. Backup output needs manifest/digest inspection. Migration rerun is checksum-aware; no generic transaction retry. |
| Provider-session lifecycle | Token/session state is process memory; redacted event is database INSERT. The route holds an in-memory rollback wrapper around DB commit, but no distributed atomic commit exists. | A lost DB acknowledgement can diverge in-memory token state and durable audit; no durable token reconciliation is claimed. |

`AuditService.record_failure()` intentionally rolls back a failed success transaction
then writes a failure event in a **new** transaction. It is not atomic with the
failed attempt. Direct privileged SQL bypasses all application lock/audit rules.

## C–D. Persistence failures and ambiguous commits

| Condition | Current translation and outward result | Commit uncertainty |
|---|---|---|
| Recognized `IntegrityError` constraint name | `translate_integrity_error()` recognizes a short whitelist: singleton/state/transition authority checks, provider attempt PK, and trusted-source domain uniqueness. Security transition returns `PersistenceBoundaryError` (HTTP 500 safe invariant message); trusted-source duplicate maps to HTTP 409; provider duplicate maps to `ProviderAttemptConflict`. | A real constraint rejection means that attempted statement/commit failed; an earlier successful attempt may still explain a duplicate on retry. |
| Unknown `IntegrityError` or missing diagnostic name | Translator re-raises the original error. Other services sometimes collapse *all* IntegrityErrors to a service conflict/denial (context, authorization, restoration, epoch replacement), without claiming a known constraint category. | No safe semantic category or automatic retry follows. |
| SQLSTATE `40001` / `40P01` | Recovery, authorization and epoch services turn serialization/deadlock into their local conflict/denial. Ordinary task/memory/provider paths generally propagate SQLAlchemy errors after rollback. | These are transaction failures, but the service wording is not a universal retry policy. |
| Connection acquisition or other `OperationalError`/`DBAPIError` | Selected backup/preflight/reconstruction paths normalize to unavailable/denied; many API/service paths propagate. No central persistence taxonomy or uniform HTTP mapping exists. | Acquire failure before work is not an ambiguous commit; loss near COMMIT may be. |
| Connection loss before COMMIT is sent | Session/context rolls back or connection closes where possible; service usually propagates DB error. | If known to be before COMMIT, no durable mutation. The current code does not classify that timing reliably. |
| Connection loss during/after COMMIT acknowledgement | Often propagates DBAPI/OperationalError and is indistinguishable from failure to the caller; `rollback()` cannot undo a commit already accepted by PostgreSQL. | **Unknown outcome**: read by durable identity or authoritative state before retry. |
| Unknown SQLAlchemy/database failure | Propagates or becomes a broad service error in a few boundaries. | No generic retry is justified. |

The recognized-constraint whitelist intentionally refuses to label unfamiliar
driver failures as known duplicates or authority violations. The broad
IntegrityError-to-conflict mappings at recovery artifact boundaries are fail-closed
public errors, but they collapse distinct constraint failures for callers; the
repository does not document them as a precise persistence taxonomy. Treat that
loss of diagnostic distinction as a review item, not as permission to infer a
retryable duplicate. API routes map selected service/domain conflicts to 403/409,
missing resources to 404, and validation to 422; uncaught database errors have
no uniform operator result and ordinarily surface as server errors.

The tests cover rollback before a known commit, real constraints, concurrency,
and exact same-command replay. A monkeypatched `Session.commit()` that raises an
`IntegrityError` before calling PostgreSQL is not a lost acknowledgement. No test
found that actually demonstrates a successful PostgreSQL COMMIT with its response
lost to the caller. The ambiguity exposure is therefore a model, not a tested
PostgreSQL outcome. In particular, generated-ID task/security/audit writes are
unsafe to blindly replay; caller-ID command histories are reconcilable, not
automatically retryable; read-only inspection is not meaningfully exposed.

## E. Constraint-coverage matrix

Names below are stable only where explicitly named or pinned; most other CHECKs
have PostgreSQL-generated names and no registered persistence translation.

| Authority-bearing invariant | Application validation | Database constraint and translation | Below-application corruption / priority |
|---|---|---|---|
| Canonical security state/version/epoch | Enum and `SecurityStateStore` fail-closed load; locked transition policy | Named `security_state_singleton_id_valid`, `security_state_state_valid`, `security_state_version_positive`, `security_state_epoch_non_nil`; first three translated as authority violations, epoch also registered. | Invalid row blocks authority loading; keep database enforcement. |
| Transition vocabulary and lineage | Transition service checks direction/actor/reason and expected version | Named state/version/reason/epoch checks; reason and epoch registered. No cross-row proof that transition versions form an unbroken canonical history. | Corrupt audit weakens authority provenance; investigate targeted relational checks, not a generic history trigger. |
| Bootstrap/reconstruction shape | Loader/startup checks metadata; C3a fenced publication validates S/V/E | Named bootstrap-shape and validation-pending-shape CHECKs; bootstrap registered, validation-pending shape is not in the translation whitelist. | Invalid fence could expose authority or block recovery; constraint exists, translation asymmetry is a candidate M3 slice. |
| RecoveryContext and authorization identity | Pydantic/domain and replay validators check basis, IDs, expiry, command equality | Context/authorization UUID, version, expiry, JSON-object checks; execution→operator FK; context→audit FK. No authorization→context FK or JSON/column equivalence check. These constraints are not registered with the general translator. | Malformed artifact/embedded basis must be rejected on read; inspect materially unsafe cross-field gaps before adding SQL. |
| Task/cycle and execution attempts | Domain statuses, cycle transition rules and attempt protocol | Task status CHECK; cycle status has no CHECK; cycle attempt status/stage CHECK and FK. | Bad cycle status can break projections/recovery; targeted cycle-status CHECK is a plausible first constraint candidate after data audit. |
| Provider attempt outcome/status | Service state machine and exact operation ID | Report attempt status CHECK, operation PK, task FK; `UNKNOWN` included. | Bad status distorts budget/dispatch/reconciliation; current CHECK is material. |
| Evidence and assessment vocabulary | Source/claim/assessment domain models and governed memory checks | Source type, claim status and assessment status are stored as TEXT without a corresponding vocabulary CHECK; links and confidence ranges have FKs/CHECKs. | Bad status can change eligibility or make projections unreadable; inspect existing rows and add only the material vocabulary checks supported by current domain values. |
| Governed memory categories/history | Domain operation/lifecycle/version/provenance checks | Memory operation/version/target CHECKs and unique `(target_type,target_id,version)`; claim/assessment lifecycle and version CHECKs. Journal JSON provenance/schema not database-validated. | Invalid journal can make governed history unreadable; do not invent a broad JSON schema constraint without a concrete invariant. |
| Stopping decision state | Service checks task revision, evidence fingerprint, reason/references, exact command replay | Reason/revision/operation uniqueness, FK and fingerprint-format CHECK; command JSON column nullable for legacy rows. | Broken task/decision or command relation weakens replay; nullable legacy data must be treated as non-provable, not normalized. |
| Source/trust relationships | Source registry validates domain/status; dependence validates endpoints, direction, acyclicity and revisions | Trusted domain UNIQUE, but trusted-source status lacks a CHECK. Relationship kind/direction/lifecycle, ordering, same-task endpoint FKs and revision uniqueness are constrained; graph acyclicity remains application-only. | Invalid trust status or relationship graph can mislead source governance; status CHECK merits targeted assessment, graph-wide SQL enforcement does not follow automatically. |
| Authority-bearing command fields | Pydantic/domain validation; accepted source/stopping commands persisted for replay | Command JSON generally only object-shaped; source/stopping `command_request` nullable for migrated history; context/authorization command JSON object checks. | Direct SQL can forge mismatched embedded command/columns; service readers must fail closed. Add only proved relational invariants. |

## F. Audit durability

Successful task, memory, source-policy, provider-attempt, security transition,
context, authorization, restoration and epoch writes generally stage audit/history
in the same database transaction. There is no migration-defined append-only trigger,
revoke/grant policy, runtime role barrier, database-owner tamper resistance, or
cryptographic chain. Some legacy task FKs cascade; migration 013 restricts
`research_events` task deletion, while memory history deliberately lacks a
cascading target FK. Audit immutability is primarily application convention plus
selected keys/FKs and role policy still to be designed. `pg_dump`/`pg_restore`
preserve ordinary audit table data in the supported archive; canonical
`security_state` and migration-ledger table data are excluded. Backup preservation
is not independent tamper evidence. Current canonical documentation describes
append-only application history and explicitly leaves retention/tamper resistance
open; it should not be read as a guarantee against the current owner credential.

## G. Feasible role model and implementation order

1. **Migration/owner role:** owns application schema/tables and migration ledger;
   `CONNECT` and `CREATE` on the database for the trusted `pgcrypto` extension,
   schema `USAGE/CREATE`, object ownership for ALTER/CREATE, and ledger
   SELECT/INSERT/UPDATE. PostgreSQL 16 documents `pgcrypto` as a
   [trusted extension](https://www.postgresql.org/docs/16/pgcrypto.html), so this
   does not itself require superuser authority.
2. **Runtime role:** `CONNECT`, schema `USAGE`, SELECT on relevant tables, INSERT/
   UPDATE on governed data and audit tables as actually written, DELETE on
   `claim_sources` and `assessment_evidence` for current memory replacement. It
   needs row-lock-compatible SELECT/UPDATE rights on task/authority records but
   neither schema ownership nor DDL. A table-by-table privilege drill is needed
   before reducing broad grants.
3. **Backup role (optional later):** `CONNECT`, schema `USAGE`, SELECT on all archive
   tables plus migration/authority metadata, allowing pg_dump's ACCESS SHARE
   locks. It need not write or own the schema.
4. **Reconstruction/operator role:** `CONNECT`, schema `USAGE`, SELECT and INSERT
   across restored data tables, singleton UPDATE, context/audit INSERT and lock
   rights. Because the existing workflow runs migrations, it also needs an
   explicitly authorized owner/migration phase or owner capability. No separate
   public restore-only role/workflow is implied. Test-only CREATE/DROP DATABASE
   remains outside these production grants.

Recommended dependency order: first make deployment credential ownership and
complete-workflow privilege tests explicit; then separate migration/owner from
normal runtime without altering recovery; then assess targeted material SQL
constraints and their exact-name translation; then define service-specific
unknown-commit reconciliation from durable identities; finally decide audit
retention and privileged-tamper requirements for the deployment threat model.
Roadmap section numbering is not an instruction to add constraints or generic
retries first. The smallest implementation candidate is a distinct least-privilege
API runtime credential while leaving migration CLI and the complete reconstruction
operator workflow on the existing owner credential initially. A real PostgreSQL
role/privilege drill must cover startup, representative governed writes and denied
runtime DDL, and separately confirm that backup and complete reconstruction still
work with their explicitly chosen credentials. Backup-role specialization can
follow only if needed. The runtime role must not silently inherit migration
ownership.

No characterization test was added in Pass 1: existing constraint/rollback/replay
tests pin those contracts, while a fake commit exception would not prove the
missing PostgreSQL lost-acknowledgement boundary. No production behavior was
changed. The main roadmap assumption needing correction is that `run_migrations`
inside reconstruction makes a simple two-role runtime/migration switch incomplete.

## Verification

The focused unit/integration run covering persistence-error translation,
security transitions and epochs, authorization, recovery context/restoration,
source-dependence, stopping decisions, reconstruction, backup inspection,
provider lifecycle and provider-session audit exited successfully. Its only
local skips were the two real `pg_dump`/`pg_restore` reconstruction variants;
their hosted C3a evidence remains pinned in the C3a closure record. Repository
Ruff lint and conformance traceability passed. `git diff --check` and a whitespace
check of this new untracked record found no errors. No new test or production file
was changed for this characterization pass.
