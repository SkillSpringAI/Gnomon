# Research Agent Architecture

## 1. Logical components

```text
Client
  |
  v
API / CLI
  |
  v
Research Orchestrator
  |-- Planner ------------> LLM provider adapter
  |-- Tool executor ------> Web/source tools
  |-- Claim extractor ----> LLM provider adapter
  |-- Report generator ---> LLM provider adapter
  |-- Network gateway ----> Agent-network adapters
  |
  v
Deterministic application services
  |-- Research task and lifecycle service
  |-- Evidence and provenance service
  |-- Evidence-aware cycle planner
  |-- Audit/event service
  |
  v
PostgreSQL / pgvector       Object storage for raw sources
```

## 2. Request lifecycle

1. The client submits a research brief containing an objective, hypotheses, questions, scope, methods, and stopping criteria.
2. The API validates the brief and creates a persistent research task.
3. The planner creates an initial investigation plan and bounded first cycle.
4. The orchestrator executes only tools allowed by application policy.
5. Retrieved material is stored as source evidence with a content hash and retrieval metadata.
6. The extractor proposes entities, claims, relationships, and confidence values.
7. The provenance service links every claim to one or more sources or explicitly marks it as inference.
8. Deterministic validators accept, reject, or quarantine proposed memory changes.
9. The task service records findings, contradictions, open questions, and the next cycle.
10. The deterministic cycle planner ranks persisted gaps and records a bounded planning basis with relevant IDs.
11. The report generator creates interim or final reports from persisted evidence and claims rather than relying only on conversation context.
12. Audit events make the important decisions and mutations inspectable.

## 3. Core domain objects

### ResearchTask

Represents an ongoing investigation or persistent subtask. It has an objective, thesis or hypotheses, research questions, scope, methods, evidence requirements, stopping criteria, status, priority, parent task, cycle history, timestamps, and result metadata.

### ResearchCycle

Represents one bounded iteration of an investigation. It records the questions selected, tools and agents consulted, observations gathered, claims changed, unresolved gaps, budget, and recommendation for the next cycle.

### HypothesisAssessment

Represents the current state of support for a thesis or competing explanation. It links supporting, contradicting, and unresolved evidence without treating the assessment as a fact.

### Source

Represents raw evidence such as a web page, document, API result, user statement, or agent message. It records origin, retrieval time, content hash, reliability metadata, and storage location.

### Entity

Represents a person, organization, technology, place, event, or other canonical object discussed by claims.

### Claim

Represents a proposition about one or more entities. A claim has a statement, status, confidence, timestamps, and links to supporting or contradicting sources.

### Relationship

Represents a typed link between entities, normally backed by a source claim.

### Memory

Represents reusable semantic or operational context. A memory can later have an embedding, importance, confidence, access history, and archive state.

### Event

Represents a state transition or proposed/accepted memory operation. Events preserve the previous state needed for rollback during the retention window.

## 4. Current service boundaries

The model-facing code should not write directly to the database. Use interfaces similar to these:

```python
class ResearchPlanner(Protocol):
    def create_plan(self, brief: ResearchBrief) -> InvestigationPlan: ...

    def plan_next_cycle(self, task: ResearchTask) -> ResearchCyclePlan: ...

class SourceRetriever(Protocol):
    def fetch(self, target: SourceTarget) -> RetrievedSource: ...

class ClaimExtractor(Protocol):
    def extract(self, source: RetrievedSource) -> ClaimProposalSet: ...

class MemoryRepository(Protocol):
    def apply_proposal(self, proposal: MemoryChangeProposal) -> AppliedChange: ...

class AgentNetwork(Protocol):
    def discover_agents(self, query: AgentQuery) -> list[AgentObservation]: ...
    def ask_agents(self, request: AgentResearchRequest) -> list[AgentObservation]: ...
    def send_message(self, message: OutboundAgentMessage) -> DeliveryResult: ...
```

The current implementation also has explicit application services for evidence,
claim extraction, hypothesis assessment, source-domain policy, snapshots, audit
events, and deterministic cycle planning. PostgreSQL task-row locks serialize
lifecycle changes, evidence writes, assessment replacement, and cycle planning.
The cycle planner reads a task-scoped snapshot, ranks contradictions and missing
assessments before weaker gaps, and stores at most three objectives. It treats
retrieved text as data and never as planning instructions.

The concrete implementations can change without changing the orchestrator or domain model.

## 5. State and event rules

- Create, update, merge, archive, logical delete, and restore are explicit operation types.
- Archive and logical delete retain the prior state.
- Permanent purge is a separate privileged operation and is never an ordinary model tool.
- A merge must record both the source record and target record.
- A rollback must be idempotent and must refuse to overwrite newer incompatible changes silently.
- Every accepted claim must have provenance, even if the provenance is a user statement or model inference.
- Lifecycle changes use compare-and-set expected statuses and are audited in the same transaction.
- New cycles require an active task and retain their planning basis for later review.
- Audit payloads contain IDs and fixed categories, never source text, URLs, credentials, or raw exception messages.

## 6. Adapter rule

Moltbook, web search providers, LLM providers, and storage backends belong behind adapters. The core domain should know that it received an `AgentObservation` or `RetrievedSource`, not how a particular platform formats HTTP requests.

## 7. Provider credentials

LLM credentials are supplied through deployment configuration or a future user session and are never part of research state. The provider adapter receives a secret through a protected configuration boundary, while tasks, sources, claims, reports, and audit events store only non-secret provider metadata such as provider name and model identifier.
