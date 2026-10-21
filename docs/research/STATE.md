# Research state

Last updated 2026-10-20. Source: the checkpoint linked below (its §-numbers are cited as "ckpt §N").

## Handoff (2026-10-20, latest): adapter increment 1 pushed to fork; viz-profile D1 rev 3 written

**Status.**
- No model call, agent run, database access or paid experiment.
- Schema 0.3 (`2273d210…`), the hand-grounded fixtures and the raw traces are unchanged. The viz profile was revised only for D1 rev 3 (below). The 621 (`aa8531f2…`) and sc3 (`4d575909…`) traces were re-hashed to confirm [OBS].
- **Commit:** fork worktree `AssetOpsBench-agenttrace-spec`, branch `research/agenttrace-specialists`, `c194233` "feat(deep_agent): add deterministic AgentTrace structural adapter and verifier". Pushed on 2026-10-20 to `fork` (`DevikaVishnu/AssetOpsBench`), branch `research/agenttrace-specialists`, fast-forward `324de44..c194233`. `git ls-remote fork` shows `c194233` [OBS]. Not merged and not in any PR. `origin` (IBM) is untouched.
- **Files:**
  - `src/agent/deep_agent/_semantic_adapter.py` (adapter);
  - `_semantic_verify.py` (independent verifier);
  - `_semantic_locator.py` (the only shared code: locator and hash resolver);
  - `tests/test_semantic_adapter.py`.
- **Worktree suite: 557 passed** [OBS]. That is the 440 before this work plus 117 adapter tests. Same command as below.

### Decisions applied (user-approved 2026-10-20)
- **E1:** `order` = the seq of the event's first raw record, as observation order only. Start and end seqs are in `raw_ref`. `profile_local.adapter.order` carries the caveat that overlapping events support no precedence, causation or reiteration, plus the list of overlaps. 0.3 is unchanged.
- **E2/E3 deferred:** eviction substitutes, the question and system prompts are recorded as skipped items with reasons.
- **E4:** code location as above. The verifier shares only `_semantic_locator`.
- **Agent-origin attribution.** `llm_start.agent_id` comes from the capture's walk of the LangChain run tree (`_subagent_capture.on_chat_model_start`: `_owner(parent_run_id)`), so it is [INF], never [OBS].
  - **`offered_tools` present and non-null:** agent origin [INF] (rule `offered_tools_present`).
  - **`offered_tools` absent:** agent origin [INF] only if `agent_loop_signature` holds:
    - the parent run is unique among model calls;
    - message 0 equals the system message of the agent's first call;
    - continuity: the first call is system + human messages only; every later call extends the previous established call's input, then its output (role, content and tool_calls), then exactly one tool message per tool call, in order.
  - Post-summary calls fail continuity, and so does every later call of that agent.
  - **Every other paired call is kept** as an event with origin `$unresolved`. Candidates are the raw agents, `framework:deepagents` and `$absent`. The rules are `no_rendered_input`, `offered_tools_null`, `agent_loop_signature_failed` and `agent_id_unattributed`.
    - Each call keeps its order, input/output locators and digests. Its argument evidence gets source `$unresolved` (agent, framework); that two-candidate set is an extractor choice.
    - Each `$unresolved` has a `profile_local.ambiguities` entry, and `conformance.canonical_complete` is false.
    - These events source no `delivers`, claims, states or uptake. O2 returns UNRESOLVED for them.
  - **The refused call 416** (no `llm_end`) is not an event. Its `model_call_unpaired` skip keeps `raw_agent_id` and `input_locator`.

### Results [OBS]

| Run | Events (agent / unresolved / tool) | Evidence (results / args / unresolved args) | Delivers |
|---|---|---|---|
| 620-fileobs | 21 (7 / 0 / 14) | 43 (14 / 29 / 0) | 172 |
| 621 | 58 (24 / 0 / 34) | 123 (34 / 89 / 0) | 1376 |
| sc3 | 153 (70 / 1 = call 383 / 82) | 261 (82 / 179 / 0) | 4546 |
| 607 | 17 (0 / 7 / 10) | 23 (10 / 0 / 13) | 0 |
| 612 | 15 (0 / 6 / 9) | 21 (9 / 0 / 12) | 0 |
| 615 | 15 (0 / 5 / 10) | 23 (10 / 0 / 13) | 0 |
| 617 | 29 (0 / 11 / 18) | 47 (18 / 0 / 29) | 0 |
| 620-1005 | 33 (0 / 11 / 22) | 64 (22 / 0 / 42) | 0 |

- **Hand-grounded links recovered:**
  - 621: 2/2, first delivery of R at 125;
  - sc3: 5/5, all first deliveries (D at 96 via the delegation_id join, G 386, R1 392, R2 398, R3 404);
  - 620 comparison: 2/2.
- **Self-checks:**
  - the 620f/621 agent calls pass `agent_loop_signature` 7/7 and 24/24;
  - delivery-link digests for the three input runs are unchanged by the origin corrections;
  - renamed IDs and shifted seqs give the same shape;
  - reruns are byte-identical;
  - joins fail closed (duplicate tool message, one-byte change, duplicate `tool_end`).
- **Independent reviews:**
  - **Trace-analyst:** recomputed delivers from raw data, with no missing or extra links (621: 1376, sc3: 4546). It confirmed the 10 evictions, the irregularities (363–365, 383, 416, 366/372/378), the overlaps and the signature results; the traces were unchanged.
  - **Schema-auditor (four rounds):** no BLOCKER, no schema conflict. The minor findings were applied, except one that predates this work: IDs and `raw_ref` objects don't follow the viz profile's §3 format.

### Remaining issues
- **Viz-profile D1 rev 3 is written and committed** (AP; profile status "DRAFT, revision 3"):
  - `order` = first raw seq, as observation order only; `start_seq`/`end_seq` in `raw_ref`; open spans run to the end of the trace;
  - observed precedence = `end_seq(X) < start_seq(Y)`, a PROFILE-LOCAL, conservative reading of 0.3's deferred partial order (§4.3, §12);
  - overlapping spans are overlapping observations, not proof of simultaneous execution; overlaps are listed in `profile_local.order`;
  - where precedence isn't observed: the stored link fails its check, a tie span goes to ambiguities, the inference (including one relying on a withheld link's absence) is UNKNOWN where it defines UNKNOWN, and "not established" for §10.3 Lineage;
  - delegation: producer (parent model event, only where the arguments first observably occur in its output; otherwise `$unresolved`), `task` carrier (never producer) and recipient (only through stored `delivers`) are kept separate.
  - Schema-auditor: three rounds, no BLOCKER. Its final nit (§10.3 Lineage has no UNKNOWN; use "not established") is applied.
- **Adapter vs D1 rev 3:** the adapter output does not yet carry `start_seq`/`end_seq` per event or the `profile_local.order` overlap list in the profile's form. Whether model calls of different agents ever overlap is unchecked.
- **Inference limits:**
  - a framework call that reproduces an agent's exact conversation state would pass `agent_loop_signature` [HYP];
  - fail-closed loses genuine post-summary agent calls as agent-input events when `offered_tools` is absent;
  - deliveries into 416 (30) are unrepresented by design.
- **Viz-profile §3 format** (IDs and `raw_ref` objects) is not followed by the adapter output.

### Next research tasks
1. **DONE (2026-10-20):** viz-profile D1 rev 3 written and committed in AP (not pushed).
2. Increment 2:
   - E2 eviction substitutes (new evidence; framework eviction event; source `$unresolved` [framework, tool]);
   - E3 question (external evidence; source `$unresolved` [user, benchmark]);
   - the system prompt;
   - re-check that a child's human message can't match both the question and a delegation argument;
   - the completed-`task` result path (not yet exercised).
3. **DONE (2026-10-20):** `c194233` pushed to `fork`.
4. Still pending: naming annotator 2, the result document, cleanup of C2 / `tsfm_plans` / `/tmp/tsfm_work`, and the instrumented-schema version bump.

Test command, from the worktree root:
`env -u OTEL_TRACES_FILE .venv/bin/python -m pytest src/agent src/servers/wo src/observability -q -p no:cacheprovider -W ignore::DeprecationWarning`

## Handoff (2026-10-20, superseded by the section above): O2/O3 committed, extraction audit done, E1–E4 recommended, work preserved

**Status.**
- No model call, agent run, database access or paid experiment.
- Schema 0.3 (`2273d210…`), the viz profile and the raw traces are unchanged.

### O2/O3 comparison (`agenttrace.compare/0.1`): implemented and committed
- **Code:** `src/agent/deep_agent/_semantic_compare.py` (O2 `exposure_at`, `claim_delivery`, O3 `state_vs_evidence`).
- **Tests:** `tests/test_semantic_compare.py`.
- **Fixtures** (`tests/fixtures/agenttrace_compare_0_1/`):
  - `SPEC.md` and `README.md`;
  - `aob-621-compare` (positive control);
  - `aob-620-compare` (abstention control);
  - `synthetic-compare` (rule coverage only, SYNTHETIC; never evidence of agent behavior).
- **Worktree suite:** **440 passed** [OBS 2026-10-20, re-run just before the commits]. Command, from the worktree root:
  `env -u OTEL_TRACES_FILE .venv/bin/python -m pytest src/agent src/servers/wo src/observability -q -p no:cacheprovider -W ignore::DeprecationWarning`

### Automated semantic-extraction feasibility audit [2026-10-20, read-only]
- **Recommendation.**
  - **Conditional GO** for one no-model step: a deterministic structural adapter (stage 1) plus an independent verifier (stage 2).
  - **NO-GO for now** on automated claims, propositions, states and direct links. There is no held-out gold data, and faithfulness and directness are human judgments (§7.1, §7.2 r4).
