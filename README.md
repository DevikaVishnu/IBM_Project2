# AgentTrace

**Semantic observability for agentic AI systems: tracing what information existed, what reached each agent, and how failures propagated.**

> CSE 523 Advanced Project in Computer Science — Devika Vishnu, Komalika Acharya

---

## What is AgentTrace?

AgentTrace is a semantic observability layer for multi-agent and agentic LLM systems. It is aimed at Mission Control-style debugging and forensics: explaining *why* a run produced the output it did, not just *what* happened turn by turn.

Agent frameworks emit rich raw telemetry: prompts, completions, tool calls, configuration and artifacts. They do not say which information actually reached which agent, which requirements anyone checked, or how a defect travelled from one artifact to the final product. AgentTrace defines a framework-independent schema for those questions. The schema sits on top of raw telemetry and never replaces it.

The project began as a belief-divergence visualiser (see [Earlier prototype](#earlier-prototype-belief-explorer)). Working with that prototype showed that many failures are not disagreements between agents at all. They are information that never reached anyone. That finding led to the broader semantic layer described here.

---

## Research question

For a given agentic run:

1. **What information existed?** Requirements, configuration, task briefs, tool results, retrieved documents, code, messages.
2. **What reached each agent?** The content actually rendered into each agent's input, as opposed to what was merely configured or available.
3. **What claims and beliefs formed?** What each agent observably asserted, and what stance it took, from observable text only and never from hidden reasoning.
4. **What was verified?** Which propositions a reviewer, test or judge actually evaluated, and which ones it was obliged to evaluate but did not.
5. **How did failures propagate?** How content was carried between artifacts, and where an omission or defect plausibly contributed to the final output.

### Motivating example

In ChatDev trace 7 (Gomoku) from the MAST dataset, the run's configuration sets `gui_design: True`. That requirement was never rendered into any agent's input: not the programmer's, and not any of the three code reviewers'. Coverage was established by reconstructing every prompt and matching its token count against the log. Nobody reasoned about a GUI, review and test never checked for one, and the console-only program was accepted as the final product.

The failure pattern:

> A requirement exists in configuration → it is never delivered → no agent reasons about it → review and test never check it → incorrect output is accepted.

A turn-by-turn belief view cannot show this failure. It needs a record of delivery, verification and provenance.

---

## Current schema: `agenttrace.semantic/0.3` (experimental)

Full specification: [`docs/agenttrace.semantic.0.3.md`](docs/agenttrace.semantic.0.3.md).

**Stored objects:**

| Object | Meaning |
|---|---|
| `run` | One execution. `run.outputs` names the final products, identified from the framework's own product markers |
| `entities` | Agents, tools, services, framework and environment. Agent identity is kept separate from role and model |
| `events` | Observable, atomic input/output units, not necessarily originating with an agent |
| `evidence` | Observable content (messages, code, files, config values, tool results…). Each item records the event that produced it (`produced_by`) |
| `claims` | Assertions extracted from a span of one evidence item |
| `propositions` | Canonical statements that don't depend on who holds them |
| `states` | A holder's observable stance on a proposition at one event, grounded in its own claims |
| `links` | The relations below |

**Relations:**

| Relation | Meaning |
|---|---|
| `delivers` | An agent's actual rendered input contained this evidence |
| `checks` | An event observably evaluated this proposition |
| `propagates_to` | Content lineage: specific content of one evidence item was reproduced in a later one |
| `depends_on` | Logical necessity between propositions |
| `supported_by` / `contradicted_by` | Evidence directly bears for or against a proposition |

**Inferred, never stored:** non-delivery (only under established input coverage), verification and obligation scope, unverified obligations, lineage chains, defect persistence, contribution hypotheses, and repetition structure.

**Design principles:**

- Raw telemetry is kept separate from inference.
- Every inferred object traces back to raw data.
- Configuration or template availability never counts as delivery.
- Testimony (an agent saying P) is kept distinct from direct evidence (the code or tool output itself).
- Causal conclusions are capped at "supported contribution", and nothing causal is stored.
- The core contains no framework or benchmark concepts: no ChatDev phases, no completion markers, no MAST codes.

---

## Validation so far

| Source | What was done | Status |
|---|---|---|
| **MAST / ChatDev Gomoku** (MAD dataset, trace 7) | Full schema validation across four gaps: information delivery, verification, failure propagation, and repetition/workflow structure. Each claim is backed by line-level citations into the raw trace | Done. This is the worked example in the schema doc |
| **Thought experiments** | Supervisor drops a budget constraint; RAG truncation followed by a bare PASS verdict; tool retries; planner/executor/reviewer loops; testimony vs direct evidence | Used to test framework independence |
| **AssetOpsBench** (IBM) | Infrastructure: benchmark fetch script, plus five instrumented deep-agent runs (Claude Sonnet 5, scenarios 607, 612, 615, 617, 620) in the raw format `assetopsbench.deepagent.instrumented/0.1` | Raw telemetry collected locally; the run files are not yet published in this repository. **The schema has not yet been validated against these runs.** All five are single-agent with no delegations |

The schema rests mainly on one real trace. It is **experimental, not frozen, and not proven complete**.

---

## Current status

- **Phase:** schema design and validation.
- **There is no production extractor yet.** No adapters or extraction code produce `agenttrace.semantic/0.3` from raw telemetry.
- The React visualiser in this repo is the earlier prototype. It does not consume the new schema.

---

## Next steps

Validate the schema against traces that stress what the Gomoku trace could not:

- **genuine multi-agent delegation**, where a supervisor hands work to sub-agents;
- **information flowing through tools**, such as a file written by one tool and read by another, or shared memory stores;
- **parallel branches and merged outputs**;
- **belief revision and retraction** (this tests the decision to leave `revises` and `conflicts_with` out of 0.3);
- **partial delivery and truncation**;
- conflicting instructions, implicit requirements, and ambiguous provenance;
- frameworks other than ChatDev, starting with the AssetOpsBench deep-agent runs.

After that, build adapters and an extractor, and connect the semantic layer to a visual front end.

---

## Repository layout

| Path | Contents |
|---|---|
| `docs/agenttrace.semantic.0.3.md` | Current schema specification (experimental) |
| `data/mast/` | MAST annotated dataset (MAD). Fetched with `data/mast/fetch.sh`; not committed |
| `data/assetopsbench/` | AssetOpsBench benchmark data, fetched with `data/assetopsbench/fetch.sh` and not committed. Instrumented runs are kept locally in `runs/` and not yet published |
| `src/` | Earlier prototype: React visualiser (`BeliefEvolution.jsx`, `App.jsx`) |
| `tests/` | Earlier prototype: trace processor, belief extractor, and four ChatDev sample traces |
| `BELIEF_EVOLUTION_README.md` | Earlier prototype documentation |

### Fetching data

```bash
bash data/mast/fetch.sh            # MAST / MAD dataset (Cemri et al., 2025)
bash data/assetopsbench/fetch.sh   # AssetOpsBench (Patel et al., 2025)
```

---

## Earlier prototype: Belief Explorer

AgentTrace started as an interactive visual analytics tool for multi-agent LLM conversations. Its pipeline had three stages:

```
Raw MAS trace  ──►  process_trace.py  ──►  belief_extractor.py  ──►  BeliefEvolution.jsx
                    normalise to JSON      classify belief states     interactive timeline grid
                                           + detect divergences
```

- **Belief grid:** agents × turns, with each cell coloured by one of ten heuristic states (idle, asking, proposing, building, reviewing, wants change, approving, blocked, pushing, completing).
- **Divergence detection:** six pattern-based detectors, including blocked-vs-pushing, approval without substance, step repetition and persistent complaints.
- **Interaction:** a playhead scrubber, phase tabs, a detail panel with MAST failure codes, and an IBM Carbon colourblind-safe palette.

**Why the project moved on.** The prototype classified states with keyword and phase heuristics, carried each agent's state forward through turns where it was silent ("sticky" states), and built in framework concepts such as ChatDev phases. Most importantly, it had no notion of what each agent actually received. The Gomoku failure is invisible at that level, because every agent "agreed" while none of them had seen the requirement. The semantic layer replaces those heuristics with these rules:

- states must be grounded in observable claims and are never carried forward;
- delivery and verification are first-class;
- framework concepts stay in raw provenance.

### Running the prototype

Prerequisites: Node.js ≥ 18, Python ≥ 3.9.

```bash
npm install
npm run dev        # then open http://localhost:5173
```

To process a new trace:

```bash
python tests/process_trace.py path/to/raw_trace.json processed.json
python tests/belief_extractor.py processed.json enriched.json
```

Load the enriched JSON into the viewer with the **Load JSON** button. Sample traces are in `tests/`.

More detail: [`BELIEF_EVOLUTION_README.md`](BELIEF_EVOLUTION_README.md).

---

## References

- Cemri, M. et al. (2025). *Why Do Multi-Agent LLM Systems Fail?* arXiv:2503.13657v2.
- Patel, D. et al. (2025). *AssetOpsBench: Benchmarking AI Agents for Task Automation in Industrial Asset Operations and Maintenance.* arXiv:2506.03828.
- Qian, C. et al. (2023). *ChatDev: Communicative Agents for Software Development.* arXiv:2307.07924.
- Epperson, W. et al. (2025). *Interactive Debugging and Steering of Multi-Agent AI Systems.* CHI 2025. arXiv:2503.02068.
- Wu, Q. et al. (2024). *AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversations.* COLM 2024.
