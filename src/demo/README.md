# AgentTrace demo views

The **AgentTrace 0.3 demo** tab (`#demo`) has two read-only views. It fills one screen on a desktop and reflows at larger browser zoom. The code is in `DemoTab.jsx`, with shared tokens and components in `ui.jsx`.

- **Observation matrix** (`MatrixView.jsx`) shows any run listed in `data/matrices/index.json`, chosen from the Run menu.
  - Rows are the agents the trace records, and columns are model calls in observation order.
  - It shows unresolved origins, delegations, structural deliveries, run status and links to an optional fixture.
  - It never shows claims, states or disagreement, because none are extracted.
  - Each run file is checked against its manifest sha256 before use.
- **Hand-grounded example · 621 / 620** (`CompareView.jsx`) shows hand-written claim, delivery and O3 comparison fixtures for runs 621 and 620-fileobs only. It is not generated for other traces.

The UI derives nothing semantic. It renders pre-built, validated JSON.

## Run the viewer

```sh
npm install      # once
npm run dev      # then open http://localhost:5173/#demo
```

`npm run build` must pass before a demo.

## Add or rebuild a matrix run (offline; no model, network or database)

Requirements:
- **The trace:** a local instrumented trace (`assetopsbench.deepagent.instrumented/0.1`). It is only read.
- **The AssetOpsBench worktree** `AssetOpsBench-agenttrace-spec`, as a sibling of this repo, at `b9e09f6` or later, with its `.venv`. The scripts import its frozen adapter and verifier.
- **Optional:** a hand-grounded 0.3 fixture for the same trace. Only its delivers links are used.

```sh
WT=../AssetOpsBench-agenttrace-spec
PY="env -u OTEL_TRACES_FILE PYTHONPATH=$WT/src $WT/.venv/bin/python"
$PY scripts/demo/build_matrix.py --trace data/assetopsbench/runs/<trace>.instrumented.json --run-id <id> [--fixture <fixture.json>]
$PY scripts/demo/validate_matrix.py --manifest src/demo/data/matrices/index.json
$PY -m pytest scripts/demo/test_matrix_pipeline.py -q -p no:cacheprovider
```

In zsh, call `$PY` as `${=PY}`.

The builder rejects a run, writing nothing, if any of these fail:
- the adapter rejects the record;
- the verifier reports any error;
- a fixture belongs to another trace;
- the independent matrix validator fails.

Output is canonical and byte-identical across reruns. The contract and its invariants are in `scripts/demo/MATRIX_CONTRACT.md`.

**Current runs:**

| Run | Fixture |
|---|---|
| `aob-sc3-B` | `agenttrace_semantic_0_3/aob-sc3-B.semantic.json` |
| `aob-621` | `agenttrace_semantic_0_3/aob-621.semantic.json` |
| `aob-620-fileobs` | `agenttrace_compare_0_1/aob-620-compare.trace.json` |
| `aob-607` | none (no input telemetry) |

**The hand-grounded example data** (`data/aob-621.demo.json`, `data/aob-620f.demo.json`) is rebuilt with `scripts/demo/build_demo_data.py --worktree $WT`.

## Reading rules shown in the UI

- Column and timeline order is observation order only (first raw seq). It implies no precedence, causation or belief persistence.
- "Delivered" means byte-identical presence in a model call's rendered input. It does not show influence.
- Hand-grounded objects come from fixtures and are labelled as such. They are never presented as adapter output.