- **Stage 1 output.** A 0.3 `semantic` block with run, entities, events, evidence and positive `delivers` only.
  - `profile_local.adapter` records the boundary rules, `$unresolved` items, skipped records with reasons, `delivery_telemetry: present|absent` and `claims_extracted: false`.
  - It never emits `propagates_to`, `checks`, direct links, non-delivery, hierarchy or `$unresolved` on `order`.
- **Facts behind it** [OBS]:
  - **Rendered model inputs** exist only in 620-fileobs, 621 and sc3, and all three are development material.
  - **Joins across those runs:**
    - tool-call lifecycle 199/199 by `tool_call_id` (one sc3 event, `tool_end` 364, has no id);
    - model start/end 142/142 by `lc_run_id` (the refused call 416 is unpaired);
    - committed tool result found in the next same-agent input 130/130.
- **Evaluation sets.**
  - **Development:** 620-fileobs and 621.
  - **Frozen regression, not held-out:** sc3. The expected result is fixture B's 5 first-delivery links plus 364/383/384/416 surfaced.
  - **Partial structural held-out:** 607, 612, 615, 617 and 620-1005. These are no-input runs: no `delivers`, and `delivery_telemetry: absent`.
  - **A true held-out trace does not exist.** It needs a new pre-registered paid run plus claim gold from two annotators.
- **Acceptance criteria:**
  1. every `raw_ref` resolves and every sha reproduces;
  2. 0 byte-equality failures, and multi-match joins fail closed;
  3. all hand-grounded `delivers` are recovered (fixture A 2, run 620 comparison 2, fixture B 5);
  4. every irregularity is surfaced;
  5. no-input runs are flagged `absent`;
  6. no run-specific constants (a grep test and a mutation test);
  7. byte-identical reruns, and the raw traces are re-hashed unchanged.
- **O2/O3 reuse.**
  - O2 `exposure_at` works unchanged on stage-1 output.
  - `claim_delivery` and O3 need verified claims and states (a later stage 3/4).

### E1–E4 adapter decisions: recommendations, not implemented
These are recommendations from the 2026-10-20 read-only review (schema-auditor plus trace-analyst). The user has not yet confirmed the individual choices.

- **E1, parallel tool-call `order`.**
  - **Recommendation:** revise viz-profile D1 as revision 3. D1 is profile-local, so this is not a 0.3 change.
    - `order` = the seq of each event's first raw record; the start and end seqs go in `raw_ref`.
    - Declared caveat: sibling order is start order only, not precedence or causation; siblings overlap; a `task` event spans its child's events.
  - **Facts** [OBS]:
    - 22 multi-call outputs, all interleaved;
    - sibling `tool_start` order = `tool_calls[]` order;
    - the next rendered input lists tool messages in `tool_calls[]` order, never in end order;
    - no agent has overlapping model calls.
  - **Rejected:**
    - emitting no tool events: `produced_by` would be fabricated (§4.4);
    - keeping D1 unchanged: it excludes every AssetOpsBench run.
- **E2, eviction substitute.** There are 10 evictions, all `history` results [OBS]: 620 ×1, 621 ×3, sc3 root ×3, sc3 sub-1 ×3.
  - Each substitute is 967/968 chars, about 205 of them a verbatim preview of the original.
  - It is recorded only in `tool_result_committed.content` and in rendered inputs.
  - **Recommendation:**
    - make it a new evidence item;
    - `produced_by` = one framework eviction event, origin `framework:deepagents`, covering `file_write` plus `tool_result_committed` (same `tool_call_id`, adjacent seqs). That they are one procedure is [INF] from `filesystem.py:1344-1347` and is to be re-checked in code; the fallback is `$unresolved`;
    - `source` = `$unresolved` with candidates [framework, tool];
    - `delivers` only where the rendered tool message equals the committed content;
    - no link from the tool result to the substitute (§5.3, §12).
- **E3, question and system prompt.**
  - **Question:**
    - external evidence (no `produced_by`), `raw_ref` = the record's `question` field;
    - `source` = `$unresolved` with candidates [user, benchmark];
    - `delivers` to root inputs, where `[0][1]` is byte-identical to the question [OBS].
    - The child's first human message is the delegation description (`llm_end` 93), not the question.
  - **System prompt:** not emitted in stage 1.
    - No record field holds it or its hash [OBS] (fixture ambiguity 4).
    - It may need splitting into several items.
    - Recorded in `profile_local` as not represented, with its hash.
- **E4, location.** The specialist worktree: `src/agent/deep_agent/_semantic_adapter.py` and `_semantic_verify.py`. The verifier shares only a locator/hash resolver with the adapter.

**Smallest next step (after approval):**
- **Build** stages 1 and 2: agent, tool and framework entities; model-call, tool-call and eviction events; evidence for tool results, substitutes, model text parts, tool-call arguments and the question; positive `delivers` joined by `tool_call_id` plus exact equality.
- **Test it:**
  - on 620-fileobs and 621;
  - frozen on sc3;
  - on the five no-input runs;
  - against the acceptance criteria above;
  - by re-running O2 `exposure_at` on the adapter output for 621.

### Preservation on GitHub [OBS 2026-10-20]
- **AssetOpsBench fork**, branch `research/agenttrace-specialists`, pushed to `fork` only, on top of `1a88708`:

  | Commit | Contents |
  |---|---|
  | `2902c12` | O2/O3 |
  | `5bf563f` | capture and file observer |
  | `ad5c69a` | specialists |
  | `3f261ab` | budget guard |
  | `9122d3b` | runner wiring and tests |
  | `324de44` | the checkpoint and handoff docs, copied with home paths redacted |

  - The committed `runner.py`, `_specialists.py`, `_subagent_capture.py`, `_file_observer.py` and `_budget_guard.py` are byte-identical to the `source_sha256` values in the sc3 post-run preflight record.
  - Not merged; no PR.
- **IBM upstream pushes are disabled.** `remote.origin.pushurl = DISABLED-no-push-to-IBM-upstream` in the shared AssetOpsBench config, so it applies to both working trees. Fetch from IBM still works.
- **AP:** branch `docs/agenttrace-research-state`, with a PR against protected `main`. Not merged.
- **Path redaction in the published AP copies.**
  - Machine-specific home paths are replaced by repo names, or by `<projects>/` in commands.
  - The sc3 scripts now derive their paths from `__file__`. The resolved paths were verified equal to the old literals, and `test_preflight_sc3_B.py` still gives 42 passed.
  - **Every sha256 quoted elsewhere in this file for these files refers to the executed, unredacted versions.** They are kept byte-exact, with `SHA256SUMS`, in the local-only, gitignored `AP/local/executed-unredacted/`:

    | File | Executed | Published |
    |---|---|---|
    | `launch_sc3_B.py` | `cd880f31…` | `a0683329…` |
    | `preflight_sc3_B.py` | `83aa1008…` | `e001bae7…` |
    | `sc3_isolation.py` | `8beb2f58…` | `de536724…` |
    | `test_preflight_sc3_B.py` | `b1c4c137…` | `016cc053…` |
    | sc3 pre-registration | `c7ed2fe2…` | `3fc46bc8…` |
    | run 620 pre-registration | `89dbdb02…` | `99ece668…` |

### Next task
1. The user confirms or adjusts E1–E4, including viz-profile D1 revision 3.
2. Implement stages 1 and 2 as above. No model, no claims, no paid run.
3. Still pending:
   - review of the IBM_Project2 PR;
   - naming annotator 2;
   - the result document;
   - cleanup of C2, `tsfm_plans` and `/tmp/tsfm_work`;
   - the instrumented-schema version bump.

## Handoff (2026-10-20, superseded by the section above): two hand-grounded 0.3 fixtures and offline tests

**Status.** Approved by the user on 2026-10-20 and implemented offline:
- no model call, agent run, database access or routing change;
- schema 0.3 (`2273d210…`) and the visualization profile are unchanged;
- the raw traces are unchanged (the tests re-hash them);
- nothing is committed.

The routed-coordinator architecture is approved as a default-off experimental condition only, and is **not implemented**.

### Files (specialist worktree, untracked)
- `src/agent/deep_agent/tests/fixtures/agenttrace_semantic_0_3/aob-621.semantic.json`
- `src/agent/deep_agent/tests/fixtures/agenttrace_semantic_0_3/aob-sc3-B.semantic.json`
- `src/agent/deep_agent/tests/fixtures/agenttrace_semantic_0_3/README.md`: anchors, adapter decisions, declared limits, the confound, the budget stop and 7 schema ambiguities
- `src/agent/deep_agent/tests/test_semantic_fixtures.py`: 31 tests. They read the AP traces read-only (`AGENTTRACE_AP_ROOT`, default `../AP`) and skip if the traces are absent.

### Tests [OBS 2026-10-20]
- `test_semantic_fixtures.py`: **31 passed**.
- Worktree suite (same command as before): **345 passed** (314 + 31).

### Fixture A: run 621, single agent
- R (`read_file` `01S66j…`, `tool_end` 123, sha `0734f555…`) is delivered at llm_start 125 and 157 (message 46).
- A is the answer, `llm_end` 158 `content[1].text` (sha `293d820e…`).
- One claim, span [1304:1428], with its proposition and a state (root, TRUE).
- `propagates_to(R → A)`:
  - S = A[1320:1349], `1,822 → 1,115 → 3,186 → 1,281`;
  - [INF] the model rounded each value;
  - the tie rule was checked over all 59 messages of input 157;
  - 5,477 is excluded because it also occurs in messages 9, 40, 43 and 44.
- Upstream hops stay unlinked. `run.outputs` is UNKNOWN: the harness `answer` equals A but is OPEN (§4.1).

