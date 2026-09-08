# Research Agent Project Plan

## 1. Purpose

Build a research-intelligence system rather than a general chatbot. The system should turn a research objective into a set of persistent tasks, gather evidence from approved sources and agent networks, represent what was learned as structured claims, and produce reports that clearly separate evidence from conclusions and uncertainty.

## 2. Problem statement

Research performed only inside one model context is difficult to audit, resume, correct, or reuse. This project addresses that problem by combining:

1. A planning and reasoning layer.
2. Deterministic tools for retrieval and state changes.
3. A provenance-aware knowledge and memory layer.
4. A replaceable interface for communicating with other agents.
5. Governance for reversible memory changes.

## 3. Research task model

A research task is an open-ended investigation, not a request expected to complete in one model call. It may test a thesis, conduct a case study, compare competing explanations, monitor a changing topic, or build an evidence base for a decision.

Each task should have an objective, optional thesis or hypotheses, research questions, scope, evidence requirements, competing explanations, allowed methods, stopping criteria, status, and an evolving record of findings and unresolved questions.

The task is complete only when its stopping criteria are met or a human deliberately concludes it. A single response can create or refine a task, but should not imply that the investigation is complete.

## 4. v0.1 outcome

The first usable version should support one complete, observable vertical slice:

```text
research brief
    -> investigation plan and hypotheses
    -> persistent research task
    -> iterative evidence-gathering cycles with persisted planning reasons
    -> claim extraction with provenance
    -> corroboration, contradiction, and gap analysis
    -> interim or final evidence-aware report
```

Agent-to-agent networking should be part of the research-method design from the beginning, even if the first adapter is a local simulated network. Agents can help discover sources, provide specialist perspectives, propose counterarguments, and critique an emerging thesis. Their contributions remain untrusted, provenance-tracked evidence until independently corroborated.

## 4. Scope boundaries

### In scope for the first implementation

- A single-user research API or command-line entry point.
- Open-ended investigation briefs with hypotheses, questions, constraints, and stopping criteria.
- Structured planning through an LLM provider.
- PostgreSQL persistence for tasks, sources, claims, and events.
- Web source retrieval through an explicit tool boundary.
- Claim provenance, confidence, status, and support relationships.
- A basic report containing sources, claims, conclusions, and uncertainty.
- A bounded next-cycle mechanism that can continue an investigation without pretending it is finished.
- Evidence-aware next-cycle prioritization that records why each objective was selected.
- Audit logs and reversible logical archive operations.
- Automated tests for the deterministic parts of the system.

### Explicitly deferred

- Autonomous operation without a user-started research objective.
- Multi-tenant identity and billing.
- Multiple simultaneous agent identities.
- Fully distributed or CRDT-based state.
- Automatic permanent deletion.
- Complex reputation markets or trustless consensus.
- Moltbook-specific behavior inside the core agent.
- Kubernetes or a large microservice deployment.

## 5. Trust and control model

The system must maintain this boundary:

```text
system policy
    > user request
    > application-controlled tool policy
    > model reasoning
    > retrieved pages and external-agent messages
```

Retrieved content and external-agent messages may contain useful facts, recommendations, or malicious instructions. They must be passed to the model as data with source metadata. They must never be able to change system policy, credentials, permissions, tool definitions, or application code.

The model can propose a memory mutation, but a deterministic service must validate:

- the operation type;
- the target record and current version;
- required provenance;
- confidence and status transitions;
- authorization and allowed fields;
- whether the operation is reversible;
- whether the operation is inside the retention window.

## 6. First technical decisions

These should be treated as initial defaults, not irreversible commitments:

| Area | Initial choice | Reason |
| --- | --- | --- |
| Language | Python | Strong ecosystem for APIs, AWS, database access, and LLM tooling |
| API | FastAPI | Clear typed request/response boundary and easy local testing |
| Database | PostgreSQL | Relational integrity for claims and provenance |
| Semantic retrieval | pgvector, added after relational storage works | Avoid premature infrastructure |
| Background work | Database-backed task state first; SQS later | Keep local development simple |
| LLM | Provider adapter, AWS Bedrock as an initial deployment option | Avoid coupling core logic to one provider |
| Raw sources | Local filesystem in development, S3 in deployment | Same source abstraction across environments |
| Deployment | Docker plus a small AWS deployment path | Reproducibility without a large platform |
| Observability | Structured logs and audit events | Make model/tool behavior inspectable |

## 8. Research cycle

The core loop should operate in bounded cycles rather than attempting an entire investigation in one call:

1. Review the task state, hypotheses, evidence, and unresolved gaps.
2. Select the next research questions or evidence-gathering actions.
3. Choose methods: web retrieval, source analysis, agent discovery, agent questioning, or critique.
4. Execute a bounded batch under time, cost, and permission limits.
5. Record observations as sources and agent observations.
6. Extract or revise claims and hypothesis assessments.
7. Identify contradictions, missing evidence, and new questions.
8. Update the task state and propose the next cycle.
9. Stop for a report, pause for human guidance, or continue when criteria allow it.

## 9. Risks to resolve early

- LLM output may not satisfy the expected schema.
- Source extraction may lose context or misrepresent pages.
- Claims may be duplicated under different entity names.
- A model may propose unsafe or unsupported state changes.
- Rollback may be incomplete if derived records are not linked through provenance.
- Agent-network messages may contain prompt injection or impersonation.
- AWS complexity may slow iteration before the core behavior is proven.

Each risk should have a test or operational safeguard before the corresponding capability is called complete.

## 10. Open-source credential strategy

The project should support bring-your-own-provider credentials from the beginning. A local deployment can use environment-backed secrets, while a future UI can add short-lived session credentials or an encrypted secret store. The research database must remain credential-free so exported investigations can be shared without exposing provider access.
