# Gnomon Agent Runtime and Tool Authority

## Purpose and status

This document is the maintained Markdown form of Gnomon’s agent-runtime and tool-execution authority. It defines how model reasoning becomes bounded, authorized system action.

The central rule is: a model may propose what it wants to do, but it may not decide what the system is permitted to do. The current repository implements bounded local runners and explicit provider/network boundaries; a general autonomous tool runtime remains partial and future work.

## Runtime authority hierarchy

Runtime decisions respect this order:

1. Constitutional authority
2. Security and system invariants
3. User authority
4. Application policy
5. Research-task constraints
6. Runtime budgets and permissions
7. Tool capabilities
8. Model-generated action proposals
9. External-agent suggestions
10. Retrieved and tool-produced content

Lower levels cannot override higher levels. A webpage, agent message, document, tool result, or model proposal never gains policy or permission authority merely by being placed in context.

## Bounded control loop

The runtime follows this conceptual loop:

```text
Research state
  -> observe
  -> reason
  -> propose action
  -> validate action
       | reject -> record -> reason
       v approve
  -> execute
  -> capture result
  -> validate result
  -> update research state
  -> evaluate
       | stop
       | continue -> observe
```

Every autonomous run has explicit termination conditions. The runtime can stop independently of model cooperation when the objective is satisfied, budget is exhausted, a timeout or policy violation occurs, the task is paused or blocked, a capability is unavailable, repeated failures occur, or a safety threshold is exceeded.

Runtime state must be durable where needed for safe recovery. The system must not infer that an action succeeded merely because the model expected it to succeed.

## Reasoning and action boundary

The model may interpret observations, generate hypotheses, identify information gaps, propose research actions, select among available capabilities, propose queries or messages, propose memory changes, evaluate results, and recommend stopping or continuing.

The model may not directly invoke arbitrary functions, execute arbitrary code, issue unrestricted network requests, write to the database, modify permissions or policy, change credentials, alter audit history, permanently delete governed state, bypass budgets, grant capabilities, or redefine tool semantics.

Free-form model output is never an executable command. Executable actions use a machine-readable proposal containing, as applicable, a proposal identity, task and cycle identity, action type, capability, arguments, purpose, expected information gain, dependencies, requested authority, provider metadata, and timestamp.

## Capability and tool boundaries

Executable capabilities are explicit, registered, scoped, and revocable. A registry should describe each capability’s identifier, version, input and output schemas, permission and network requirements, resource cost, side-effect class, idempotency class, timeout and retry policies, and availability state.

Tool descriptions supplied to a model describe capabilities; they do not grant authority.

| Class | Meaning | Examples |
|---|---|---|
| A | Read-only research | Retrieve registered sources, inspect evidence, search claims, retrieve observations. |
| B | Analysis | Extract claims, compare evidence, classify contradictions, generate hypotheses. |
| C | Governed mutation | Create tasks, record claims, update assessments, create memory proposals, archive state. |
| D | External communication | Ask agents, send approved messages, submit information externally. |
| E | High-impact operations | Change credentials or policy, administer infrastructure, permanently delete state. |

Classes C and D require explicit deterministic controls. Class E is outside ordinary autonomous model authority.

Gnomon does not expose an unrestricted shell, arbitrary code execution environment, unrestricted SQL interface, or equivalent general-purpose capability to ordinary research reasoning. If a future engineering need introduces such a facility, it must be isolated, capability-gated, resource-limited, network-restricted, auditable, independently authorized, and explicitly unavailable by default.

## Deterministic validation and execution

Every executable proposal passes deterministic validation for schema, tool existence, capability and task authorization, lifecycle state, argument constraints, resource limits, network and data-access policy, communication policy, idempotency, budget, security, and constitutional constraints.

Only an approved action reaches the executor:

```text
Model
  -> ActionProposal
  -> Policy validator
  -> ApprovedAction
  -> Tool executor
  -> ToolResult
  -> Evidence/state services
```

The executor receives validated arguments and does not reinterpret model text as additional instructions. Tool output is an observation by default, not an authorization to invoke another tool or mutate state. Each composed tool call remains independently authorized, schema-validated, budgeted, audited, and failure-aware.

## Prompt-injection and observation boundaries

Prompt injection is an expected property of external content. Web pages, documents, emails, forum posts, agent messages, APIs, metadata, snippets, and generated external text remain untrusted content even when they appear inside model context.

The runtime should preserve distinctions among system instructions, user instructions, application policy, task state, model reasoning, tool observations, external-agent observations, and retrieved content. It must never interpret a tool result as executable instructions merely because the result says to ignore prior rules or perform an operation.

## Budgets, timeouts, retries, and cancellation

