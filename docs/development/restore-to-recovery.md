# Restore-to-Recovery Integration — M2.8

> Dated execution and verification record. Status and remaining-work statements below describe this checkpoint; use the maintained [current source of truth](source-of-truth.md) and [roadmap](roadmap.md) for present claims.

Date: 25 September 2026.
Status: hosted-verified at `7ba585a`.

The operator reconstruction path now restores and verifies data, invokes the
existing M1 recovery bootstrap, and captures a new RecoveryContext with a
one-hour expiry. The bootstrap retains the backup's state and version as its
origin, increments the version, and exposes effective `RECOVERY_REQUIRED`
authority. Ordinary protected effects remain denied while bootstrap is pending.

Historical RecoveryContexts are restored as history. Their IDs cannot replace
the newly captured context for the current bootstrap. A backup taken while an
earlier bootstrap was pending starts a new bootstrap; the old pending flag is
not carried into the target without its original metadata.

The pre-recovery data comparison remains an internal test boundary. The
operator script calls the full reconstruction path and prints the new context
ID only after capture succeeds. If capture fails after bootstrap, the pending
fence remains in place and the command reports failure.

Local checks covered stored NORMAL, DEGRADED, LOCKDOWN and RECOVERY_REQUIRED
states, a backup with a pending bootstrap flag, historical context separation,
protected-effect denial, and capture failure. The real PostgreSQL drill compares
the canonical fixture before bootstrap and then enters recovery. M2.9 will
exercise reconciliation and protected restoration; M2.10 will rotate the epoch.

Hosted [Quality run 36103438929](https://github.com/SkillSpringAI/Gnomon/actions/runs/36103438929)
passed all three jobs with 1,815 tests passed and 28 skipped.
