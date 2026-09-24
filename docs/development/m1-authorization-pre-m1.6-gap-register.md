# M1 Authorization Gap Register Before M1.6

Date: 24 September 2026.
Status: M1.6 pass-2 review checkpoint. This file records known gaps that must be
reviewed before the M1.6 exit gate. It is not a final implementation claim and
does not authorize restoration beyond the tested local scope.

## Purpose

M1.2 and M1.3 now provide bounded `OperatorAuthorization` and
`ExecutionAuthorization` artifacts, trusted local issuance, append-only persistence,
audit coupling and exact replay validation. The remaining issues below should be
checked before M1.6 declares authority epoch replacement complete, because stale
or incomplete authorization semantics would otherwise leak into restoration.

## Gap Register

| ID | Area | Status before M1.6 | Required disposition before M1.6 exit |
| --- | --- | --- | --- |
| AUTH-G01 | Restoration consumption | Addressed for M1.5 | M1.5 consumes RecoveryContext, M1.4 reconciliation, OperatorAuthorization and ExecutionAuthorization under protected restoration preflight and completion transactions, then clears the fence with audit. M1.6 passes 1-2 add epoch replacement and current execution validation after restoration. |
| AUTH-G02 | Point-of-effect capability | Partially addressed | Restoration and epoch replacement re-read current authority for their own effects, and `AuthorizationService.require_current_execution` now distinguishes current-use validation from historical replay. Pass 3 should audit remaining consumers before exit. |
| AUTH-G03 | RecoveryContext reconciliation | Addressed for M1.5 | M1.4 produces a read-only reconciliation verdict over supported evidence and provider/cycle outcomes. M1.5 consumes that verdict with authorization under one protected restoration transaction. |
| AUTH-G04 | Authority epoch replacement | Partially addressed | M1.6 pass 1 rotates the epoch after protected restoration. Pass 2 proves old execution authorization remains historical replay only and is rejected by the current execution boundary while new-epoch authorization is accepted. Pass 3 must refresh exit-gate evidence and consumer audit. |
| AUTH-G05 | Authenticated operator identity | Deferred | Current local principal attribution is bounded evidence, not authentication. Multi-user identity can remain deferred only if M1.6 explicitly keeps the local-only scope. |
| AUTH-G06 | Database tamper resistance | Deferred | Application reads fail closed on malformed authorization history, but database-owner rewrites are not cryptographically prevented. M1.6 must not claim stronger guarantees. |
| AUTH-G07 | Expired historical replay | Narrowed limitation | Exact replay can return historical authorization records even after expiry or epoch replacement. Current protected effects now have `require_current_execution`, which fails stale, expired, wrong-context and wrong-capability records before use. |
| AUTH-G08 | Recovery fence clearing | Addressed for M1.5 | Protected restoration is the legal RECOVERY_REQUIRED clearing transition and appends security-transition audit. M1.6 pass 1 then rotates authority lineage after audited restoration. |
| AUTH-G09 | Cross-artifact reconciliation | Addressed for M1.5, extended in M1.6 pass 2 | M1.5 proves RecoveryContext, operator grant, execution authorization, security-state version and restoration command align for protected restoration. Pass 2 extends current execution validation across epoch replacement. |
| AUTH-G10 | Hosted evidence | Pending | Local verification exists for M1.2/M1.3. A hosted Quality run for the final closeout commit remains required before promoting the baseline. |

## Closeout Rule

Before M1.6 exits, each open item above must be either implemented with tests and
linked evidence, or explicitly reclassified as deferred with a narrow scope limit
in source-of-truth, roadmap and conformance records.
