# AgentTrace

AgentTrace is a framework-independent, evidence-grounded observability layer for multi-agent AI systems. For each run it records what information existed, what reached each agent's model input, what agents asserted, and how those assertions compare with the evidence they received.

- **IBM Research collaboration:** Mission Control for Agentic AI
- **Authors:** Devika Vishnu, Komalika Acharya (CSE 523, Advanced Project in Computer Science)
- **Status:** research prototype

## The problem

Agent frameworks log prompts, completions and tool calls, but these logs do not show which information actually reached which agent, or whether an agent's statements were backed by the evidence it saw. Some important failures leave no sign of disagreement at all. In a ChatDev run from the MAST dataset (a Gomoku game), the configuration required a graphical interface (`gui_design: True`), but that requirement never appeared in the input of the programmer or of any reviewer. Every review passed, and a console-only program shipped: the agents never disagreed, because the requirement was never delivered.

## The approach

AgentTrace describes a run in three layers:

1. **Skeleton.** Agents, model calls, tool calls and the items they produce, derived from raw telemetry by a deterministic structural adapter and checked by an independent verifier.
2. **Belief layer.** Observable claims (the exact words in an agent's output), the propositions they express, and the states they express (TRUE, FALSE or UNCERTAIN) at a specific model call.
3. **Evidence links with delivery.** Which evidence supports or contradicts a proposition, and whether that evidence was present, byte-identical, in the rendered input of the model call that made the claim.

All objects follow the canonical schema [`agenttrace.semantic/0.3`](docs/agenttrace.semantic.0.3.md). The schema is frozen for the current work, and every object in it points back to the raw record it came from.

Two comparisons are computed on demand and never stored:

- **Evidence exposure (`exposure_at`):** was a given evidence item, or an exact span of it, in the rendered input of a given model call?
- **State versus evidence (`state_vs_evidence`):** does an agent's stated value for a proposition agree with, or differ from, the evidence linked to that proposition, and was that evidence delivered to the agent?

**Principle.** Only observable assertions are modelled: there are no hidden beliefs, and nothing is carried forward through silence. Anything the telemetry cannot establish is reported as UNKNOWN, never as a guess. A non-delivery, for example, is stated only when the full model input is known.

## What's here

| Path | Contents |
|---|---|
| [`docs/agenttrace.semantic.0.3.md`](docs/agenttrace.semantic.0.3.md) | The schema, its inference rules, known limits, and the Gomoku worked example (§14) |
| [`src/explorer/`](src/explorer/) | **Belief Explorer**: a React view of one trace bundle, with an overview, a claim-by-claim evidence chain, the interaction matrix, the skeleton and flags. The bundle format is documented in [`CONTRACT.md`](src/explorer/CONTRACT.md) |
| [`scripts/explorer/`](scripts/explorer/) | Bundle builder, independent bundle validator and tests |
| [`scripts/demo/`](scripts/demo/) | Interaction-matrix pipeline (agents × model calls in observation order): builder, independent validator, tests, and its contract [`MATRIX_CONTRACT.md`](scripts/demo/MATRIX_CONTRACT.md) |
| [`src/demo/`](src/demo/) | Earlier demo, kept as an archive tab. Its matrix component is reused by the Belief Explorer |
| `src/App.jsx`, `src/BeliefEvolution.jsx`, `tests/` | Legacy prototype (heuristic belief timeline over ChatDev/AG2 traces), kept for reference; see [`BELIEF_EVOLUTION_README.md`](BELIEF_EVOLUTION_README.md) |
| [`docs/experiments/`](docs/experiments/) | Pre-registrations, results and launch scripts for the recorded AssetOpsBench runs |
| [`docs/DATA.md`](docs/DATA.md) | How to obtain the datasets and traces, and how to build the explorer data |

The structural adapter, the verifier, the comparison code, the DeepAgents instrumentation and their tests live in the AssetOpsBench fork, under `src/agent/deep_agent/` (see Related repositories).

## Quickstart

```sh
npm install
npm run dev
```

Then open `http://localhost:5173/#explorer`.

The trace data is local-only and not in git: raw traces contain complete model inputs, and publication waits on a licence check. Without the data the Belief Explorer shows "Explorer data is local-only." See [`docs/DATA.md`](docs/DATA.md) to obtain the traces and build the bundles.

## Current status

- **Implemented and verified:** the structural adapter and verifier convert AssetOpsBench DeepAgents traces into 0.3 with 0 verifier errors on the four recorded runs used here. Three of these runs captured full model inputs.
- **Implemented and tested:** the interaction-matrix pipeline, with an independent validator and offline tests.
- **Implemented:** the Belief Explorer for three traces: AssetOpsBench run 621 (single agent), AssetOpsBench scenario 3 (a root agent and a helper sub-agent), and ChatDev Gomoku. The Gomoku skeleton is reconstructed by hand from the schema's worked example, with every cited log line checked.
- **Hand-annotated and illustrative:** claims, propositions, states and evidence links are written by hand, and are not a gold standard. Where they can be computed, the comparisons run on these hand-written links.
- **Not done:** automatic claim extraction; validated cross-agent divergence on industrial multi-agent runs (no recorded run yet has specialists delegating to and disagreeing with each other); integration into Mission Control.

A capability-by-capability table is in [`docs/STATUS.md`](docs/STATUS.md). The current research question and next step are in [`docs/research/STATE.md`](docs/research/STATE.md), and the dated history is in [`docs/research/RESEARCH_LOG.md`](docs/research/RESEARCH_LOG.md).

## Related repositories

- **[AssetOpsBench fork, branch `research/agenttrace-specialists`](https://github.com/DevikaVishnu/AssetOpsBench/tree/research/agenttrace-specialists):** DeepAgents instrumentation, structural adapter (`_semantic_adapter.py`), verifier (`_semantic_verify.py`), comparisons (`_semantic_compare.py`), fixtures and tests. It is a research branch of [IBM/AssetOpsBench](https://github.com/IBM/AssetOpsBench) and is not merged upstream.
- **[Mission Control](https://github.com/kevin-chaudhari/Advanced-Project-Fall2026):** the IBM Research collaboration dashboard. The Belief Explorer is built to become one of its panels; it has not been integrated yet.

## References

- Cemri, M. et al. (2025). *Why Do Multi-Agent LLM Systems Fail?* arXiv:2503.13657v2.
- Patel, D. et al. (2025). *AssetOpsBench: Benchmarking AI Agents for Task Automation in Industrial Asset Operations and Maintenance.* arXiv:2506.03828.
- Qian, C. et al. (2023). *ChatDev: Communicative Agents for Software Development.* arXiv:2307.07924.
- Wu, Q. et al. (2024). *AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversations.* COLM 2024.
- Epperson, W. et al. (2025). *Interactive Debugging and Steering of Multi-Agent AI Systems.* CHI 2025. arXiv:2503.02068.

## License

See [LICENSE](LICENSE).
