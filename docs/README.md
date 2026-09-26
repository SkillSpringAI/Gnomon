# Gnomon Documentation

This directory contains the maintained documentation for Gnomon. Start with the root [README](../README.md) for a concise project introduction, then use the areas below for deeper technical and operational material.

## Current documentation map

### Architecture

The architecture area describes the implemented application boundaries, persistence model, and runtime structure.

- [Architecture overview](architecture/overview.md) — current implementation-facing architecture summary.
- [Persistence](architecture/persistence.md) — maintained persistence, migration, and data-integrity rules.
- [Agent runtime](architecture/agent-runtime.md) — maintained runtime, capability, and tool-boundary rules.
- [External agent network](architecture/external-agent-network.md) — maintained agent identity, trust, provenance, and communication boundaries.

### Governance

The governance area describes constitutional, epistemic, memory, security, and research-methodology principles. Normative claims must identify whether they are implemented, partial, designed, or deferred.

- [Constitutional principles](governance/constitutional-principles.md) — maintained root authority summary.
- [Epistemic authority](governance/epistemic-authority.md) — maintained evidence and knowledge distinctions.
- [Memory authority](governance/memory-authority.md) — maintained state, lifecycle, and rollback rules.
- [Security authority](governance/security-authority.md) — maintained security, audit, and recovery requirements.
- [Research methodology](governance/research-methodology.md) — maintained investigation and evidence-gathering rules.

### Operations

The operations area contains local development, provider configuration, migrations, workspace verification, and verification procedures.

- [Provider configuration](operations/provider-configuration.md) — provider selection, credential handling, and usage bounds.
- [Migrations](operations/migrations.md) — migration history, commands, and integrity rules.
- [Workspace verification](operations/workspace-verification.md) — browser and workspace verification procedure.
- Backup and restore — to be added after the documented recovery capability is reviewed.
- Verification — to be added when the normal verification stack is consolidated.

### Development

The development area separates current implementation truth, future work, conformance rules, and completed history. Dated M1/M2 pages are execution and verification records: their status and remaining-work text applies to their original checkpoint, not automatically to the current repository.

- [Source of truth](development/source-of-truth.md) — concise current-state reference.
- [Roadmap](development/roadmap.md) — dependency-ordered future-work reference.
- [Conformance](development/conformance.md) — maintained implementation, evidence, testing, and release-gate rules.
- [Development history](development/development-history.md) — completed slices and meaningful exit-gate evidence.
- [Implementation status](conformance/implementation-status.md) — current verification summary and exact hosted baseline; the [authority matrix](conformance/authority-matrix.md) retains requirement traceability.
- [Architectural invariant verification map](conformance/architectural-invariant-verification.md) — existing tests, coverage limits, and refactoring implications for INV-01–INV-12.

### Archive

Archived material is retained for historical context only. It may conflict with the current implementation, is non-normative, and is not the correct starting point for understanding Gnomon behavior. See the [archive index](archive/README.md) for its categories and handling rules.

## Current source materials during cleanup

The [repository documentation inventory](source_of_truth/repository-documentation-inventory.md) and [cleanup working plan](source_of_truth/Gnomon%20Repository%20Cleanup%20Working%20Plan.md) retain the 16 September cleanup baseline and classifications. The maintained [roadmap](development/roadmap.md) owns current consolidation order; the current source of truth and normative documents above own present claims.

## Navigation rule

When documents disagree, prefer current implementation evidence and the maintained documents in this map. Treat dated reviews, completed plans, and archived material as historical context unless a current document explicitly adopts a decision from them.