### Fixture B: scenario_3 condition B
- **Evidence:**
  - O, root's `history` result (38/39);
  - F, the eviction file (`file_write` 40). Its origin is `framework:deepagents`, verified in code at `filesystem.py:1344-1347`; its source is `tool`;
  - D, the description (`llm_end` 93);
  - G, the child's `grep` (381);
  - R1–R3, the child's reads (390/396/402).
- **Links:** only `delivers` at 96, 386, 392, 398 and 404.
- **Not stored:** claims, states, availability, file lineage and parent/child links.
- **Summarizer 383:** not represented; its origin is left UNRESOLVED.
- **Documented in the fixture:** the identical-sha confound and the budget stop.

### Corrected scenario_3 file-channel provenance [OBS, verified 2026-10-20 by two independent trace-analyst passes and by the tests]
- Root `history` `01CD6j…`: `tool_end` 39 → eviction `file_write` 40 (`/large_tool_results/toolu_01CD6jj8EqAo3Qv59xzjUKmP`, sha `00ab1468…`, 133,306 B). Root's model saw only the 967-char substitute (sha `1f32f254…`) from llm_start 42 on.
- **Availability:** no event records the child's state copy at delegation (94). `ls` 313 lists directories only.
- **Child `grep` 380:** its result (`tool_end` 381, sha `33f27177…`) lists root's file. It is **first delivered at llm_start 386**, in the verbatim tail the summarizer kept. The input of 383 does not contain it, and the summary at 385 does not mention it. *(The 2026-10-20 audit report said "381" for exposure; 381 is the tool result, not a model input.)*
- **Child `read_file` of root's file:**
  - `file_read` 389, 395 and 401: offset/limit 0/30, 30/25 and 4965/30; `created_at` equal to root's `file_read` 45; windows recompute from `tool_end` 39;
  - **first delivered at llm_start 392, 398 and 404.**
- **No child claim.** The child's outputs 387–411 are empty thinking blocks plus tool calls. The guard refused 416, and the child returned nothing.
- **Confound:** the child's own eviction file (`file_write` 135, `/large_tool_results/toolu_01VwZ82BKDyeSFwC5oMi3FwH`) has the **same sha `00ab1468…`** as root's file. Only the path and `tool_call_id` join can separate them.
- **Under 0.3:**
  - storable: exposure (`delivers`);
  - not storable: availability (DEFERRED) and F → R_i lineage (§5.3 known limit).

### Run 621 hash correction [OBS 2026-10-20]
- The recorded `tool_end` 25 is the list form, **145,917 chars, sha `5d37d836…`**.
- The figures "130,849 chars, sha `384780…`" quoted in the 2026-10-14 audit and in "Verified findings" belong to its joined text (`38478099…`). That text is what `file_write` 26 stored.
- The other earlier 621 facts were re-confirmed: substitute 27 (`ccfd85be…`, 967 chars, delivered at 28), window `8fe92fd5…`, and answer `293d820e…`.
- Small correction: the `grep` tool events span seq 108–118; seq 107 is the `llm_end` that issued them.

### Schema ambiguities found (no 0.3 change; details in the fixture README)
1. §3 and §11 r1 vs §4.6/§4.7: `raw_ref` on propositions and states.
2. Whether a state's claims must assert the state's proposition.
3. `order` for multi-record events.
4. No `raw_ref` rule for content first seen in a rendered input.
5. The origin of a framework-initiated call inside an agent (383).
6. Whether a refused call (416) is an event.
7. The §12 OPEN text assumes file writes and reads are unobservable. In the fileobs capture they are observable; the outcome is unchanged.

### Independent reviews [2026-10-20]
- **schema-auditor:** 621 PASS WITH NOTES, sc3-B PASS, no must-fix items. The optional notes were applied: a located heading span, `values_as_stated`, the variant list for the tie check, and ambiguities 5–7.
- **trace-analyst:** every raw_ref matches. Three completeness points were applied: the 5476.77 carriers, the `native_trajectory_file` field nuance, and `file_write` 384.

### Next task
1. **DONE (2026-10-20):** the two canonical 0.3 fixtures and their offline tests (4 named files) were committed as `1a88708407985bb640505e303f73e5dc6342183e` on branch `research/agenttrace-specialists` in the `AssetOpsBench-agenttrace-spec` worktree. The 345-test suite passed before the commit. On 2026-10-20 the commit was pushed to the user's fork `DevikaVishnu/AssetOpsBench` (remote `fork`), branch `research/agenttrace-specialists`. It is **not merged and not in any PR**. `origin` (IBM/AssetOpsBench) is untouched.
2. **Still pending from earlier:** naming annotator 2, the result document, cleanup of C2, `tsfm_plans` and `/tmp/tsfm_work`, and the instrumented-schema version bump.
3. **Deferred until approved:** implementing the routed-coordinator flag and its fake-model tests.

## Handoff (2026-10-20, superseded by the section above): scenario_3 condition-B run executed once, BUDGET-STOPPED, annotator-1 analysis done

**Status.** The single approved paid run is done. It must not be repeated (§7). Its outcome is **BUDGET-STOPPED**, with **GENERIC MULTI-AGENT** delegation: only `general-purpose` was delegated to, and no specialist was. No grader, baseline or other paid call has been made. Nothing is committed.

### Final corrections before the run (approved 2026-10-14; pre-registration §14.8)
- **Launcher** `launch_sc3_B.py` (sha256 `cd880f31…`):
  - `PRICES_CHECKED_ON = "2026-10-14"`;
  - prices verified [OBS] on the official pricing page on 2026-10-14 and again just before the run: Sonnet 5 input 2.00, 5m cache write 2.50, 1h cache write 4.00, cache read 0.20, output 10.00 USD/MTok;
  - no long-context premium; `inference_geo` is not set.
- **Post-run checks** `preflight_sc3_B.py` (`83aa1008…`). `--post` now calls two functions:
  - `classify_outputs` returns COMPLETED / ERROR / BUDGET-STOPPED / EVIDENCE-INVALID;
    - A missing `$RID.json` is accepted only when a valid instrumented record has `status: error`.
    - It requires a consistent `budget_guard` object with the configured limits and prices, and a non-empty OTEL file.
  - `classify_db_changes` sorts DB changes into four classes:
    - expected new DBs `tsfm_*`/`*_result`;
    - permitted writes to `model_catalog`/`feature_catalog`/`failure_mode`;
    - unexpected writes;
    - any change to the shared DB, which is a safety failure.
- **Tests** `test_preflight_sc3_B.py` (`b1c4c137…`): 42 passed, with no LLM and no Docker. The worktree suite is still **314 passed**.
- **Pre-registration** is now sha256 `c7ed2fe2…`. §14.8 was appended; §1–§14.7 are unchanged apart from the status line.

### The run [OBS 2026-10-14, 18:01:50–18:11:49 UTC, exit 1]
- **Checks:**
  - Pre-run dry run PASS 24/24 (`pre.20261014T180110Z`). The launcher's own pre check is `pre.20261014T180140Z`.
  - Post-run check PASS 28/28 (`post.20261014T181215Z`), outcome **BUDGET-STOPPED**.
- **Budget guard:**
  - It refused llm_start seq 416, inside the child, before any provider request: 71 calls committed at $8.598 estimated, plus a $1.625 reservation, would exceed $10.
  - 0 calls over their reservation, 0 errored, peak in flight 1.
- **Calls and tokens:**
  - Root `deep-agent` made 14 calls; `general-purpose` made 57, plus the 1 refused.
  - Input tokens: 3,992,936. Of these, 3,610,564 were cache reads and 363,034 were 5-minute cache writes.
  - Output tokens: 43,102.
- **Cost:** about $2.10 at list prices with the cache discount [INF]. The Console figure is authoritative and has not been checked yet (user).
- **Database and host side effects:**
  - The shared CouchDB is unchanged.
  - The isolated DB has one expected new DB, `tsfm_plans` (5 docs); there are no permitted or unexpected writes; WO 1000045 is unchanged.
  - Host `/tmp/tsfm_work` gained 5 `plan_run_*.json` files.
  - `traces.jsonl` is still 101,154 B and the schema is still `2273d210…`.
- **Outputs (read-only evidence):**
  - `AP/data/assetopsbench/runs/aob-sc3-sonnet5-deep-spec-B-20261014.instrumented.json`: 10,384,890 B, sha256 `4d5759091df0e9bc800f209ff4cffca916a33b06b1441ee086cbf1585c339386`.
  - `AP/data/assetopsbench/runs/otel-aob-sc3-sonnet5-deep-spec-B-20261014.jsonl`: 90,932 B, sha256 `f78389150f55023eaf95d1eef1110cac070c3b0acbc5a76d0217843dbaf52a5f`.
  - There is **no** native `$RID.json`. This is expected: the runner writes it only on success.
  - **The console stderr log is lost.** It was kept in a session scratchpad that has since been cleared. The instrumented record and the OTEL file hold the evidence.

### Annotator-1 analysis (trace-analyst + schema-auditor, 2026-10-14; verified joins re-checked by hand)
- **Delegation [OBS]:**
  - Root llm_end 93 issues `task` `toolu_01KyhJPc3G7q4qtTuKQFRFMu` with:
    - description "Fetch Chiller 6 condenser water flow history and run anomaly detection" (70 chars, sha `ec4ce14d…`);
    - plus `instructions:"placeholder"`, which deepagents 0.5.3 `task` does not accept.
  - `delegation_start` is seq 94.
  - The child's first llm_start, seq 96, holds:
    - its own 2,352-char system prompt, without the parent's domain prompt;
    - a human message byte-identical to the description.
  - The description omits facts the parent already held: WO 1000045 (seq 9), registry asset (seq 15), range and 2,876 records (seq 22), history pages (27/39/51). It also omits the TSFM file requirement and the JSON output spec.
  - Formal non-delivery under 0.3 is UNK until coverage is established (§10.1).
