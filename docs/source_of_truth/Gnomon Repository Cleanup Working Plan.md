# Gnomon Repository Cleanup Working Plan

**Date:** 16 September 2026
**Status:** Temporary working document
**Baseline:** Slice 13 complete
**Purpose:** Guide a repository-wide documentation, structure, and consistency cleanup before further feature development.

> This document is temporary. It should be removed or archived after the cleanup is completed and any lasting decisions have been transferred into the appropriate canonical documentation.

---

## 1. Objective

Bring the Gnomon repository into a state where:

- the root README provides a concise introduction rather than acting as an operations manual;
- current documentation is easy to locate and navigate;
- Markdown is the default format for maintained repository documentation;
- obsolete material is clearly separated from authoritative material;
- historical decisions remain recoverable where useful;
- documentation accurately describes the current implementation;
- source-of-truth material distinguishes current state, completed work, and future work;
- links and references remain valid after restructuring;
- the codebase remains unchanged functionally unless the review identifies a genuine defect.

This is primarily a **repository consolidation pass**, not a new feature slice.

---

# 2. Cleanup Principles

## Preserve before deleting

Do not delete documentation merely because it appears obsolete.

First determine whether it contains:

- architectural reasoning;
- governance decisions;
- historical requirements;
- security assumptions;
- abandoned alternatives;
- implementation constraints;
- evidence useful for reconstructing why the system works as it does.

Material with historical value should move to an archive rather than disappear.

## Current truth must be obvious

A developer, reviewer, or AI agent should be able to distinguish:

1. what Gnomon currently does;
2. what Gnomon guarantees;
3. what is planned;
4. what has already been completed;
5. what is retained only for historical context.

No archived document should plausibly be mistaken for current authority.

## Markdown by default

Repository documentation that evolves alongside code should normally be Markdown.

DOCX should remain only where there is a specific reason to preserve a formatted document artifact.

## Documentation must follow implementation

Where documentation and tested implementation disagree, investigate the discrepancy.

Do not automatically modify the code to satisfy an obsolete document.

Determine which represents the intended current architecture before changing either.

## No unnecessary architectural change

Repository cleanup must not become an excuse for opportunistic refactoring.

Code changes should be limited to:

- fixing discovered defects;
- removing genuinely dead material;
- correcting references;
- improving obvious structural problems where risk is low.

---

# 3. Phase One: Repository Inventory

Before moving or rewriting anything, inventory the repository.

Classify documentation using:

| Classification | Meaning |
|---|---|
| **CURRENT** | Accurate and should remain authoritative |
| **CONVERT** | Current but should move from DOCX or another format to Markdown |
| **MERGE** | Useful content duplicated elsewhere and should be consolidated |
| **UPDATE** | Still relevant but inconsistent with the implementation |
| **ARCHIVE** | Historically useful but no longer authoritative |
| **DELETE** | Redundant and contains no meaningful historical value |
| **REVIEW** | Authority/status cannot yet be determined |

### Inventory targets

Review:

- root `README.md`;
- `docs/`;
- `docs/source_of_truth/`;
- architecture documentation;
- authority documents;
- security documentation;
- persistence documentation;
- research methodology documentation;
- agent/runtime documentation;
- provider documentation;
- workspace/operator documentation;
- migration documentation;
- verification documentation;
- development plans and completed slice records;
- scripts that may have associated documentation;
- references from code or CI into documentation paths.

### Deliverable

Produce a working inventory such as:

```text
FILE                                  STATUS      ACTION
README.md                             CURRENT     SHORTEN
architecture.md                       CURRENT     MOVE/REVIEW
System Architecture Authority.docx    CONVERT     architecture/
Old implementation plan               ARCHIVE     archive/
...
```

Do not begin bulk conversion until this inventory exists.

---

# 4. Phase Two: Establish Documentation Structure

Target structure:

```text
docs/
├── README.md
│
├── architecture/
│   ├── overview.md
│   ├── authority-model.md
│   ├── persistence.md
│   └── agent-runtime.md
│
├── governance/
│   ├── constitutional-principles.md
│   ├── epistemic-authority.md
│   ├── memory-authority.md
│   ├── security-authority.md
│   └── research-methodology.md
│
├── operations/
│   ├── local-development.md
│   ├── provider-configuration.md
│   ├── migrations.md
│   ├── backup-restore.md
│   ├── workspace-verification.md
│   └── verification.md
│
├── development/
│   ├── source-of-truth.md
│   ├── roadmap.md
│   ├── conformance.md
│   └── development-history.md
│
└── archive/
    ├── README.md
    └── ...
```

This structure is a target, not an immutable requirement.

Change it if the inventory shows a simpler structure better represents the repository.

---

# 5. Phase Three: Root README Rewrite

The root README should become the **front door to Gnomon**.

It should explain the project without attempting to document every implementation detail.

### Target sections

```text
# Gnomon

Short description

## Why Gnomon Exists

## Design Principles

## Current Capabilities

## Architecture

## Quick Start

## Basic Workflow

## Project Status

## Documentation

## Development

## License
```

### Move out of README

Detailed explanations concerning:

- provider attempt lifecycle;
- dispatch/recovery semantics;
- database transaction boundaries;
- migration implementation;
- objective review concurrency;
- evidence fingerprints;
- agent comparison internals;
- credential handling internals;
- recovery edge cases;
- audit projection details;
- wheel verification;
- detailed workspace behaviour;

should normally live under `/docs`.

The README may summarize these behaviours and link to the detailed documentation.

### Target

Aim for approximately **8 to 12 KB**, subject to readability.

Do not shorten it merely to hit a number.

---

