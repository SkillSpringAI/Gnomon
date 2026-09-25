# Reconstruction Reconciliation and Restoration — M2.9

Date: 25 September 2026.
Status: hosted-verified at `15e19d2`.

The canonical PostgreSQL restore drill now continues through the existing M1
services: recovery bootstrap, a new RecoveryContext, read-only reconciliation,
fresh OperatorAuthorization and ExecutionAuthorization, and protected
restoration. It uses the same authorization and restoration contracts as other
recovery paths; no backup-specific grant or fence-clearing path was added.

The baseline fixture must pass reconciliation and restoration. The previously
restored authorizations are tested as historical evidence and cannot replace
fresh authorizations bound to the new context. The restrictive fixture retains
an unknown provider attempt; reconciliation must leave its outcome unknown and
deny restoration even when fresh authorizations have been issued. The recovery
fence remains pending after denial.

Authority Epoch replacement remains M2.10. A successful M2.9 restoration
clears the recovery fence under M1 authority, but this drill does not claim
post-reconstruction execution authority until a fresh epoch is established.

Hosted [Quality run 36104809601](https://github.com/SkillSpringAI/Gnomon/actions/runs/36104809601)
passed all three jobs with 1,815 tests passed and 28 skipped.