- **Delivery [OBS]:** all 83 committed tool results reached the next same-agent llm_start byte-identical.
- **Earliest observable failure [OBS]:**
  - seq 158: TSFM `profile_series` ENOENT on the virtual eviction path `/large_tool_results/toolu_01BLT6…`;
  - delivered only to the child, at seq 160;
  - the parent never saw any error (its last llm_start is 92).
- **File-system split [OBS]:**
  - Virtual `write_file` files (168, 287) are visible to `read_file`/`ls` but give ENOENT from TSFM tools.
  - The host `plan_run` files are readable by `json_reader` (282) but invisible to `ls` (323).
  - [INF] This is configuration-induced (StateBackend vs host `TSFM_WORKDIR`), as predicted in §5.
  - `run_plan` failed 7 times; `run_recipe` was never called; R4a and R5 were never achieved.
  - R4b was not violated in tool arguments (max 539 B). Real series values entered the child's input through `read_file` (372/378).
- **Summarization [OBS]:**
  - Framework llm_start 383 had `offered_tools` null. Its summary (llm_end 385, 8,874 chars) replaced the child's history from seq 386 on.
  - The description is absent from child inputs from 386 on.
  - `/conversation_history/…md` (file_write 384, agent_id null) was never read back.
- **Child claims:**
  - Mostly in the summary at 385.
  - The arithmetic "1000+1000+896 = 2876" is wrong (the sum is 2,896; 2,876 is the count of records with a value).
  - The claim that `read_file` failed is contradicted by seq 220.
  - The `data://`+`run_recipe` plan is unsupported.
- **Criteria:**
  - S1 not met (generic only).
  - S2 **MET**.
  - S3 **NOT OBSERVABLE**: the handoff never happened, stopped at seqs 417–419.
  - S4 **NOT MET under the strict wording**, only because the summarization call 383 has null `offered_tools`. The other clauses hold: `task` is root-only, `readonly_servers` is `["wo"]`, no WO write tool, child 86 tools = root minus `task`.
  - §14.4 overrides the §6 INCONCLUSIVE clause for S3.
- **0.3 gaps (schema unchanged):**
  1. §4.3 does not say whether a model call with a rendered input but no output and no provider request (seq 416) is an event, so `delivers` for it cannot be decided.
  2. 0.3 does not fix the origin of a framework-initiated model call inside an agent's execution (summarization 383). The choice decides the lineage through the summary and the speaker of the claims at 385.
  - Not gaps:
    - tool → file → tool lineage and availability stay DEFERRED; this run is a stronger instance, because that chain leads to the first failure;
    - first-class delegation stays OPEN: the downward handoff is representable, the return path is unexercised;
    - `run.outputs` is UNKNOWN.
- **Telemetry gaps:**
  - `tool_end.status` does not flag in-band MCP errors.
  - write_todos tool_end 364 lacks `tool_call_id`.
  - `delegation_start` does not record all `task` args.
  - Thinking blocks are empty (signatures only).

### Next task
1. **Recommended implementation:** a deterministic, offline adapter for the 0.3 structural layer only:
   - it emits entities, events, evidence and `delivers` from the instrumented record via `tool_call_id`/sha joins, and flags seq 383 and 416 as unresolved;
   - tests on the verified joins: 96 (description), 160 (error), 386 (summary);
   - no claims, states or model calls: semantic extraction stays deferred.
   - This needs user approval before any code is written.
2. **User:** name the blind annotator 2 before any further labeling; check the actual cost in the Console.
3. **User decisions:** whether the two gaps go into a result document; whether to clean up C2 and `/tmp/tsfm_work` (5 files) and the `tsfm_plans` DB; the result document `result-aob-sc3-sonnet5-deep-spec-B-20261014.md` (not written yet).
4. **Do not rerun scenario_3 condition B.** Condition A is not eligible (§7: requires MULTI-AGENT (specialist)).

## Handoff (2026-10-14, superseded by the section above): preparation done, execution NOT approved

**Status.** Pending decisions 1–3 (below) were resolved by the user on 2026-10-14 and implemented as **preparation only**. The authoritative plan is pre-registration **§14** (`docs/experiments/prereg-aob-sc3-sonnet5-deep-spec-B-20261014.md`, sha256 `052e4c07…`).
- **No model call, scenario run, grader or baseline has been executed.**
- The paid run requires a new, explicit user approval.
- No commits or pushes; everything below is uncommitted.

**Approved decisions** (2026-10-14):
- separate disposable CouchDB (C2) instead of M5, with **all original MCP tools kept**;
- budget guard (G1): 200 calls and $10 estimated, off by default;
- launcher at `AP/docs/experiments/launch_sc3_B.py`;
- second annotator TBD, to be named before evaluation.

### C2: isolated CouchDB [OBS 2026-10-14]
- **Container:**
  - name `agenttrace-sc3-couchdb`, id `aded8f744af2`, label `agenttrace.purpose=sc3-isolated`;
  - image `sha256:8cf5f844…`, the same as the shared container (CouchDB 3.5.2);
  - published only on `127.0.0.1:5985`;
  - single volume `agenttrace-sc3-couchdb-data`, no bind mounts;
  - server uuid `a2897b31…`; the shared server's is `1ff30653…`.
- **Credentials:**
  - user `agenttrace` with a random password that exists **only in the container config** (`docker inspect`); it is never written to a file or printed;
  - the shared server rejects them (401);
  - the shared `.env` CouchDB credentials are **not** passed to the run.
- **Durability:**
  - restart policy `no`: after a Docker restart, run `docker start agenttrace-sc3-couchdb`; the volume and credentials survive;
  - **do not `docker rm` it before the run.** Removing it loses the credentials, and C2 would have to be re-created, reloaded and re-verified.
- **Load:**
  - `sc3_isolation.py load` ran `init_data.py` with the scenario_3 manifest. Its sha256 `cb28f1be…` equals the default manifest that loaded the shared DB.
  - It ran in a child process whose `COUCHDB_URL` was bound to C2, asserted in-process before the first request. `--reset` was never used.
- **Fidelity** versus the shared DB:
  - all 9 DBs have equal doc_count, no deletions and `update_seq` = `doc_count`;
  - 8 DBs have identical content and revs;
  - `catalog` has identical bodies but random server-generated `_id`s, because `collections.json` gives it no `primary_key`. This is declared as `GENERATED_ID_DBS` and in §14.2;
  - WO 1000045 is WAPPR `1-850525…` in both;
  - the source hashes match §2.
- **Shared container untouched:**
  - a before/after snapshot shows the same DB set and identical doc_count, update_seq, content and rev digests;
  - same `StartedAt` and 0 restarts;
  - only GET and `_find` requests were made, plus one deliberately rejected auth probe.
- **Not isolated:** `/tmp/tsfm_work`, a host path that TSFM writes to. It is absent now and is listed by the pre- and post-run checks.

### G1: budget guard (worktree `src/agent/deep_agent/_budget_guard.py`, sha256 `6d48006d…`)
- **Configuration:**
  - flag `AGENTTRACE_BUDGET_GUARD`, plus `AGENTTRACE_MAX_MODEL_CALLS`, `AGENTTRACE_MAX_COST_USD` and four `AGENTTRACE_PRICE_*_USD_PER_MTOK` variables;
  - there are no defaults: a missing value raises `ValueError` before any connection or model call.
- **Attachment:**
  - one guard is attached to the runner's chat-model instance (`runner.py`, flag-on only);
  - [OBS] deepagents `resolve_model` returns that same instance for the coordinator, the specialists, `general-purpose` and summarization.
- **Reservation:**
  - made before each call, under a lock;
  - it is the UTF-8 bytes of the messages and tool schemas + 2,048 + 16 per message, at the highest input-side price, plus `max_tokens` × the output price.
- **Refusal:**
  - `BudgetExceeded` is raised before the provider request on call 201, when the cost limit would be exceeded, when `max_tokens` is unknown, or when the estimate itself fails;
  - the stop is sticky.
- **Settlement:**
  - from `usage_metadata`, with all input priced as uncached and cache writes at their write price;
  - an errored call, or one without usage, keeps its full reservation.
- **Record:**
  - the instrumented record gets a top-level `budget_guard` (`outcome` = `BUDGET-STOPPED` or null, `stop_reason`, counts, estimates, `blocked[].lc_run_id`, `calls_over_reservation`);
  - a refused call keeps its `llm_start` but has no `llm_end`;
  - [OBS in tests] an interrupted `task` delegation is recorded as `status: error`.
- **[OBS, offline] Real `ChatAnthropic("claude-sonnet-5")` settings:**
  - `max_tokens` = 4,096 (the langchain-anthropic default), `max_retries` = 2;
  - `max_tokens` reaches the guard via `invocation_params`;
  - a refused call sends no request.
- **Limits of the guard. It is NOT a hard dollar cap:**
  - the byte-per-token input bound is [INF];
  - retries are invisible to callbacks;
  - prices are configured, not fetched;
  - a provider-side spend limit is [HYP] and for the user to verify.
- **[INF] BUDGET-STOPPED is realistic for a long run:** uncached pricing ignores cache discounts.

