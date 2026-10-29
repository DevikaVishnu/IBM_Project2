# Status

Capability-by-capability status of AgentTrace as of 2026-10-27. For the current research question and next step see [`research/STATE.md`](research/STATE.md); for the dated history see [`research/RESEARCH_LOG.md`](research/RESEARCH_LOG.md).

"Fork" means the AssetOpsBench fork, branch [`research/agenttrace-specialists`](https://github.com/DevikaVishnu/AssetOpsBench/tree/research/agenttrace-specialists), files under `src/agent/deep_agent/`.

| Capability | Where | Status |
|---|---|---|
| Canonical schema `agenttrace.semantic/0.3` | [`agenttrace.semantic.0.3.md`](agenttrace.semantic.0.3.md) | **Defined; frozen for the current work.** Exercised against ChatDev (MAST) and AssetOpsBench DeepAgents traces |
| DeepAgents instrumentation: rendered model inputs, delegations, large-result eviction, file reads and writes | Fork | **Implemented**, off by default (environment flags). Used in the recorded runs |
| Structural adapter and independent verifier: raw trace → skeleton and delivery links | Fork: `_semantic_adapter.py`, `_semantic_verify.py` | **Implemented and verified.** 0 verifier errors on the four recorded AssetOpsBench runs used here (607, 620, 621, scenario 3 condition B). Run 607 has no captured model inputs, so it has no delivery links |
| Comparisons: evidence exposure (`exposure_at`) and state versus evidence (`state_vs_evidence`), profile `agenttrace.compare/0.1` | Fork: `_semantic_compare.py` | **Implemented and tested** on hand-grounded fixtures (two from real runs, one synthetic) |
| Interaction matrix: agents × model calls in observation order, contract `agenttrace-matrix/0.2` | [`scripts/demo/`](../scripts/demo/) | **Implemented and tested.** An independent validator re-runs the adapter and verifier and re-derives every field; 32 offline tests |
| Belief Explorer | [`src/explorer/`](../src/explorer/) | **Implemented for three traces** (run 621, scenario 3 condition B, ChatDev Gomoku): overview, claim-by-claim evidence chain, interaction matrix with claim and flag markers, skeleton, flags |
| Explorer bundle builder and validator, contract `agenttrace-explorer-bundle/0.1` | [`scripts/explorer/`](../scripts/explorer/) | **Implemented and tested.** Offline tests; the builder stops if the adapter counts, the verifier or any annotated value disagrees with the raw trace |
| Claims, propositions, states and evidence links | Local annotation files | **Hand-annotated, illustrative, not gold.** 7 claims for run 621, 2 for scenario 3, 1 for Gomoku. Comparisons are computed from these hand-written links where possible |
| Gomoku skeleton | Local annotation file, from schema §14 | **Hand-reconstructed.** 7 of the 12 model calls are reconstructed; every cited log line is checked against the dataset |
| Automatic claim, proposition and state extraction | — | **Not done** |
| Two-annotator claim annotation | — | **Not done.** An annotation package has been piloted blank only |
| Cross-agent belief divergence on industrial multi-agent runs | — | **Not demonstrated.** No recorded run has specialists that delegate, hand back and disagree on observable evidence |
| Mission Control integration | [Mission Control](https://github.com/kevin-chaudhari/Advanced-Project-Fall2026) | **Not done.** The Belief Explorer page takes a bundle as data and uses scoped styles, so it can be mounted as one route |
| Publication of trace data and explorer bundles | [`DATA.md`](DATA.md) | **Local only**, pending a licence check of the AssetOpsBench data |
| Earlier demo (`#demo`) | [`src/demo/`](../src/demo/) | **Archived.** Superseded by the Belief Explorer; kept unchanged as a tab |
| Legacy belief-timeline prototype | `src/BeliefEvolution.jsx`, `src/App.jsx`, `tests/` | **Superseded.** It infers belief states heuristically and models no information delivery |
