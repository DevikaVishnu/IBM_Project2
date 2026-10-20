# Pre-registration: scenario_3, DeepAgents specialists, condition B

- **Run ID:** `aob-sc3-sonnet5-deep-spec-B-20261014`
- **Status:** DRAFT, amended by §14 and §14.8 (2026-10-14). The preparation decisions in §14 and the corrections in §14.8 are approved; **execution is not approved** and nothing has been executed. Exactly one run, after explicit approval.
- **Label:** a declared research configuration (Open decision 1, resolved 2026-10-14). It is reported apart from the natural-benchmark runs 607–621 and never pooled with them.

## 1. Question

When a multi-agent DeepAgents configuration attempts upstream `scenario_3`, can AgentTrace show:
- which agent first made a failure observable;
- which agents received the relevant evidence;
- how claims moved between agents;
- where the final answer diverged from the task requirements?

All of this must come from the raw capture alone.

## 2. Task (verbatim)

- **Question:** `AssetOpsBench/src/couchdb/scenarios_data/scenario_3/question.txt`, sha256 `ab0147071bed7eed…`.
  - It is passed as `"$(cat …/question.txt)"`. Command substitution strips the trailing newline. That is the only transformation.
- **Ground truth:** `scenario_3/groundtruth.txt`, sha256 `ff1d124863f3cad7c73617723b1780bef3f5128e4c992de48f04d9d7dde667f8`. It is not edited.
- **IoT data:** `shared/iot/chiller_6.json`, sha256 `8073af23ea71fc401aee97fd40b47678a80ad0549eb4153b1eb0ab8dc9b246e2`.
- **WO data:** `shared/work_order/workorders.csv`, sha256 `86ea1dd775361fa4…`.
- [OBS] The worktree copies and the original copies of all four files hash-equal (2026-10-14).

## 3. Configuration and declared modifications

Code: worktree `<projects>/AssetOpsBench-agenttrace-spec`, branch `research/agenttrace-specialists` (base `6ec35fb`), uncommitted. It contains:
- the Part A–C instrumentation, copied unchanged;
- M1, M4 and M6. All three are active only with `AGENTTRACE_SPECIALISTS=1`, and flag-off behaviour is unchanged (tests).

The production elements are unchanged:
- the coordinator's system prompt (`AGENT_SYSTEM_PROMPT`);
- the model route `anthropic:claude-sonnet-5`;
- the recursion limit (100);
- the default `StateBackend`;
- the MCP servers.

| ID | Modification | Effect visible to the model |
|---|---|---|
| M1 | Four specialist sub-agents: `iot`, `tsfm`, `fmsr`, `wo` | The `task` tool lists them with the general-purpose sub-agent. |
| M1 | Each specialist gets its own server's tools plus `utilities` | `vibration` stays with the coordinator only. |
| M1 | Specialist model | Inherited from the coordinator. |
| M1 | Coordinator tools | All 79 original tools are kept, so delegation is **not forced**. |
| M1 | Specialist prompt | A neutral template. The scope line is the server's FastMCP `instructions`, verbatim (for `wo`, see M4b). |
| M1 | Server descriptions now reach a model | They appear in the `task` tool description. Previously no model saw them, because the MCP adapter doesn't forward them. `tsfm`'s includes its own anomaly-detection workflow text. |
| M4 | `env={"AOB_READONLY": "1"}` on the `wo` stdio connection | The WO server registers 9 read tools instead of 15, for the coordinator and the `wo` specialist alike. |
| M4b | `wo` scope line edited to drop the write verbs | "Read-only work order access … Query work orders; compute KPIs, costs, and schedules…". The verbatim server text is kept in code and recorded by sha256 (`scope_source: readonly_edit`). |
| M6 | `llm_start.offered_tools` and top-level `tool_availability` | None. These are raw-capture fields only. |

