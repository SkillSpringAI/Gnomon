# Gnomon

Gnomon is a local-first research API for persistent investigations, evidence, claims, hypothesis assessments, bounded research cycles, and traceable reports.

Its central design rule is simple: models and external agents may propose, observe, and reason, but deterministic application code decides what is authorized and what becomes persisted state.

## Why Gnomon exists

Research systems need to preserve more than generated answers. They need to retain what was observed, where it came from, what remains uncertain, which claims conflict, how assessments changed, and why the system took a particular action.

Gnomon provides a structured foundation for that work while keeping providers, networks, and deployment infrastructure replaceable.

## Design principles

- Retrieved content and external-agent messages are untrusted data, not instructions.
- Model output is a proposal, not system authority.
- Accepted knowledge preserves provenance, uncertainty, and support or contradiction relationships.
- Persistent state is governed, versioned where required, and recoverable within defined limits.
- Autonomous execution is bounded, auditable, and allowed to stop safely.
- External providers and network platforms belong behind replaceable adapters.
- Research state, epistemic state, audit history, and derived reports remain distinct.

## Current capabilities

The current implementation supports:

- Investigations with briefs, hypotheses, research questions, plans, bounded cycles, and lifecycle controls.
- PostgreSQL persistence for tasks, sources, claims, provenance, assessments, cycles, reports, audit, and security state.
- Registered-domain HTTP retrieval with redirect, public-network, content-type, size, and deadline controls.
- Conservative deterministic claim extraction and exact evidence/claim reuse on retries.
- Evidence-aware next-cycle planning with persisted reasons, evidence identifiers, reviews, and unresolved objectives.
- Durable cycle attempts, partial-progress retention, operator recovery, and explicit blocked or failed outcomes.
- Governed memory proposals for claims and hypothesis assessments with versions, append-only history, redacted audit metadata, and eligible 48-hour reversal.
- Deterministic snapshots and reports that preserve provenance, uncertainty, limitations, and non-authoritative agent comparison metadata.
- Local rule-based and optional AWS Bedrock provider boundaries with bounded output limits, idempotent attempts, dispatch fencing, and explicit unknown outcomes.
- A bounded fake agent network whose observations can enter ordinary evidence with task-scoped provenance.
- A persisted security-state model and controlled transitions for the current Slice 13 scope.

Live external-agent networks, semantic/vector memory, long-running worker orchestration, full multi-user authentication, complete backup/restore operations, and production-grade autonomous tool execution remain future or partial work.

## Quick start

Requirements: Python 3.11 or newer and Docker with Compose.

```powershell
python -m pip install -e ".[dev]"
docker compose up -d postgres
```

The default local provider requires no model credentials. Optional AWS Bedrock support is installed with:

```powershell
python -m pip install -e ".[dev,aws]"
```

Set `LLM_PROVIDER=bedrock`, `MODEL_ID`, and `AWS_REGION` only when using Bedrock. Keep credentials in the standard AWS credential chain or protected environment variables; never place them in source, research records, prompts, reports, or audit payloads.

Start the API with:

```powershell
python -m research_agent
```

The health endpoint is available at `GET /health`. The CLI and API entry points are defined in `pyproject.toml`.

## Basic workflow

1. Create an investigation with an objective, scope, hypotheses, questions, methods, evidence requirements, and stopping criteria.
2. Register or enable permitted source domains.
3. Add or retrieve source material through the bounded source interfaces.
4. Extract conservative claims and retain their provenance.
5. Inspect the investigation snapshot or deterministic report.
6. Plan and run a bounded next cycle, then review its completed, blocked, or failed outcome.
7. Recover interrupted work explicitly when required; do not assume an in-flight external operation succeeded.
8. Request a provider draft only as a bounded, unpersisted presentation of current research state.

The local workspace exposes a read-only operator surface for reports, bounded drafts, planning, lifecycle controls, reviews, and the local fake-agent cycle. It never accepts credentials.

## Architecture

The repository is organized into API, application, domain, ports, adapters, persistence, configuration, and security boundaries. PostgreSQL is the reference durable store. External models, providers, web retrieval, and agent networks are accessed through explicit boundaries.

See the [architecture overview](docs/architecture/overview.md), [agent runtime](docs/architecture/agent-runtime.md), [external-agent network](docs/architecture/external-agent-network.md), and [persistence authority](docs/architecture/persistence.md).

## Project status

Gnomon is in an implementation-hardening phase. The current baseline has strong local persistence, evidence, lifecycle, provider, audit, recovery, and bounded fake-agent foundations, but it is not a claim of full v0.1 conformance or operational readiness.

Open release work includes backup/restore conformance, security-state authority reconciliation, historical journal compatibility, deeper dependency-aware reassessment, complete operational recovery, hosted CI evidence, and broader external-boundary testing.

PostgreSQL startup defaults to `AUTHORITY_STARTUP_MODE=continuing`. Use `fresh` only
for a pristine newly migrated deployment and `recovery` only to establish the
restrictive recovery-bootstrap fence before requests. Recovery mode has no
reconciliation or fence-clearing operation in the current scope.

The [current source of truth](docs/development/source-of-truth.md) describes the supported implementation and active gaps. The [roadmap](docs/development/roadmap.md) contains future work. The [development history](docs/development/development-history.md) preserves completed slices and verification evidence.

## Documentation

Use the [documentation map](docs/README.md) to find maintained material.

- [Constitutional principles](docs/governance/constitutional-principles.md)
- [Epistemic authority](docs/governance/epistemic-authority.md)
- [Memory authority](docs/governance/memory-authority.md)
- [Security authority](docs/governance/security-authority.md)
- [Research methodology](docs/governance/research-methodology.md)
- [Implementation and conformance](docs/development/conformance.md)
- [Workspace verification](docs/operations/workspace-verification.md)
- [Migration operations](migrations/README.md)
- [Repository structure](docs/repo-structure.md)

Archived documents are retained for historical context only and are explicitly non-authoritative. Start with maintained Markdown in the documentation map rather than the archive.

## Development and verification

Run the normal local checks from the repository root:

```powershell
python -m pytest -ra
python -m ruff check .
python -m mypy src
python scripts/check_conformance.py
python scripts/smoke_test.py
```

The full verification stack also includes PostgreSQL integration, fresh-database migration, packaging/wheel, prototype, and workspace checks where applicable. `scripts/check_conformance.py` verifies authority-source revisions and traceability; it does not establish behavioral or release conformance.

Use `make` targets where available for common local workflows. Do not run live provider or external-agent operations without the required configuration and authorization.

## License
This project is licensed under the Mozilla Public License, version 2.0.

This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this project, you can obtain one at https://mozilla.org/MPL/2.0/.

SPDX-License-Identifier: MPL-2.0

