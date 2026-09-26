# Gnomon Security Audit and Recovery Authority

## Purpose and status

This document is the maintained Markdown form of Gnomon’s security, audit, and recovery authority. It defines how Gnomon protects authority boundaries, secrets, network access, state integrity, audit history, privacy, and recovery operations.

These requirements are normative. The current implementation-status section identifies demonstrated controls and open release gaps. The persisted global security-state vocabulary below follows the implemented Slice 13 model; the original authority document and Slice 13 directive remain historical source records.

## Governing security principles

1. Authority is explicit.
2. Components receive least privilege.
3. Trust is bounded and contextual.
4. Untrusted inputs remain untrusted.
5. Compromise must be containable.
6. Security decisions are external to model reasoning.
7. State integrity takes priority over convenience.
8. Auditability is part of security.
9. Recovery is a normal operating capability.
10. Failure fails closed.

Security controls must be enforced by deterministic application, infrastructure, and persistence boundaries. Model reasoning may propose actions or explain results, but it cannot authorize itself, change security policy, grant capabilities, or decide that an unsafe operation is permitted.

## Threat and trust boundaries

The threat model includes malicious or compromised model providers, external agents, retrieved content, tools, operators, credentials, network services, application components, persistence, derived indexes, and supply-chain or deployment inputs.

Trust boundaries include:

```text
User / operator
  -> API and authorization boundary
  -> application and domain validation
  -> adapters and controlled egress
  -> external providers, networks, and retrieved content
```

Information crossing a boundary is validated, scoped, attributed, and treated according to its trust level. A compromised component must not be able to silently rewrite unrelated authoritative state or elevate its own authority.

## Secrets, authentication, and authorization

Credentials, API keys, tokens, private keys, and internal network information remain in protected configuration or adapter boundaries. They must not be stored as ordinary research evidence, exposed to model context unnecessarily, returned by status endpoints, placed in prompts, or written to audit payloads.

Authentication establishes identity; authorization determines permitted operations. Model identity is not user identity and does not grant policy authority. Authorization is explicit, least-privilege, task-scoped where appropriate, and independently enforced from model reasoning.

Secret handling includes separation, protected logging, and rotation. The current local provider boundary supports redacted credential modes and does not expose token values; full authenticated multi-user authorization and operational rotation remain open.

## Network egress and untrusted content

External network access is mediated by controlled adapters or tools. Egress policy should enforce destination restrictions, private-network protection, timeouts, response-size limits, content-type restrictions, logging, credentials isolation, and resource limits.

Retrieved web pages, documents, API responses, agent messages, metadata, and generated external text are untrusted content. Prompt-injection instructions inside them remain data and cannot override system instructions, application policy, security state, or user intent.

## Data and state integrity

Authoritative state changes pass through application and domain validation, appropriate database constraints, transaction boundaries, and concurrency controls. Related writes commit atomically where practical or produce an explicit incomplete or failed state.

Important state changes use operation identities, idempotency, compare-and-set or version checks, row locks, and explicit unknown outcomes as appropriate. A failure or timeout must not silently become successful completion. Unknown external effects must be reconciled before unsafe duplicate execution.

Security state, constitutional policy, audit history, and ordinary research memory remain conceptually distinct. A model or external agent cannot mutate security or constitutional state through ordinary memory operations.

## Audit authority

Audit records are security evidence, not a replacement for current domain state or a second uncontrolled memory system. Important events include authorization decisions, security denials, credential and provider operations, lifecycle and state changes, external communication, recovery, rollback, configuration changes, and integrity failures.

Audit events should retain an immutable identity, event type, actor or initiating process, timestamp, task or scope, affected records, operation/correlation identity, result category, and redacted structured metadata. Audit payloads must avoid raw source text, credentials, unrestricted provider errors, and sensitive data not required for accountability.

Audit integrity requires protection against ordinary deletion or mutation, tamper evidence appropriate to the deployment, retention policy, and access controls. The current repository has broad redacted audit coverage for task, cycle, evidence, memory, rollback, provider dispatch, provider-session lifecycle, security-denial, and trusted-source registration/activation paths. Complete audit retention, tamper-evidence, authenticated multi-user identity, and unrelated configuration-writer coverage remain open.

## Security state and containment

The persisted global operational security states are:

| State | Meaning |
|---|---|
| `NORMAL` | Expected capabilities operate under ordinary policy. |
| `DEGRADED` | Security assurance is reduced without established compromise; safe local capabilities remain available and consequential capabilities are restricted by policy. |
| `COMPROMISED_SUSPECTED` | Evidence suggests possible compromise of the environment or authority boundary; it is distinct from ordinary degradation and denies consequential execution. |
| `LOCKDOWN` | Explicit global containment denies ordinary external and authority-bearing execution while preserving evidence and diagnostics. |
| `RECOVERY_REQUIRED` | Ordinary authority remains unavailable pending governed recovery verification and separately authorized recovery actions. This state grants no recovery authority by itself. |

