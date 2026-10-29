# Getting the data to run the demos

This repo holds code, schemas and documentation. The data the demos read is **not** in git. This guide explains what data exists, where it goes, how to get public data, how to obtain or regenerate the exact AssetOpsBench traces, and how to build the demo data from them.

## 1. What data exists and where it goes

| Path | Contents | In git? |
|---|---|---|
| `data/mast/` | MAST / MAD multi-agent traces (public, fetched) | No (`data/mast/*.json` is ignored) |
| `data/assetopsbench/` | AssetOpsBench scenario lists (public, fetched) | Only `fetch.sh` |
| `data/assetopsbench/runs/` | Raw AssetOpsBench run traces: native `*.json`, `*.instrumented.json`, `otel-*.jsonl` | No (ignored) |
| `src/demo/data/` | Demo data built from those traces (`*.demo.json`, `matrices/*.matrix.json`, `matrices/index.json`) | No (ignored) |
| `src/explorer/data/` | Planned: data for the new Belief Explorer. It does not exist yet. | Planned to stay local-only, like `src/demo/data/` |

Raw traces and built demo data are gitignored and kept private. Raw traces contain complete model inputs and tool results. The built demo data contains trace excerpts, and publishing them waits on a licence check of the AssetOpsBench data and on the annotation pilot. Never commit either.

## 2. Public data

### MAST (MAD dataset)

```sh
bash data/mast/fetch.sh
```

This downloads `MAD_full_dataset.json` (about 190 MB, 1,642 records) and `MAD_human_labelled_dataset.json` from HuggingFace (`mcemri/MAD`) into `data/mast/`. See `data/mast/README.md` for the record shape.

- The Gomoku trace used in this project is **index 7** of `MAD_full_dataset.json`: ChatDev, ProgramDev, GPT-4o (`trace_id` 7).
- The full dataset file used here has sha256 `d636ac63dfc1c6af2d312e862f4b7d383b62d3898d431ccd0e7a79d21d85406f`. A fresh download may differ if the dataset was updated upstream.

### AssetOpsBench scenarios

```sh
bash data/assetopsbench/fetch.sh
```

This downloads the IBM AssetOpsBench dataset files from HuggingFace (`ibm-research/AssetOpsBench`) into `data/assetopsbench/`, including the scenario list `data/assetopsbench/scenarios/all_utterance.jsonl` (scenarios 620 and 621 come from it). It does not contain any agent runs.

## 3. The exact AssetOpsBench traces used in this project

These runs are **available from the maintainer on request**, subject to the AssetOpsBench data licence check. Put them in `data/assetopsbench/runs/` with their original file names.

**Why the exact files matter.** The hand-written fixtures, the validators and the hand annotations refer to these files by sha256 and by step number (`seq`). The demo builders check the hashes and refuse a trace that does not match. A regenerated run of the same scenario is a different trace: it will not match the fixtures or annotations (see §4).

| Run | Files (`data/assetopsbench/runs/`) | sha256 |
|---|---|---|
| 621 | `aob-621-sonnet5-deep-fileobs-20261013.instrumented.json` | `aa8531f2b9771397ecd539fc0bbef8f6da8cfbe681a53fee59b557c3c55c74cd` |
| | `aob-621-sonnet5-deep-fileobs-20261013.json` | `8645198b2fe14df9a7afd0c8e8b4530eff1067eeb166e8c823fed5309d0130ef` |
| 620-fileobs | `aob-620-sonnet5-deep-fileobs-20261013.instrumented.json` | `890f8fc78637f20c614df46bae49600d0178c6fa81c1aec23f352d27985a1436` |
| | `aob-620-sonnet5-deep-fileobs-20261013.json` | `3fad53361a372b91c5a7c6d4e299625935b4c76713ba295d5f0481b68044719e` |
| | `otel-aob-620-sonnet5-deep-fileobs-20261013.jsonl` | `a2eb8262b257675d9fdf6680d6c717cebb28c923f8d38ec28759b44c085d6142` |
| sc3-B | `aob-sc3-sonnet5-deep-spec-B-20261014.instrumented.json` | `4d5759091df0e9bc800f209ff4cffca916a33b06b1441ee086cbf1585c339386` |
| | `otel-aob-sc3-sonnet5-deep-spec-B-20261014.jsonl` | `f78389150f55023eaf95d1eef1110cac070c3b0acbc5a76d0217843dbaf52a5f` |
| 607 | `aob-607-sonnet5-deep-20261005.instrumented.json` | `362ec6a25550abcdb56279f2166da71a4df52afebaeefb9ba34e8d2548fd1708` |
| | `aob-607-sonnet5-deep-20261005.json` | `74601fa457278f63e287ea95534a517f20907f650cb012deb0c6952d89fd27df` |

The sc3-B run stopped on its budget guard, so it has no native `.json` (the runner writes that file only on success). Run 607 has no input telemetry.

Check your copies with:

```sh
shasum -a 256 data/assetopsbench/runs/*.json data/assetopsbench/runs/*.jsonl
```

## 4. Generating your own traces

> **Warning.** These runs make **paid model calls** with your own API key. Model behaviour differs on every run, so your traces will differ from ours. Regenerated traces **will not match** the fixture hashes, the step numbers or the hand annotations, so the existing fixtures and the 621/620 comparison view cannot be used with them. Only the observation matrix (built without a fixture) works for a new trace.

