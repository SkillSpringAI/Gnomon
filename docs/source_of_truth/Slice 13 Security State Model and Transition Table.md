# Slice 13: Security State Machine

## Goal

Introduce an explicit, persisted, fail-closed operational security state machine that governs whether Gnomon may perform authority-bearing or externally interacting operations.

The security state machine is independent from:

- investigation lifecycle state;
- research-cycle state;
- cycle execution-attempt state;
- provider-attempt state;
- individual evidence, claim, assessment, or memory lifecycle.

Those state machines may constrain one another, but their states must not be overloaded or silently inferred from one another.

## Core invariant

Gnomon's operational authority must be a deterministic function of its persisted security state and the requested capability.

External content, models, providers, agents, sources, retrieved text, or ordinary application code must never directly elevate Gnomon's security state or grant themselves additional authority.

A transition toward greater restriction may occur automatically when a trusted internal detector establishes the required condition.

A transition toward greater authority must require an explicitly authorized recovery path and must never occur merely because time passed, a process restarted, or the triggering error disappeared.

Unknown or contradictory security-state information fails closed.

---

# 1. Canonical states

## `NORMAL`

The system has no currently established security condition requiring reduced authority.

Normal configured capabilities may operate, subject to all existing governance, lifecycle, budget, provenance, and capability checks.

`NORMAL` does not mean that external content is trusted. Existing untrusted-input boundaries remain in force.

## `DEGRADED`

A security-relevant anomaly or loss of assurance has occurred, but there is not sufficient evidence to treat the environment as actively compromised.

Read operations and safe local analysis remain available.

Sensitive or externally consequential capabilities may be restricted according to policy.

Typical causes include:

- partial loss of a security dependency;
- unverifiable but non-critical integrity information;
- repeated provider/network anomalies;
- incomplete security telemetry;
- recoverable security subsystem failure.

`DEGRADED` must not silently behave identically to `NORMAL`.

## `LOCKDOWN`

A sufficiently serious security condition exists that external or authority-bearing execution must stop.

The system preserves existing evidence, audit history, attempts, provenance, and diagnostic information but denies capabilities that could increase exposure or mutate governed state beyond explicitly permitted containment operations.

Typical causes include:

- confirmed integrity violation;
- credential or authority-boundary compromise;
- forbidden capability execution;
- security invariant violation;
- explicit operator emergency lockdown.

`LOCKDOWN` is fail-closed.

## `RECOVERY_REQUIRED`

The immediate triggering condition has been contained or is no longer active, but Gnomon has not yet re-established sufficient assurance to return to ordinary operation.

This is an explicit recovery state rather than an automatic route back to `NORMAL`.

Recovery verification may inspect state, run diagnostics, reconcile interrupted attempts, validate configuration and persistence integrity, and perform specifically authorized recovery operations.

Normal external execution remains unavailable.

## `COMPROMISED_SUSPECTED`

Gnomon has evidence suggesting that its execution environment, authority boundary, credentials, persisted state, or security controls may have been compromised, but the condition has not yet been conclusively established or cleared.

This state is intentionally conservative.

Potential compromise must not be represented merely as `DEGRADED`, because uncertainty about the integrity of the authority boundary itself requires stronger containment.

Externally consequential and authority-bearing operations are denied.

Read-only forensic inspection, audit retrieval, diagnostics, and explicitly bounded containment operations remain available.

---

# 2. Restrictiveness

For authority decisions, use the following conceptual ordering:

```text
NORMAL
  |
  v
DEGRADED
  |
  v
COMPROMISED_SUSPECTED
  |
  v
LOCKDOWN
  |
  v
RECOVERY_REQUIRED
```

This diagram describes increasing restriction, not the complete legal transition graph.

`RECOVERY_REQUIRED` is not necessarily "more compromised" than `LOCKDOWN`. It is more accurately a controlled recovery phase in which ordinary authority remains unavailable until recovery verification succeeds.

Code must therefore use explicit state/capability rules rather than numeric comparisons such as:

```python
if security_state >= LOCKDOWN:
    ...
```

---

# 3. Valid transition table

