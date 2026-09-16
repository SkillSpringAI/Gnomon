# Repository Structure

The repository is organized around a small Python application and a documentation split between maintained architecture/governance material, operational procedures, development truth, and historical archive.

```text
concept docs/
├── README.md
├── pyproject.toml
├── scripts/                         # verification and maintenance commands
├── migrations/                      # migration notes; SQL is packaged under src
├── src/research_agent/
│   ├── api/                         # application factory and HTTP routes
│   ├── config/                      # environment-backed settings and secrets
│   ├── domain/                      # business concepts and response models
│   ├── application/                 # research, evidence, planning, audit services
│   ├── ports/                       # replaceable repository/provider protocols
│   ├── adapters/                    # LLM and web integrations
│   ├── persistence/                 # SQLAlchemy models, sessions, repositories
│   └── security/                    # security boundaries under active development
├── tests/
│   ├── unit/
│   └── integration/                 # API, persistence, audit, lifecycle, planning
└── docs/
    ├── architecture/                # current implementation-facing architecture
    ├── governance/                  # maintained normative principles and limits
    ├── operations/                  # provider, migration, and workspace procedures
    ├── development/                 # source truth, roadmap, conformance, history
    ├── conformance/                 # evidence and verification records
    ├── source_of_truth/              # cleanup artifacts and current slice evidence
    └── archive/                      # historical, non-authoritative material
```

## Boundary rules

- `domain` defines business concepts without provider or database imports.
- `ports` defines replaceable interfaces; adapters integrate external systems.
- `persistence` owns database mapping and repository implementation.
- Some evidence, assessment, registry, and snapshot services query SQLAlchemy directly; new repository ports should be added when another implementation is needed.
- Snapshot reads use a consistent transaction and do not generate or update research conclusions.
- Cycle planning is deterministic, consumes a persisted snapshot, and records only fixed reasons and relevant IDs.
- Allowlisted, redacted audit events share transactions with evidence, lifecycle, and planning writes.
- Deployment infrastructure, multi-user authentication, live agent networking, and advanced synthesis remain future work unless a maintained document says otherwise.

For navigation, use the [documentation map](README.md). For implementation status and evidence, use [development conformance](development/conformance.md) and the [source-of-truth summary](development/source-of-truth.md).
