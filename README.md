# AgentTrace

**A framework-independent semantic observability layer for agentic AI systems.**

> Developed as part of an IBM Research collaboration on *Mission Control for Agentic AI*.
> CSE 523 Advanced Project in Computer Science — Devika Vishnu, Komalika Acharya

---

## Overview

Agent frameworks emit raw telemetry: prompts, completions, tool calls, configuration, files and logs. That telemetry records what happened. It does not record what any of it *meant* for the run. AgentTrace adds a semantic layer above raw telemetry, without replacing it, that answers six questions about a run:

- **What existed:** which information was present, such as requirements, configuration, task briefs, tool results, documents and code.
- **What reached each agent:** which information was actually in each agent's rendered input, as opposed to merely configured or available.
- **What agents claimed or believed:** observable assertions and stances only, never hidden reasoning.
- **What was verified:** which propositions a reviewer, test or judge actually evaluated, and which required checks were missed.
- **How content moved and failures may have spread:** how content propagated between artifacts, and where failures may have propagated.
- **Where the telemetry runs out:** which conclusions must stay UNKNOWN because the necessary information was never recorded.

The aim is Mission Control-style debugging and forensics: explaining *why* a run produced its output, and being explicit about what cannot be known.

**Status:** schema design and validation. The schema, `agenttrace.semantic/0.3`, is **experimental and not frozen**. No production extractor exists yet.

---

## Research progression

```
Belief Explorer ──► Gomoku falsification ──► agenttrace.semantic/0.3 ──► cross-framework validation
   (prototype)       (delivery failure,        (experimental schema)      (ChatDev, HyperAgent,
                      not belief divergence)                                deepagents/AssetOpsBench)
                                                                                     │
                       next falsification experiment ◄── observability-boundary findings
```