### Launcher and checks (`AP/docs/experiments/`, untracked)
- `sc3_isolation.py` (`8beb2f58…`): `create | load | verify`, `assert_isolated`, inventory and digests. `create` refuses if the container or volume already exists; `load` refuses if C2 already has user DBs.
- `preflight_sc3_B.py` (`89c69471…`):
  - pre mode runs 24 checks: worktree, schema hash, verbatim question, environment names, connections built exactly as the runner builds them, guard limits, isolation and fidelity, `traces.jsonl` size, no outputs yet, and a real MCP server probe (partitions 79/18/47/9/15, no WO write tools, WO and IoT reads from C2);
  - `--post` diffs C2 against the latest passing pre record. It allows only new `tsfm_runs`, `tsfm_plans` and `*_result` DBs, and requires the outputs and a non-empty OTEL file;
  - records go to `data/assetopsbench/runs/preflight/<run id>.<mode>.<UTC>.json`, holding names and hashes only.
  - Four passing pre records exist (`…T172906Z`, `…T172933Z`, `…T172938Z`, `…T172944Z`); the last three came from launcher tests. A scan found 0 secret values in them.
  - [OBS] The post mode, exercised on a scratch copy, failed only `outputs_exist` and `otel_nonempty`, as expected before a run.
- `launch_sc3_B.py` (`516a7df9…`):
  - with no arguments it is a dry run: preflight, then print the environment *names*;
  - `--execute --confirm-run-id aob-sc3-sonnet5-deep-spec-B-20261014` refuses unless `PRICES_CHECKED_ON` is the run date (currently `None`), every check passes and no output file exists. It then `execve`s `deep-agent`;
  - the run environment holds the process basics, the non-CouchDB `SERVER_ENV` names and `ANTHROPIC_API_KEY` from the original `.env`, C2's URL and credentials, the flags, the guard settings and the per-run paths;
  - both refusals were tested with `execve` patched out.

### Tests [OBS 2026-10-14]
- Worktree: `env -u OTEL_TRACES_FILE .venv/bin/python -m pytest src/agent src/servers/wo src/observability -q -p no:cacheprovider -W ignore::DeprecationWarning` → **314 passed** (277 + 37 in `tests/test_budget_guard.py`).
- What the guard tests cover:
  - the 200/201 call boundary and the sticky stop;
  - in-flight reservations, and 32 threads racing for 5 reservations;
  - parallel `iot` + `wo` specialists through one guard (peak 2 in flight);
  - the call limit stopping a specialist before the provider, with the record written;
  - the cost limit refusing the second parallel specialist;
  - unbounded output and missing configuration failing closed;
  - flag off: nothing attached, no `budget_guard` field;
  - real `ChatAnthropic` without network.
- Synthetic OTEL: `init_tracing` + `agent_run_span` wrote 1 span (1,106 B) to a scratch file. `traces.jsonl` is still **101,154 B**, and the schema sha256 is still `2273d210…25c01c06`.

### Worktree state (2026-10-14; base `6ec35fb`, no commits)
`M runner.py` (also wires G1), `_subagent_capture.py` (untracked; gains `budget_guard`), and new untracked `_budget_guard.py` and `tests/test_budget_guard.py`, in addition to the files listed in the superseded handoff.

### Remaining before the paid run (the user decides)
1. Explicit approval of §14 and of exactly one run.
2. On run day: re-check the Sonnet 5 prices (currently input 2.00, 5-minute cache write 2.50, 1-hour cache write 4.00 [INF], output 10.00 USD/MTok) and set `PRICES` and `PRICES_CHECKED_ON` in the launcher.
3. Optional: a provider-side workspace spend limit.
4. Name the second annotator, before evaluation (not needed before the run).

Then:
- `launch_sc3_B.py` (dry run; must PASS);
- `launch_sc3_B.py --execute --confirm-run-id aob-sc3-sonnet5-deep-spec-B-20261014`, exactly once;
- `preflight_sc3_B.py --post`;
- the trace-analyst pass, the blind second annotation and the result document.

Cleanup of C2 and `/tmp/tsfm_work` is a separate user decision, after the result document.

### Next task
Do nothing paid. Wait for the user's approval of §14 and the run. If Docker was restarted, run `docker start agenttrace-sc3-couchdb`, then the dry run.

## Handoff (2026-10-14, superseded by the section above): specialist worktree prepared, three decisions pending

**Objective.** Validate `agenttrace.semantic/0.3` against genuine industrial multi-agent execution. From raw capture alone, reconstruct:
- evidence-grounded observable agent states;
- information delivery between agents;
- divergence from task requirements;
- failure localization.

Never infer hidden beliefs or causal links without supporting evidence. Label everything [OBS], [INF] or [HYP].

**Status.** The implementation and the no-LLM validation are done. **No real scenario_3 run, model call or grader has been executed.** No paid execution is authorized.

### Implementation (uncommitted, in an isolated worktree)
- **Worktree and branch:**
  - worktree `AssetOpsBench-agenttrace-spec` (sibling of `AP`);
  - branch `research/agenttrace-specialists`, base `6ec35fb`;
  - no commits on the branch.
- **Carried over:** the Part A–C instrumentation (the `deep_agent/runner.py` diff, `_subagent_capture.py`, `_file_observer.py` and 3 test files) was copied unchanged from the original working tree.
- **Flag:** everything new is behind `AGENTTRACE_SPECIALISTS`, off by default. Tests show flag-off behaviour is unchanged: the same connections, one `get_tools()` call, and the same `create_deep_agent` arguments and outputs.
- **M1, specialists** (`src/agent/deep_agent/_specialists.py`):
  - The specialists are `iot`, `tsfm`, `fmsr` and `wo`. Each gets its own server's tools plus `utilities`. `vibration` stays with the coordinator only.
  - The model is inherited from the coordinator.
  - The coordinator keeps all 79 original tools and `AGENT_SYSTEM_PROMPT`, so delegation is not forced. `general-purpose` is kept.
  - Both `create_deep_agent` paths (capture on and capture off) receive `subagents=`.
  - Prompts are neutral. Each scope line is the server's FastMCP `instructions` verbatim, checked against the source by AST.
  - **Exception:** `wo` uses `READONLY_SCOPES["wo"]` (write verbs removed). The verbatim text is kept in `SERVER_SCOPES` and recorded by sha256 (`scope_source: readonly_edit`).
  - Real partitions [OBS]: coordinator 79 tools, iot 18, tsfm 47, fmsr 9, wo 15.
- **M4, read-only WO:**
  - The `wo` stdio connection gets `env={"AOB_READONLY": "1"}`.
  - [OBS] The real `uv run wo-mcp-server` lists 9 tools with it and 15 without it. An unregistered write tool returns "unknown tool".
- **M6, tool availability** (`_subagent_capture.py`, flag-on only):
  - Every `llm_start` gets `offered_tools`, the bound tool names from `invocation_params["tools"]`.
  - The record gets a top-level `tool_availability`: configured tools per agent, `readonly_servers`, `forwarded_env_names` (names only), and prompt and scope hashes.
- **Credentials** (`with_forwarded_env`, flag-on):
  - Each connection gets only an allowlist of the variables that server reads (`SERVER_ENV`): the CouchDB URL, user and password, plus that server's DB names.
  - Never forwarded: model-provider keys, `OTEL_*`, and `AOB_READONLY` (M4 sets it).
  - **There is no `.env` symlink and none should be created.**
  - [OBS] A read-only end-to-end check with no model key in the process: WO `get_workorder(1000045, MAIN)` returned WAPPR / CHILLER6, and `iot.sites` returned MAIN and NORTH.
- **Environment:**
  - The approved `uv sync --inexact --locked --offline --group otel` installed the 8 locked OTEL/protobuf packages in the worktree `.venv`.
  - The worktree and original venvs now have identical package sets, and the original venv was verified unchanged.
  - `uv run` in the worktree uses `worktree/.venv`, whose editable install points to the worktree `src`. A dry run reports no changes.
  - The worktree `.venv` was first created at 12:28 by an outside process, most likely VS Code; the tests did not create it.
- **Tests:** latest command, from the worktree root:
  `env -u OTEL_TRACES_FILE .venv/bin/python -m pytest src/agent src/servers/wo src/observability -q -p no:cacheprovider -W ignore::DeprecationWarning` → **277 passed**.
  - Of these, `src/agent/deep_agent/tests/test_specialists.py` has 24 tests.
  - The M4 server test starts the real WO server, using `python -m servers.wo.main` rather than `uv run`.
- **OTEL:** a synthetic span through `init_tracing` + `agent_run_span` wrote 1 line to a scratch file, with no network.

Worktree `git status --short` (2026-10-14):
```
 M src/agent/deep_agent/runner.py
?? src/agent/deep_agent/_file_observer.py
?? src/agent/deep_agent/_specialists.py
?? src/agent/deep_agent/_subagent_capture.py
?? src/agent/deep_agent/tests/test_file_observability.py
?? src/agent/deep_agent/tests/test_offloading_probe.py
?? src/agent/deep_agent/tests/test_specialists.py
?? src/agent/deep_agent/tests/test_subagent_capture.py
```

### Experimental target (pre-registered; draft, not approved)
- **Pre-registration:** `AP/docs/experiments/prereg-aob-sc3-sonnet5-deep-spec-B-20261014.md`.
  - §1–§12 hold the original draft. **§13 holds the readiness amendments**: FACT items, plus PROPOSED items that are not adopted.
  - Run ID `aob-sc3-sonnet5-deep-spec-B-20261014`.
- **Task:** upstream `scenario_3`, used verbatim: WO 1000045 (WAPPR, MAIN, CHILLER6) → Chiller 6 → Condenser Water Flow.
- **Data** [OBS]:
  - The IoT DB matches `chiller_6.json`: 2,896 records, 2,876 with a value, from `2020-06-01T00:00:00` to `2020-06-30T23:45:00`.
  - sha256 `chiller_6.json` `8073af23…46e2`, `groundtruth.txt` `ff1d1248…67f8`.