| Current state | Requested next state | Valid | Authority | Required condition |
|---|---|---:|---|---|
| `NORMAL` | `DEGRADED` | Yes | trusted detector or authorized operator | Security assurance has materially weakened |
| `NORMAL` | `COMPROMISED_SUSPECTED` | Yes | trusted detector or authorized operator | Evidence creates a credible compromise suspicion |
| `NORMAL` | `LOCKDOWN` | Yes | trusted detector or authorized operator | Critical invariant violation, confirmed severe condition, or emergency operator action |
| `NORMAL` | `RECOVERY_REQUIRED` | No | n/a | Recovery requires a preceding restrictive condition |
| `DEGRADED` | `NORMAL` | Yes | authorized recovery path | Cause resolved and required verification passes |
| `DEGRADED` | `COMPROMISED_SUSPECTED` | Yes | trusted detector or authorized operator | New evidence raises compromise suspicion |
| `DEGRADED` | `LOCKDOWN` | Yes | trusted detector or authorized operator | Condition becomes critical or containment is required |
| `DEGRADED` | `RECOVERY_REQUIRED` | Yes | authorized recovery path | Condition has been contained but assurance must be re-established |
| `COMPROMISED_SUSPECTED` | `LOCKDOWN` | Yes | trusted detector or authorized operator | Compromise is confirmed or containment policy requires lockdown |
| `COMPROMISED_SUSPECTED` | `RECOVERY_REQUIRED` | Yes | authorized recovery path | Suspected compromise has been contained and recovery verification is required |
| `COMPROMISED_SUSPECTED` | `DEGRADED` | No | n/a | Do not weaken containment without recovery verification |
| `COMPROMISED_SUSPECTED` | `NORMAL` | No | n/a | Direct restoration of ordinary authority is forbidden |
| `LOCKDOWN` | `RECOVERY_REQUIRED` | Yes | authorized recovery path | Immediate threat is contained and controlled recovery may begin |
| `LOCKDOWN` | `NORMAL` | No | n/a | Lockdown may not directly restore normal authority |
| `LOCKDOWN` | `DEGRADED` | No | n/a | Recovery verification must occur first |
| `LOCKDOWN` | `COMPROMISED_SUSPECTED` | No | n/a | Lockdown remains the containment state until recovery begins |
| `RECOVERY_REQUIRED` | `NORMAL` | Yes | authorized operator/recovery service | Full required recovery verification passes |
| `RECOVERY_REQUIRED` | `DEGRADED` | Yes | authorized operator/recovery service | Core integrity is restored but reduced-assurance operation remains appropriate |
| `RECOVERY_REQUIRED` | `COMPROMISED_SUSPECTED` | Yes | trusted detector or recovery service | Recovery discovers unresolved evidence of possible compromise |
| `RECOVERY_REQUIRED` | `LOCKDOWN` | Yes | trusted detector or recovery service | Recovery discovers a critical or confirmed security condition |

A request to transition to the current state is an idempotent no-op only when its expected version matches the persisted state.

It must not create a second logical transition.

---

# 4. Forbidden transitions

The following transitions are explicitly forbidden:

```text
NORMAL -> RECOVERY_REQUIRED

COMPROMISED_SUSPECTED -> NORMAL
COMPROMISED_SUSPECTED -> DEGRADED

LOCKDOWN -> NORMAL
LOCKDOWN -> DEGRADED
LOCKDOWN -> COMPROMISED_SUSPECTED
```

The important rule is:

> Restriction may escalate quickly. Authority must return slowly.

A process restart, elapsed timeout, successful network request, provider response, disappearance of an exception, or absence of new alerts must never perform a recovery transition automatically.

---

# 5. Capability policy

Security state must be evaluated before authority-bearing operations.

Baseline policy:

| Capability class | NORMAL | DEGRADED | COMPROMISED_SUSPECTED | LOCKDOWN | RECOVERY_REQUIRED |
|---|---:|---:|---:|---:|---:|
| Read persisted investigation state | Allow | Allow | Allow | Allow | Allow |
| Read audit/security history | Allow | Allow | Allow | Allow | Allow |
| Deterministic local reporting | Allow | Allow | Allow | Allow | Allow |
| Security diagnostics | Allow | Allow | Allow | Allow | Allow |
| Ordinary governed memory mutation | Allow | Policy-restricted | Deny | Deny | Recovery-only |
| Start research cycle | Allow | Policy-restricted | Deny | Deny | Deny |
| External source retrieval | Allow | Policy-restricted | Deny | Deny | Deny |
| Provider/model dispatch | Allow | Policy-restricted | Deny | Deny | Deny |
| External agent dispatch | Allow only where separately authorized | Deny by default | Deny | Deny | Deny |
| Security containment action | Allow | Allow | Allow | Allow | Allow |
| Recovery verification/action | n/a | Allow where applicable | Allow where applicable | Begin-recovery only | Allow |

Slice 13 must implement the mechanism without using it as justification to expand currently deferred live-agent capabilities.

---

# 6. Transition contract

Every persisted security transition must contain at minimum:

```text
transition_id
previous_state
new_state
reason_code
actor_type
actor_id / trusted subsystem identity
created_at
security_state_version
related_event_ids[]
```

Free-form untrusted content must not become authoritative transition rationale.

Use bounded reason codes for authority decisions. Detailed diagnostic context may be retained separately where policy permits.

Suggested reason-code families:

```text
OPERATOR_LOCKDOWN
SECURITY_INVARIANT_VIOLATION
INTEGRITY_CHECK_FAILED
CREDENTIAL_COMPROMISE_SUSPECTED
AUTHORITY_BOUNDARY_VIOLATION
SECURITY_DEPENDENCY_DEGRADED
RECOVERY_STARTED
RECOVERY_VERIFIED
RECOVERY_PARTIAL
RECOVERY_FAILED
OPERATOR_DEGRADED_MODE
```

---

# 7. Concurrency and persistence rules

Security transitions are compare-and-set operations.

A transition request must provide the expected security-state version.

Within one transaction:

```text
lock canonical security-state record
-> verify expected version
-> verify requested transition is legal
-> verify actor is authorized
-> persist new state/version
-> append security transition/audit record
-> commit
```

The state update and authoritative audit event must succeed or fail together.

Concurrent transitions from the same version must not both succeed.

When competing transitions are valid but one represents greater containment, the loser must reload the current state and be re-evaluated rather than blindly retrying its original write.

Security state must survive application restart.

Application startup must never default an existing installation back to `NORMAL` because the previous state cannot be loaded.

Failure to read or validate persisted security state must fail closed for authority-bearing operations.

---

# 8. Interaction with in-flight work

Entering a restrictive state does not erase already committed work.

For an operation already in progress:

1. no new external dispatch occurs after the restrictive transition is observed;
2. existing provider/network calls may physically finish if cancellation is impossible;
3. their returned data must pass the current security-state guard before authoritative persistence;
4. already committed evidence remains retained and attributable;
5. uncertain external execution follows the existing attempt/recovery semantics;
6. security transition does not rewrite historical cycle or provider outcomes.

`LOCKDOWN` therefore means "no further authority is granted", not "pretend previous work never happened."

---

# 9. Audit requirements

Record:

- successful transitions;
- rejected invalid transitions;
- stale-version conflicts;
- unauthorized transition attempts;
- capability denials caused by security state;
- recovery initiation;
- recovery success;
- recovery failure;
- escalation discovered during recovery.

Public audit projections must use bounded categories and must not expose credentials, raw secrets, arbitrary provider payloads, or unrestricted operator prose.

---

# 10. Minimum implementation shape

Prefer one canonical domain model:

```python
class SecurityState(StrEnum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    COMPROMISED_SUSPECTED = "compromised_suspected"
    LOCKDOWN = "lockdown"
    RECOVERY_REQUIRED = "recovery_required"
```

and one explicit transition map:

```python
VALID_TRANSITIONS = {
    SecurityState.NORMAL: {
        SecurityState.DEGRADED,
        SecurityState.COMPROMISED_SUSPECTED,
        SecurityState.LOCKDOWN,
    },
    SecurityState.DEGRADED: {
        SecurityState.NORMAL,
        SecurityState.COMPROMISED_SUSPECTED,
        SecurityState.LOCKDOWN,
        SecurityState.RECOVERY_REQUIRED,
    },
    SecurityState.COMPROMISED_SUSPECTED: {
        SecurityState.LOCKDOWN,
        SecurityState.RECOVERY_REQUIRED,
    },
    SecurityState.LOCKDOWN: {
        SecurityState.RECOVERY_REQUIRED,
    },
    SecurityState.RECOVERY_REQUIRED: {
        SecurityState.NORMAL,
        SecurityState.DEGRADED,
        SecurityState.COMPROMISED_SUSPECTED,
        SecurityState.LOCKDOWN,
    },
}
```

The transition map defines structural legality only.

Authorization, reason-code requirements, recovery evidence, expected version, and capability policy must be checked separately.

---

# 11. Required tests

Slice 13 is not complete without positive and negative transition tests.

At minimum verify:

- every transition marked valid succeeds with proper authority;
- every transition marked invalid fails without changing persisted state;
- stale expected versions return conflict;
- two concurrent transitions cannot both consume the same state version;
- unauthorized actors cannot transition security state;
- external/untrusted input cannot directly trigger an authority-restoring transition;
- `LOCKDOWN` survives restart;
- `RECOVERY_REQUIRED` survives restart;
- unreadable/invalid persisted security state fails closed;
- entering `LOCKDOWN` blocks new provider dispatch;
- entering `LOCKDOWN` blocks new source retrieval;
- entering `LOCKDOWN` blocks new cycle execution;
- safe read/audit/diagnostic operations remain available;
- an in-flight external result cannot bypass the new restrictive state;
- committed evidence is not deleted by a security transition;
- transition state and audit event commit atomically;
- recovery cannot jump directly from `LOCKDOWN` to `NORMAL`;
- failed recovery remains restrictive;
- successful verified recovery can restore `NORMAL`;
- duplicate same-state transition requests are idempotent only under the documented version contract.

---

# 12. Exit gate

Slice 13 is complete only when:

1. the canonical security states and valid transition graph are documented;
2. the state is persisted and versioned;
3. transition and audit persistence are atomic;
4. authority-restoring transitions require an authorized recovery path;
5. capability enforcement is centralized rather than scattered through API handlers;
6. external/provider/agent content cannot directly alter security authority;
7. restrictive state is checked at external-dispatch and governed-mutation boundaries;
8. restart and corrupted/unavailable-state behavior fail closed;
9. concurrency and stale-version behavior are tested against PostgreSQL;
10. positive and negative transition matrices pass;
11. existing Slice 11/12 attempt, retention, audit, and recovery invariants remain intact;
12. Ruff, strict mypy, unit tests, PostgreSQL integration tests, smoke, prototype, traceability, and clean-wheel verification pass.

Completion of Slice 13 does not authorize live external-agent expansion and does not satisfy the separate Slice 14 backup/restore conformance requirement.