1. **Belief Explorer (prototype).** A visualiser of per-agent belief states and divergence in multi-agent conversations (see [Earlier prototype](#earlier-prototype-belief-explorer)).
2. **Gomoku falsification.** A MAST/ChatDev failure that belief tracking could not explain. Every agent "agreed"; none of them had received the requirement.
3. **`agenttrace.semantic/0.3`.** A schema built around delivery, verification, provenance and lineage, designed by validating one gap at a time against that trace.
4. **Cross-framework validation.** The schema was run against HyperAgent and AssetOpsBench deep-agent traces to try to break it.
5. **Observability-boundary findings.** Most remaining failures to represent a trace came from missing telemetry, not from missing schema concepts.
6. **Next experiment.** A fully observable delegated deep-agent run.

---

## Motivating example: MAST/ChatDev Gomoku trace #7

The run's configuration sets `gui_design: True`. The rest of the chain:

```
GUI requirement exists in configuration
  → it is never rendered into the programmer's input
  → the programmer never receives it
  → the three code reviewers do not receive it either
  → GUI verification is missed (reviewers: UNCERTAIN obligation; test: no GUI obligation)
  → a console-only program reaches the final output
```

Delivery was established by reconstructing every prompt and matching its token count against the logged count. The residual was a constant +2 tokens on all 12 model calls. So "not delivered" is a supported finding, not a guess.

This is **not primarily a belief divergence**. It is an **information-delivery failure**: the agents didn't disagree; the requirement never reached them. A turn-by-turn belief view cannot show it. That finding broadened the project from belief tracking to semantic information-flow observability.

---

## Current schema: `agenttrace.semantic/0.3`

Canonical specification: [`docs/agenttrace.semantic.0.3.md`](docs/agenttrace.semantic.0.3.md). **Experimental, not frozen.**

### Stored objects

| Object | Meaning |
|---|---|
| `run` | One execution. `run.outputs` names its final products, identified from framework product markers |
| `entities` | Agents, tools, services, framework and environment. Agent identity is separate from role and model |
| `events` | Observable atomic input/output units. Not necessarily agent-originated |
| `evidence` | Observable content. Each item records the event that first produced it (`produced_by`) |
| `claims` | Observable assertions extracted from a span of one evidence item |
| `propositions` | Canonical statements, independent of who holds them |
| `states` | A holder's observable stance on a proposition at one event |
| `links` | The relations below |

### Relations

| Relation | Endpoints | Meaning |
|---|---|---|
| `delivers` | agent-input event → evidence | The evidence was present in the agent's **actual rendered input**. Configuration, templates or availability never count |
| `checks` | event → proposition | An observable event evaluated the proposition |
| `propagates_to` | evidence → evidence | **Content lineage only**: specific content of one item was reproduced in a later one by an event that received it. Not causality, not semantic equivalence |
| `depends_on` | proposition → proposition | Logical necessity: A cannot be TRUE unless B is TRUE |
| `supported_by` / `contradicted_by` | proposition → evidence | The evidence **directly** bears for or against the proposition |

`segments`, `revises` and `conflicts_with` are not part of 0.3.

### Key distinctions

- **Evidence** is role-neutral observable content: messages, code, files, config values, tool results, retrieved chunks, reports, final answers. Evidence does not intrinsically mean support. Support and contradiction exist only through links.
- **Claims** are observable assertions extracted from evidence.
- **States** take one of four values: `TRUE | FALSE | UNKNOWN | UNCERTAIN`. Each is grounded in the holder's own claims at one event. There are no sticky beliefs carried forward through silence, and nothing is inferred from hidden reasoning.
- **Direct evidence vs testimony:**
  - Every assertion is a claim, and a claim is testimony.
  - `supported_by` / `contradicted_by` represent only direct bearing.
  - Agent-authored content can still be direct evidence when it is itself the thing being evaluated, such as code or structured output.
  - Testimonial and direct assessments are kept separate and never merged.
- **Stored vs inferred:** these are computed by an inference layer and never stored:
  - non-delivery;
  - verification scope and obligations;
  - unverified requirements;
  - lineage chains and defect persistence;
  - contribution hypotheses (capped at "supported contribution");
  - repetition structure.

  The core contains no framework or benchmark concepts: no ChatDev phases, no completion markers, no MAST codes.

---

## Cross-framework validation

0.3 has been exercised against three real settings. "Partial" means some relations could not be established from the recorded telemetry. It does not mean the schema failed.

### 1. MAST / ChatDev: Gomoku trace #7 (full)

- **Stresses:** requirement non-delivery, verification scope, artifact lineage, a repeated review/modification workflow.
- **Result:** fully represented. This trace directly motivated several 0.3 additions: `delivers`, `checks`, `produced_by` and `run.outputs`. It is the worked example in the schema document.

### 2. MAST / HyperAgent: trace #25, `pylint-dev__pylint-6506` (partial)

- **Stresses:** real Planner → Navigator / Editor / Executor delegation; contradictory and unattributed testimony; missing direct execution evidence; incomplete telemetry.
- **Result:** partially represented. **No stored-schema gap found.**
- **Why partial:** rendered prompts aren't logged, and neither are the calls that produced the relayed reports, so every `delivers` and `propagates_to` link is UNKNOWN.
- **Supported finding:** H1 and H3, two of the reports relayed to the Planner, are unattributed relay content. Neither can be traced to the corresponding sub-agent's observed output, and H3 is inconsistent with the Executor's last observed claim. The Planner then declared the issue resolved.
- **Direct evidence:** the command output that would settle the question is not in the trace.

### 3. AssetOpsBench / deep-agent: run 620 (partial)

- **Stresses:** very large tool results (≈90K–115K characters); the framework offloading them to files; partial exposure to the model; later recovery with `read_file` and `grep`; paginated tool results; parallel tool calls.
- **Key finding: partiality at two levels.**
  1. The industrial `history` tool returned only part of the available data: one page of 1,000 observations with `has_more: true`.
  2. The framework then gave the model only a small substitute of that already-partial result, about 400 tokens. This is shown by the growth in logged input tokens, not by the prompts, which aren't recorded.
- **Recovery:** the model later read back exact fragments of the result through `read_file`/`grep`. These were verified line by line against the original.
- **Limitation:** 0.3 cannot store lineage across `tool result → framework/file → read_file/grep result`, because `propagates_to` requires the producing event to have received the source as agent input. This is a real, known limitation. It has **not yet justified a stored-schema change**: the recovered fragments didn't affect the final answer, and the file write and read aren't observable events.

### What 0.3 has survived

- **Frameworks:** ChatDev, HyperAgent, deepagents/AssetOpsBench.
- **Phenomena:** information omission, verification, delegation, contradictory testimony, artifact lineage, repeated workflows, large outputs, partial/truncated exposure, file-mediated retrieval, parallel tool calls, paginated results.

**No stored-schema change has been required since the 0.3 design was finalized.**

### Inference clarifications from validation

These refine the inference layer only; the stored schema is unchanged.

- A witness who supports both P and ¬P makes that witness's testimonial contribution **UNCERTAIN**. Each event-anchored state is kept, and the latest claim is never silently preferred.
- If the lineage between testimonial claims is UNKNOWN, their **independence is UNKNOWN**. They are not counted as independent corroboration.
- No observable product marker means `run.outputs` is **UNKNOWN, not empty**.
- **Whole-item non-delivery** can be inferred from a valid token or size upper bound. This proves only that the complete item wasn't delivered, not which part was.
- **Span-level exposure** of any evidence can be inferred by containment against delivered items. Content overlap never establishes lineage.
- **Partial delivery** does not need a new relation yet: separate evidence items, ordinary `delivers` and containment are enough.
- **`propagates_to` is not generalized** yet.

---

## Open issues

These are open research questions. None has been added to the stored schema.

- lineage through tools and files (non-agent dataflow);
- first-class delegation and hierarchy;
- availability and access (data an agent could have read but didn't);
- nested runs;
- parallel branches and merged outputs;
- belief revision and retraction;
- ambiguous provenance;
- whether benchmark-harness markers can identify `run.outputs`.

The main practical finding cuts across all of them: **`delivers` can only be established when each model call's rendered input is logged.** In two of the three traces it wasn't, so most exposure-based conclusions had to stay UNKNOWN.

---

## Current status

**Completed**

- AssetOpsBench environment and industrial MCP tools exercised.
- CouchDB, trajectory and OpenTelemetry persistence working. Run trajectories and OTEL spans are kept locally under `data/assetopsbench/runs/`.
- The plan-execute, claude-agent and deep-agent runners exercised.
- Passive deep-agent instrumentation with sub-agent fields (`delegations`, `delegation_id`, `parent_agent_id`). These were unused in the runs so far, which were single-agent.
- `agenttrace.semantic/0.3` designed and documented.
- Cross-framework validation performed (above).

**Not yet implemented**

- a production semantic extractor;
- framework adapters emitting 0.3;
- a Mission Control UI consuming the new schema;
- a fully observable delegated deep-agent run.

The React UI in this repository is the **earlier Belief Explorer prototype**. It is not the 0.3 Mission Control UI and does not consume the new schema.

---

## Next experiment: a fully observable delegated deep-agent run

The next high-value step is one deliberately instrumented run, not another benchmark example. It should log:

- the model inputs of both the parent agent and its sub-agents, including system prompts;
- handoff content in both directions;
- delegation IDs and parent agent IDs;
- full tool outputs;
- any large-result eviction or substitute text;
- file writes and the reads that follow them.

Ideally, a value recovered from an offloaded result should actually affect the final answer.

This would test:

- whether delegation can remain an inference rather than a stored concept;
- whether `delivers` works when telemetry is complete;
- whether non-agent lineage actually requires a schema change;
- whether availability/access needs representation;
- whether a future 0.4 is justified at all.

---

## Repository layout

| Path | Contents |
|---|---|
| `docs/agenttrace.semantic.0.3.md` | Canonical schema specification (experimental), including the Gomoku worked example and validation status |
| `data/mast/` | MAST annotated dataset (MAD). `fetch.sh` downloads it; the JSON files are not committed |
| `data/assetopsbench/` | AssetOpsBench benchmark data. `fetch.sh` downloads it; the data files are not committed. Instrumented runs are kept locally in `runs/` and not yet published |
| `src/` | Earlier prototype: React visualiser (`App.jsx`, `BeliefEvolution.jsx`) |
| `tests/` | Earlier prototype: trace processor, belief extractor, four ChatDev sample traces |
| `BELIEF_EVOLUTION_README.md` | Earlier prototype documentation |

Fetch the datasets:

```bash
bash data/mast/fetch.sh            # MAST / MAD dataset (Cemri et al., 2025)
bash data/assetopsbench/fetch.sh   # AssetOpsBench (Patel et al., 2025)
```

---

## Earlier prototype: Belief Explorer

> Historical. This was AgentTrace's first architecture, not its current one.

The prototype visualised multi-agent conversations as a belief timeline:

```
Raw MAS trace  ──►  process_trace.py  ──►  belief_extractor.py  ──►  BeliefEvolution.jsx
                    normalise to JSON      classify belief states     interactive timeline grid
                                           + detect divergences
```

- **Belief grid:** agents × turns, each cell one of ten heuristic states (idle, asking, proposing, building, reviewing, wants change, approving, blocked, pushing, completing).
- **Divergence detection:** six pattern-based detectors, such as blocked-vs-pushing, approval without substance, and step repetition.

**Why it was superseded:**
- It classified states with keyword and phase heuristics.
- It carried states forward through silence.
- It built in ChatDev concepts.
- Above all, it had no notion of what each agent actually received, which is exactly what the Gomoku failure turned on.

**Running it:** requires Node.js ≥ 18 and Python ≥ 3.9.

```bash
npm install
npm run dev        # then open http://localhost:5173

python tests/process_trace.py path/to/raw_trace.json processed.json
python tests/belief_extractor.py processed.json enriched.json
```

Load the enriched JSON with the viewer's **Load JSON** button; sample traces are in `tests/`. More detail: [`BELIEF_EVOLUTION_README.md`](BELIEF_EVOLUTION_README.md).

---

## References

- Cemri, M. et al. (2025). *Why Do Multi-Agent LLM Systems Fail?* arXiv:2503.13657v2.
- Patel, D. et al. (2025). *AssetOpsBench: Benchmarking AI Agents for Task Automation in Industrial Asset Operations and Maintenance.* arXiv:2506.03828.
- Qian, C. et al. (2023). *ChatDev: Communicative Agents for Software Development.* arXiv:2307.07924.
- Wu, Q. et al. (2024). *AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversations.* COLM 2024.
- Epperson, W. et al. (2025). *Interactive Debugging and Steering of Multi-Agent AI Systems.* CHI 2025. arXiv:2503.02068.