- **Ground truth:** preserved as is.
  - Report E-GT (benchmark literal, `end` `2020-06-26T11:14:36`, which has no value and so violates R7) and E-R7 (`end` `2020-06-30T23:45:00`) separately. Never merge them.
- **Expected failure:** under condition B (the default virtual `StateBackend`), TSFM is expected to fail on path access (R4a/R5), labeled configuration-induced.
- **Delegation:** not guaranteed; there were 0 delegations in 7 earlier natural runs.
  - With no specialist `delegation_start`, the run is recorded as SINGLE-AGENT and not retried, and condition A is not run.
- **DB baseline** [OBS], all pristine (update_seq = doc_count, no deletions):
  - asset 10, catalog 7, failure_code 10, failure_mode 3, feature_catalog 5;
  - iot 10,218, model_catalog 5, vibration 4,097, workorder 7.
  - There is no `tsfm_*` or `*_result` DB, and `/tmp/tsfm_work` is absent.

### Pending decisions (RESOLVED 2026-10-14; see the newest handoff and §14. Kept for history)
1. **Write safety.**
   - **M5:** remove the 9 TSFM catalog-mutation tools (`register_model`, `register_finetuned`, `update_model`, `deprecate_model`, `new_model_version`, `register_feature`, `update_feature`, `deprecate_feature`, `new_feature_version`) and FMSR `add_failure_modes` from every agent.
   - **Alternative:** an isolated CouchDB container on another port, loaded from the same manifest.
   - **Either way:** `run_recipe`/`run_plan`/`evaluate` create the new DBs `tsfm_runs`, `tsfm_plans` and `anomaly_result` and write to `/tmp/tsfm_work`. Those DB names are hardcoded. Use a full before/after DB inventory.
   - FMSR `generate_failure_modes` is already disabled (empty WatsonX key), so it makes no external LLM call.
2. **Model-call and spending guard.**
   - [INF] `recursion_limit=100` is **not** a cost cap: each child graph gets its own 100 steps.
   - Proposed: a flag-gated `raise_error` callback that stops before call N+1 or at budget B. The suggestion is N=150 and B=$10, **not approved**.
   - [OBS] Feasibility was shown with a fake model in a scratch script: the call was blocked before the provider, inside the child too, and `write_instrumented` still ran. The guard is not implemented.
   - A provider-side workspace spend limit is [HYP]; the user should verify it in the Console.
3. **Approval of the amended pre-registration** (§13), including:
   - the **launcher's** location and behaviour. The draft in §13.6 builds a minimal env from the allowlisted names plus `ANTHROPIC_API_KEY` via `dotenv_values` and `execve`s `deep-agent`, without sourcing the whole `.env`;
   - a price re-check on run day;
   - naming the **second human annotator**.

### Caveats
- **`offered_tools` on a real `ChatAnthropic` call is [INF].** It was validated only with a fake model. A null value is INCONCLUSIVE for M6.
- **Server descriptions now reach a model.** They appear in the coordinator's `task` description; previously no model saw them. This is declared in the pre-registration (§3), and `tsfm`'s includes workflow text.
- **Instrumented schema not bumped.** It is still `assetopsbench.deepagent.instrumented/0.1` (Open decision 2).
- **Deprecated hook.** The backend-factory hook is deprecated in deepagents 0.5.3, with removal in v0.7.
- **No hard cost cap.** G1 bounds an estimate only (newest handoff). There is no `timeout` binary on macOS, and SIGINT would skip `write_instrumented`.
- **Cost estimate** [INF]: about $0.6–$3.3 cached, about $7.7 uncached at the high end.

### Preservation rules (unchanged)
- **Leave unchanged:** the original AssetOpsBench tree (its own WIP included), its `.env` and `.venv`, the benchmark data and all traces. `traces.jsonl` is **101,154 B**.
- **No commits or pushes.**
- **No paid model calls, graders or baselines** without explicit authorization.
- **No schema 0.3 change** without a concrete trace-backed counterexample. The schema hash `2273d210…` was verified unchanged.
- **Every change to an experimental condition is recorded** in the pre-registration before it takes effect.

### Next task (superseded)
Done: decisions 1–3 were resolved and prepared. See the newest handoff.

## Current direction (2026-10-14, latest): multi-agent failure diagnosis

**Objective.** Evidence-grounded failure diagnosis in multi-agent systems. When a multi-agent industrial system fails a task, AgentTrace should identify:
- where the failure first became observable;
- which agents received the relevant evidence;
- how their claims evolved;
- where the final behavior diverged from the task requirements.

**Canonical `agenttrace.semantic/0.3` is unchanged.** It stays frozen, with no redesign unless a trace-backed counterexample appears. The viz profile (rev 2) is **not** a prerequisite for this track. C1–C6 are not defined in any repo file and stay out of scope.

### Verified facts behind the decision (2026-10-14 read-only audits)
- [OBS] **Current AOB runners are single-agent.**
  - DeepAgents builds one agent with all MCP tools and no `subagents=` (`AOB/src/agent/deep_agent/runner.py:203-219`).
  - plan-execute runs planned steps as tool calls, not agents.
  - The README's "agent-as-tool delegation" claims (`AOB/README.md:101-102`) are not in the code.
  - The IoT/TSFM/FMSR/WO "agents" are FastMCP tool servers.
- [OBS] **What "99 + 42" means.** The figure is the 141-scenario release (`d931bd9^`: `scenarios/single_agent/*` = 99, `multi_agent/end2end_utterance.json` = 42). "multiagent" means multi-*domain* tasks, not multi-agent execution. The local file has 152 rows (141 + 11 WO).
- [OBS] **No graded run and no recorded multi-agent run exists locally.** Success of runs 607–621 is UNKNOWN.
- [OBS] **Natural failures found in run 621 (single agent).** Both `profile_series` calls failed with ENOENT on virtual paths (seq 54–55 `/large_tool_results/…`, seq 65–66 `/tmp/test.csv`). The errors reached `llm_start` 57/68/157, and the answer omits that detection failed. Run 620 states month min and max (0 and 11,206.9) as "consecutive samples".
- [OBS] **Natural delegation likelihood is weak.** It was 0 of 7 runs with only the general-purpose subagent offered.

### Decisions
- **Approach: DeepAgents specialist subagents (Option B). AgentHive restoration is rejected.**
  - AgentHive needs private `github.ibm.com/GenAIApps/*` packages (`4e42951:benchmark/extra_requirements.txt:1-7`).
  - Its committed entry script is broken.
  - It uses watsonx model indices.
  - Its old tool signatures and few-shots don't match the current MCP servers.
  - So a restoration could not be faithful.
- **Task: upstream `scenario_3`** (`AOB/src/couchdb/scenarios_data/scenario_3/`, commit `9bad1aa` on `origin/main`), used verbatim. It is the only multi-domain task (WO → registry → IoT → disk file → TSFM recipe) with a checkable answer whose data is present.
- **Research modifications** (each behind an off-by-default flag; the flag-off path must be byte-identical):
  - **M1 — specialist subagents** (`iot`, `tsfm`, `fmsr`, `wo`):
    - tools split per server via `client.get_tools(server_name=…)`;
    - `utilities` goes to every specialist, and `vibration` to the parent only;
    - neutral prompt template whose scope line is copied verbatim from each server's FastMCP description, with no scenario, error or file hints;
    - the model is inherited;
    - **the parent keeps all its original tools (no forced delegation)**;
    - the general-purpose subagent stays (it is always added, `SP/deepagents/graph.py:544-548`).
  - **M4 — explicit read-only WO environment.**
    - stdio MCP servers inherit only `HOME, LOGNAME, PATH, SHELL, TERM, USER` (`SP/mcp/client/stdio/__init__.py:28-58, 127`), and the runner passes no `env`. So `AOB_READONLY=1` in the shell **does not reach** the WO server.
    - Pass `env={"AOB_READONLY": "1", …}` on the WO connection (`wo/main.py:11, 406`).
    - A fresh worktree has no `.env` (it is untracked). How the servers get credentials is a user decision; `.env` itself stays unchanged.
  - **M6 — record the tools offered to each agent** (names bound per agent). Tool schemas are not in `input_batches`.
- **Ground-truth discrepancy in `scenario_3`** [OBS]:
  - `groundtruth.txt` `end` = `2020-06-26T11:14:36`. That is the last record in *file order* of the unsorted `shared/iot/chiller_6.json` (2 order breaks), and it **has no Condenser Water Flow value**, so it violates the task's own rule to count only valued records.
  - The chronological maximum among valued records is `2020-06-30T23:45:00`.
  - The other 5 checkable keys agree with the data (WO 1000045 WAPPR at `workorders.csv:2`; Chiller 6; 2876 valued observations; start `2020-06-01T00:00:00`). `anomalies_found` was not checked.
  - Plan: report E-GT (benchmark literal) and E-R7 (requirement-derived) separately. Never edit the ground truth or treat the two as equivalent.
- **Known virtual-FS / TSFM incompatibility** [OBS]:
  - TSFM reads host paths (`AOB/src/servers/tsfm/io/refs.py:23-24, 50-51`) and accepts no inline series (`tsfm/main.py:1494`).
  - DeepAgents' default `StateBackend` files are in-memory only.
  - So under the default backend, steps R4a/R5 are predicted to fail. The only way to make a file is `write_file(content=series)`, which violates the scenario's R4b.
  - The upstream stirrup runner solves this with `workspace_host_path`, added in the same commit as scenario_3 (`AOB/src/agent/stirrup_agent/handoff_tools.py:17-46`).
