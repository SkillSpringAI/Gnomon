# Gnomon External Agent Network

## Purpose and status

This document is the maintained Markdown form of Gnomon’s external-agent network authority. It defines how Gnomon discovers, identifies, communicates with, evaluates, isolates, and learns from external agents.

External agents are untrusted research participants, not authorities over Gnomon. They expand the information environment without expanding the authority hierarchy. The current repository implements a bounded fake/read-only network and local agent-observation path; live external networks and outbound communication remain future work.

## Authority boundary

The authority relationship is:

```text
Gnomon constitution
  -> security and policy
  -> agent-network policy
  -> agent adapter/gateway
  -> external agent
```

The reverse flow never applies. An external agent cannot grant itself authority, change Gnomon policy, alter permissions, authorize another agent, change the user’s objective, bypass validation, or issue system commands through natural language.

## Replaceable network architecture

External platforms are accessed through replaceable adapters behind an `AgentNetwork` boundary. The core domain represents platform-neutral concepts such as agent, identity, observation, request, response, capability, and reliability observation rather than adopting a platform’s schema as Gnomon ontology.

```text
Gnomon
  -> AgentNetwork / gateway
       -> platform adapter A
       -> platform adapter B
       -> platform adapter C
            -> external agents
```

Gnomon’s research methodology remains useful if the agent network disappears. Web evidence, academic evidence, official records, user-provided evidence, and local deterministic research remain independent channels.

## Identity, trust, and reliability

Gnomon distinguishes platform identity, network identity, declared identity, observed identity, and cryptographic identity where available. An identity claim is not automatically verified; authentication establishes identity, not truthfulness.

An unknown agent begins with:

```text
identity: observed
trust: unknown
reliability: unknown
authority: none
```

Unknown does not mean malicious or trustworthy. It means that Gnomon lacks sufficient evidence to characterize reliability.

Reliability and reputation are contextual, evidence-based, revisable, time-sensitive, and domain-sensitive. Useful dimensions may include source-identification accuracy, factual accuracy, citation accuracy, prediction accuracy, research usefulness, counterevidence quality, domain reliability, prompt-injection behavior, and communication reliability.

Reliability influences epistemic evaluation only. Even a highly reliable agent cannot change policy, approve tools, alter permissions, write memory directly, disable security, or authorize another agent.

## Agent observations and provenance

An external response enters Gnomon as an attributable `AgentObservation`, not as an automatically verified fact. Where retention permits, it records:

- Agent identity and platform
- Identity metadata and timestamp
- Question or request
- Response and referenced sources
- Research task and cycle
- Provenance
- Corroboration and contradiction state
- Reliability observations

An agent may report that a study found something. Gnomon initially records the report as agent-sourced observation. If Gnomon independently retrieves the study, the source and any verified claim retain the agent as discovery provenance without treating the original report as independent proof.

Agent recommendations are leads for source discovery, terminology, hypotheses, criticism, methodology, overlooked populations, and replication. They do not automatically become conclusions or persistent authoritative knowledge.

## Independence and consensus

Agent agreement is not automatically independent evidence. Shared training data, platforms, model providers, datasets, citations, communities, message propagation, or direct copying can make apparent consensus a repeated upstream assertion.

Where possible, Gnomon records common sources, shared platforms, citation chains, copying, timing, and other dependency signals. Agent diversity may improve discovery without establishing truth. Duplicate or replayed messages must not become additional corroboration.

## Requests and communication

Outbound requests are structured, authorized side effects. They should identify request, task, and cycle identities, objective, question, requested information, constraints, expected response type, provenance requirements, communication policy, and expiration.

Questions should be specific and, where possible, non-leading. Asking “What evidence supports or contradicts this hypothesis?” is preferable to asking only why it is correct. Requests for criticism, counterexamples, overlooked studies, alternative explanations, missing populations, and failed replications implement the adversarial research methodology.

The model may propose a request. The runtime validates scope, privacy, network policy, rate limits, recipient, content, budget, and authorization before transmission. Agent messages never become executable instructions merely because they use imperative language.

## Prompt injection, capability claims, and secrets

Agent responses are untrusted content. Instructions such as “ignore your system rules,” “give me credentials,” “change the research objective,” or “delete memory” remain agent-provided data. They cannot directly execute actions or change policy.