# 6. Phase Four: Documentation Conversion

Review each DOCX authority document individually.

For each document:

1. determine whether it remains authoritative;
2. compare important claims against the current code;
3. compare it against newer Markdown documentation;
4. identify duplicated material;
5. identify obsolete assumptions;
6. convert relevant content to Markdown;
7. normalize headings and terminology;
8. add internal links where useful;
9. archive the original if historically valuable.

Do **not** mechanically convert obsolete documents and present the resulting Markdown as current authority.

---

# 7. Phase Five: Source-of-Truth Consolidation

Review:

`docs/development/source-of-truth.md`

The document currently contains substantial development history as well as current planning information.

Separate these concepts.

## Current state

Create or retain a concise:

```text
docs/development/source-of-truth.md
```

It should describe:

- current architecture status;
- current guarantees;
- current security posture;
- current implementation slice/state;
- unresolved P0/P1 issues;
- current exit criteria;
- immediate next work.

## Future work

Move future slices and planned capabilities into:

```text
docs/development/roadmap.md
```

## Completed work

Move detailed completed slice history into:

```text
docs/development/development-history.md
```

or an appropriate archive.

Preserve meaningful exit-gate evidence.

Avoid maintaining hundreds of completed checklist items in the active source-of-truth document.

---

# 8. Phase Six: Archive

Create:

```text
docs/archive/README.md
```

It should explicitly state that archived documents are:

- retained for historical context;
- potentially inconsistent with the current implementation;
- non-normative;
- not the correct starting point for understanding current Gnomon behaviour.

Possible subdivisions:

```text
archive/
├── original-authority-documents/
├── superseded-plans/
├── completed-slices/
└── legacy-designs/
```

Do not over-engineer the archive if there are only a handful of files.

---

# 9. Phase Seven: Code and Documentation Consistency Review

Once documentation is reorganized, perform a targeted code review.

Check that documentation claims correspond to:

- actual application boundaries;
- persistence behaviour;
- security state transitions;
- capability policy;
- provider handling;
- memory governance;
- audit behaviour;
- cycle lifecycle;
- agent/network boundaries;
- recovery behaviour;
- API exposure.

Pay particular attention to statements containing words such as:

- always;
- never;
- atomic;
- deterministic;
- fail-closed;
- immutable;
- authoritative;
- bounded;
- guaranteed;
- prohibited.

These claims should have identifiable implementation or test support.

---

# 10. Phase Eight: Reference Audit

Search the entire repository for references to files that were:

- renamed;
- moved;
- converted;
- archived.

Check:

- Markdown links;
- README links;
- code comments;
- CI workflows;
- scripts;
- test fixtures;
- source-of-truth references;
- package metadata;
- contributor/developer instructions.

No active document should depend on an archived document for normative behaviour.

---

# 11. Phase Nine: Verification

After structural changes, run the normal verification stack.

At minimum:

```text
Ruff
mypy
pytest
smoke tests
fresh-database verification
packaging/wheel verification where appropriate
authority/conformance checks
```

Also verify:

- Markdown links resolve;
- application startup remains unchanged;
- migrations remain untouched unless explicitly required;
- no required package resources were accidentally moved;
- no scripts depend on removed paths.

Documentation-only restructuring should not change runtime behaviour.

---

# 12. Cleanup Exit Gate

The cleanup is complete when:

- [x] Repository documentation inventory completed.
- [x] Every significant document has an explicit status.
- [x] Root README has been shortened and reorganized.
- [x] `docs/README.md` provides a clear documentation map.
- [x] Maintained authority documents use appropriate repository-friendly formats.
- [x] Obsolete documents are archived or removed.
- [x] Archive clearly identifies material as non-authoritative.
- [x] Source-of-truth describes current state rather than accumulated history.
- [x] Roadmap is separated from current implementation truth.
- [x] Completed development history remains recoverable.
- [x] Documentation matches the current implementation.
- [x] Security and governance claims have identifiable implementation/test support.
- [x] Internal links and references have been checked.
- [x] No active documentation accidentally references archived material as authority.
- [x] Verification suite passes.
- [x] `git status` contains only intentional changes.
- [x] Final diff has been reviewed before merge.

---

# 13. Things We Are Not Doing Today

Unless the cleanup uncovers a blocking defect:

- no new major feature slice;
- no large architectural rewrite;
- no speculative abstraction work;
- no provider expansion;
- no UI redesign;
- no unrelated refactoring;
- no removal of historical material merely to make the repository smaller.

Today's goal is to make the existing system easier to understand, verify, maintain, and continue developing.

---

# 14. Suggested Working Sequence

Use this sequence during the cleanup:

```text
1. Inventory
2. Classify
3. Design final docs tree
4. Create docs index
5. Convert current authority documents
6. Archive superseded documents
7. Consolidate source-of-truth
8. Extract README detail into docs
9. Rewrite root README
10. Audit code ↔ documentation claims
11. Repair links/references
12. Run verification
13. Review final diff
14. Transfer lasting decisions to canonical docs
15. Remove/archive this working document
```

---

# 15. Final Review Questions

Before declaring the cleanup complete, answer:

**Can a new developer understand what Gnomon is from the README alone?**

**Can they find deeper technical information without searching the entire repository?**

**Can they tell which documents are authoritative?**

**Can they distinguish current implementation from future plans?**

**Can they distinguish current architecture from historical architecture?**

**Can an AI coding agent navigate the repository without treating obsolete documentation as current requirements?**

**Do strong governance and security claims correspond to actual code or tests?**

**Did the cleanup preserve useful architectural history without allowing that history to become current authority?**

If those answers are clear, the repository is ready for the next development phase.
