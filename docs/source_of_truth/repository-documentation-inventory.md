# Repository Documentation Inventory

**Date:** 16 September 2026
**Purpose:** Phase One deliverable for the repository cleanup working plan.
**Status:** Working inventory; classifications must be confirmed against implementation before conversion or movement.

## Classification key

- **CURRENT** — accurate and authoritative in its present role.
- **CONVERT** — useful current authority that should be represented as maintained Markdown.
- **MERGE** — useful content duplicated elsewhere and should be consolidated.
- **UPDATE** — relevant, but claims, links, or status need reconciliation.
- **ARCHIVE** — historically useful, but no longer authoritative.
- **DELETE** — redundant with no meaningful historical value.
- **REVIEW** — authority or status cannot yet be determined.

## Inventory

| File | Classification | Proposed action | Notes |
|---|---|---|---|
| `README.md` | UPDATE | Shorten and reorganize as the project front door | 37.9 KB; contains substantial operations and implementation detail that belongs under `docs/`. |
| `docs/architecture.md` | MERGE / ARCHIVE | Supersede with `docs/architecture/overview.md`; retain the original until final archive review | The new overview reconciles the summary with the implemented package boundaries and labels partial/future capabilities. |
| `docs/byo-api-keys.md` | ARCHIVE / MERGE | Moved to `docs/archive/legacy-designs/byo-api-keys.md`; maintained operational guidance is now `docs/operations/provider-configuration.md` | Useful provider material was reconciled with current API behavior. |
| `docs/conformance/authority-matrix.md` | CURRENT / UPDATE | Move or retain under `docs/development/conformance.md`; repair authority links after conversion | Important evidence map; currently points directly at DOCX source files. |
| `docs/conformance/authority-sources.json` | CURRENT | Retain with conformance material and update paths only when source records move | Machine-readable source manifest used by conformance checks. |
| `docs/conformance/implementation-status.md` | MERGE / UPDATE | Use `docs/development/source-of-truth.md` as the concise current-state reference; retain the verification summary and update cross-links | Detailed verification evidence remains useful, but active current state is now separated from history and roadmap. |
| `docs/conformance/known-gaps.md` | ARCHIVE / MERGE | Moved to `docs/archive/superseded-plans/known-gaps.md`; active gaps are represented in current source of truth and roadmap | It explicitly identifies itself as historical and contains dated baseline claims. |
| `docs/initial-investigation.md` | ARCHIVE / REVIEW | Moved to `docs/archive/legacy-designs/initial-investigation.md` as historical research context | Describes the original investigation hypotheses rather than current implementation authority. |
| `docs/project-plan.md` | ARCHIVE / MERGE | Moved to `docs/archive/legacy-designs/project-plan.md`; active constraints are represented in the roadmap | Earlier project plan overlaps with roadmap and source-of-truth material. |
| `docs/repo-structure.md` | CURRENT / UPDATE | Rewritten in place against the consolidated tree | The page remains a useful navigation aid and now points to maintained documentation areas. |
| `docs/roadmap.md` | ARCHIVE / MERGE | Moved to `docs/archive/superseded-plans/roadmap.md`; maintained future work is now in `docs/development/roadmap.md` | Main future-work document was reconciled into the maintained roadmap. |
| `docs/workspace-verification.md` | ARCHIVE / MERGE | Moved to `docs/archive/legacy-designs/workspace-verification.md`; maintained procedure is now `docs/operations/workspace-verification.md` | Operational procedure was retained and reconciled with current links. |
| `migrations/README.md` | CURRENT / UPDATE | Retain as migration history and link from `docs/operations/migrations.md` | Operational migration guidance remains discoverable and accurate. |
| `docs/source_of_truth/GNOMON_SOURCE_OF_TRUTH.md` | MERGE / ARCHIVE | Moved to `docs/archive/superseded-plans/GNOMON_SOURCE_OF_TRUTH.md` after splitting current state, roadmap, and history | The active current-state, future-work, and completed-history concepts are now separated. |
| `docs/source_of_truth/Gnomon-Architecture-Code-Review-2026-09-15.md` | ARCHIVE | Moved to `docs/archive/completed-slices/Gnomon-Architecture-Code-Review-2026-09-15.md` | Dated review with historical findings; not a current normative specification. |
| `docs/source_of_truth/Gnomon-Next-Two-Slices-2026-09-15.md` | ARCHIVE / MERGE | Moved to `docs/archive/superseded-plans/Gnomon-Next-Two-Slices-2026-09-15.md`; unresolved work is represented in roadmap/current gaps | Superseded planning snapshot. |
| `docs/source_of_truth/Slice 13 Security State Model and Transition Table.md` | CONVERT / UPDATE | Extract current security-state authority into governance docs; retain slice record in development history | Current slice material must be compared with the implemented security state and tests. |
| `docs/source_of_truth/Gnomon Repository Cleanup Working Plan.md` | CURRENT / TEMPORARY | Use as the governing cleanup checklist; archive or remove only at completion | This is the active working plan and should not be treated as product authority. |
| `docs/Gnomon Authority & Constitutional Principles.docx` | CONVERT | Converted verified normative content into `docs/governance/constitutional-principles.md`; archive original after cross-document references are updated | Maintained Markdown preserves the hierarchy, axioms, and implementation-status distinction. |
| `docs/Gnomon System Architecture Authority.docx` | CONVERT | Converted verified architectural content into `docs/architecture/overview.md`; archive original after cross-document references are updated | The maintained overview preserves requirements and distinguishes implemented guarantees. |
| `docs/Gnomon Epistemic & Evidence Authority.docx` | CONVERT | Converted verified epistemic content into `docs/governance/epistemic-authority.md`; archive original after cross-document references are updated | Normative model is preserved and implementation coverage is labeled as partial where required. |
| `docs/Gnomon Memory & State Authority.docx` | CONVERT | Converted verified memory/state content into `docs/governance/memory-authority.md`; archive original after cross-document references are updated | Maintained Markdown preserves authoritative state, history, dependency, rollback, and derived-state distinctions. |
| `docs/Gnomon — Agent Runtime & Tool Authority.docx` | CONVERT / UPDATE | Converted verified runtime content into `docs/architecture/agent-runtime.md`; archive original after cross-document references are updated | Runtime capabilities remain explicitly labeled as implemented, partial, or future. |
| `docs/Gnomon — External Agent Network Authority.docx` | CONVERT / UPDATE | Converted verified network content into `docs/architecture/external-agent-network.md`; archive original after cross-document references are updated | Maintained Markdown preserves the untrusted-participant boundary and labels live-network capabilities as future. |
| `docs/Gnomon — Research Methodology Authority.docx` | CONVERT / UPDATE | Converted verified methodology content into `docs/governance/research-methodology.md`; archive original after cross-document references are updated | Maintained Markdown preserves methodology requirements and labels the current deterministic scope. |
| `docs/Gnomon — Implementation & Conformance Authority.docx` | CONVERT / UPDATE | Converted verified conformance content into `docs/development/conformance.md`; archive original after cross-document references are updated | Maintained Markdown preserves conformance levels, evidence expectations, and release gates. |
| `docs/Gnomon — Persistence & Data Authority.docx` | CONVERT / UPDATE | Converted verified persistence content into `docs/architecture/persistence.md`; archive original after cross-document references are updated | Maintained Markdown reconciles the authority model with current migrations, repositories, and persistence tests. |
| `docs/Security, Audit & Recovery Authority.docx` | CONVERT / UPDATE | Converted verified security, audit, and recovery requirements into `docs/governance/security-authority.md`; add operations/recovery procedure only when implementation evidence exists; archive original after cross-document references are updated | Replacement security authority contains substantial unimplemented requirements and an unresolved security-state vocabulary conflict. |

