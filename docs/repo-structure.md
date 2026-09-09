# Repository Structure

The current implementation uses these boundaries:

```text
concept docs/
├── README.md
├── pyproject.toml
├── .env.example
├── docker-compose.yml
├── Makefile
├── migrations/                  # Six ordered SQL scripts; no migration runner yet
├── src/research_agent/
│   ├── api/
│   │   ├── app.py               # Application composition
│   │   └── routes/              # Investigations, evidence, assessments, reports, provider, events, snapshots, registry, health
│   ├── cli.py                  # API startup guidance
│   ├── config/                 # Environment-backed settings and provider secrets
│   ├── domain/
│   │   ├── research.py         # Investigation, evidence, lifecycle, and cycle-planning models
│   │   ├── events.py           # Allowlisted audit event types and payloads
│   │   └── snapshot.py         # Snapshot response models
│   ├── application/            # Research, evidence, extraction, assessment, registry, snapshot, audit, planning services
│   ├── ports/                  # Task repository, retrieval, extraction, and LLM protocols
│   ├── adapters/
│   │   ├── llm/                # Rule-based extractor, report providers, AWS Bedrock adapters
│   │   └── web/                # HTTP retriever and public-address transport
│   ├── persistence/            # SQLAlchemy models, engine/session factory, task repository
│   └── security/               # Placeholder; dedicated security services are not implemented
├── tests/
│   ├── unit/
│   └── integration/            # PostgreSQL API, persistence, audit, lifecycle, and planning contracts
└── docs/
```

## Boundary rules and current compromises

- `domain` defines business concepts and response models without provider or database imports.
- `ports` defines replaceable interfaces. `ResearchService` accepts the task repository protocol,
  implemented by both PostgreSQL and the in-memory test repository.
- `adapters` integrates external systems and contains the local deterministic extractor.
- `persistence` owns database mapping and task repository implementation.
- Evidence, assessment, registry, and snapshot services currently query SQLAlchemy directly.
  Extract additional repository ports when another implementation is needed, rather than
  adding empty abstractions for every table now.
- The snapshot route owns a consistent read transaction; its service bulk-loads task-scoped
  evidence and assembles the response. It does not generate or update research conclusions.
- The cycle planner is deterministic and consumes a persisted snapshot. It records no source
  text in planning metadata; each objective stores only a fixed reason and relevant IDs.
- Audit events are allowlisted and redacted. Evidence, lifecycle, and planning writes share
  the transaction that changes state, so an audit failure rolls the state change back.
- The application factory and route dependencies compose services and close sessions.
- Add modules and folders when a real boundary emerges. Deployment infrastructure,
  multi-user authentication, agent networking, and advanced synthesis remain future work.