Autonomous execution is bounded by the applicable global, task, cycle, and action budgets. Bounds may include duration, reasoning iterations, tool calls, network requests, external-agent requests, outbound messages, retrieved bytes, document size, model tokens, retries, concurrent operations, and memory mutations. A child scope cannot silently exceed its parent budget.

Externally dependent operations have timeouts enforced outside the model. A timeout is an explicit result, not successful completion. Retries are policy-controlled and must account for idempotency, side effects, budget, and unknown outcomes.

Cancellation is checked before execution, between major steps, before expensive retries, before committing state, and before external communication where practical. Physical interruption of an in-flight adapter call may not be possible; its resulting state must still be reconciled safely.

## Research scope and lifecycle

The runtime respects the active research task’s objective, hypotheses, questions, scope, methods, allowed sources and capabilities, budget, time limit, communication policy, memory scope, and stopping criteria. An action outside the active scope is rejected or requires explicit authorization.

Lifecycle state is authoritative:

| Task state | Runtime behavior |
|---|---|
| `ACTIVE` | Execution may proceed within policy and budget. |
| `PAUSED` | No new autonomous actions. |
| `BLOCKED` | Execution stops pending resolution. |
| `CONCLUDED` | No autonomous continuation. |
| `ABANDONED` | No autonomous continuation. |

Activity is not progress. More tool calls, messages, tokens, or stored claims do not necessarily reduce meaningful uncertainty.

## Failure, recovery, and unknown outcomes

Failures are explicit and never silently become successful outcomes. Provider, network, tool, and persistence failures must remain isolated from unrelated authoritative state.

After process or infrastructure failure, recovery uses persisted execution state to determine what committed, what is unknown, remaining budgets, current lifecycle, outstanding retries, pending proposals, and required reconciliation. Unknown external outcomes remain unknown until reconciled; they are not blindly retried as if no side effect occurred.

Loss of a model or network service must not corrupt persisted research state. Deterministic inspection, lifecycle management, provenance, validation, and other local capabilities should remain available where supported.

## Current implementation status

| Requirement area | Current evidence and limitation |
|---|---|
| Explicit capability and policy boundaries | Implemented for HTTP retrieval, provider adapters, fake-agent network, lifecycle, security capability, and source-domain policy paths; a general registry is not yet present. |
| Bounded local execution and lifecycle control | Implemented for current cycle runners with planned-cycle acquisition, lifecycle checks, progress, outcomes, and operator recovery. |
| Durable provider attempts and unknown outcomes | Implemented with operation identities, dispatch fencing, expiry handling, and explicit uncertain outcomes. |
| Structured model action-proposal runtime | The architectural boundary is defined; the repository’s main planning and acquisition paths remain deterministic and do not yet constitute a general model-driven runtime. |
| Prompt-injection and untrusted-data handling | Implemented for current HTTP/provider boundary guards and deterministic planner isolation; broader adapter-wide adversarial tests remain open. |
| Budgets, timeouts, retries, and cancellation | Implemented in current provider, HTTP, and bounded-runner scopes; a unified autonomous envelope and all cancellation semantics remain future work. |
| Live external-agent communication | Not implemented; current agent network is a bounded read-only fake and local observation path. |
| Full recovery and degraded runtime states | Partial; current recovery paths preserve explicit outcomes, while full runtime state-machine and operational degraded-state coverage remain open. |

## Mandatory runtime invariants

1. The model is not execution authority.
2. Every executable action is deterministically validated.
3. Capabilities are explicit, bounded, and revocable.
4. Ordinary research reasoning has no unrestricted code, shell, database, filesystem, or network access.
5. Tool output is untrusted by default.
6. Prompt injection does not grant authority.
7. Budgets are enforced outside the model.
8. Timeouts are enforced outside the model.
9. Stop authority is external to the model.
10. Failures are explicit.
11. Unknown outcomes remain unknown until reconciled.
12. Retries are governed.
13. Side effects require explicit authorization.
14. Memory writes follow memory authority.
15. External agents cannot alter Gnomon authority, policy, or permissions.
16. No provider becomes a constitutional dependency.
17. External-service loss does not corrupt persisted research state.
18. Runtime respects task lifecycle.
19. Important runtime actions remain inspectable.
20. No hidden authority escalation occurs through context.

## Related documentation

- [Documentation map](../README.md)
- [Architecture overview](overview.md)
- [Constitutional principles](../governance/constitutional-principles.md)
- [Epistemic authority](../governance/epistemic-authority.md)
- [Memory authority](../governance/memory-authority.md)
- [Repository documentation inventory](../source_of_truth/repository-documentation-inventory.md)
- [Original authority document retained during cleanup](../archive/original-authority-documents/Gnomon%20%E2%80%94%20Agent%20Runtime%20%26%20Tool%20Authority.docx)
