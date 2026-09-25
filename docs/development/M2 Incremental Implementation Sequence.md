# M2 Incremental Implementation Sequence

**Purpose:** Break M2 into bounded implementation slices while preserving the dependency order defined by the M2 authority document.

---

# M2.0 — M1 Closeout Synchronization

Documentation-only unless review finds a defect.

Update canonical docs to record:

- M1 closeout SHA: `316c90bf1816743ce73571e907b5c24e4da6cdec`
- Hosted Quality run: `35981852013`
- `checks`: success
- `minimal-install`: success
- `browser`: success

Promote M1 from “hosted pending” to “hosted verified for the current local scope.”

Do not alter runtime behavior during this slice.

### Exit

Canonical source-of-truth, roadmap, M1.6 document and gap register agree.

---

# M2.1 — Backup Manifest Domain Contract

Implemented locally: [Backup Manifest](backup-manifest.md) defines frozen v1
manifest metadata and negative contract coverage. No backup execution occurs in
this slice.

Implement domain-only structures first.

Add bounded models for:

- BackupManifest
- BackupDatabaseMetadata
- BackupApplicationMetadata
- BackupSchemaMetadata
- BackupMigrationEntry
- BackupAuthorityMetadata
- BackupIntegrityMetadata

Requirements:

- manifest version fixed to v1;
- non-nil backup ID;
- UTC timestamp;
- PostgreSQL major version;
- ordered migration records;
- SHA-256 digest format validation;
- valid Authority Epoch;
- valid security state/version;
- no arbitrary extra authority-bearing fields.

No `pg_dump` execution yet.

### Tests

Cover malformed:

- UUID;
- timestamp;
- database engine;
- PostgreSQL version;
- migration entry;
- checksum;
- dump hash;
- Authority Epoch;
- security-state value/version.

### Exit

Manifest serialization/deserialization is deterministic and fully bounded.

---

# M2.2 — Backup State Inspection

Implemented locally: [Backup State Inspection](backup-state-inspection.md)
describes PostgreSQL, migration, application and authority metadata in a
repeatable-read read-only transaction. No backup execution occurs in this slice.

Create a read-only service that gathers the metadata required to build a manifest.

Read:

- PostgreSQL server major version;
- migration table and checksums;
- canonical security state;
- current Authority Epoch;
- current package/source revision through an explicitly supplied build value rather than Git shell dependence where practical.

The service must not mutate application state.

### Tests

- valid populated database;
- missing migration table;
- malformed migration history;
- missing security state;
- invalid epoch;
- unsupported PostgreSQL major.

### Exit

Gnomon can deterministically describe the state that would be backed up.

---

# M2.3 — Backup Creation Boundary

Implemented locally: [Backup Creation Boundary](backup-creation.md) creates a
complete `database.dump` plus `manifest.json` set through a trusted service and
operator script. Publication is atomic at the backup-directory level; failed
stages remove temporary output.

Implement one trusted operator backup command/script.

Recommended initial location:

```text
scripts/backup_postgres.py
```

or an equivalent CLI entry point if CLI integration is cleaner.

Responsibilities:

1. validate backup-state inspection;
2. generate backup ID;
3. invoke `pg_dump` custom format;
4. compute dump SHA-256;
5. create canonical manifest;
6. write into a newly created backup directory;
7. fail without publishing a complete backup set if any stage fails.

Do not store database credentials in arguments, manifest or application audit.

Prefer protected PostgreSQL credential mechanisms/environment.

### Important

Avoid shell interpolation.

Invoke subprocess arguments as a list.

### Tests

Use mocked process invocation for unit behavior plus one PostgreSQL integration backup.

Test:

- pg_dump failure;
- output write failure;
- digest generation;
- existing destination collision;
- malformed source state;
- no half-valid manifest publication.

### Exit

A populated test database can produce a valid dump + manifest pair.

---

# M2.4 — Restore Preflight

