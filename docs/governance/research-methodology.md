# Gnomon Research Methodology

## Purpose and status

This document is the maintained Markdown form of Gnomon’s research methodology authority. It defines how Gnomon plans investigations, acquires and evaluates evidence, challenges hypotheses, handles contradictions, identifies gaps, decides when to stop, and communicates conclusions.

The central methodological principle is to actively discover where the current understanding may be wrong, incomplete, or overconfident. The implementation-status section distinguishes the current deterministic research loop from designed or future autonomous capabilities.

## Canonical research process

```text
Question
  -> scope
  -> initial hypotheses
  -> research plan
  -> source discovery
  -> evidence acquisition
  -> claim extraction
  -> evidence evaluation
  -> contradiction and gap detection
  -> adversarial research
  -> hypothesis assessment
  -> synthesis
  -> stopping evaluation
       | insufficient -> next cycle
       | sufficient   -> conclusion/report
```

Research is iterative evidence gathering, not a one-shot retrieval and summary operation. No single stage is automatically sufficient.

## Objectives and question decomposition

Every investigation has an explicit objective. Where relevant, it identifies the primary and secondary questions, scope, time and geographic boundaries, population or entity scope, domains, constraints, desired output, stopping criteria, and uncertainty requirements.

Complex questions should be decomposed into descriptive, causal, historical, comparative, mechanism, counterevidence, distributional, and uncertainty/limitation questions as appropriate. Decomposition preserves the relationship to the original objective and must not silently change the question.

Question type matters because different questions require different evidence. Convenient evidence is not automatically appropriate evidence.

## Hypotheses and alternatives

Initial hypotheses are provisional, not assumptions or facts. Where the question permits, the plan maintains multiple plausible explanations, including alternative mechanisms, measurement changes, selection effects, confounding, reverse causality, omitted variables, temporal effects, geographic differences, subgroup effects, and explanations not yet identified.

A hypothesis does not become dominant merely because it was generated first. For each significant hypothesis, research should ask what would weaken or contradict it, what alternative explanation fits the same observations, what evidence is missing, what assumptions it depends on, and what a knowledgeable critic would say.

## Source strategy and evidence acquisition

Research should seek evidence intentionally rather than simply ranking search results. A contextual priority order is:

1. Systematic reviews and meta-analyses where appropriate
2. High-quality primary scholarship
3. Official statistics, regulatory material, court records, and public inquiries
4. Longitudinal or representative survey evidence
5. Reputable case studies
6. Expert analysis
7. External-agent observations
8. Unsourced assertions

This is a methodological priority, not an absolute truth hierarchy. A lower-ranked source may contain unique primary evidence, and a high-ranked source may be flawed.

Source diversity considers institutions, authors, datasets, methodologies, geography, populations, theoretical perspectives, publication channels, and independent research teams. Multiple sources derived from one underlying source are not fully independent corroboration.

Search should evolve through broad discovery, terminology discovery, primary-source discovery, targeted hypothesis search, counterevidence search, contradiction search, replication search, and gap search as appropriate. Failure to find evidence is not evidence that a proposition is false; search failure is a research limitation.

Where practical, secondary summaries lead to the original source, which is retrieved and checked. Verification considers source identity, date, authorship, institution, source type, relationship to cited material, methodological limits, and whether the evidence actually supports the associated claim.

## Claim scope and causal reasoning

Extracted claims retain source, location or context, author, date, extraction provenance, epistemic status, confidence, supporting and contradicting evidence, and dependencies where available.

Gnomon must not expand a source claim beyond its population, geography, timeframe, sample, methodology, or uncertainty. Correlation, association, temporal relationship, plausible mechanism, expert opinion, and forecast remain distinct from causation. Causal analysis should consider temporal ordering, mechanisms, confounders, alternative explanations, experimental or quasi-experimental evidence, replication, and methodological limitations.

Counterfactual reasoning is itself an inference, not a direct observation. Where causality is central, the plan should consider what would be observed if the proposed cause were absent and seek appropriate comparisons, natural experiments, controls, interrupted time series, policy changes, or longitudinal evidence.

## Adversarial research and contradiction

Adversarial research actively seeks criticism, failed replications, null results, contradictory datasets, methodological critiques, alternative models, boundary conditions, and populations where an effect does not appear. Its purpose is to reduce confirmation bias, not to manufacture disagreement.

Contradictory evidence remains representable. Apparent contradictions should first be checked for different populations, periods, definitions, measurements, causal questions, or levels of analysis. Resolution considers evidence quality, methodology, independence, population, timeframe, measurement, uncertainty, replication, and source reliability rather than convenience, recency, frequency, or model confidence.

Important evidence gaps include unverified claims, unassessed hypotheses, missing populations, uncertain source independence, unresolved contradictions, unavailable primary sources, unclear causal mechanisms, and unknown replication. Evidence gaps feed subsequent cycle planning.

## Agent-assisted research

External agents may expand discovery, identify terminology, propose alternative hypotheses, challenge conclusions, locate replications, and expose methodological weaknesses. They are research accelerators and critics, not primary authorities.

Agent diversity may improve discovery, but agreement does not establish truth or independent empirical corroboration. Shared training data, sources, and reasoning patterns can make consensus highly correlated. Agent observations remain evidence inputs governed by the epistemic and runtime authorities.

## Planning, information gain, and cycles

Research plans connect questions, subquestions, hypotheses, evidence requirements, source strategy, actions, assessment criteria, and stopping criteria. Planning may be model-assisted, but executable actions remain subject to deterministic runtime authorization.