Real tool partitions [OBS] (2026-10-14, listed through the runner's own flag-on connections with `uv run`; no tool calls):

| Agent | MCP tools |
|---|---|
| coordinator | 79 (iot 12, utilities 6, fmsr 3, tsfm 41, wo 9, vibration 8) |
| `iot` | 12 + 6 = 18 |
| `tsfm` | 41 + 6 = 47 |
| `fmsr` | 3 + 6 = 9 |
| `wo` | 9 + 6 = 15 |

Read-only WO [OBS]: started with the runner's `uv run wo-mcp-server` connection, the WO server listed 9 tools with `AOB_READONLY=1` and 15 without it.

## 4. Pre-run state [OBS] (2026-10-14; re-check immediately before the run)

- WO DB `doc_count` = 7, and `update_seq` starts with `7-`.
- WO `1000045`: `status` WAPPR, `siteid` MAIN, `assetnum` CHILLER6, `_rev` `1-850525…`. It is the only WAPPR work order in the DB.
- The IoT DB holds 2,896 Chiller 6 records, 2,876 of them with Condenser Water Flow, from `2020-06-01T00:00:00` to `2020-06-30T23:45:00`. Those are the same counts and range as `chiller_6.json`.
- `traces.jsonl` is 101,154 B. No `aob-sc3-*` file exists in `AP/data/assetopsbench/runs/`.
- Canonical `agenttrace.semantic.0.3.md` sha256 starts `2273d210090d19c1`. It is unmodified and **needs no change**: all new fields are raw-capture fields, mapped onto plain 0.3 objects at analysis time.

## 5. Requirements (for labeling)

| ID | Requirement (from question.txt) |
|---|---|
| R1 | Find the MAIN work order awaiting approval that asks for an anomaly investigation. Identify its asset and the named measurement. |
| R2 | Look up the asset in the registry and use the registry name. |
| R3 | Retrieve the full available history of that single measurement. |
| R4a | Write the series to a file on disk that the TSFM tooling can read. |
| R4b | Do not paste the series into reasoning or a tool argument. |
| R5 | Run a TSFM anomaly-detection recipe over that file and obtain dense labels. |
| R6-k | Report one JSON object with exactly the 7 keys k ∈ {work_order, asset, sensor, observations, start, end, anomalies_found}. |
| R7 | Count only the records that carry a value. |

Two reference answers are scored **separately and never merged**:
- **E-GT** (benchmark literal): `groundtruth.txt`.
- **E-R7** (derived from the requirements): it is identical except `end` = `2020-06-30T23:45:00`.
  - [OBS] The `end` value in `groundtruth.txt`, `2020-06-26T11:14:36`, is the last record in *file order* of the unsorted file. It has no Condenser Water Flow value, so it violates R7.
  - `anomalies_found` cannot be checked independently. It is scored against E-GT only and marked UNVERIFIED.

**Predicted configuration-induced failure** [INF]:
- TSFM reads host paths (`tsfm/io/refs.py:20-51`) and accepts no inline series. DeepAgents' default `StateBackend` files exist only in memory.
- So under B, R4a/R5 are expected to fail. The only way to make a file, `write_file(content=series)`, also violates R4b.
- Such a failure is labeled **configuration-induced (condition B)** and is not counted as an agent-reasoning failure.

## 6. Success criteria

- **S1:** at least one `delegation_start` whose `subagent_type` is one of `iot`, `tsfm`, `fmsr` or `wo`.
- **S2:** every specialist delegation is attributable:
  - a `sub-N` agent whose `name` equals `subagent_type`, with `parent_agent_id` = `root`;
  - its own `llm_start` events;
  - the sha256 of the child's first HumanMessage equals that of the `delegation_start.description`.
- **S3:** child→parent delivery. For each specialist delegation, the parent's next `llm_start` contains exactly one ToolMessage with `tool_call_id` = the delegation id, and its sha256 equals that of `returned_to_parent`.
- **S4:** tool availability:
  - every `llm_start` has a non-null `offered_tools`;
  - each specialist's offered set minus the framework tools equals its partition in §3;
  - `task` appears only in the coordinator's sets;
  - `tool_availability.readonly_servers` = `["wo"]`;
  - no `offered_tools` set contains a WO write tool.
- **S5:** scoring. R1–R7 and R6-k are scored against E-GT and E-R7 separately.

Outcome labels:
- **MULTI-AGENT (specialist):** S1–S4 are met. S5 is reported, whatever its value.
- **GENERIC MULTI-AGENT:** only `general-purpose` was delegated to. S2–S4 are checked for it. No specialist claims are made.
- **SINGLE-AGENT:** there is no `delegation_start`. It is recorded as a single-agent run and **never presented as multi-agent evidence**.
- **INCONCLUSIVE:** one of these holds:
  - the instrumentation is missing or malformed;
  - the OTEL file is empty;
  - events can't be joined;
  - S2 or S3 can't be evaluated even though a `task` call occurred;
  - the WO DB `doc_count`, `update_seq` or `1000045` status changed;
  - `traces.jsonl` changed.

## 7. Stopping rule

- Run **once**. There are no retries for any reason, including provider errors, a bad answer or no delegation.
- If the outcome is SINGLE-AGENT: do not retry, do not run condition A, and return to the user.
- Condition A (M2/M2b/M3) is considered only if the outcome is MULTI-AGENT (specialist), the user then approves M2/M2b/M3, and their compatibility tests pass.
- If the provider fails mid-run, `write_instrumented` records `status: error`. That is reported as is, and the run is not repeated without new approval.

## 8. Analysis protocol (after the run; trace-analyst, then the report)

- **Joins** use `tool_call_id`, sha256 and `seq`; `seq` is observation order, not causal order. The protocol:
  - maps every agent's tool calls;
  - follows each delegation's description → child input, and child final → parent ToolMessage;
  - tracks evictions and `read_file`.
- **Failure labeling: two annotators.**
  - Annotator 1 is a trace-analyst pass. Annotator 2 is an independent pass blind to annotator 1's labels; the user decides who that is.
  - For each requirement, label:
    - the **first observable failure** (seq, agent, evidence item);
    - **delivery**: which agents' rendered inputs contained the relevant evidence;
    - **propagation** into later claims;
    - **claim attribution** (agent and `llm_end` seq);
    - **unsupported claims**, meaning no delivered source;
    - **abstentions / UNKNOWN**.
  - Disagreements are reported, not reconciled silently.
- **Localization metrics:** precision and recall of the first-failure location (agent and seq window) against the consensus labels, and false positives.
- **Baseline (planned, not run):** an LLM given the raw trace only, asked for the same labels. It needs its own pre-registration and approval.
- **0.3 mapping** (plain objects, no profile rev 3):
  - root and `sub-N` as agents;
  - per-call events;
  - the delegation description as parent-produced evidence;
  - the child's final message as the child's item, `delivers`-ed to the parent when it is byte-identical;
  - the ground truth as external `benchmark` testimony;
  - the `end` readings as two propositions;
  - "first observable failure" as a consumer-side rule labeled **not 0.3**.

Declared limits that will appear [INF]:
- the file hop (§5.3, §12);
- `run.outputs` as a harness marker (OPEN);
- the order of parallel tool calls;
- the PROVISIONAL rules.

## 9. Cost (no hard cap)

- **There is no hard budget cap.** Neither the runner nor the provider call stops at a spend limit.
  - The only bound is `--recursion-limit 100` on the coordinator graph.
  - [HYP] Whether sub-agent graphs get their own limit is unverified.
- Prices from the run-620 pre-registration (checked 2026-10-13; **re-check on run day**), Sonnet 5:
  - $2/MTok input;
  - $2.50/MTok 5-minute cache writes;
  - $0.20/MTok cache hits;
  - $10/MTok output.
- Anchors [OBS]: run 620 cost about $0.32; run 621 used 1.12M input and 12k output tokens, about $0.50 cached or $2.37 uncached.
- Estimate [INF]:
  - 1–3.6M input tokens and 15–50k output.
  - Higher than 621 because:
    - each child starts a fresh context, which means more cache writes;
    - the `tsfm` specialist carries 47 tool schemas;
    - the coordinator's `task` description is now longer.
  - About **$0.6–$3.3** with caching like 621's; **about $7.7** uncached at the high end.
  - This is an estimate, not a guarantee.

## 10. Operational risks

- **Delegation probability is unknown.** It was 0 of 7 runs when only general-purpose was offered. SINGLE-AGENT is a likely outcome.
- **WO writes are prevented by M4**, and are also guarded by the `doc_count`, `update_seq` and `1000045` checks.
  - FMSR (`add_failure_modes`) and TSFM (`register_*`, `update_*`, `deprecate_*`) still have write tools, unchanged from production.
  - [INF] TSFM's catalog writes would go to its own catalog DB, which is not checked here. A write there is reported as a side effect.
- `observing_backend_factory` uses the backend-factory hook, which is deprecated in deepagents 0.5.3 (removal in v0.7). The installed version is 0.5.3 in both venvs.
- [INF] `offered_tools` relies on `invocation_params["tools"]` (`ChatAnthropic.bind_tools` → `self.bind(tools=…)`). This was checked with a fake model. If it is null on a real call, S4 fails and the run is INCONCLUSIVE for M6 only.

## 11. Environment preconditions (each requires approval)

- **E1. The worktree venv lacks the `otel` dependency group.** [OBS]
  - Missing: `protobuf` 6.33.6, `googleapis-common-protos` 1.74.0, `opentelemetry-exporter-otlp-proto-{common,http}` 1.39.1, `opentelemetry-proto` 1.39.1, `opentelemetry-instrumentation{,-httpx}` 0.60b1, `opentelemetry-util-http` 0.60b1.
  - `file_exporter.py:68-69` imports `google.protobuf` and the OTLP encoder at export time, so without them the per-run OTEL file would get no spans.
  - Otherwise both venvs have the same 256 packages:
    - Python 3.12 from the same uv-managed interpreter;
    - deepagents 0.5.3, langchain-core 1.3.0, langchain 1.2.15, langgraph 1.1.9;
    - langchain-mcp-adapters 0.2.2, mcp 1.26.0, langchain-anthropic 1.4.1, anthropic 0.96.0.
  - `uv run` in the worktree uses `worktree/.venv` ("Would make no changes"). Its editable install points to the worktree's `src`.
  - Fix: `uv sync --inexact --locked --offline --group otel`. A dry run lists exactly those 8 locked versions, the same ones the original venv has.
- **C1. Credentials.**
  - The stdio MCP servers receive only `HOME, LOGNAME, PATH, SHELL, TERM, USER`, so exported variables do not reach them.
  - Each server's `load_dotenv()` searches upward from its own source file, and the worktree has no `.env`.
  - [OBS] Without credentials, the IoT server logs a failed DB connection at startup.
  - Proposal: a symlink `worktree/.env → ../AssetOpsBench/.env`.
    - No copy is made, the original `.env` is unchanged, and `.env` is gitignored in the worktree.
    - Removing the symlink afterwards leaves the target untouched.
    - The runner process additionally sources it in a subshell, as in run 620. The command-level `OTEL_TRACES_FILE` and `AGENT_TRAJECTORY_DIR` win, because `load_dotenv` defaults to `override=False`.

## 12. Commands (proposed; DO NOT RUN without approval)

```bash
W=<projects>/AssetOpsBench-agenttrace-spec
R=<projects>/AP/data/assetopsbench/runs
RID=aob-sc3-sonnet5-deep-spec-B-20261014

# E1 (approval): add the locked otel group to the worktree venv
cd "$W" && uv sync --inexact --locked --offline --group otel
"$W/.venv/bin/python" -c "import google.protobuf, opentelemetry.exporter.otlp.proto.common; print('otel ok')"

# C1 (approval): credentials by symlink, no copy
cd "$W" && ln -s ../AssetOpsBench/.env .env && git status --short   # .env must not appear

# Pre-run checks: print only these fields
( cd "$W" && set -a && . ./.env && set +a
  curl -s -u "$COUCHDB_USERNAME:$COUCHDB_PASSWORD" "$COUCHDB_URL/$WO_DBNAME" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["doc_count"], str(d["update_seq"])[:2])'
  curl -s -u "$COUCHDB_USERNAME:$COUCHDB_PASSWORD" -H 'Content-Type: application/json' \
    -X POST "$COUCHDB_URL/$WO_DBNAME/_find" \
    -d '{"selector":{"wonum":"1000045"},"fields":["wonum","status","_rev"]}' \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["docs"])' )
shasum -a 256 "$W/src/couchdb/scenarios_data/shared/iot/chiller_6.json" \
              "$W/src/couchdb/scenarios_data/scenario_3/groundtruth.txt"
stat -f %z "$R/traces.jsonl"            # expect 101154
ls "$R" | grep "$RID"                   # expect nothing

# The run (exactly once)
( cd "$W" && set -a && . ./.env && set +a
  AGENTTRACE_SPECIALISTS=1 \
  AGENTTRACE_CAPTURE_SUBAGENTS=1 \
  AGENT_TRAJECTORY_DIR="$R" \
  OTEL_TRACES_FILE="$R/otel-$RID.jsonl" \
  .venv/bin/deep-agent \
    --model-id anthropic:claude-sonnet-5 \
    --run-id "$RID" \
    --scenario-id scenario_3 \
    --json \
    "$(cat src/couchdb/scenarios_data/scenario_3/question.txt)" )

# Post-run: repeat the pre-run checks (expect 7 / "7-" / WAPPR, rev 1-850525…, same hashes,
# traces.jsonl 101154 B). Then confirm $RID.json, $RID.instrumented.json and a non-empty
# otel-$RID.jsonl exist. Then trace-analyst against §6 and §8.
```

Order: E1 → C1 → pre-run checks (stop if any value differs from §4) → the run → post-run checks → analysis → result document. The symlink is then removed or kept, as the user decides.

## 13. Readiness-review amendments (2026-10-14)

Items marked **FACT** correct §3–§12 with new observations. Items marked **PROPOSED** change the experimental conditions and are **not adopted** until the user approves them. Sections 1–12 are left as written.

### 13.1 FACT: E1 resolved
- `uv sync --inexact --locked --offline --group otel` installed exactly the 8 locked packages in the worktree.
- [OBS] The worktree and original venvs now have identical dist-info sets. The original venv's 51,752 files are unchanged (mtime/size snapshot).
- A dry run of `uv run` in the worktree says "Would make no changes".
- A synthetic span through `init_tracing` + `agent_run_span` was written to a scratch OTEL file (1 line, 7 attributes), with no network.

### 13.2 FACT: credentials are forwarded by allowlist (replaces the C1 symlink proposal)
- With `AGENTTRACE_SPECIALISTS=1`, `with_forwarded_env` copies onto each stdio connection only the variables that server reads:
  - every server gets `COUCHDB_URL/USERNAME/PASSWORD`, plus `LOG_LEVEL` if set;
  - iot: `IOT_DBNAME`, `ASSET_DBNAME`;
  - utilities: `CATALOG_DBNAME`;
  - fmsr: `FAILURE_MODE_DBNAME`;
  - tsfm: `MODEL_CATALOG_DBNAME`, `FEATURE_CATALOG_DBNAME`, `TSFM_WORKDIR`;
  - wo: `WO_DBNAME`, `FAILURE_CODE_DBNAME`;
  - vibration: `VIBRATION_DBNAME`.
- **Never forwarded:** model-provider keys (`ANTHROPIC_API_KEY`, WatsonX, LiteLLM, TokenRouter), `OTEL_*`, and `AOB_READONLY` (M4 sets it to `1`).
- A test fails if a server's code reads an environment variable that is neither forwarded nor deliberately excluded.
- [OBS] With the current `.env`, FMSR's LLM tools are disabled either way: `WATSONX_APIKEY` is empty, and FMSR checks `not os.environ.get(...)`.
- [OBS] An end-to-end read-only check through the runner's flag-on connections, with no model key in the process: WO `get_workorder(1000045, MAIN)` returned WAPPR / CHILLER6, the WO server listed 9 tools, and `iot.sites` returned MAIN and NORTH.
- `tool_availability.forwarded_env_names` records names only. A test with sentinel values confirms that no value is written to any output file.
- The runner process gets only the allowlisted names plus `ANTHROPIC_API_KEY`, through a launcher that `execve`s `deep-agent` with a minimal environment (§13.6). The whole `.env` is not sourced.

### 13.3 FACT: write-capable tools and backing stores (all in the local `couchdb:3.5` container)

| Server | Tool(s) | Writes to |
|---|---|---|
| TSFM | `run_recipe`, `run_tabular_recipe`, `run_plan`, `evaluate` | **creates** CouchDB DBs `tsfm_runs`, `tsfm_plans` and the task result DB (`anomaly_result` for AD) via `CouchStore._ensure` (PUT db); writes files to `/tmp/tsfm_work` (it does not exist now) |
| TSFM | `register_model`, `register_finetuned`, `update_model`, `deprecate_model`, `new_model_version` | `model_catalog` (5 docs) |
| TSFM | `register_feature`, `update_feature`, `deprecate_feature`, `new_feature_version` | `feature_catalog` (5 docs) |
| FMSR | `add_failure_modes` | `failure_mode` (3 docs) |
| FMSR | `generate_failure_modes` | none; disabled (no WatsonX key), so no external LLM call |
| WO | 6 write tools | none; not registered under M4 |

- TSFM has no read-only switch.
- `tsfm_runs`, `tsfm_plans` and the result DB names are hardcoded (`tsfm/config.py:10-11`, `core/tasks.py`), so they cannot be redirected through the environment.
- Baseline [OBS], all pristine (update_seq = doc_count, no deletions):
  - asset 10, catalog 7, failure_code 10, failure_mode 3, feature_catalog 5;
  - iot 10,218, model_catalog 5, vibration 4,097, workorder 7.
  - There is no `tsfm_*` or `*_result` DB.
  - The inventory was unchanged after all readiness probes.
- [INF] Under B, the predicted R4a/R5 failure means `run_recipe` most likely fails before it persists anything. But an agent could point it at any host CSV, so ledger writes cannot be ruled out.

**PROPOSED M5 (requires approval; changes the offered tools):** remove from every agent's tool list the 9 TSFM catalog-mutation tools and FMSR `add_failure_modes`.
- None of them is needed for R1–R7.
- `run_recipe` and its siblings stay, because R5 requires them. Their append-only ledger writes into *new* DBs are accepted as expected, declared side effects.
- **Alternative (stricter, heavier):** an isolated CouchDB container on another port, loaded with `init_data.py` from the same manifest, which would make all writes disposable.
- **Either way, also adopt:** a full `_all_dbs` inventory (doc_count, update_seq, deletions) before and after, plus a listing of `/tmp/tsfm_work`.
  - Any change outside `tsfm_runs`, `tsfm_plans` and `*_result` makes the run INCONCLUSIVE (side effect).
  - Cleanup of the new DBs is a separate user decision.

### 13.4 FACT: recursion_limit is not a cost cap
- [INF] `task` calls `subagent.ainvoke(state)` with no config (`subagents.py:440`). The child inherits the coordinator's config through the context, including `recursion_limit=100`, but counts its own steps.
- So the coordinator gets about 50 model turns and *each* delegation gets up to about 50 more, including parallel ones. No hard total exists.
- Other model calls:
  - `ChatAnthropic.max_retries=2`. Failed attempts are retried inside one callback-visible call.
  - `max_tokens` is unset, so the library default applies [HYP: value not checked].

**PROPOSED budget guard (requires approval; invisible to the model unless it fires):** a flag-gated callback with `raise_error=True`, counting every `on_chat_model_start` across all agents, summarization included.
- It raises **before** call N+1, or once the cumulative cost estimated from `usage_metadata` reaches B − margin.
- [OBS] Feasibility probe (fake model, scratch script, no worktree change): with cap 2, the third call, inside the general-purpose child, was blocked before the provider (2 provider calls for 3 attempts). The exception propagated out of `ainvoke`, where the runner writes the instrumented record with `status: error`.
- Suggested N = 150 calls and B = $10. Overshoot is bounded by the calls already in flight × the cost of one call.
- **New outcome label: BUDGET-STOPPED.** It is reported as is and never retried.
- **Provider-side hard cap [HYP, user to verify in the Anthropic Console]:** a dedicated API key in a workspace with a spend limit, as defense in depth.
- **Wall clock:** macOS has no `timeout`. SIGINT/SIGKILL would skip `write_instrumented` (KeyboardInterrupt is not an `Exception`), so the in-process guard is the primary bound.

### 13.5 Other corrections
- **§4:** add the full DB inventory (13.3) to the pre-run state, and record that `/tmp/tsfm_work` is absent.
- **§10:** replace the TSFM/FMSR bullets with 13.3.
- **§11:** E1 is done. C1 is replaced by 13.2.
- **§9:** the bound is the guard of 13.4 if approved. Otherwise "no hard cap" stands.
- **§12:** superseded by 13.6.

### 13.6 Revised run command (replaces §12's run step once 13.3 and 13.4 are decided; DO NOT RUN)

The launcher is a script file (`$LAUNCHER`, `launch_sc3_B.py`, kept outside the worktree; its location is to be chosen at approval, and it is run from the worktree root). It builds a minimal environment from the allowlisted server variables plus `ANTHROPIC_API_KEY`, read from the original `.env`, and prints nothing:

```python
import os, sys
from dotenv import dotenv_values
sys.path.insert(0, "src")
from agent.deep_agent._specialists import SERVER_ENV

rid, runs = sys.argv[1], sys.argv[2]
vals = dotenv_values("<projects>/AssetOpsBench/.env")
keep = {k for names in SERVER_ENV.values() for k in names} | {"ANTHROPIC_API_KEY"}
env = {k: os.environ[k] for k in ("HOME", "PATH", "USER", "LOGNAME", "SHELL", "TERM", "TMPDIR") if k in os.environ}
env |= {k: v for k, v in vals.items() if k in keep and v}
env |= {"AGENTTRACE_SPECIALISTS": "1", "AGENTTRACE_CAPTURE_SUBAGENTS": "1",
        "AGENT_TRAJECTORY_DIR": runs, "OTEL_TRACES_FILE": f"{runs}/otel-{rid}.jsonl"}
q = open("src/couchdb/scenarios_data/scenario_3/question.txt").read().rstrip("\n")
os.execve(".venv/bin/deep-agent", [".venv/bin/deep-agent", "--model-id", "anthropic:claude-sonnet-5",
          "--run-id", rid, "--scenario-id", "scenario_3", "--json", q], env)
```

```bash
cd <projects>/AssetOpsBench-agenttrace-spec
.venv/bin/python "$LAUNCHER" aob-sc3-sonnet5-deep-spec-B-20261014 \
  <projects>/AP/data/assetopsbench/runs
```

- Pre- and post-run checks: §12's checks, plus the full DB inventory and the `/tmp/tsfm_work` listing.
- Add the guard's variables (e.g. `AGENTTRACE_MAX_MODEL_CALLS`, `AGENTTRACE_MAX_COST_USD`) to `env` only if 13.4 is approved and implemented.

## 14. Approved preparation decisions and final amended plan (2026-10-14)

The user approved these preparation decisions on 2026-10-14. **They do not authorize the paid run.** Where §14 conflicts with §3–§13, §14 applies. §1–§13 are left as written.

- **Write safety:** a separate, disposable CouchDB (C2) instead of M5. **All original MCP tools are kept**, so the partitions in §3 and the S4 check are unchanged.
- **Budget guard (G1):** off by default and shared by all agents. Limits are 200 model calls and $10 estimated cost at uncached prices.
- **Launcher:** `AP/docs/experiments/launch_sc3_B.py`, with the no-LLM checks in `preflight_sc3_B.py` and `sc3_isolation.py` beside it.
- **Second annotator:** TBD. They must be named before any labeling or evaluation (§8).

### 14.1 Upstream benchmark versus research modifications

| | Upstream benchmark, unchanged | Research modification (declared) |
|---|---|---|
| Task | `question.txt` verbatim (only the trailing newline is stripped), `groundtruth.txt`, `chiller_6.json`, `workorders.csv` (hashes in §2, re-checked by the preflight) | none |
| Data loading | `init_data.py` with the scenario_3 manifest. Its sha256 `cb28f1be…` equals the default manifest that loaded the shared DB. | **C2:** loaded into a separate container (14.2) |
| Agent | `AGENT_SYSTEM_PROMPT`, `anthropic:claude-sonnet-5`, `recursion_limit` 100, default `StateBackend`, deepagents 0.5.3 | **M1** specialists, **M4/M4b** read-only WO, **M6** tool capture (§3) |
| Tools | every MCP tool of every server (no M5) | WO write tools are not registered (M4) |
| Model call settings | `max_tokens` = 4,096 ([OBS]: the langchain-anthropic default for this model id, checked offline), `max_retries` = 2 | none. G1 reads them and never changes a request. |
| Environment | MCP server code and its env-variable names | allowlisted variables only (§13.2); the CouchDB URL and credentials point to C2 |
| Cost | none upstream | **G1:** budget guard (14.3) |

Visibility to the model:
- **C2:** visible only through data, and the data is the same. One exception: `catalog` document `_id`s are random per load (14.2). If a tool returns them, the values differ from a run on the shared DB [INF].
- **G1:** invisible unless it fires, in which case the run stops.

### 14.2 C2: isolated CouchDB [OBS 2026-10-14]

Setup, by `sc3_isolation.py create`, then `load`:
- **Container:** `agenttrace-sc3-couchdb`, labelled `agenttrace.purpose=sc3-isolated`.
- **Image:** the same image id as the shared container (`sha256:8cf5f844…`, CouchDB 3.5.2).
- **Network:** published only on `127.0.0.1:5985`.
- **Storage:** one new named volume, `agenttrace-sc3-couchdb-data`, and **no bind mounts**. It cannot see the shared volume `couchdb_couchdb-data` or the repository.
- **Credentials:** its own admin user, with a random password held only in the container's config. They are never written to a file or printed.

**Isolation checks.** Every write step, every preflight and the launcher first run `assert_isolated`. It rejects:
- any URL other than `http://127.0.0.1:5985`, and port 5984 in particular;
- an unexpected container id, label, mount or port binding;
- a server uuid at the URL that differs from the uuid read inside the container with `docker exec`, or that equals the shared server's uuid;
- isolated credentials that the shared server accepts. [OBS] It returns 401.

The loader ran in a child process whose `COUCHDB_URL` was bound to the isolated URL. That process asserted `loader.COUCHDB_URL` before its first request. `--reset` was never used.

**Fidelity**, isolated versus shared, via GET and `_find` requests only:

| DB | doc_count | Content and revs | Bodies without `_id` |
|---|---|---|---|
| asset 10, failure_code 10, failure_mode 3, feature_catalog 5, iot 10,218, model_catalog 5, vibration 4,097, workorder 7 | = shared = §4 | identical | identical |
| catalog 7 | = shared = §4 | **differ** | identical |

- **Why `catalog` differs:** `collections.json` gives it no `primary_key`, so CouchDB assigns random `_id`s at load.
- **Other checks:** no deletions in any DB, and `update_seq` = `doc_count`. WO 1000045 is WAPPR with `_rev` `1-850525…` in both DBs.
- **Inferred:** the §4 Chiller 6 counts and range hold for the isolated IoT DB, because its content is identical [INF].

The shared container was not modified. Its inventory, update_seq values and start time were snapshotted before C2 was created and again after all preparation; they are identical (see the preparation report).

**Not isolated:** `/tmp/tsfm_work` is a host path. TSFM writes files there whatever DB it uses. It is absent now. It is listed before and after the run, and cleaning it up is a separate user decision.

### 14.3 G1: model-call and spending guard (`src/agent/deep_agent/_budget_guard.py`)

**Activation.** `AGENTTRACE_BUDGET_GUARD=1`, off by default.
- Every limit and price must be set explicitly, or the run fails before any connection or model call.
- With the flag off, nothing is attached (tests).

**Mechanism.**
- One `BudgetGuard` callback is attached to the runner's chat-model instance.
- The coordinator, every specialist, `general-purpose` and summarization all call that same instance ([OBS] `resolve_model` returns it unchanged). Every call therefore passes through one guard.
- Before each call, under a lock, the guard reserves an upper-bound cost:
  - the input bound is the UTF-8 bytes of the messages and tool schemas, plus 2,048 + 16 per message, at the highest input-side price;
  - the output bound is `max_tokens` at the output price.
- It raises `BudgetExceeded` **before the provider request** when any of these holds:
  - call 201 would start;
  - committed cost + in-flight reservations + this reservation would exceed $10;
  - `max_tokens` is unknown (fail closed);
  - the estimate itself fails.
- When a call ends, its reservation is replaced by its cost from `usage_metadata`:
  - every input token is priced as uncached, cache reads included;
  - cache writes are priced at their write price.
  - An errored call, or one without usage, keeps its full reservation.
- The stop is sticky: once the guard fires, every later call is refused too.

**Prices** (USD/MTok): input 2.00, 5-minute cache write 2.50, 1-hour cache write 4.00 ([INF] 2× input), output 10.00.
- They are taken from the run-620 pre-registration and **must be re-checked on run day**.
- The launcher refuses `--execute` unless `PRICES_CHECKED_ON` equals the run date.

**Record.** The instrumented record gains a top-level `budget_guard` object, flag-on only. It holds:
- `outcome` (`BUDGET-STOPPED` or null), `stop_reason`, limits and prices;
- calls started, settled, errored, without usage and over reservation;
- committed and unsettled estimates and peaks;
- `blocked`, each entry with the refused call's `lc_run_id`.

A refused call's `llm_start` is still captured (capture runs first), but it has no `llm_end`. Its `lc_run_id` in `blocked` marks it as refused.

**Validated without an LLM** (`tests/test_budget_guard.py`, 37 tests):
- **Limits:** exactly 200 calls are allowed and the 201st is refused; the stop stays in force; in-flight reservations count towards the limit.
- **Concurrency:** 32 threads racing for 5.5 reservations get exactly 5.
- **Real deepagents graph** (specialists, scripted fake model):
  - two parallel specialist calls overlap (peak 2 in flight) through one guard;
  - the call limit stops a `wo` specialist's turn before the provider, and the record is written with `status: error`, `outcome: BUDGET-STOPPED`;
  - the cost limit refuses the second of two parallel specialists while the first's reservation is in flight.
- **Real `ChatAnthropic` class** (dummy key, closed localhost port): a refused call makes no request, and `max_tokens` reaches the guard.

**Limitations. G1 is not a hard dollar cap.**
- It bounds an *estimate*. The input bound assumes at least one byte per token plus a fixed framing allowance [INF]. `calls_over_reservation` in the record reports any call whose actual usage cost exceeded its reservation.
- `max_retries=2` retries happen inside one guarded call and are invisible to callbacks. If the provider bills a request that is then retried, the real cost of that call can exceed its estimate.
- Prices are configured, not fetched.
- The only hard cap available is provider-side: a dedicated key in a workspace with a spend limit [HYP]. The user must check this in the Console.

**Risk of a stop** [INF]. Uncached pricing ignores cache-read discounts. At the high end of the §9 estimate (3.6M input and 50k output tokens), the committed estimate is about $7.2 + $0.5. Late-run reservations then add up to roughly $0.1–$1.7 per in-flight call, depending on context size. **BUDGET-STOPPED is a realistic outcome for a long run**, even though the actual billed cost with caching would be lower.

### 14.4 Outcome labels (amends §6)

- **BUDGET-STOPPED** (new):
  - The guard fired, as shown by `budget_guard.outcome` in the instrumented record.
  - It is reported as is and **never retried**. Whether any delegation happened before the stop, and S1–S4 on the captured portion, are reported descriptively.
  - It is never presented as a completed multi-agent run.
- **INCONCLUSIVE** (§6) gains these conditions, all evaluated by `preflight_sc3_B.py --post`:
  - an existing isolated DB changed (doc_count, update_seq or digests);
  - a new isolated DB other than `tsfm_runs`, `tsfm_plans` or `*_result` appeared;
  - the WO 1000045 status or rev changed;
  - the shared inventory changed;
  - `traces.jsonl` changed;
  - the `budget_guard` object is missing from the record.
  - New `tsfm_runs`, `tsfm_plans` or `*_result` DBs, and new files in `/tmp/tsfm_work`, are expected, declared side effects.
- S1–S5 and the other labels are unchanged. The S4 partitions are those of §3 (coordinator 79; iot 18, tsfm 47, fmsr 9, wo 15), re-observed by the preflight server probe on 2026-10-14.

### 14.5 Preserved from §1–§13

- **Ground-truth discrepancy (§5):** E-GT (benchmark literal, `end` `2020-06-26T11:14:36`, which has no value and so violates R7) and E-R7 (`end` `2020-06-30T23:45:00`) are scored separately and never merged. `anomalies_found` is UNVERIFIED.
- **Predicted condition-B failure (§5):** R4a/R5 are expected to fail on virtual versus host paths. Such a failure is labeled configuration-induced and is not counted as an agent-reasoning failure.
- **Stopping rule (§7):** exactly one run, with no retry for any reason (provider error, bad answer, no delegation, BUDGET-STOPPED).
  - SINGLE-AGENT: record it, never present it as multi-agent evidence, do not run condition A, and return to the user.
- **Labeling (§8):** two annotators. Annotator 2 is independent and blind to annotator 1's labels, and is named before evaluation. Disagreements are reported, not reconciled. The LLM baseline and any grader need their own pre-registration and approval.
- **Cost (§9):** the estimate is unchanged. "No hard cap" is replaced by "G1 estimated bound; no hard cap" (14.3).

### 14.6 Procedure (replaces §12 and §13.6)

All commands run from the worktree root with its `.venv`. There is no `.env` in the worktree and no `source .env`.

1. **Run day:** re-check the Sonnet 5 prices. Set `PRICES` and `PRICES_CHECKED_ON` in the launcher. The launcher, guard and source hashes are recorded in every preflight record.
2. **User, optional:** a provider-side spend limit [HYP].
3. **Dry run:** `.venv/bin/python …/AP/docs/experiments/launch_sc3_B.py`. It runs every preflight check, including the real MCP server probe against C2, writes `runs/preflight/<run id>.pre.<UTC>.json` and makes no model call. Stop on any FAIL.
4. **The run, exactly once, after explicit approval:** `.venv/bin/python …/launch_sc3_B.py --execute --confirm-run-id aob-sc3-sonnet5-deep-spec-B-20261014`.
   - The launcher repeats the preflight.
   - It refuses if the confirmation, price date or any check fails, or if an output file for the run ID already exists.
   - Otherwise it `execve`s `deep-agent` with the minimal environment.
   - The run ID is kept as pre-registered, even if the run happens on a later date.
5. **Post-run:** `.venv/bin/python …/preflight_sc3_B.py --post`. Then the trace-analyst pass, the blind second annotation and the result document.
6. **Cleanup** of C2 and `/tmp/tsfm_work`: a separate user decision, after the result document.

### 14.7 Open before execution can be approved

- Explicit user approval of this amended pre-registration and of the single paid run.
- The run-day price re-check (step 1).
- The second annotator named (required before evaluation; not before the run).
- Optional: a provider-side spend limit.
- Unchanged open decisions (STATE.md): the instrumented schema version bump (0.1, additive fields `tool_availability` and `budget_guard`), and the historical `traces.jsonl`.

### 14.8 Final corrections before execution (2026-10-14)

The user approved these corrections on 2026-10-14. **They do not authorize the paid run.** Where §14.8 conflicts with §14.4 or §13.3, §14.8 applies. They are enforced by `preflight_sc3_B.py --post` and tested in `test_preflight_sc3_B.py` (no LLM, no Docker).

**Prices** [OBS 2026-10-14, official pricing page `platform.claude.com/docs/en/about-claude/pricing`], Claude Sonnet 5, USD/MTok:
- input 2.00; 5-minute cache write 2.50; 1-hour cache write 4.00 (now [OBS]; replaces the [INF] in 14.3); cache read 0.20; output 10.00.
- $2/$10 is the standard price: the increase to $3/$15 that had been scheduled for 2026-09-01 was cancelled.
- Sonnet 5 has no long-context premium. The run does not set `inference_geo`, so the 1.1× US-only multiplier does not apply. A workspace-level default region is not visible to the launcher [HYP, the user checks this].
- G1 still prices cache reads at the full input price (10× the actual rate). Its estimate therefore stays above the expected bill, and BUDGET-STOPPED stays a realistic outcome (14.3).
- `PRICES_CHECKED_ON` is `2026-10-14`. `--execute` on any later local date refuses until the prices are re-checked and the date is updated.

**Database changes.** The post check compares the isolated and shared inventories with the latest passing pre record and classifies every change:

| Class | Which changes | Label |
|---|---|---|
| Safety failure | Any change to the **shared** CouchDB | `shared_safety_failure: true`. The run is reported first as a safety failure, and no result is evaluated until the cause is explained. |
| Expected TSFM databases | New isolated DBs `tsfm_runs`, `tsfm_plans`, `*_result` (§13.3) | Declared side effect. Listed with doc counts; not a failure. |
| Permitted writes | Changed isolated `model_catalog`, `feature_catalog` or `failure_mode`. These are the only isolated DBs that the production write tools kept in §14 can write (TSFM catalog and feature tools, FMSR `add_failure_modes`). [OBS] No other server has a registered write tool: vibration keeps its signals in memory, and WO writes are not registered (M4). | **Not INCONCLUSIVE.** Reported as observed agent behaviour and assessed against §5 like any other action. The trace analyst must attribute each change to a tool call in the trace by `tool_call_id`. A change that cannot be attributed is reclassified as unexpected. |
| Unexpected writes | A change to any other isolated DB (`workorder`, `iot`, `asset`, `catalog`, `failure_code`, `vibration`); a removed DB; a new DB outside the declared pattern; any change to the status or rev of WO 1000045 | INCONCLUSIVE (side effect). They violate the scenario's read-only inputs, and no registered tool can make them. |

**Host side effect.** `/tmp/tsfm_work` was absent at every pre check. `TSFM_WORKDIR` is not set in `.env`, so TSFM uses this upstream default. New files there are an expected, declared side effect: the post record lists their names, and they are not a failure. The directory is not isolated [INF]: no other TSFM process is expected to write there during the run. Cleanup remains a separate user decision.

**Outcome from the output files** (`classify_outputs`):
- **Evidence required in every case.**
  - A valid instrumented record: schema `assetopsbench.deepagent.instrumented/0.1`, this run ID, `status` `ok` or `error`.
  - `error` consistent with `status`: null when `ok`, a typed object when `error`.
  - A `budget_guard` object with `source` `AGENTTRACE_BUDGET_GUARD` and exactly the configured limits (200 calls, $10) and launcher prices. It must also be internally consistent: `outcome` is BUDGET-STOPPED ⇔ `stopped` ⇔ a `stop_reason` ⇔ at least one `blocked` call, and a fired guard implies `status: error`.
  - A non-empty OTEL file.
- **COMPLETED:** `status: ok`, the guard did not fire, and the native trajectory `$RID.json` exists with this run ID. These success checks are as strict as before.
- **ERROR:** `status: error`, the guard did not fire, and no native trajectory. The runner writes `$RID.json` only on success (`runner.py`, `persist_trajectory` after `ainvoke`), so its absence is expected here, and its presence would contradict the record. Reported as is and never retried.
- **BUDGET-STOPPED:** the guard fired, with `status: error` and no native trajectory. Reported as in 14.4, separately from ERROR, with its `stop_reason`, calls started and estimate.
- **EVIDENCE-INVALID:** any of the checks above fails, including missing outputs. No outcome is claimed; the failing checks are reported. This replaces 14.4's "`budget_guard` missing → INCONCLUSIVE", which is now enforced.
- **Trace evidence after an ERROR or BUDGET-STOPPED run.** The analysis uses the instrumented record and the OTEL span:
  - the agents, delegations and events up to the stop; a delegation still running at the stop is marked `incomplete` (an interrupted `task` is `status: error` [OBS in tests]);
  - a refused call keeps its `llm_start`, has no `llm_end`, and its `lc_run_id` appears in `blocked`.
  - The missing native trajectory is reported as missing, never reconstructed.
- SINGLE-AGENT (§7) is still assigned by the trace analyst, on top of the outcome above.

**Limitations.**
- The post check cannot itself attribute a permitted write to a tool call; the trace analyst does.
- A hard kill (SIGKILL, power loss) can leave no instrumented record. That run is EVIDENCE-INVALID.
- G1 remains an estimate, not a hard cap (14.3).