The older authority document's `SAFE` is not a persisted global state. Its useful meaning is expressed through explicit read, audit, local-report, and diagnostic capabilities permitted under restrictive states. `ISOLATED` is likewise not a global state: it describes future scoped containment of a provider, agent, network, or other bounded component. Scoped containment is not implemented as a general operational facility. The older `RECOVERY` term is expressed as `RECOVERY_REQUIRED` plus separately authorized recovery actions; a state label alone never grants those actions.

Structural transition legality, actor and reason authorization, capability policy, and persisted version validation all apply to state changes. A pending recovery-bootstrap fence is a separate restriction and cannot be cleared through the ordinary security-state transition service. The [architecture overview](../architecture/overview.md#architectural-invariants) records the cross-boundary invariants; the [Slice 13 record](../source_of_truth/Slice%2013%20Security%20State%20Model%20and%20Transition%20Table.md) preserves the implementation rationale and original transition table.

### AuthorityDirection

`AuthorityDirection` classifies the direction of a requested authority-bearing effect for capability checks. It is not a complete ordering of how permissive or hazardous every restricted state is, and it does not grant authority by itself. The current transition classifier uses:

| Transition shape | Direction |
|---|---|
| `NORMAL` to any other global state | `REDUCE` |
| Any non-`NORMAL` state to `NORMAL` | `BROADEN` |
| Between two non-`NORMAL` states | `PRESERVE` |

For example, `DEGRADED` to `LOCKDOWN` is classified `PRESERVE`; that label does not say the states have equal incident meaning or that the transition is automatically permitted. A request must also pass structural transition legality, actor and reason authorization, direction-aware authority administration, recovery or containment capability as applicable, and locked persisted state/version validation. Recovery bootstrap adds its own fence. These checks serve different purposes and no direction value substitutes for another check.

Containment should preserve research state while restricting compromised providers, agents, networks, derived indexes, or storage paths. Examples include provider loss without research-state corruption, agent isolation without deleting unrelated evidence, and vector-index loss while structured state remains authoritative.

## Incident response

Incident response follows four broad steps:

1. Detect anomalous behavior, integrity failures, policy violations, or suspicious external input.
2. Classify the affected component, scope, confidence, and potential impact.
3. Contain by restricting capabilities, isolating providers/networks/agents, and preventing unsafe retries or writes.
4. Preserve evidence, audit history, provenance, and state needed for investigation and recovery.

A compromised provider or agent must not be treated as authoritative. Its contributions remain attributable and subject to epistemic evaluation, reassessment, and dependency-aware remediation.

## Backup, restore, rollback, and recovery

Backups are security controls, not merely operational conveniences. Backup integrity requires known provenance, verification, version compatibility, protected access, and evidence that restoration can recover authoritative state without silently erasing history.

### Separate recovery authority dimensions

| Dimension | Role |
|---|---|
| SecurityState | The current global operational restriction. `RECOVERY_REQUIRED` permits only capabilities allowed by current policy; it is not a recovery grant. |
| Recovery bootstrap | A separate persisted pending fence for reconstructed or restored authority. While pending, effective state is `RECOVERY_REQUIRED` even if the restored raw state was `NORMAL`; ordinary authority-bearing capabilities and normal security transitions remain blocked. |
| AuthorityEpoch | The UUID lineage of the canonical authority state. Possessing an epoch ID grants no permission; current protected effects must validate authorization against the current epoch. Reconstruction completion replaces the restored epoch. |
| Recovery context and evidence | A bounded, time-limited snapshot of bootstrap basis and supported evidence/operation inventory, followed by fresh reconciliation and separately issued operator/execution authorization. A context or a passing verdict alone grants no restoration authority. |
| Recovery fingerprint | A hash of observed investigation status and cycle progress used for operator recovery of an execution cycle. A stale fingerprint rejects recovery; it is neither a SecurityState version nor an AuthorityEpoch. |

**Recovery from reconstructed or restored authority is not an ordinary security-state transition.** Database restoration does not manufacture trust. The reconstruction path enters the recovery-bootstrap fence, captures fresh context, reconciles supported evidence and outcomes, and requires protected restoration with epoch rotation before ordinary authority becomes available. The ordinary security-state transition service cannot clear the pending fence. Historical recovery contexts and authorizations remain evidence, not current grants.

The bounded implementation and verification records are [recovery bootstrap](../development/recovery-bootstrap-boundary.md), [RecoveryContext](../development/recovery-context.md), [reconciliation](../development/recovery-reconciliation.md), [protected restoration](../development/recovery-restoration.md), [epoch replacement](../development/authority-epoch-replacement.md), and [reconstruction epoch rotation](../development/reconstruction-epoch-rotation.md).

Restore must distinguish current state from historical state, preserve audit and provenance requirements, and record the restoration event. Rollback reverses eligible state transitions without pretending the attempted mutation never happened. Provenance-aware recovery identifies dependent claims, assessments, inferences, and conclusions rather than indiscriminately deleting records.

Derived state such as indexes, caches, embeddings, and summaries should be rebuildable from authoritative state. Their loss must not become loss of the underlying research record.

The repository has transactional recovery and rollback tests plus the hosted-verified M2 backup/reconstruction/recovery drill for a supported test deployment. A consolidated operator procedure and broader deployment or release conformance remain open.

## Privacy and secure deletion

Data minimization applies to model context, logs, audit, exports, network requests, and external communication. Outbound data must be limited to what the authorized operation requires and must not disclose credentials, private research state, unnecessary personal information, or internal security details.

Permanent purge is privileged, explicitly authorized, retention-aware, auditable, and outside ordinary model capabilities. Logical deletion, archive, and retention states preserve the history needed for recovery and accountability. Security and constitutional history receive stronger protection than ordinary temporary artifacts.

## Resource exhaustion and replay

Security controls enforce bounded time, tokens, requests, bytes, concurrency, retries, memory mutations, provider attempts, and external communication. A model cannot extend its own limits. Replay and duplicate delivery must be identified through operation or message identities and must not create duplicate semantic mutations or extra corroboration.

## Mandatory security invariants

1. Authority separation is explicit.
2. Least privilege applies to every component.
3. Secrets remain isolated.
4. Prompt injection is contained as untrusted content.
5. Network egress is controlled.
6. Authoritative state integrity is protected.
7. Important operations are auditable.
8. Audit history is protected.
9. Failures are contained.
10. Security state is explicit.
11. Unsafe uncertainty fails closed.
12. Recovery is supported and tested.
13. Recovery is not historical erasure.
14. Remediation is provenance-aware.
15. Derived state is rebuildable.
16. Permanent destruction is privileged.
17. Resources are bounded.
18. External dependencies are not constitutional dependencies.
19. Privacy boundaries are enforced.
20. Security history is preserved.

## Current implementation status

| Requirement area | Current evidence and limitation |
|---|---|
| Boundary guards, least authority, and untrusted input handling | Implemented for current HTTP, provider, fake-agent, capability, source-domain, and lifecycle paths; broader adapter coverage remains open. |
| Secrets and provider configuration | Current settings and provider status expose credential mode without secret values; full authentication and rotation operations remain open. |
| State integrity, concurrency, idempotency, and explicit unknown outcomes | Implemented across migrations, lifecycle, provider attempts, memory governance, cycle recovery, and audit transactions for the current scope. |
| Auditability and redaction | Broad task-scoped redacted audit coverage exists; provider-session create/delete lifecycle metadata is now durable; complete retention, tamper evidence, operator identity, and unrelated provider/configuration-writer coverage remain open. |
| Security state machine | The five-state Slice 13 vocabulary, persisted versioned transitions, and centralized capability policy are implemented for the reviewed scope. Recovery bootstrap and protected restoration remain distinct from ordinary state transitions; scoped component isolation remains future work. |
| Failure containment and degraded operation | Current provider, cycle, and retrieval failures preserve explicit outcomes and local state; broader incident containment and restrictive-state operations remain partial. |
| Backup, restore, and recovery | Transactional recovery and the bounded M2 backup/reconstruction/recovery drill have executable evidence; a consolidated operator procedure and broader deployment/release evidence remain open. |
| Secure deletion, privacy, and external disclosure | Redacted audit and provider boundaries exist; privileged purge, full export review, and outbound privacy enforcement remain open. |
| Security conformance tests | Deterministic boundary, injection, lifecycle, persistence, provider, and state-transition tests exist; the complete contract-test set is not yet satisfied. |

The [constitutional principles](constitutional-principles.md), [agent runtime](../architecture/agent-runtime.md), [external-agent network](../architecture/external-agent-network.md), [memory authority](memory-authority.md), [workspace verification](../operations/workspace-verification.md), [conformance records](../conformance/implementation-status.md), and [Slice 13 state model](../source_of_truth/Slice%2013%20Security%20State%20Model%20and%20Transition%20Table.md) provide supporting evidence and known limitations.

## Related documentation

- [Documentation map](../README.md)
- [Constitutional principles](constitutional-principles.md)
- [Memory authority](memory-authority.md)
- [Agent runtime](../architecture/agent-runtime.md)
- [External-agent network](../architecture/external-agent-network.md)
- [Repository documentation inventory](../source_of_truth/repository-documentation-inventory.md)
- [Original authority document retained during cleanup](../archive/original-authority-documents/Security,%20Audit%20%26%20Recovery%20Authority.docx)