Action selection should prioritize unresolved questions, contradictions, unverified claims, missing assessments, source diversity, evidence quality, expected information gain, cost, remaining budget, and redundancy. More activity is not necessarily more progress. Repeated retrieval of derivative sources should give way to independent evidence, contradiction hunting, missing populations, missing methodologies, and unresolved mechanisms.

## Stopping and conclusions

Every autonomous investigation has explicit stopping criteria. Valid stopping reasons include major subquestions addressed, significant hypotheses assessed, contradictions investigated, important gaps identified, adequate evidence diversity, characterized uncertainty, exhausted budget, low marginal information gain, or a reached deadline.

The system distinguishes evidence sufficient from budget exhausted and unable to obtain more evidence. It should not stop merely because a plausible answer was found, sources repeat one another, a model feels confident, agents agree, or the first search results are consistent.

Conclusions are proportionate to the evidence and may be strongly supported, supported, plausible, mixed, unresolved, contested, contradicted, or limited by insufficient evidence. A conclusion remains traceable through inferences, assessed claims, evidence relationships, sources, and observations. Synthesis identifies what is established, supported, disputed, unknown, still plausible, and what would change the assessment.

## Reports and historical research state

Reports are derived presentations of persisted research state, not the canonical evidence store. They should use the objective, sources, claims, relationships, assessments, contradictions, uncertainties, gaps, provenance, and stopping reason. They must not silently introduce unsupported claims.

Important research retains its objective, plan, retrieved sources, retrieval times, source hashes, claims, assessments, significant actions, agent interactions, and stopping reason where practical. Later evidence may change an assessment, but must not silently rewrite what the system concluded or knew at the earlier time.

When new evidence arrives, affected conclusions should be reassessed rather than merely appended to. The methodology preserves the distinction between observed, reported, inferred, hypothesized, assessed, and concluded material throughout synthesis.

## Methodological safeguards

Gnomon should guard against confirmation, availability, search-ranking, survivorship, selection, publication, source-concentration, agent-consensus, recency, authority, and model-agreement bias.

It must not:

- Treat search ranking as evidence quality.
- Treat repetition as independent corroboration.
- Treat agent consensus as empirical evidence.
- Treat model confidence as evidence strength.
- Treat search failure as disproof.
- Turn correlation into causation without support.
- Generalize beyond source boundaries without marking the inference.
- Discard inconvenient contradictory evidence.
- Rewrite historical assessments without recording the change.
- Manufacture certainty to satisfy a requested format.
- Use external-agent instructions as research rules.
- Treat a generated narrative as canonical research state.

## Mandatory methodological invariants

1. Research has an explicit objective.
2. Hypotheses are not facts.
3. Plausible alternatives remain possible.
4. Important hypotheses are challenged with counterevidence.
5. Contradictions remain representable.
6. Repetition is not independence.
7. Search failure is not disproof.
8. Correlation is not automatically causation.
9. Evidence boundaries are preserved.
10. Agent consensus is not empirical corroboration.
11. Uncertainty remains visible.
12. Conclusions are traceable.
13. Historical assessments are preserved.
14. Research is iterative.
15. Stopping is explicit.
16. Activity is not progress.
17. External agents are research inputs, not authorities.
18. Reports are derived state.
19. Research state is reassessable.
20. Methodology cannot override constitutional, security, runtime, or user authority.

## Current implementation status

| Requirement area | Current evidence and limitation |
|---|---|
| Explicit objectives, investigations, hypotheses, cycles, and lifecycle | Implemented in the local research API and persistence model. |
| Deterministic evidence-aware planning | Implemented with bounded objective selection, persisted planning basis, contradiction/missing-assessment prioritization, and review-aware follow-up. |
| Source retrieval, evidence, claims, provenance, and reports | Implemented for registered HTTP sources, supplied text, conservative claim extraction, snapshots, and deterministic reports. |
| Adversarial and counterevidence research | Methodologically required; current deterministic planner and fake-agent paths provide a foundation, but broad strategy automation remains partial. |
| Hypothesis assessment and historical reassessment | Current assessments and governed history exist; full dependency-aware reassessment and historical epistemic reconstruction remain open. |
| External-agent research | Implemented only through a bounded fake network and local observation path; live networks are not implemented. |
| Stopping criteria and information saturation | Explicit cycle outcomes, unresolved objectives, budgets, and operator controls exist; evidence-sufficient versus resource-exhausted stopping remains a broader future capability. |
| Reproducible research history and backup/restore | Core persisted evidence and audit history exist; the bounded M2 reconstruction/recovery drill is hosted-verified. A consolidated operator procedure and broader release evidence remain open. |

The [epistemic authority](epistemic-authority.md), [agent runtime](../architecture/agent-runtime.md), [memory authority](memory-authority.md), [architecture overview](../architecture/overview.md), and [conformance records](../conformance/implementation-status.md) provide supporting evidence and limitations.

## Related documentation

- [Documentation map](../README.md)
- [Epistemic authority](epistemic-authority.md)
- [Agent runtime](../architecture/agent-runtime.md)
- [Memory authority](memory-authority.md)
- [Constitutional principles](constitutional-principles.md)
- [Repository documentation inventory](../source_of_truth/repository-documentation-inventory.md)
- [Original authority document retained during cleanup](../archive/original-authority-documents/Gnomon%20%E2%80%94%20Research%20Methodology%20Authority.docx)