### Set up AssetOpsBench

1. Clone the fork and check out the research branch:

   ```sh
   git clone https://github.com/DevikaVishnu/AssetOpsBench.git
   cd AssetOpsBench
   git checkout research/agenttrace-specialists
   ```

2. Follow the branch's `INSTRUCTIONS.md` ("Quick Start"):
   - `uv sync`, then `uv sync --group otel` for the OpenTelemetry trace file;
   - `cp .env.public .env`, then set your own model key in `.env` (for the `anthropic:` route below, `ANTHROPIC_API_KEY`);
   - start CouchDB with `docker compose -f src/couchdb/docker-compose.yaml up -d` and check it with `curl -X GET http://localhost:5984/`.

### A run like 621 (single agent, instrumented)

The research checkpoint (`docs/agenttrace-research-checkpoint-20261013.md` §5.1 on that branch) records the command used for run 621. From the AssetOpsBench root, with `.env` in place, and with a new run ID and a new trace file for every run:

```sh
AGENTTRACE_CAPTURE_SUBAGENTS=1 \
AGENT_TRAJECTORY_DIR=<output dir> \
OTEL_TRACES_FILE=<output dir>/otel-<your-run-id>.jsonl \
  .venv/bin/deep-agent --model-id anthropic:claude-sonnet-5 \
  --run-id <your-run-id> --scenario-id 621 --json "<question>"
```

- `<question>` is the text of scenario 621 in `data/assetopsbench/scenarios/all_utterance.jsonl`, used verbatim.
- With `AGENTTRACE_CAPTURE_SUBAGENTS=1`, the runner writes `<output dir>/<your-run-id>.instrumented.json` next to the native `<your-run-id>.json`.
- Run 621 itself was produced from the maintainer's local AssetOpsBench tree. The capture code is the same as on this branch, but the run was not made from a clone of the branch.

### Scenario 3, condition B (specialists, isolated CouchDB, budget guard)

The sc3-B run was started by `docs/experiments/launch_sc3_B.py` in this repo, under the pre-registration `docs/experiments/prereg-aob-sc3-sonnet5-deep-spec-B-20261014.md` (§14). The launcher:
- creates the run's environment itself: specialist sub-agents (`AGENTTRACE_SPECIALISTS=1`), capture (`AGENTTRACE_CAPTURE_SUBAGENTS=1`), the budget guard (`AGENTTRACE_BUDGET_GUARD`, 200 calls / $10 estimated) and the per-run output paths;
- points the run at an isolated, disposable CouchDB on `127.0.0.1:5985`, created and loaded by `docs/experiments/sc3_isolation.py` (`create`, `load`, `verify`);
- runs a preflight check first; without `--execute` it makes no model call.

It is a record of that one run, not a general tool:
- It expects `AP`, an `AssetOpsBench` clone (whose `.env` provides the model key and server settings) and the worktree `AssetOpsBench-agenttrace-spec` (which must have no `.env`) as sibling directories.
- Its run ID is fixed. It refuses to execute if that run's output files already exist, and refuses unless `PRICES_CHECKED_ON` in the file equals today's date (after a price re-check).
- To reproduce the setup you would need your own copy with a new run ID and your own pre-registration. The usage lines are at the top of the file:

  ```sh
  cd AssetOpsBench-agenttrace-spec
  .venv/bin/python ../AP/docs/experiments/launch_sc3_B.py            # preflight and redacted plan only
  ```

Specialist delegation is not guaranteed: the recorded sc3-B run delegated only to the general-purpose sub-agent.

## 5. Building the demo data from traces

Full details are in `src/demo/README.md` and `scripts/demo/MATRIX_CONTRACT.md`. All of this runs offline: no model, network or database. It needs the AssetOpsBench worktree `AssetOpsBench-agenttrace-spec` as a sibling of this repo, at commit `b9e09f6` or later on `research/agenttrace-specialists`, with its `.venv`.

```sh
WT=../AssetOpsBench-agenttrace-spec
PY="env -u OTEL_TRACES_FILE PYTHONPATH=$WT/src $WT/.venv/bin/python"
$PY scripts/demo/build_matrix.py --trace data/assetopsbench/runs/<trace>.instrumented.json --run-id <id> [--fixture <fixture.json>]
$PY scripts/demo/validate_matrix.py --manifest src/demo/data/matrices/index.json
$PY -m pytest scripts/demo/test_matrix_pipeline.py -q -p no:cacheprovider
```

In zsh, call `$PY` as `${=PY}`.

The fixtures for the existing runs are on the AssetOpsBench branch under `src/agent/deep_agent/tests/fixtures/`. The 621/620 comparison data (`src/demo/data/aob-621.demo.json`, `aob-620f.demo.json`) is built with:

```sh
$PY scripts/demo/build_demo_data.py --worktree $WT
```

Both builders work only with the exact traces in §3 when a fixture is used.

### Belief Explorer data

To be written when the Belief Explorer data builder exists.

## 6. What you'll see without the data

The app builds and runs without any local data (`npm install`, then `npm run dev`). In the `#demo` tab, both views then show:

> Demo data is local-only. See docs/DATA.md to get or build it.

Once the data is in `src/demo/data/`, restart the dev server (or rebuild) and the views load it.
