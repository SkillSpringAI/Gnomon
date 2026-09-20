# Authority foundations — 19 September 2026

## Scope and baseline

The starting verified commit is `9c82544ddd582770332df2174d93c2ca759a28bd`:
[Quality run #12 passed](https://github.com/SkillSpringAI/Gnomon/actions/runs/35414849048).
It implements READ_AUDIT, source-retrieval, and provider-dispatch point-of-effect checks.
The sequence is documentation synchronization, epoch persistence, verification,
then transition actor/reason hardening. Contracts #1–#5 are not modified.

## Authority Epoch foundation

`AuthorityEpochId` is a validated, non-nil UUID identifying a continuous authority
lineage. Possession provides no authentication, authorization, or capability.
The canonical security-state row persists `state`, `version`, and
`authority_epoch_id`; `PersistedSecurityState.identity` is `(epoch, version)`.
Ordinary restart and state/version transitions retain the same epoch.

Migration 023 initializes the existing continuing installation once, without
changing state, version, or timestamps. It adds no persistent UUID default.
Reapplying its SQL preserves a valid epoch and rejects absent/invalid lineage;
normal migration reruns skip the checksummed applied migration. Runtime loading
and transition requests validate lineage and never generate or repair an epoch.
The database rejects null, malformed, and nil UUIDs on the canonical row.

New transitions copy the locked canonical row's epoch into their audit record
within the state-update transaction. Historical pre-023 transition records retain
null lineage; this means “recorded before epoch attribution,” not permission to
infer a lineage. State and transition API responses expose the UUID (nullable only
for historical audit). No epoch replacement operation exists. Transition requests
still compare the version within the sole active epoch; cross-epoch request fencing
must precede any future epoch replacement implementation.

Evidence: `test_security_state_store.py`, `test_authority_epoch.py`,
`test_security_state_transitions.py`, and `test_security_api.py` cover fail-closed
loading, capabilities, populated migration, corruption, rerun, restart/reload,
atomic transitions, and operator-visible attribution.

## Transition actor/reason hardening

The service now uses an explicit matrix of `(current_state, requested_state,
actor_type, reason_code)`. Structural edges remain unchanged; an absent tuple
denies the transition. A detector cannot use operator or recovery reason codes.

| Destination (only on existing structural edges) | Local operator reasons | Detector reasons | Recovery service reasons |
| --- | --- | --- | --- |
| DEGRADED | OPERATOR_DEGRADED_MODE, SECURITY_DEPENDENCY_DEGRADED | SECURITY_DEPENDENCY_DEGRADED | None |
| COMPROMISED_SUSPECTED | Security findings below | Security findings below | None |
| LOCKDOWN | OPERATOR_LOCKDOWN, security findings below | Security findings below | None |
| RECOVERY_REQUIRED | RECOVERY_STARTED | None | RECOVERY_STARTED |
| NORMAL | RECOVERY_VERIFIED | None | RECOVERY_VERIFIED |

Security findings are SECURITY_INVARIANT_VIOLATION, INTEGRITY_CHECK_FAILED,
CREDENTIAL_COMPROMISE_SUSPECTED, and AUTHORITY_BOUNDARY_VIOLATION. RECOVERY_PARTIAL
and RECOVERY_FAILED do not authorize state-changing transitions in this bounded
matrix. Their restoration semantics remain deferred. Existing actor paths to
NORMAL and RECOVERY_REQUIRED are retained, without introducing protected human
authentication or a new automated restoration path.

`AuthorityDirection` compares the implemented capability sets: NORMAL to a
restrictive state is REDUCE; restrictive to NORMAL is BROADEN; transitions between
restrictive states are currently PRESERVE because those states share a capability
set. This is not a claim that their incident or restoration semantics are equivalent.
Mixed capability changes classify as BROADEN. Broadened capability paths require
RECOVERY_ACTION; direction never substitutes for actor/reason authorization.

Same-state requests retain the existing matching-version no-op behavior: they
neither change state/version nor append a transition. They still require valid
request metadata and canonical lineage. The response captures its observed version
before releasing the lock, so a concurrent transition cannot mix a later version
with the no-op's earlier state. Exhaustive policy tests cover all 825
state/actor/reason combinations and all 25 direction pairs. Integration tests
prove invalid reasons leave both state and transition history unchanged.

Capability reads explicitly refresh the SQLAlchemy identity map. Locked transition
reads also refresh existing ORM objects before validating state, epoch, and version.
This prevents a reused session's cached NORMAL state from authorizing work after
a committed lockdown, or from consuming a stale version a second time. Regression
tests hold a cached object while another session commits containment, then verify
capability denial and conflict without any additional audit entry. These checks
use the existing PostgreSQL READ COMMITTED behavior; they do not add atomic locking
across an external network effect.

## Deferred authority machinery

Recovery bootstrap, new-epoch replacement, RecoveryContext, OperatorAuthorization,
ExecutionAuthorization epoch binding, deployment cloning, and backup reconstruction
remain unimplemented. Existing bounded recovery transition behavior does not
establish those architectural capabilities or protected human authentication.

The unresolved lifecycle question is: when a restrictive SecurityState transition
interrupts an already-running cycle, which authority permits a durable
BLOCKED/INTERRUPTED closure? Resolve this before generalizing capabilities,
containment bookkeeping, recovery semantics, or MEMORY_MUTATION. No lifecycle
behavior is changed by this slice.

The [20 September closure decision](cycle-closure-authority.md) now documents a
bounded containment path, now implemented in local changes following this
checkpoint, together with the five-path mutation/lockdown ordering protocol.
