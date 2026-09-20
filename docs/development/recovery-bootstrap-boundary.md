# Recovery/bootstrap entry boundary

Date: 20 September 2026.
Status: implemented for startup entry only.

This boundary distinguishes fresh bootstrap, continuing authority and recovery
bootstrap without implementing RecoveryContext, protected restoration, backup
tooling, external recovery, OperatorAuthorization or a generic epoch-replacement
API. Contracts #1–#5 and the canonical SecurityState vocabulary/transition graph
are unchanged.

## Startup modes

`AUTHORITY_STARTUP_MODE` is a trusted deployment setting with three values:

- `fresh` accepts only a pristine newly migrated PostgreSQL deployment: canonical
  NORMAL/version 1 authority and no task, trusted-source, memory-journal or security-
  transition history. Migration 021 remains the fresh-deployment policy that creates
  ordinary NORMAL authority; fresh mode never resets an existing installation.
- `continuing` validates and loads the current canonical authority without changing
  its state, version or epoch. A pending recovery-bootstrap fence also survives an
  ordinary restart unchanged.
- `recovery` locks the canonical security row before the application can serve a
  request. On first entry it records the restored state/version, sets the durable
  recovery-bootstrap-pending fence and advances the version once. Repeated recovery
  startup is idempotent. It never creates or replaces the Authority Epoch.

The application startup hook completes this boundary before FastAPI admits ordinary
requests. Recovery mode is rejected for the development memory backend because it
cannot provide the persistence guarantee.

## Effective authority during recovery bootstrap

The restored state is retained as historical evidence in the canonical row. While
the pending fence is set, `SecurityStateStore` exposes the effective current state as
`RECOVERY_REQUIRED`; a restored raw `NORMAL` value is therefore not current NORMAL.
Epoch identity is retained only as lineage and grants no permission.

Pending recovery bootstrap permits only the existing safe read, audit, local-report
and diagnostic capabilities. Runtime capability guards additionally deny ordinary
execution/mutation and all directional authority-control capabilities, regardless of
the effective state's baseline matrix. The normal transition service also rejects
state changes while the fence is pending. This slice deliberately provides no
reconciliation or fence-clearing operation.

Consequently restored trusted-source entries, RUNNING cycle attempts, PENDING
provider reservations and other active-looking records remain stored but inert.
They cannot be consumed as current authorization. No startup path dispatches or
reconciles them automatically.

## Evidence and limits

Migration 024 adds the durable fence and its bounded origin metadata, with a database
shape constraint. Unit tests reject inconsistent metadata. Isolated-schema tests
prove a pristine fresh bootstrap, rejection of a history-bearing "fresh" request,
and byte-for-byte state/version/epoch preservation on continuing startup.

The adversarial integration test begins with historical epoch/version 7, raw NORMAL,
an enabled trusted source, a RUNNING cycle attempt, committed evidence/claim history
and a PENDING provider reservation. Recovery startup produces effective
RECOVERY_REQUIRED/version 8 before request handling and proves, before any
reconciliation exists:

- no provider generation or reservation dispatch;
- no source fetch;
- no fake-agent discovery/ask;
- no cycle start;
- no ordinary evidence/memory mutation;
- no security transition or historical provider-authorization consumption.

The records and epoch remain unchanged except for the documented bootstrap fence,
origin metadata, timestamp and single version advance. A following continuing
restart preserves that effective restrictive state, version and epoch.

This is not restoration completion, proof that historical data is trusted, or an
authority grant. No claim is made about backup import, external recovery, human
authentication, recovered configuration activation, credential rotation or clearing
the pending fence.