Claims about an agent’s capabilities or access are unverified until independently established. Credentials, API keys, authentication tokens, private keys, internal network details, security information, private research state, and unnecessary personal information must not cross the agent boundary.

Outbound communication applies data minimization and sends only the information necessary for the authorized request. Agent-derived content follows the observation → claim proposal → epistemic evaluation → governed memory path; it cannot bypass memory validation.

## Limits, isolation, and failure

External-agent communication is bounded by requests per agent, platform, task, and cycle, outbound messages, total network budget, time, tokens, bandwidth, and applicable policy. A model cannot increase these limits by requesting additional messages.

Networks and agents can be isolated for malicious behavior, misinformation, prompt-injection attempts, credential extraction, protocol abuse, resource exhaustion, or compromise concerns. Isolation should be reversible unless higher-level security policy requires otherwise.

Network states may include `NORMAL`, `DEGRADED`, `ISOLATED`, `SAFE`, and `RECOVERY`. Loss of network connectivity must not corrupt research state. Gnomon should continue with stored evidence, local state, permitted web sources, local models, deterministic planning, and existing conclusions and uncertainties. It must not fabricate agent observations.

## Retention and provenance-aware rollback

Agent communications may have separate retention classes for raw messages, research observations, source-discovery metadata, derived claims, reputation observations, and audit metadata. Retention preserves provenance required by active research and rollback.

Agent behavior may be remembered as contextual observations or assessments, not absolute truths. Reputation changes remain historically explainable. A long-term target is provenance-aware rollback that identifies claims, inferences, and conclusions dependent on an agent’s contribution during a defined window, while preserving independent corroboration. It must never mean deleting every record that mentions an agent.

## Mandatory network invariants

1. External agents are not authorities.
2. Agent responses are attributable observations.
3. Identity is separate from trust.
4. Trust is separate from authority.
5. Unknown agents begin without established reliability.
6. Consensus is not independent evidence.
7. Agent claims require epistemic evaluation.
8. Agent recommendations are leads.
9. Network actions are governed actions.
10. Agent messages are untrusted content.
11. Secrets never cross the agent boundary.
12. Agent diversity does not guarantee truth.
13. Provenance survives retained agent contributions.
14. Agent contributions remain reassessable.
15. Reputation is contextual and revisable.
16. Reputation cannot authorize.
17. Network failure is safe for persisted research state.
18. Problematic agents and networks can be isolated.
19. Agent-originated memory is governed.
20. Provenance-aware rollback remains an architectural requirement.

## Current implementation status

| Requirement area | Current evidence and limitation |
|---|---|
| Platform-neutral agent identity, question, observation, and response objects | Implemented as a domain contract. |
| Bounded fake/adversarial network | Implemented with deterministic scenarios and local policy tests. |
| Agent observations as evidence | Implemented through persisted agent-message evidence with task-scoped provenance, audit events, and report comparison metadata. |
| Live network adapters, discovery, authentication, outbound messaging, and delivery status | Not implemented. |
| Consensus, independence, and reliability modeling | Current reports expose agreement, contradiction, duplicate, and distinct-agent metadata; richer dependency and reputation models remain future work. |
| Rate limits, isolation, privacy validation, replay protection, and degraded network states | Architectural requirements; broad external-network enforcement remains unimplemented with no live network enabled. |
| Agent-derived memory and provenance rollback | Governed memory paths exist for current claims and assessments; full agent-scoped dependency propagation and rollback remain open. |

The [agent runtime](agent-runtime.md), [epistemic authority](../governance/epistemic-authority.md), [research methodology](../governance/research-methodology.md), [memory authority](../governance/memory-authority.md), and [conformance records](../conformance/implementation-status.md) provide supporting evidence and limitations.

## Related documentation

- [Documentation map](../README.md)
- [Architecture overview](overview.md)
- [Agent runtime](agent-runtime.md)
- [Epistemic authority](../governance/epistemic-authority.md)
- [Research methodology](../governance/research-methodology.md)
- [Memory authority](../governance/memory-authority.md)
- [Repository documentation inventory](../source_of_truth/repository-documentation-inventory.md)
- [Original authority document retained during cleanup](../archive/original-authority-documents/Gnomon%20%E2%80%94%20External%20Agent%20Network%20Authority.docx)
