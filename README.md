# AgentTrace

> To get the data the demos need (public datasets, the project's traces, building demo data), see [docs/DATA.md](docs/DATA.md).

**A framework-independent semantic observability layer for agentic AI: it records what information existed in a run, what reached each agent, what agents asserted, and what was verified.**

> Developed as part of an IBM Research collaboration on *Mission Control for Agentic AI*.
> CSE 523 Advanced Project in Computer Science — Devika Vishnu, Komalika Acharya

**Status: research prototype.**
- The canonical schema is experimental.
- Semantic representations are currently written and checked by hand.
- No automatic semantic extractor or final visualization exists yet.

---

## Problem

Agent frameworks emit raw telemetry: prompts, completions, tool calls, configuration and files. That record of *what happened* does not directly answer:

- **Exposure:** which evidence actually reached each agent's rendered model input, as opposed to being configured or merely available?
- **Assertions:** what did each agent observably assert, and on what evidence?
- **Information-flow failures:** where was required information lost, truncated, or never delivered?
- **Divergence:** where do agents' observable positions differ from each other, or from the evidence they received?

**Motivating case:** MAST/ChatDev Gomoku trace #7.
- The configuration required a GUI, but that requirement never reached the programmer's or the reviewers' inputs.
- No review checked for a GUI, and a console-only program was shipped.
- The agents did not disagree. The information was simply never delivered.
- A belief-timeline view could not show this, which moved the project from belief tracking to information-flow observability.

**What "belief" means here.** In AgentTrace, beliefs and states are **observable, evidence-grounded assertions**: what an agent's output text claims at a specific event. They are never hidden LLM mental states, and they are never carried forward through silence.

## Approach

```
raw traces ──► canonical semantic representation ──► evidence-grounded comparison ──► visualization
(framework      (agenttrace.semantic/0.3: entities,     (derived, never stored:          (planned)
 telemetry)      events, evidence, delivers, claims,      exposure, state vs evidence)
                 states, provenance to raw records)
```

**Design principles:**
- Every semantic object points back to the raw record it came from.
- Delivery is stored only when it is observed in a rendered input.
- Anything the telemetry cannot establish is reported as **UNKNOWN**, not guessed.
- The core schema contains no framework- or benchmark-specific concepts.

## Current implementation

| Capability | Status |
|---|---|
| `agenttrace.semantic/0.3` schema | **Defined.** Experimental canonical schema. Exercised against MAST/ChatDev, MAST/HyperAgent and AssetOpsBench traces, with no stored-schema change so far |
| DeepAgents instrumentation: rendered model inputs, delegations, large-result eviction, file reads/writes | **Implemented**, flag-gated. Used in three real runs |
| Research configuration: specialist sub-agents, read-only work-order server, call/cost budget guard | **Implemented**, experimental, off by default |
| Hand-grounded 0.3 fixtures (run 621, scenario_3) | **Completed** and independently reviewed |
| O2/O3 comparison (`agenttrace.compare/0.1`) | **Implemented** and tested on fixtures |
| Automated structural adapter + verifier (traces → 0.3) | **Planned.** Design recommended; adapter decisions pending |
| Automated claim, proposition and state extraction | **Planned.** Not automated |
| Belief-divergence detection on real industrial multi-agent runs | **Not demonstrated** |
| Mission Control visualization of 0.3 | **Planned.** A JSON profile draft exists; the legacy Belief Explorer UI does not read 0.3 |

**O2/O3 in brief.**
- **O2, evidence exposure:** given a model call, which parts of which evidence items were present in its rendered input.
- **O3, state versus evidence:** given an agent's observable state on a proposition, how it compares with the evidence that directly bears on that proposition.

Both are derived on demand. They never add objects to the stored representation.

## Validation

All runs used AssetOpsBench with the DeepAgents runner and Claude Sonnet 5. Raw traces are kept locally and are not published.

- **Run 620** (natural; run on 2026-10-05, then again on 2026-10-13 pre-registered with rendered inputs captured): single agent, no delegation.
  - A large tool result was moved to a file. Only a short substitute reached the model.
  - The model later read the file back, and that content reached its input.
  - Use of that content in the final answer was **not** demonstrated.
- **Run 621** (natural): single agent.
  - Values read back from an offloaded file were restated in the final answer. This is the basis of manual fixture A.
  - The hop from tool result to file to read is observable, but 0.3 cannot store it as lineage. That is a declared schema limit, not a counterexample.
- **scenario_3, condition B** (a declared research configuration with specialist sub-agents; executed once):
  - The coordinator delegated only to the generic sub-agent.
  - The sub-agent never returned, and the run was stopped by the budget guard.
  - The earliest observable failure, a file-path error, was seen only by the sub-agent.
  - One annotator only; a second is not yet named.
- **Natural delegation:** 0 of 7 unmodified natural runs delegated.

**Manual fixtures.**
- Two hand-grounded 0.3 fixtures (run 621, scenario_3 condition B), with every object anchored to raw records.
- Three comparison fixtures for O2/O3: two from real runs and one synthetic, used for rule coverage only.

**Offline tests.** 440 tests pass on the implementation branch. They use fake models and make no model calls. They check:
- the instrumentation and flag-off behavior;
- the budget guard;
- the fixtures against the raw traces;
- the comparison rules.

**Test counts are not evidence of extraction accuracy.** No automatic extractor exists yet, and no held-out, fully instrumented gold trace is available to measure one.

## Research roadmap

1. **Structural adapter and independent verifier.** Deterministic conversion of instrumented traces into 0.3. It covers entities, events, evidence and observed delivery, with no claims, and it is checked against the manual fixtures.
2. **Constrained claim extraction.** Verbatim-span claims and propositions from a declared vocabulary, with abstention. Faithfulness is judged by two human annotators.
3. **Held-out validation.** A new pre-registered, fully instrumented run that was not used during development.
4. **Genuine industrial multi-agent belief divergence.** Runs where specialists actually delegate, hand back and disagree on observable evidence.
5. **Visualization and dashboard integration.** Mission Control views built on the 0.3 representation.

## Repositories and code

| Repository | Contents |
|---|---|
| **IBM_Project2** (this repo) | Canonical schema, research state, visualization profile, experiment records and scripts, and the legacy Belief Explorer prototype |
| **[AssetOpsBench fork, `research/agenttrace-specialists`](https://github.com/DevikaVishnu/AssetOpsBench/tree/research/agenttrace-specialists)** | The implementation, under `src/agent/deep_agent/`: instrumentation, specialist configuration, budget guard, [O2/O3 code](https://github.com/DevikaVishnu/AssetOpsBench/blob/research/agenttrace-specialists/src/agent/deep_agent/_semantic_compare.py), fixtures and tests. It is a research branch on a fork of [IBM/AssetOpsBench](https://github.com/IBM/AssetOpsBench) and is not merged upstream |

Datasets are not committed. Fetch them with `bash data/mast/fetch.sh` (MAST/MAD) and `bash data/assetopsbench/fetch.sh` (AssetOpsBench).

## Documentation

- **[Schema `agenttrace.semantic/0.3`](docs/agenttrace.semantic.0.3.md):** objects, relations, inference rules, known limits, and the Gomoku worked example.
- **[Research state](docs/research/STATE.md):** current findings, decisions and the next step.
- **[Research log](docs/research/RESEARCH_LOG.md):** dated chronology from the Belief Explorer to the current milestone, with corrected interpretations and open gaps.
- **[Visualization profile 0.1](docs/research/agenttrace-viz-profile-0.1.md):** JSON serialization profile (draft).
- **Experiment records:**
  - run 620: [pre-registration](docs/experiments/prereg-aob-620-sonnet5-deep-fileobs-20261013.md) and [result](docs/experiments/result-aob-620-sonnet5-deep-fileobs-20261013.md);
  - scenario_3: [pre-registration](docs/experiments/prereg-aob-sc3-sonnet5-deep-spec-B-20261014.md);
  - [experiment scripts](docs/experiments/).
- **Fixtures and the comparison spec:**
  - [0.3 fixtures](https://github.com/DevikaVishnu/AssetOpsBench/tree/research/agenttrace-specialists/src/agent/deep_agent/tests/fixtures/agenttrace_semantic_0_3);
  - [`agenttrace.compare/0.1` spec](https://github.com/DevikaVishnu/AssetOpsBench/blob/research/agenttrace-specialists/src/agent/deep_agent/tests/fixtures/agenttrace_compare_0_1/SPEC.md).
- **[MAST dataset notes](data/mast/README.md).**
- **Legacy Belief Explorer:** see [`BELIEF_EVOLUTION_README.md`](BELIEF_EVOLUTION_README.md).
  - The prototype is a React timeline of heuristic per-agent belief states and divergence patterns over ChatDev/AG2 traces (`src/`, `tests/`).
  - It was superseded because it modelled no information delivery.
  - To run it: `npm install && npm run dev`.

## References

- Cemri, M. et al. (2025). *Why Do Multi-Agent LLM Systems Fail?* arXiv:2503.13657v2.
- Patel, D. et al. (2025). *AssetOpsBench: Benchmarking AI Agents for Task Automation in Industrial Asset Operations and Maintenance.* arXiv:2506.03828.
- Qian, C. et al. (2023). *ChatDev: Communicative Agents for Software Development.* arXiv:2307.07924.
- Wu, Q. et al. (2024). *AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversations.* COLM 2024.
- Epperson, W. et al. (2025). *Interactive Debugging and Steering of Multi-Agent AI Systems.* CHI 2025. arXiv:2503.02068.

See [LICENSE](LICENSE).