Implemented locally: [Restore Preflight](restore-preflight.md) validates
`manifest.json`, `database.dump`, target PostgreSQL/schema compatibility,
migration checksum compatibility and pristine target state before any
`pg_restore` execution. A freshly migrated target may retain only canonical
migration metadata and the singleton security-state row.

Implement validation before `pg_restore`.

Validate:

- manifest version;
- dump hash;
- PostgreSQL major compatibility;
- migration compatibility;
- source revision metadata;
- Authority Epoch metadata shape;
- target database emptiness/pristine status.

Restore MUST refuse a populated target.

No application authority change occurs here.

### Tests

Include:

- hash mismatch;
- malformed manifest;
- future PostgreSQL major;
- newer unsupported schema;
- altered migration checksum;
- populated target.

### Exit

Invalid reconstruction input is rejected before import.

---

# M2.5 — Database Reconstruction

Implemented locally: [Database Reconstruction](database-reconstruction.md)
restores backup data into a preflighted pristine target through `pg_restore`
with data-only, single-transaction, owner/privilege-disabled execution. It keeps
the target migration ledger, applies manifest authority metadata only after a
successful restore and verifies critical table accessibility. Recovery startup,
equivalence and epoch rotation remain later slices.

Implement restore into a clean target.

Use `pg_restore` with:

- ownership restoration disabled;
- privilege restoration disabled;
- explicit target database;
- failure surfaced directly.

After import:

1. verify migration table;
2. verify canonical security state;
3. verify Authority Epoch;
4. verify critical table accessibility;
5. run allowed forward migrations if the compatibility policy permits them.

Do not start ordinary application authority yet.

### Tests

Use a real PostgreSQL integration fixture.

Test:

- complete restore;
- interrupted/failed restore;
- malformed restored authority row;
- missing migration history.

### Exit

Restored database is structurally valid but still not authorized for ordinary execution.

---

# M2.6 — Canonical Reconstruction Fixture

Implemented locally: [Canonical Reconstruction Fixture](canonical-reconstruction-fixture.md)
seeds a compact source database with every M2 authority/history family needed
for later reconstruction comparison, plus a restrictive/unresolved variant for
LOCKDOWN and unknown operation coverage.

Build one intentionally rich source database fixture.

Populate:

- investigation;
- multiple cycles;
- sources;
- claims;
- provenance;
- assessments;
- source dependence plus history;
- memory mutation/history;
- stopping decision/history;
- cycle attempt;
- provider attempt;
- security transition history;
- RecoveryContext history;
- OperatorAuthorization history;
- ExecutionAuthorization history;
- audit events.

Include at least one restrictive or unresolved condition in dedicated test variants.

Do not make the fixture enormous.

Its purpose is coverage, not scale testing.

### Exit

Fixture exercises every authority/history family required by M2.

---

# M2.7 — Reconstruction Equivalence Verifier

Implemented locally: [Reconstruction Equivalence Verifier](reconstruction-equivalence-verifier.md)
adds deterministic projection helpers for every M2 comparison group plus
snapshot/report projections for the canonical fixture task. The baseline and
restrictive/unresolved backup -> restore equivalence drills passed hosted
Quality at `a75e47a`.

Create deterministic comparison helpers.

Compare canonical source and restored projections.

Avoid raw database dumps or row serialization where ordering is undefined.

Compare by stable keys/order.

Required projection groups:

- research;
- evidence/provenance;
- assessments;
- source dependence;
- memory;
- stopping;
- execution attempts;
- provider attempts;
- audit;
- security/epoch;
- recovery/authorization;
- migration state.

Also compare deterministic snapshots and reports.

### Exit

Pre-recovery reconstructed state is demonstrably equivalent to source state within documented exclusions.

---

# M2.8 — Restore-to-Recovery Integration

Implemented locally: [Restore-to-Recovery Integration](restore-to-recovery.md)
uses the M1 startup bootstrap and captures a new RecoveryContext after verified
reconstruction. Hosted Quality passed at `7ba585a`.

Connect reconstruction to M1.

After database reconstruction:

1. application starts in recovery mode;
2. recovery bootstrap becomes pending;
3. original state/version are retained as bootstrap origin;
4. normal protected effects remain denied;
5. new RecoveryContext is captured.

Historical RecoveryContexts restored from backup must not substitute for the new reconstruction context.

### Tests

Cover backups whose stored state was:

- NORMAL;
- DEGRADED;
- LOCKDOWN;
- RECOVERY_REQUIRED.

### Exit

Every reconstructed deployment enters governed recovery before normal authority.

---

# M2.9 — Reconstruction Reconciliation and Restoration

Implemented locally: [Reconstruction Reconciliation and Restoration](reconstruction-reconciliation-restoration.md)
extends the canonical restore drill through the existing M1 authority services.
Hosted Quality passed at `15e19d2`.

Use existing M1 services without bypasses.

Test:

```text
restore
→ recovery bootstrap
→ RecoveryContext
→ reconciliation
→ OperatorAuthorization
→ ExecutionAuthorization
→ protected restoration
```

Unknown provider/cycle outcomes must remain unknown and block restoration where required.

Do not add “backup special-case” authority that skips M1.

### Exit

Reconstruction follows the same restoration authority as other recovery.

---

# M2.10 — Mandatory Reconstruction Epoch Rotation

After successful protected restoration:

1. invoke M1.6 Authority Epoch replacement;
2. preserve old epoch on historical records;
3. create new epoch;
4. reject restored old-epoch authorization for current effects;
5. permit freshly issued new-epoch execution authorization.

### Tests

Explicitly verify:

- old authorization can still be read historically;
- exact historical replay remains history only;
- `require_current_execution` rejects old epoch;
- new epoch authorization works.

### Exit

Reconstructed deployments never silently continue old execution authority.

---

# M2.11 — Credential Sentinel Verification

Set known fake secret sentinels through every supported runtime credential path.

Perform:

```text
populate
→ backup
→ restore
→ inspect database
```

Assert sentinels are absent from every persisted field reviewed by M2.

At minimum test:

- AWS credential sentinel;
- provider bearer/session sentinel;
- database password sentinel where safely simulated.

Search:

- research records;
- evidence;
- claims;
- reports;
- audit;
- RecoveryContexts;
- authorization records;
- provider-session audit;
- command metadata;
- manifest.

### Exit

No reviewed credential sentinel survives into persistent backup material.

---

# M2.12 — Adversarial Reconstruction Matrix

Add negative reconstruction scenarios:

- manifest tampering;
- dump tampering;
- migration checksum drift;
- missing migration row;
- malformed security state;
- nil epoch;
- stale reconstruction authorization;
- unresolved external attempt;
- stale RecoveryContext;
- restoration audit failure;
- epoch replacement audit failure;
- repeated reconstruction recovery command;
- interrupted restore.

Each must fail closed without manufacturing current NORMAL authority.

---

# M2.13 — Operational Procedure

Create maintained documentation:

```text
docs/operations/backup-restore.md
```

Document exact supported operator sequence.

Separate:

### Backup

How to create and validate backup.

### Restore

How to reconstruct into a clean PostgreSQL target.

### Recovery

How to start Gnomon in recovery mode.

### Restoration

How M1 authority completes the reconstruction.

### Verification

How to prove post-restore equivalence and new Authority Epoch.

Include explicit unsupported cases.

---

# M2.14 — Hosted Closure

Run:

- focused M2 tests;
- full pytest;
- Ruff;
- strict mypy;
- migration verification;
- smoke;
- prototype verification;
- wheel verification;
- browser suite;
- conformance checker;
- hosted Quality.

Update:

- `source-of-truth.md`;
- `roadmap.md`;
- `implementation-status.md`;
- authority matrix where applicable;
- development history.

### M2 Exit

Do not close M2 merely because `pg_restore` succeeds.

M2 closes when reconstruction, recovery authority, equivalence, credential exclusion and fresh Authority Epoch establishment are all verified.