- **Conditions:**
  - **B** (default virtual backend; predicted TSFM failure, labeled configuration-induced) runs first.
  - **A** (functional filesystem) needs further modifications:
    - M2: a `CompositeBackend` route to disk;
    - M2b: `LocalShellBackend` `execute`, which is unsandboxed host execution;
    - M3: a port of `workspace_host_path`.
  - A also needs no-LLM compatibility tests. `CompositeBackend` strips the route prefix (`composite.py:100-115`), so virtual paths are not host paths.
  - A is not a single-variable contrast with B.
- **Stopping rule:**
  - Run B once. With no specialist `delegation_start`, record a single-agent run, never present it as multi-agent evidence, do not retry, do not run A, and return to the user.
  - If only general-purpose is used, report it as generic multi-agent; specialist claims are not made.
  - A runs only after B delegates to a specialist, the user approves M2/M2b/M3, and the compatibility tests pass.
- **Diagnosis output** (plain 0.3 objects plus a report; no profile revision 3):
  - entities: root and `sub-N` as agents;
  - per-call events;
  - the delegation description as parent-produced agent evidence;
  - the child's final message as the child's item, which is `delivers`-ed to the parent if the ToolMessage is byte-identical;
  - the ground truth as external `benchmark` testimony (§4.4 L148, §7.1);
  - the end readings as two propositions;
  - the "first observable failure" as a consumer-side rule labeled **not 0.3**.

  The schema-auditor predicts no counterexample. Declared limits that will appear: the file hop, the `run.outputs` harness marker (OPEN), parallel order, and the PROVISIONAL rules.
- **Cost:** UNKNOWN for a multi-agent run. Anchors: run 620 about $0.32 cached; run 621 1,123,772 input + 12,123 output tokens, about $2.37 uncached at the prices in the run-620 result doc. Re-check prices at pre-registration.

## Earlier validation work (2026-10-14): belief-model validation

