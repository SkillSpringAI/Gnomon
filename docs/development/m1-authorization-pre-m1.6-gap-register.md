# M1 Authorization Gap Register

Date: 24 September 2026.
Status: M1.6 hosted closeout checkpoint. This file records the remaining
limitations after the M1.6 exit gate. It does not
authorize restoration beyond the tested local scope.

## Purpose

M1.2 and M1.3 now provide bounded `OperatorAuthorization` and
`ExecutionAuthorization` artifacts, trusted local issuance, append-only persistence,
audit coupling and exact replay validation. The remaining limitations below are
retained as explicit scope boundaries while M1.6 closes its local evidence review,
because stale or incomplete authorization semantics must not leak into restoration.

## Gap Register

| ID | Area | Status before M1.6 | Required disposition before M1.6 exit |
| --- | --- | --- | --- |
| AUTH-G01 | Restoration consumption | Addressed for M1.5 | M1.5 consumes RecoveryContext, M1.4 reconciliation, OperatorAuthorization and ExecutionAuthorization under protected restoration preflight and completion transactions, then clears the fence with audit. M1.6 passes 1-2 add epoch replacement and current execution validation after restoration. |
| AUTH-G02 | Point-of-effect capability | Addressed for local M1 scope | Pass 3 audited the local consumers: restoration and epoch replacement re-read locked current authority for their own effects, and `AuthorizationService.require_current_execution` distinguishes current-use validation from historical replay. Broader future consumers remain outside this slice. |
| AUTH-G03 | RecoveryContext reconciliation | Addressed for M1.5 | M1.4 produces a read-only reconciliation verdict over supported evidence and provider/cycle outcomes. M1.5 consumes that verdict with authorization under one protected restoration transaction. |
| AUTH-G04 | Authority epoch replacement | Addressed for local M1.6 scope | M1.6 rotates the epoch after protected restoration, rejects old execution authorization at the current execution boundary, accepts new-epoch authorization, and records the pass-3 exit-gate evidence map. |
| AUTH-G05 | Authenticated operator identity | Deferred | Current local principal attribution is bounded evidence, not authentication. Multi-user identity can remain deferred only if M1.6 explicitly keeps the local-only scope. |
| AUTH-G06 | Database tamper resistance | Deferred | Application reads fail closed on malformed authorization history, but database-owner rewrites are not cryptographically prevented. M1.6 must not claim stronger guarantees. |
| AUTH-G07 | Expired historical replay | Narrowed limitation | Exact replay can return historical authorization records even after expiry or epoch replacement. Current protected effects now have `require_current_execution`, which fails stale, expired, wrong-context and wrong-capability records before use. |
| AUTH-G08 | Recovery fence clearing | Addressed for M1.5 | Protected restoration is the legal RECOVERY_REQUIRED clearing transition and appends security-transition audit. M1.6 pass 1 then rotates authority lineage after audited restoration. |
| AUTH-G09 | Cross-artifact reconciliation | Addressed for M1.5, extended in M1.6 pass 2 | M1.5 proves RecoveryContext, operator grant, execution authorization, security-state version and restoration command align for protected restoration. Pass 2 extends current execution validation across epoch replacement. |
| AUTH-G10 | Hosted evidence | Addressed for local M1 scope | Local M1.1-M1.6 verification and the pass-3 evidence map are recorded. Hosted Quality run `35981852013` passed for closeout SHA `316c90bf1816743ce73571e907b5c24e4da6cdec`. |

## Closeout Rule

M1.6 is closed for the bounded local recovery-authority scope. Deferred items above
remain narrow scope limits for later milestones, especially M2 backup/reconstruction,
multi-user authentication and cryptographic tamper resistance.
