# Pre-registration: natural delegation run, scenario 620

Status: **PROPOSED. Not executed. Waiting for user approval.**
Prepared 2026-10-13. It follows `docs/research/STATE.md` § Next action (ckpt §10).

## 1. Scenario (verbatim, unchanged)

Source: `data/assetopsbench/scenarios/all_utterance.jsonl`, `id` 620. Its fields are type `multiagent`, category `Knowledge Query`, group `prescriptive`, entity `Chiller`, and `deterministic: false`.

> I want to build an anomaly model for identifying a chiller trip failure for MAIN chiller 6. Provide me a list of sensors that I should use, along with the temporal behavior,

The trailing comma is part of the original text. Keep it.

## 2. Why this scenario, and what tools and data it needs

I compared the candidates 606, 607, 616, 617 and 620.

| ID | Natural sub-tasks | Large result likely (eviction to a file) | Prior run |
|---|---|---|---|
| 606 | weak (temperature vs power) | unlikely: FMSR and the sensor list only | none |
| 607 | weak | no. The 20261005 run had 0 `large_tool_results` | 0 `task` calls |
| 616 | word-for-word duplicate of 606 | — | none |
| 617 | one chain (failure mode → power history) | yes. 1 `history` call and 1 `read_file` | 0 `task` calls |
| **620** | **several independent ones (temporal behavior per sensor, plus failure-mode knowledge)** | **near-certain. 3 `history`, 2 `read_file`, 2 `grep`, 9 `large_tool_results` mentions** | 0 `task` calls |

[OBS] The counts above come from `aob-{607,617,620}-sonnet5-deep-20261005.json`, as reported by the Explore subagent.

Why 620:
- It is the only candidate with several independent sub-objectives, so it gives `task` delegation the best natural opening.
- It already produced evictions and file reads by the parent, so the file-mediated half of the lineage (T1–T3, T6–T7) is very likely to occur.
- It has never been run with file observability or sub-agent capture. Its 20261005 run predates that instrumentation (ckpt l.330).
- [HYP] Wording that covers several sensors raises the chance of delegation. This is untested (ckpt l.331).

Tools and data:
- AssetOpsBench servers in `src/servers/`:
  - FMSR: `get_failure_modes`, `generate_failure_modes`
  - IoT: `history` (PAGE_SIZE 1000), `sensor_stats`, `sensor_coverage`, `measured_sensors`
  - WO: `list_workorders`, `get_failure_codes`
- The DeepAgents built-ins (`task`, `read_file`, `grep`, `write_file`, and the others) come from the production runner, unchanged.
- Data: Chiller 6 at MAIN has June 2020 data only (2,896 records). One sensor's history page is about 103–130k chars, which is above the ~80k-char eviction threshold (ckpt l.175).

## 3. Run ID and model configuration

- Run ID: `aob-620-sonnet5-deep-fileobs-20261013`. If the run happens on a later date, replace the date suffix. Before running, confirm that no file with this ID exists in `data/assetopsbench/runs/`.
- Model: `anthropic:claude-sonnet-5`, the native provider route. LiteLLM routes do not work (ckpt l.55).
- Production system prompt, tools and runner. The default `--recursion-limit 100` is unchanged.
- Capture: `AGENTTRACE_CAPTURE_SUBAGENTS=1`. Output goes to `AGENT_TRAJECTORY_DIR` (`AP/data/assetopsbench/runs`) as `{run_id}.json` and `{run_id}.instrumented.json`.

## 4. Criteria

All checks are made on the run's own `.instrumented.json`, `.json` and per-run OTEL file. Joins use `tool_call_id` and sha256, as in ckpt §4.

**SUCCESS.** All of S1–S5 are [OBS]:
- S1: delegation occurs. At least one `task` tool call, a `delegation_start`/`delegation_end` pair, and a child agent in `agents`.
- S2: the child writes a file. A `file_write` event is attributed to the child, either an evicted tool result or an explicit `write_file`.
- S3: the parent reads that child path. The two read tools are observed differently:
  - `read_file` emits a `file_read` event with `path`, `offset`, `limit` and `window_sha256` (`_file_observer.py:115–131`). The `path` must match S2. `window_sha256` equals the S2 `sha256` only when the window covers the whole file. A partial read is **not** required to match the whole-file hash.
  - `grep` emits **no** `file_*` event (`_file_observer.py:173–177`). It counts only as a parent `tool_start` whose args name the S2 path (or a pattern scoped to it), together with the matching `tool_end`.
  - Corroborating evidence, not independent proof of provenance [INF]: the read text (from `tool_end.output`) is a substring of the child's original tool result (from the child's `tool_end.output`). Provenance rests on the path and `tool_call_id` joins (S2 → S3). A substring match alone cannot prove the content came from that file.
- S4: the read content appears in the rendered input of a later parent `llm_start` (`input_batches`).
- S5: a span of that content, or a value derived from it by a stated rule [INF], is carried into the parent's final answer. The source is the `answer` field of `{run_id}.json`. The instrumented record has no answer field.