Validation of the AgentTrace belief-model implementation comes first. **The primary target is real AssetOpsBench traces.** MAST (Gomoku #7) is secondary, cross-framework validation. Visualization and integration are deferred.

### Run 621 industrial fixture feasibility audit (2026-10-14, read-only)

Method: one trace-analyst pass over the raw run, one schema-auditor pass over 0.3 and the profile, and a direct spot-check of the key facts.

Run files:
- `.json`: sha256 `8645198b2fe1…`
- `.instrumented.json`: sha256 `aa8531f2b977…`

**Verdict: NO-GO under profile rev 2. CONDITIONAL GO after the profile decisions listed below.**

Rejection by profile rev 2 (all [OBS]):
- **D1 excludes this trace.** Nine model turns issued parallel tool calls. They are the `llm_end` events at seq 7, 15, 69, 77, 85, 93 (4 calls), 107, 137 and 150, and their tool events interleave.
- `seq` 0–159 is still a strict, gap-free total order (`mono_ns` strictly increasing). It is an observation order, not a causal order.
- The profile currently forbids such traces, even though the minimal slice itself contains parallel turns (the greps at seq 107–113, and seq 150).

What the run supports:
- [OBS] **Events.** 24 model calls (`llm_start`/`llm_end` pairs), 34 tool calls (start, end and committed), 4 `file_write` and 4 `file_read` events. There is 1 agent ("root", model `anthropic:claude-sonnet-5`) and `delegations=[]`.
- [OBS] **Delivery.** Each `llm_start` holds the full LangChain message list. Each input extends the previous one and the system message is constant. All 34 tool-message contents hash-equal `tool_result_committed.sha256`, so `delivers` can be shown by `tool_call_id` plus sha.
- [OBS] **Gaps in delivery evidence.**
  - Tool schemas are not captured.
  - The input is the LangChain view, not the wire format.
  - Thinking blocks are redacted to signatures.
  - No framework event records the eviction middleware or the producer of the substitute.
  - `file_write` has no `created_at`; `created_at` is on `file_read` only, so it is temporal corroboration and not a field join.
- [OBS] **016q lineage.**
  - Chain: `history` `tool_end` 25 (text 130,849 chars, sha `384780…`) → `file_write` 26 (same sha) → substitute 27 (967 chars) → delivered at 28 → `grep` 108–118 → `read_file` 121–124 (`window_sha256` `8fe92f…` matches the recomputed file lines [4695:4735]) → first model input at 125 → answer `llm_end` 158 (2,715 chars, sha `293d82…`).
  - The full original is never in any model input.
- [INF] **Storable under 0.3:**
  - `delivers` for every tool result and for the substitute;
  - `propagates_to` read result `01S66j` → answer, for the June-10 sequence (offset ~1320), whose only delivered source is `01S66j`.
  - States held by the root agent can be grounded by the answer's claims (`llm_end` 158).
  - Claims on tool outputs are stored but never ground a state.
- [INF] **Not storable (declared limits, §5.3, §12):** original → substitute, original → file, file → `read_file` result.
- [INF] **Tie rule blocks some answer links:**
  - The 06-01 table rows have two delivered sources (`01DC8K` at 134, `01U6gc` at 129).
  - 5476.77 occurs in `sensor_stats`, `grep` and `read`.
  - Under §5.3(4b) the tie rule stores no link for either.

Conditions for GO (each is the user's decision):
- **C-a.** Revise D1 to admit parallel tool calls in observation (`seq`) order, or confirm that real DeepAgents runs are excluded.
- **C-b.** Resolve MAJOR #1 (`propagates_to` `raw_ref` shape), #4 (state `raw_ref` equality) and #5 (claim/state proposition tie). #2 applies partially. #3 recurs only if a non-observed "eviction event" candidate is used.
- **C-c.** Decide new gaps G1 and G4:
  - **G1:** no evidence `raw_ref` rule for an item first seen in a rendered input with no producing event, such as the substitute.
  - **G4:** no `profile_local` slot for the provenance of the whole-item non-delivery bound.
- **C-d.** Adapter decisions to record:
  - **G3:** DeepAgents `read_file` and `grep` are tool or framework entities.
  - **G5:** `run.outputs` is likely `"UNKNOWN"`, because the runner's `answer` is a harness marker.

Smallest meaningful fixture [INF]:
- entities: root agent, framework, and the tools used in the slice;
- events: user input; the `history` call (24–27); the model call at 28; the `grep` and `read_file` calls (107–124); the model call at 125; the final call (157–158);
- evidence: user text, the 016q original, the substitute, the read result `01S66j`, the answer;
- links: `delivers` (substitute → 28, `01S66j` → 125/157) and `propagates_to(01S66j → answer)`;
- claims and states: the June-10 claim, plus one hedged claim (UNCERTAIN) by the root agent;
- `profile_local`: the unstorable hops and the whole-item bound.

Untestable with this run (single agent): multi-holder disagreement, cross-agent propagation and testimony (§7.3), delegation lineage (T4–T5), state non-persistence across agents, verification by another agent, and testifier deduplication across agents (§7.2 r8).

### Gomoku #7 gate (secondary)

**Gate result: BLOCKED. No fixture or validator has been written.**
- `docs/research/agenttrace-viz-profile-0.1.md` is still marked **DRAFT, revision 2**, not "BASELINE FOR VISUALIZATION V1".
- An independent schema-auditor review on 2026-10-14 found five MAJOR issues that are still unresolved. Each was spot-checked against schema §14:
  1. **The `propagates_to` `raw_ref` shape** `{in_target, in_source}` is not a §3 locator or locator array, so the m3 provenance rule cannot be checked. This affects all 5 Gomoku `propagates_to` links.
  2. **`$unresolved` is allowed on almost any required field**, but the link and claim checks don't define what happens then. The Task → v1 ordering check depends on the unresolved Task `produced_by`.
  3. **The Gomoku Task candidate `evt:<framework event>`** (profile §5) has no matching event in schema §14.2. The candidate would need an invented object, which the profile's own §5 forbids.
  4. **"State `raw_ref` = union of claim spans"** has no defined equality.
  5. **State validity (M1) never ties the state's proposition to its claims' propositions.** The R3 state is FALSE on P, but R3's text asserts ¬P (§14.3, §4.5), and D5 leaves this open.
- Minor issues:
  - M1 requires the holder to be an agent, which is stricter than 0.3 and untagged.
  - The vocabulary is untagged.
  - Undelivered external spans are marked `$unresolved`, but they are missing, not undecided.
  - The §5 Gomoku example is incomplete: the config item's `produced_by`, the test report's source candidates, and "not examined" items are missing.
  - The run-row wording is unclear.
  - The schema hash is truncated in the profile. The full value was verified: `2273d210090d19c17f75e98bb06875e0c55ef10b9c26528ea2471cee25c01c06`.
- Source evidence is ready: `data/mast/MAD_full_dataset.json` [7], sha256 `d636ac63…d85406f`.

## Question

Can schema 0.3 represent file-mediated information flow, in particular the **delegated** lineage? That lineage runs: child tool result → framework-managed file → parent `read_file` result → parent final answer. The steps are T1–T7 (ckpt §6).

Under 0.3 the answer is currently no. `propagates_to` needs `delivers` from an agent-input event, so it cannot cross a tool → file → tool step (schema §5.3, §12 DEFERRED/OPEN).

**Status: OPEN.** Cross-agent file lineage (T4–T5) has not been observed in any natural run.

## Verified findings

**Synthetic delegated test** (Chiller 6 lockout, ckpt §4) [OBS]:
- All of T1–T7 are observable and join by `tool_call_id` and sha256. The lockout line first reaches the parent model only through the parent's `read_file`.
- Every model decision in it was scripted. It proves the instrumentation is correct and says nothing about natural behavior.

**Natural run 621** (`aob-621-sonnet5-deep-fileobs-20261013`, ckpt §5, §7):
- [OBS] There was no delegation, though the `task` tool was offered. The natural delegation rate at that point was 0 of 6 (Sonnet 5, runs 607–621). T4 and T5 did not occur.
- [OBS] The page-1 `history` result (130,849 chars) was evicted to `/large_tool_results/016q`. The model saw a 967-char substitute and its input grew by only +874 tokens, which bounds out delivery of the whole item.
- [OBS] The agent itself ran `grep` and then `read_file` (seq 121–123). The window hash and the file's `created_at` match the write. The June-10 values first appear in a model input at seq 125, and are restated in the final answer (anomaly point 3).
- [INF] Under 0.3, read result → answer can be stored. Original → file → read result cannot: the read result has no storable origin. This is a **declared** limit and not a counterexample. Every raw step is observed, so the gap is now only on the schema side.
- [INF] The retrieved sequence is one of four supporting observations for the recommendation. That it was decisive is unestablished, because there is no contrast evidence.

**Natural run 620** (`aob-620-sonnet5-deep-fileobs-20261013`). It was pre-registered and run once, with no retry. Result: `docs/experiments/result-aob-620-sonnet5-deep-fileobs-20261013.md`.
- [OBS] There was no delegation: 1 agent, 0 delegations, 0 `task` calls. The natural delegation rate is now **0 of 7** (Sonnet 5).
- [OBS] One agent offloaded a file and read it back:
  - a `history` result (86,015 chars) was evicted to `/large_tool_results/toolu_01MHvH…` (seq 37);
  - the root agent read it back with `read_file` (seq 43–45; the window hash and prefix match) and with `grep` (seq 49–50);
  - the window content first reached a model input at seq 47.
- [OBS/INF] Use of the read content in the final answer was **not demonstrated**. No window value is in the answer, and its one related claim also follows from `sensor_stats` (seq 39).
- Pre-registered outcome: S1 failed (FAILURE). S2–S4 were met by the root agent and S5 was not met (PARTIAL). It is not inconclusive. The WO DB count stayed at 7, `traces.jsonl` is unchanged, and the cost was about $0.32.

## Instrumentation and tests

- Capture is enabled with `AGENTTRACE_CAPTURE_SUBAGENTS=1`. It writes `{run_id}.instrumented.json` (raw schema `assetopsbench.deepagent.instrumented/0.1`).
- Parts A, B and C are implemented but uncommitted (ckpt §3).
- `.venv/bin/python -m pytest src/agent/deep_agent/tests/ -q -p no:cacheprovider` gave **38 passed** at the checkpoint, in the original tree.
- In the specialist worktree: **314 passed** on 2026-10-14 (277 + 37 budget-guard tests; command in the 2026-10-14 handoff).
- `AP/docs/experiments/test_preflight_sc3_B.py`: **42 passed** on 2026-10-14 (post-run classification; run with the worktree venv).
- **Risk:** the backend-factory hook is deprecated in deepagents 0.5.3 and will be removed in v0.7.

## Next action

**See "Handoff (2026-10-20, latest)" at the top** (O2/O3 committed, 440 tests passing; extraction audit; E1–E4 recommended; work preserved on GitHub). The paragraph below is kept from the previous handoff: The scenario_3 condition-B run was executed once (BUDGET-STOPPED, GENERIC MULTI-AGENT) and analysed by annotator 1. Next: the user approves (or not) the offline structural adapter and names annotator 2. No model run, grader or new code change happens without explicit approval.

**Earlier validation track (paused; superseded in priority by the above):** the user decides C-a to C-d (run 621 audit) and resolves the MAJOR viz-profile issues as revision 3, then marks it BASELINE FOR VISUALIZATION V1. The run 621 fixture, validator and negative tests come next; Gomoku #7 follows as cross-framework validation. C1–C6 stay out of scope.

**Delegation track (deferred):** Open decision 1 still requires a user decision. Choose between:
- **(a)** more unchanged natural benchmark runs, with production prompt, tools and model, accepting a low observed delegation rate (0 of 7);
- **(b)** a separately labeled **controlled, unscripted** delegation experiment. Any change to the condition must be declared, and model decisions stay unscripted. It is reported apart from the natural-benchmark results and never pooled with them.

Either path needs its own pre-registration and explicit approval before any run.

## Open decisions (the user decides)

1. **Experimental delegation condition.** RESOLVED 2026-10-14: a declared research configuration (M1 specialists). The parent keeps its original tools, delegation is not forced and model decisions are unscripted. It is labeled separately and never pooled with natural runs.
2. **Instrumentation schema version.** Should `assetopsbench.deepagent.instrumented/0.1` be bumped for the additive fields (`tool_availability`, `llm_start.offered_tools`, `budget_guard`)?
3. **Historical `traces.jsonl`.** Run 621 appended lines 51–69 (79,114 → 101,154 B) and there is no backup. Should it be truncated back to the first 79,114 B, or left as it is?
4. **Viz profile revision 3.** Resolve the five MAJOR issues (see Earlier validation work) and decide when to mark the profile BASELINE FOR VISUALIZATION V1.
5. **Run 621 fixture conditions C-a to C-d** (see Earlier validation work): above all, whether D1 admits parallel tool calls in `seq` order.
6. **Approvals pending for the specialist track:**
   - DONE: the M1/M4/M6 implementation, the worktree, the `otel` group install, and credentials via the per-server allowlist (no symlink);
   - DONE (preparation, 2026-10-14): write safety by the isolated CouchDB C2 (not M5), the G1 call/spend guard, the launcher and checks;
   - DONE (2026-10-14): approval of §14/§14.8, the price re-check and the single run (BUDGET-STOPPED; never to be repeated);
   - PENDING: naming the second annotator; the offline structural adapter (recommended next step); the result document; cleanup of C2, `tsfm_plans` and `/tmp/tsfm_work`;
   - later, M2/M2b/M3 and condition A;
   - any grader or baseline run.

## Paths

| What | Path |
|---|---|
| Canonical schema | `AP/docs/agenttrace.semantic.0.3.md` (relevant: §4.1, §5.1, §5.3, §10.1, §12, §13) |
| Full checkpoint | `AssetOpsBench/docs/agenttrace-research-checkpoint-20261013.md` |
| DeepAgents internals | `AssetOpsBench/docs/agenttrace-file-observability-handoff.md` §4 |
| Runner | `AssetOpsBench/src/agent/deep_agent/runner.py` |
| Specialist worktree (branch `research/agenttrace-specialists`) | `AssetOpsBench-agenttrace-spec` (sibling of `AP`); new code `src/agent/deep_agent/_specialists.py`, tests `src/agent/deep_agent/tests/test_specialists.py` |
| scenario_3 condition-B pre-registration | `AP/docs/experiments/prereg-aob-sc3-sonnet5-deep-spec-B-20261014.md` (§13 = amendments, §14 = approved preparation and final plan, §14.8 = final corrections) |
| sc3 launcher / checks / isolation / tests | `AP/docs/experiments/{launch_sc3_B.py, preflight_sc3_B.py, sc3_isolation.py, test_preflight_sc3_B.py}` |
| sc3 condition-B run (read-only evidence) | `AP/data/assetopsbench/runs/aob-sc3-sonnet5-deep-spec-B-20261014.instrumented.json`, `otel-aob-sc3-sonnet5-deep-spec-B-20261014.jsonl` (no native `.json`: error path) |
| Preflight records | `AP/data/assetopsbench/runs/preflight/` |
| Budget guard and tests (worktree) | `src/agent/deep_agent/_budget_guard.py`, `src/agent/deep_agent/tests/test_budget_guard.py` |
| Isolated CouchDB | container `agenttrace-sc3-couchdb`, `http://127.0.0.1:5985`, volume `agenttrace-sc3-couchdb-data` |
| Capture / file observer | `AssetOpsBench/src/agent/deep_agent/{_subagent_capture,_file_observer}.py` |
| Run 621 | `AP/data/assetopsbench/runs/aob-621-sonnet5-deep-fileobs-20261013{.json,.instrumented.json}` |
| Run 620 (fileobs) | `AP/data/assetopsbench/runs/aob-620-sonnet5-deep-fileobs-20261013{.json,.instrumented.json}`, `otel-aob-620-sonnet5-deep-fileobs-20261013.jsonl` |
| Run 620 pre-registration and result | `AP/docs/experiments/{prereg,result}-aob-620-sonnet5-deep-fileobs-20261013.md` |
| Earlier runs | `AP/data/assetopsbench/runs/aob-{607,612,615,617,620}-sonnet5-deep-20261005*` |
| OTEL spans | `AP/data/assetopsbench/runs/traces.jsonl` |
| Scenarios | `AP/data/assetopsbench/scenarios/all_utterance.jsonl` |
| scenario_3 (selected task) | `AssetOpsBench/src/couchdb/scenarios_data/scenario_3/{question.txt,groundtruth.txt,manifest.json}`; data `…/scenarios_data/shared/{iot/chiller_6.json,work_order/workorders.csv}` |
| DeepAgents subagent API (0.5.3) | `AssetOpsBench/.venv/lib/python3.12/site-packages/deepagents/{graph.py:469-548,middleware/subagents.py:25-93,384-411,569-575}` |
| TSFM path handling | `AssetOpsBench/src/servers/tsfm/io/refs.py:20-51` |
| Upstream host-path handoff | `AssetOpsBench/src/agent/stirrup_agent/handoff_tools.py` |
| Historical AgentHive (rejected) | `AssetOpsBench` rev `4e42951` (= `54d3301^`): `src/agent_hive/`, `src/meta_agent/` |

**RESOLVED: schema hash discrepancy.** The verified sha256 of `agenttrace.semantic.0.3.md` is `2273d210…25c01c06` (913 lines). The checkpoint's tail `…5c74cd` was a transcription slip.