## Supporting implementation and verification surfaces

These are not documentation artifacts, but they are in scope for the reference and consistency audits:

| Surface | Inventory action |
|---|---|
| `scripts/check_conformance.py` | Keep as the conformance verification entry point; update source paths only after document moves. |
| `scripts/smoke_test.py` | Keep; confirm README and operations docs point to the supported invocation. |
| `scripts/verify_prototype.py` | Keep; identify any documentation references during the reference audit. |
| `scripts/verify_wheel.py` | Keep; document packaging verification under operations/development docs if currently undocumented. |
| `.github/` workflows | Inspect for documentation paths and whether CI actually runs the promised verification stack. |
| `Makefile`, `pyproject.toml`, `migrations/`, `src/`, `tests/` | Use as implementation evidence when validating normative documentation claims. |

## Initial findings

1. No documentation files are safe to delete at inventory time. Several files explicitly preserve dated baselines or authority evidence.
2. The root README is the clearest candidate for shortening; it currently includes detailed provider lifecycle, recovery, workspace, and verification behavior.
3. The conformance matrix and source manifest are valuable current verification artifacts, but their DOCX paths must be preserved or deliberately migrated together.
4. The source-of-truth document is the main consolidation target because it mixes current status, completed slice evidence, open gaps, and future work.
5. The maintained documentation map and architecture, governance, operations, development, and archive tree are now present.
6. The working tree was clean apart from two untracked source-of-truth working documents before this inventory was added: the cleanup plan and the Slice 13 security-state document.

## Phase One completion condition

Phase One is complete when this inventory has been reviewed against the implementation and every significant documentation artifact has an explicit classification and proposed action. No bulk conversion or movement should begin before that review.