**PARTIAL**, reported as such and not as success:
- S1 holds but S2–S5 fail, for example because the child returns content only through the `task` result.
- S1 fails but the non-delegated file chain recurs. That repeats the run-621 finding.

**FAILURE (of the natural-delegation hypothesis for this run):** S1 fails. Report it as **0 of 7** natural delegations (Sonnet 5, runs 607–620-fileobs). Under Open decision 1, ask the user before any non-production condition.

**INCONCLUSIVE:**
- The run errors, hits the recursion limit, or hits a provider or tool failure before a final answer.
- The instrumentation is missing or malformed: no `.instrumented.json`, an empty OTEL file, or events that cannot be joined.
- The WO DB count changes (see §7). The run is then flagged as having side effects.

## 5. Stopping rule

Exactly **one** run. There are no retries, even if the result is a failure or inconclusive. A rerun needs a new pre-registration and new approval.

## 6. Trace file

- Per-run file: `<projects>/AP/data/assetopsbench/runs/otel-aob-620-sonnet5-deep-fileobs-20261013.jsonl`. Confirm it does not exist before the run.
- It is set only in that one command's environment. `.env` is not edited.
- [OBS] `_cli_common.py:148` calls `load_dotenv()` with its default `override=False`. A variable that is already exported therefore beats the `.env` value, and the historical `traces.jsonl` is not appended to.
- After the run, confirm that `traces.jsonl` is still 101,154 B.

## 7. Work-order DB check (before and after)

Run this from the AssetOpsBench root in a subshell that sources `.env`. It prints only the count.

```bash
( set -a; . ./.env; set +a
  curl -s -u "$COUCHDB_USERNAME:$COUCHDB_PASSWORD" "$COUCHDB_URL/$WO_DBNAME" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["doc_count"])' )
```

- The expected baseline is 7 (ckpt l.64, l.170; it was 7 → 7 around run 621).
- If the "before" value is not 7, stop and report without running.
- An "after" value that differs from "before" makes the run INCONCLUSIVE (see §4).

## 8. Cost and operational risk

**Cost. These are estimates, not guarantees.**
- Price [OBS], from the official pricing page (platform.claude.com/docs/en/about-claude/pricing, checked 2026-10-13). Claude Sonnet 5 costs:
  - $2/MTok base input
  - $2.50/MTok 5-minute cache writes
  - $0.20/MTok cache hits
  - $10/MTok output
  - $2/$10 is now the standard price, and there is no long-context surcharge up to 1M tokens.
- Reference point [OBS]: run 621, from its 24 `llm_end` usages:
  - 1,123,772 input tokens: 1,058,788 cache reads, 64,936 5-minute cache writes, 48 uncached.
  - 12,123 output tokens.
  - At the prices above that is about **$0.50**. Uncached it would have been $2.37. Prompt caching was active.
- Estimate [INF]:
  - 1–2.5M input tokens and 12–40k output tokens. The input share of cache writes is 6–20%, higher than in 621 because child agents start with fresh context.
  - With caching patterns like run 621's: **about $0.45–$2.05**.
  - Upper bound with no caching (2.5M input, 40k output): **about $5.40**.

**Risks:**
- The prior probability of delegation is low (0 of 6). The most likely result is FAILURE.
- The backend-factory hook used by capture is deprecated in deepagents 0.5.3, so check that the installed version is unchanged.
- Sub-agent capture is validated only by the synthetic test (ckpt §4). A real delegation could expose capture gaps, and those would count as INCONCLUSIVE, not as a schema finding.
- Genuine delegation could occur while child attribution fails. The child agent (`sub-N`) is created only if callbacks propagate into `subagent.ainvoke(subagent_state)`, which passes no explicit config (`subagents.py:440`). If they don't, child events are missing or recorded as unattributed. Files written when the framework summarizes history are also recorded as unattributed (`filesystem.py:1437–1448`). If a `task` call is observed but S2 cannot be attributed to the child, the result is **INCONCLUSIVE** (unjoinable events, §4), not FAILURE.
- The run writes only to new files: `{run_id}.json`, `{run_id}.instrumented.json` and the per-run OTEL file.
- WO tools could write to CouchDB. This is guarded by the count check in §7.
- No prompts, tools, scenarios or site-packages are modified.

## 9. Proposed execution command (do not run without approval)

From `<projects>/AssetOpsBench`:

```bash
( set -a; . ./.env; set +a
  AGENTTRACE_CAPTURE_SUBAGENTS=1 \
  OTEL_TRACES_FILE=<projects>/AP/data/assetopsbench/runs/otel-aob-620-sonnet5-deep-fileobs-20261013.jsonl \
  .venv/bin/deep-agent \
    --model-id anthropic:claude-sonnet-5 \
    --run-id aob-620-sonnet5-deep-fileobs-20261013 \
    --scenario-id 620 \
    --json \
    "I want to build an anomaly model for identifying a chiller trip failure for MAIN chiller 6. Provide me a list of sensors that I should use, along with the temporal behavior," )
```

Order of steps: run the §7 count (before), then the command above, then the §7 count (after), then the §6 size check on `traces.jsonl`, then the analysis against §4 by trace-analyst.
