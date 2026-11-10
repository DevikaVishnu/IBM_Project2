# Reproducing the Belief Explorer demo locally

The tracked code builds and runs without any trace data. The demo content comes from private inputs that are deliberately **not committed**. They are gitignored, and each person keeps their own copy.

## Private inputs (local-only, gitignored)

| Path | What it is | Needed for |
|---|---|---|
| `data/agent-council/<archive>.zip` | Agent-council trace export (`ida.agenttrace.export/1.0`) | Building council bundles |
| `local/agent-council/<trace id>/*.semantic.json` | Optional hand-grounded 0.3 slice for one run (must match the run id and member sha256) | Annotated claims for that run |
| `local/agent-council/<trace id>/*.findings.json` | Optional hand-validated findings for one run | Findings panel |
| `src/explorer/data/index.json`, `*.bundle.json`, `*.guide.json` | The explorer manifest, the built bundles and optional guide sidecars | What the UI shows |
| `../AssetOpsBench-agenttrace-spec` (worktree, with `.venv`) | The `agenttrace.compare/0.1` module and the pytest interpreter | O3 comparison and the pytest suites |

Without these inputs the viewer still builds; it shows no explorer traces.

## Steps

1. **Build a council bundle** (output goes to `local/agent-council/bundles/`, which is gitignored):

   ```sh
   python3 -I scripts/explorer/build_council_bundle.py --archive data/agent-council/<archive>.zip --run <trace id or unique part>
   ```

2. **Register it with the viewer.**
   - Copy `<trace id>.bundle.json` into `src/explorer/data/`.
   - Add an entry to `src/explorer/data/index.json`: `{contract, file, kind, label, sha256, trace_id}`. Here `sha256` is the sha256 of the bundle file. The UI refuses a bundle whose hash doesn't match.

3. **Validate the manifest and every bundle it lists:**

   ```sh
   python3 -I scripts/explorer/validate_bundle.py
   ```

4. **Run the viewer** with `npm ci` and then `npm run dev`. To check the production build, run `npm run build`.

## Tests

```sh
WT=../AssetOpsBench-agenttrace-spec
env -u OTEL_TRACES_FILE PYTHONPATH=$WT/src $WT/.venv/bin/python -m pytest scripts/explorer/test_explorer_bundles.py -q -p no:cacheprovider
env -u OTEL_TRACES_FILE PYTHONPATH=$WT/src $WT/.venv/bin/python -m pytest scripts/demo/test_matrix_pipeline.py -q -p no:cacheprovider
```

Tests that need the local bundles, the raw traces or the worktree are skipped when those are absent.

## Not committed, on purpose

- Raw traces.
- Built bundles and the manifest.
- Semantic slices, annotations and findings files.
- Screenshots.
- Anything under `local/`.
