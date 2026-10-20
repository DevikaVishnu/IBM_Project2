# AgentTrace research log

A chronological history of the project, for personal reference. It runs from the Belief Explorer prototype to the automated-extraction milestone of 2026-10-20.

- **Current state:** [`STATE.md`](STATE.md) remains the current-state handoff. This log does not replace it.
- **Detail:** this log summarises and links. Full detail lives in the linked documents.

## Conventions

**Evidence labels**

| Label | Meaning |
|---|---|
| **[REC]** | Recorded in a primary source: a commit, a run file's metadata, an experiment record, STATE.md, or the checkpoint. The source is cited |
| **[RETRO]** | A retrospective interpretation written for this log, or taken from a later document looking back. It is not a contemporaneous record |
| [OBS] / [INF] / [HYP] | Quoted unchanged from the source document |

**Date confidence**

| Form | Meaning |
|---|---|
| `2026-10-13` | Exact: from a commit date, a run timestamp, or a dated section of a record |
| `≈2026-10-04` | Approximate: from a file modification time only |
| `undated (A … B)` | Only bounded by surrounding dated events |

**Abbreviations**
- **AP:** this repo, `DevikaVishnu/IBM_Project2`.
- **AOB:** AssetOpsBench.
- **Worktree:** the AssetOpsBench specialist worktree, branch `research/agenttrace-specialists`, on the fork `DevikaVishnu/AssetOpsBench`.
- **Fork docs:** the two documents committed in the worktree at `324de44`:
  - [checkpoint 2026-10-13](https://github.com/DevikaVishnu/AssetOpsBench/blob/research/agenttrace-specialists/docs/agenttrace-research-checkpoint-20261013.md);
  - [file-observability handoff](https://github.com/DevikaVishnu/AssetOpsBench/blob/research/agenttrace-specialists/docs/agenttrace-file-observability-handoff.md).
- **Raw runs:** the files in `AP/data/assetopsbench/runs/` are local-only and gitignored. They are cited by file name, not linked.

---

## Timeline at a glance

| Date | Milestone | Phase |
|---|---|---|
| 2026-04-15 | Repository created; first trace processor and timeline viewer (`v2_timeline`) | Belief Explorer |
| 2026-04-24 | Belief timeline v4: belief extractor and React viewer | Belief Explorer |
| 2026-05-29 / 2026-05-30 | v4.4 belief timeline; first README (CSE 523) | Belief Explorer |
| 2026-09-22 | v4.4 promoted to the repo root; `node_modules` untracked | Belief Explorer |
| undated (2026-09-22 … 2026-10-05) | Gomoku #7 falsification; reconstruction of 0.2 → design of 0.3 | Schema |
| ≈2026-10-04 / 2026-10-05 | AssetOpsBench bring-up runs; natural deep-agent runs 607–620 | AOB |
| 2026-10-05 | `agenttrace.semantic/0.3` committed; README reframed; MAST/AOB fetch scripts | Schema |
| undated (2026-10-05 … 2026-10-13) | Cross-framework validation: HyperAgent #25 and AOB run 620 | Schema |
| 2026-10-13 | 0.3 finalized (cross-trace clarifications); README overview updated | Schema |
| 2026-10-13 | File-observability instrumentation; synthetic delegated test; run 621; run 620-fileobs (pre-registered) | AOB |
| 2026-10-14 | Viz profile rev 2; run 621 fixture audit; Gomoku gate BLOCKED | Validation |
| 2026-10-14 | Direction change to multi-agent failure diagnosis; specialist worktree; scenario_3 pre-registration | AOB |
| 2026-10-14 | Isolated CouchDB, budget guard, launcher; scenario_3 condition B run once (BUDGET-STOPPED) | AOB |
| 2026-10-20 | Two hand-grounded 0.3 fixtures (621, sc3-B); committed and pushed to the fork | Fixtures |
| 2026-10-20 | O2/O3 comparison operations (`agenttrace.compare/0.1`) | Comparison |
| 2026-10-20 | Automated-extraction feasibility audit; E1–E4 recommendations | Extraction |
| 2026-10-20 | Work preserved on GitHub (fork commits, AP PR #1) | Housekeeping |

---

## Phase 1: Belief Explorer prototype (2026-04 to 2026-09)

### 2026-04-15: repository start and base timeline
- **Research question** [REC, May README `9d80f9e`]: which agent believed what at each point, when beliefs first diverged, and how divergence propagated into downstream failures.
- **Work** [REC, commits]:
  - `d3c39aa`: initial commit (LICENSE).
  - `32acc00`, "Base timeline and python processing file":
    - `tests/process_trace.py`;
    - raw and processed ChatDev and AG2 traces under `tests/`;
    - a Vite/React viewer `v2_timeline/agenttrace-viewer` and `v2_timeline/viewer.html`.
  - `ef4766a`: merge with the GitHub-initialized `main`. It survives only on local branch `claude/inspiring-lumiere-0e232e`.
- **Limitations:** no design notes from this date survive in the repo.

### 2026-04-24: belief timeline v4
- **Work** [REC, `df8cd9c`]:
  - `v4_beliefs/` with `belief_extractor.py`, `process_trace.py` and `BeliefEvolution.jsx`;
  - four ChatDev traces plus their "enriched" outputs;
  - `BELIEF_EVOLUTION_README.md`.

### 2026-05-29 / 2026-05-30: v4.4 and the first README
- **Work** [REC]:
  - `229081c` (2026-05-30) added `v4.4_beliefs` as a submodule pointer to `205d578`. That commit is not in this repo's history.
  - `9d80f9e` and `c0b0971` (2026-05-30) added and trimmed the README.
  - `dbfc036`, "Belief timeline with modifications", has author date 2026-05-29 and **commit date 2026-09-22**. It was re-applied during the September restructure.
- **What the README describes** [REC, `9d80f9e:README.md`]:
  - A three-stage pipeline: normalise the trace, classify belief states, render a grid.
  - Belief classification uses **seven heuristics**: explicit markers, blocking phrases, code blocks, review signals, questions, phase defaults and a fallback.
  - States are **sticky**: silent agents keep their last state.
  - There are **six divergence patterns** (P1–P6). Examples: blocked vs pushing, approval without substance, step repetition, and fuzzy repetition at Jaccard > 0.85.
  - Data: ChatDev (GPT-4o, ProgramDev) and AG2 (GSM-Plus) traces with MAST failure codes.
- **Limitations** [REC, the current README's "Why it was superseded"]:
  - keyword and phase heuristics;
  - states carried through silence;
  - ChatDev concepts built in;
  - above all, **no notion of what each agent actually received**.

### 2026-09-22: restructure
- **Work** [REC]:
  - `373a297` promoted the v4.4 viewer to the repo root (−22,564 lines of duplicated versions).
  - `71e8c16` stopped tracking `node_modules` and fixed a stale run instruction.
- The tag `pre-rewrite-backup` (`4450ca2`) shows that history was later rewritten. The rewrite happened after 2026-10-13, because the 2026-10-13 commits also have twins.
  - The rewritten line is `373a297` → `71e8c16` → `52626e3` and later.
  - Pre-rewrite twins also exist: `77fd21e`, `4450ca2`, `5fcbde9`, `b04d4ec`, `26078ab`, `c303c8d`.
  - Local branch `backup-before-remove-claude-coauthor` (`c303c8d`) indicates a co-author-trailer removal.
  - The rewrite date is not recorded. See the gaps section.

---

## Phase 2: Gomoku falsification and schema 0.3 (2026-09 to 2026-10-13)

### Undated (2026-09-22 … 2026-10-05): MAST/ChatDev Gomoku trace #7
- **Question:** could the belief model explain a real MAST failure?
- **Finding** [REC, README "Motivating example"; schema §14]:
  - The config sets `gui_design: True`, but the requirement is never rendered into the programmer's or the reviewers' inputs.
  - GUI verification is missed, and a console-only program is shipped.
  - Non-delivery was established by reconstructing every prompt against the logged token counts. The residual was a constant +2 tokens on all 12 calls.
- **Interpretation** [RETRO, stated in the README]:
  - This is an **information-delivery failure, not a belief divergence**.
  - A turn-by-turn belief view cannot show it.
  - It broadened the project from belief tracking to semantic information-flow observability.
- **Decision:** design a schema around delivery, verification, provenance and lineage.
- **Limitation** [REC, schema §2]: **0.2 was never written down.** 0.3 was derived by reconstructing 0.2's concepts and validating them against four gaps, so no 0.2 field list survives.

### 2026-10-05: schema 0.3 and README reframe
- **Work** [REC]:
  - `52626e3` added `docs/agenttrace.semantic.0.3.md` (884 lines).
  - `b448252` reframed the README around semantic observability and added `data/mast/` and `data/assetopsbench/` fetch scripts. The MAD dataset has 1,642 LLM-judged records plus 19 human-labelled ones ([`data/mast/README.md`](../../data/mast/README.md)).
- **What 0.3 holds:** see [schema §3–§5](../agenttrace.semantic.0.3.md) (objects, fields, relations) and [§15](../agenttrace.semantic.0.3.md#15-exact-02--03-delta) (the 0.2 → 0.3 delta). The full schema is not repeated here.
- **Status** [REC, schema header]: "EXPERIMENTAL. Not frozen."
  - From 2026-10-14 the research **treats 0.3 as frozen for this work** [REC, STATE "Current direction"; CLAUDE.md]: no redesign without a trace-backed counterexample.
  - The schema text itself still says "not frozen". Both statements are true in their own scope.

### Undated (2026-10-05 … 2026-10-13): cross-framework validation
- **Question:** can real traces from other frameworks break 0.3?
- **Work and findings** [REC, schema §13.1; README "Cross-framework validation"]:
  - **HyperAgent trace #25** (`pylint-dev__pylint-6506`): partially represented, with no stored-schema gap.
    - Rendered inputs are not logged, so every `delivers` and `propagates_to` is UNKNOWN.
    - The relayed reports H1 and H3 to the Planner are unattributed, and H3 is inconsistent with the Executor's last claim.
  - **AOB deep-agent run 620** (the 2026-10-05 run): partially represented.
    - The `history` result was paginated, and the model saw a substitute. Partial exposure was shown by input-token growth.
    - Fragments were recovered through `read_file`/`grep`.
    - Lineage from tool to file to tool cannot be stored (§5.3, §12).
- **Decisions** [REC, `8f84321`, 2026-10-13]: the **inference layer only** was clarified; no stored change.
  - `run.outputs` UNKNOWN vs empty, and harness markers OPEN (§4.1);
  - a self-contradicting testifier is UNCERTAIN; testimonial claims of unknown lineage have UNKNOWN independence (§9);
  - whole-item non-delivery by an upper bound, and exposed spans (§10.1);
  - new OPEN items (§12): lineage through tools and files, first-class delegation, availability.
- **Key practical finding** [REC]: `delivers` can only be established when each model call's rendered input is logged.
- **Superseded premises** (see "Corrected interpretations"):
  - "the file write and read aren't observable events";
  - "the recovered fragments didn't affect the final answer". This was true for run 620; run 621 later restated read content in its answer.

### 2026-10-13: 0.3 finalized and README updated
- [REC] `8f84321`: "finalize experimental agenttrace.semantic/0.3" (+37/−8, the clarifications above). `3f7f28b` updated the README overview.
- [REC] Verified schema sha256: `2273d210…25c01c06`, 913 lines.
  - This hash is referenced throughout later work.
  - An earlier checkpoint tail `…5c74cd` was a transcription slip [REC, STATE "RESOLVED: schema hash discrepancy"].

---

## Phase 3: AssetOpsBench instrumentation and natural runs (2026-10-04 to 2026-10-13)

### ≈2026-10-04 / 2026-10-05: environment bring-up and the first natural deep-agent runs
- **Bring-up runs** [REC, file metadata only; dates from file mtimes]:

  | Run | Runner | Scenario | Model |
  |---|---|---|---|
  | `aob-s1-sonnet5` | plan-execute | 1 | — |
  | `agenttrace-rich-001` | claude-agent | `rich-test-001` | — |
  | `agenttrace-deep-001` | deep-agent | 432 | Sonnet 5 |

  - Their purpose is not recorded beyond the README's "plan-execute, claude-agent and deep-agent runners exercised".
- **Natural runs, 2026-10-05, 06:54–07:01 UTC** [REC, `started_at` fields]: `aob-{607,612,620,615,617}-sonnet5-deep-20261005` (listed in start order).
  - Each has an `.instrumented.json` with raw schema `assetopsbench.deepagent.instrumented/0.1`. So the base capture (`_subagent_capture.py`) existed by that date. Its authoring date is not recorded.
  - All had a single agent and 0 delegations.
- **Limitations** [REC, the 2026-10-20 extraction audit]:
  - These five runs have no rendered model inputs and no file events.
  - Delivery can never be established on them.
  - Success of runs 607–621 is UNKNOWN: none was graded [REC, STATE 2026-10-14].

### 2026-10-13: file-observability investigation and instrumentation
- **Question:** can every hop of a file-mediated, delegated information flow be observed?

  The flow is: child tool result → framework file → parent `read_file` → parent answer, numbered T1–T7.
- **Work** [REC, [fork docs](https://github.com/DevikaVishnu/AssetOpsBench/blob/research/agenttrace-specialists/docs/agenttrace-file-observability-handoff.md), handoff "written 2026-10-13"; checkpoint §3]:
  - DeepAgents 0.5.3 internals were confirmed from installed source.
  - Instrumentation Parts A–C were implemented:
    - **A:** `files_returned` on `delegation_end`, `tool_result_committed` with the substitute content, and `tool_end` output hashes;
    - **B:** `_file_observer.py`, emitting `file_write`, `file_read` and `file_edit`;
    - **C:** the runner integration.
  - The suite gave **38 passed**.
- **Synthetic delegated experiment** (Chiller 6 lockout, scripted fake model) [REC, checkpoint §4]:
  - All of T1–T7 are observable and join by `tool_call_id` and sha256.
  - **Limitation:** every model decision was scripted and the lockout fact was planted. This proves instrumentation correctness only, not behavior.

### 2026-10-13, 13:14–13:17 UTC: natural run 621
- **Record** [REC, checkpoint §5]: `aob-621-sonnet5-deep-fileobs-20261013`, scenario 621 used verbatim, unchanged production prompt, tools and model. No pre-registration file exists for it.
- **Findings** [REC]:
  - **No delegation.** The `task` tool was offered and not used, making 0 of 6 natural runs.
  - **Eviction and read-back:** three `history` pages were evicted. The model read page 1 back with `grep` and `read_file`.
  - **First exposure:** the June-10 values first reach a model input at seq 125 and are **restated in the final answer**.
  - **Failed TSFM calls:** two `profile_series` calls failed with ENOENT on virtual paths. The answer omits that detection failed [REC, STATE 2026-10-14].
- **Interpretation** [REC, checkpoint §7]:
  - The tool → file → tool gap is now **schema-side only**. Every raw step is observed.
  - This is a *declared* 0.3 limit, **not a counterexample**.
  - The read-back sequence was one of four supporting observations. That it was decisive is unestablished.
- **Incident** [REC, checkpoint §1.4]:
  - The run appended lines 51–69 to the shared `traces.jsonl` (79,114 → 101,154 B), and there is no backup.
  - **Decision:** from then on, every run gets its own `OTEL_TRACES_FILE`.
  - Whether to truncate the file is still open (STATE Open decision 3).

### 2026-10-13, 13:57–13:59 UTC: run 620-fileobs (pre-registered)
- **Records:**
  - [pre-registration](../experiments/prereg-aob-620-sonnet5-deep-fileobs-20261013.md);
  - [result](../experiments/result-aob-620-sonnet5-deep-fileobs-20261013.md).
- **Question:** will a natural run delegate, and will file-mediated content reach the answer?
- **Outcome** [REC]:
  - **S1 failed:** no delegation, making **0 of 7** natural runs.
  - S2–S4 were met by the root agent: an eviction, a read-back, and delivery at seq 47.
  - **S5 was not met:** no window value is in the answer.
  - Classified as FAILURE/PARTIAL, not INCONCLUSIVE.
  - About $0.32. The WO DB count stayed at 7.
- **Resulting step:** the user had to choose between more natural runs and a declared, controlled delegation condition (STATE Open decision 1). It was resolved on 2026-10-14.

---

## Phase 4: Validation track and the change of direction (2026-10-14)

### 2026-10-14: viz profile rev 2, run 621 fixture audit, Gomoku gate
- **Visualization profile** [REC, [`agenttrace-viz-profile-0.1.md`](agenttrace-viz-profile-0.1.md)]:
  - DRAFT revision 2, a profile-local JSON serialization of 0.3.
  - It records decisions D1–D6. **D1 excludes traces with parallel or undeterminable order.**
  - The dates of revisions 1 and 2 are not recorded.
- **Run 621 fixture feasibility audit** [REC, STATE "Earlier validation work"]:
  - **Verdict:** NO-GO under rev 2 (D1 excludes the trace because of nine parallel tool-call turns). CONDITIONAL GO after the user decides C-a to C-d.
  - The decisions span D1 revision, the five MAJOR profile issues, the gaps G1/G4, and the adapter choices G3/G5.
- **Gomoku #7 gate** [REC]:
  - **BLOCKED.**
  - An independent schema-auditor review found **five MAJOR issues** in profile rev 2, among them the `propagates_to` `raw_ref` shape and state validity not tied to the claims' proposition.
  - No fixture or validator was written.
- **Status:** C-a to C-d and the MAJOR issues remain open (STATE Open decisions 4–5).

### 2026-10-14: direction change to multi-agent failure diagnosis
- **New objective** [REC, STATE "Current direction"]: when a multi-agent industrial run fails, find:
  - where the failure first became observable;
  - who received the evidence;
  - how claims evolved;
  - where behavior diverged from the requirements.
- **Facts verified that day** [REC]:
  - **Single-agent runners:** the AOB runners are single-agent. The README's "agent-as-tool delegation" claims are not in the code.
  - **"Multiagent" scenarios:** this means multi-*domain* tasks.
  - **No graded runs:** no graded or multi-agent run existed locally.
- **Decisions and rationale** [REC]:
  - **AgentHive restoration rejected:** it needs private IBM packages, has a broken entry script, uses watsonx model indices and has stale tool signatures, so it could not be faithful.
  - **DeepAgents specialist subagents (Option B)** behind off-by-default flags:
    - M1: specialists; the parent keeps all its tools, and delegation is not forced;
    - M4: a read-only WO environment;
    - M6: `offered_tools` recorded per agent.
  - **Task:** upstream `scenario_3` used verbatim. It is the only multi-domain task with a checkable answer and local data.
  - **Ground-truth discrepancy:** the `end` value in `groundtruth.txt` has no value in the data.
    - Decision: report E-GT and E-R7 separately and never edit the ground truth.
  - **Predicted failure:** TSFM is expected to fail under the default virtual backend (labelled configuration-induced).
  - **Condition order:** condition B (the default backend) runs first. A runs only after a specialist delegation and further approval.
- **Work** [REC]:
  - The specialist worktree was created (base `6ec35fb`, uncommitted at the time). Tests: **277 passed**.
  - The [scenario_3 pre-registration](../experiments/prereg-aob-sc3-sonnet5-deep-spec-B-20261014.md) was drafted: §1–§12, with readiness amendments in §13.

### 2026-10-14: preparation of the paid run
- **Approved by the user** [REC, STATE handoff "preparation done"]:
  - a disposable isolated CouchDB (C2) instead of removing tools (M5);
  - the budget guard (G1);
  - the launcher location.
- **Work** [REC]:
  - **C2:** an isolated container on `127.0.0.1:5985` whose fidelity to the shared DB was verified. The shared container was proven untouched.
  - **G1:** `_budget_guard.py` (call and estimated-cost limits, refusal before the provider request). Suite: **314 passed**.
  - **Scripts:** `sc3_isolation.py`, `preflight_sc3_B.py` (24 pre checks / 28 post checks), `launch_sc3_B.py` and `test_preflight_sc3_B.py` (**42 passed**). All are in [`../experiments/`](../experiments/).
  - **Final corrections:** the pre-registration's §14.8 recorded them, including the post-run outcome classification and the run-day price check.
- **Limitation** [REC]: G1 bounds an *estimate*. It is not a hard dollar cap.

### 2026-10-14, 18:01:50–18:11:49 UTC: scenario_3 condition B, executed once
- **Outcome** [REC, STATE handoff "scenario_3 condition-B run executed once"]: **BUDGET-STOPPED**, with **GENERIC MULTI-AGENT** delegation.
  - Root delegated once, to `general-purpose`, and no specialist was used.
  - The guard refused child call 416 before the provider request.
  - Estimated cost about $2.10 [INF]. The Console figure has not been checked.
  - Exit code 1. There is no native `.json`, as expected on the error path.
- **Annotator-1 findings** (trace-analyst + schema-auditor) [REC]:
  - **Delegation:** the description given to the child (70 chars) omits facts the parent already held.
  - **Earliest observable failure:** seq 158, TSFM ENOENT on a virtual path. It was seen only by the child; the parent never saw an error.
  - **File-system split:** configuration-induced [INF]. `run_plan` failed 7 times.
  - **Summarization:** framework call 383 replaced the child's history.
  - **Child claims:** they include wrong arithmetic (1000+1000+896 ≠ 2876).
  - **Criteria:**
    - S1 not met;
    - S2 MET;
    - S3 NOT OBSERVABLE: the handoff never happened;
    - S4 NOT MET under the strict wording.
  - **0.3 gaps found** (no schema change):
    - whether the refused call 416 is an event;
    - the origin of a framework-initiated model call inside an agent (383).
- **Failed or lost:**
  - The stderr console log was lost when a session scratchpad was cleared [REC].
  - The scenario must not be rerun. Condition A is not eligible.

---

## Phase 5: Hand-grounded fixtures (2026-10-20)

### 2026-10-20: two canonical 0.3 fixtures and offline tests
- **Question:** can real traces be written as strictly conformant 0.3 by hand, with every object anchored to raw records?
- **Work** [REC, STATE handoff "two hand-grounded 0.3 fixtures"; worktree commit `1a88708`, pushed to the fork]:
  - **Fixture A, run 621:**
    - the read result R;
    - `delivers` at 125/157;
    - the answer, with one claim, proposition and state;
    - `propagates_to(R → A)` over a span checked by the tie rule.
  - **Fixture B, sc3-B:** evidence O, F, D, G and R1–R3, plus five first-delivery `delivers`. It has no claims.
  - **Tests:** `test_semantic_fixtures.py`, **31 tests**. Suite: **345 passed**.
- **Findings:**
  - **Fixture README:** it records 7 schema ambiguities and the adapter decisions: [fixture README](https://github.com/DevikaVishnu/AssetOpsBench/blob/research/agenttrace-specialists/src/agent/deep_agent/tests/fixtures/agenttrace_semantic_0_3/README.md).
  - **Identical-sha confound:** the child's own eviction file has the same sha256 as root's file. Only the path and `tool_call_id` join can separate them [REC].
  - **Reviews:** schema-auditor gave PASS WITH NOTES (621) and PASS (sc3-B). Trace-analyst found every `raw_ref` matching.
- **Corrections made that day:** see the next section.

---

## Phase 6: Comparison operations (2026-10-20)

### 2026-10-20: `agenttrace.compare/0.1`, O2/O3
- **Work** [REC, worktree commit `2902c12`; STATE latest handoff]:
  - **Code:** `_semantic_compare.py`, with O2 `exposure_at`, `claim_delivery` and O3 `state_vs_evidence`.
  - **Spec and fixtures:** a SPEC plus three fixture pairs:
    - 621 (positive control);
    - 620 (abstention control);
    - a SYNTHETIC rule-coverage fixture, never used as behavior evidence.
- **Test result** [REC]: worktree suite **440 passed** (re-run 2026-10-20 just before the commits).
- **Links:**
  - [SPEC](https://github.com/DevikaVishnu/AssetOpsBench/blob/research/agenttrace-specialists/src/agent/deep_agent/tests/fixtures/agenttrace_compare_0_1/SPEC.md);
  - [README](https://github.com/DevikaVishnu/AssetOpsBench/blob/research/agenttrace-specialists/src/agent/deep_agent/tests/fixtures/agenttrace_compare_0_1/README.md).
- **Limitation:** `claim_delivery` and O3 need verified claims and states, which do not exist automatically yet.

---

## Phase 7: Automated extraction milestone (2026-10-20, current)

### 2026-10-20: automated semantic-extraction feasibility audit (read-only)
- **Question:** can previously unseen AOB traces be turned into 0.3 automatically?
- **Recommendation** [REC, STATE latest handoff]:
  - **Conditional GO:** a deterministic structural adapter (stage 1) plus an independent verifier (stage 2).
  - **NO-GO for now:** automated claims, propositions, states and direct links. There is no held-out gold, and faithfulness and directness are human judgments.
- **Findings** [REC]:
  - Rendered inputs exist only in 620-fileobs, 621 and sc3, all of which are development material.
  - The mechanical joins are complete (199/199, 142/142, 130/130), apart from two known irregularities.
  - **No genuinely held-out, fully instrumented trace exists.**
- **Evaluation plan and acceptance criteria:** see STATE.

### 2026-10-20: E1–E4 adapter decisions
- **Status:** **recommendations, not implemented.** The user has not confirmed the individual choices [REC, STATE].
- **The four decisions:**
  - **E1:** revise viz-profile D1 to allow observation (start) order with a declared caveat.
  - **E2:** treat the eviction substitute as a framework-produced item with `$unresolved` source.
  - **E3:** treat the question as external evidence; leave the system prompt out of stage 1.
  - **E4:** build the adapter and verifier in the worktree.
- **Facts used** [REC, trace-analyst]:
  - 22 parallel multi-call outputs, all interleaved;
  - sibling start order equals `tool_calls[]` order, which equals the order of messages in the next input;
  - **10** evictions, not the 4 previously listed.

### 2026-10-20: preservation on GitHub
- **Fork commits** [REC], on `research/agenttrace-specialists`, pushed to `fork` only:

  | Commit | Contents |
  |---|---|
  | `2902c12` | O2/O3 |
  | `5bf563f` | capture and file observer |
  | `ad5c69a` | specialists |
  | `3f261ab` | budget guard |
  | `9122d3b` | runner wiring and tests |
  | `324de44` | checkpoint and handoff docs |

  - The committed sources are byte-identical to the hashes in the sc3 post-run record.
- **IBM upstream push disabled** through a non-functional push URL.
- **AP** [REC]: branch `docs/agenttrace-research-state` (`d00673e`, `0592620`, `6402e17`, `dbaa332`), [PR #1](https://github.com/DevikaVishnu/IBM_Project2/pull/1). Open and unmerged.
  - Home paths were redacted in the published copies.
  - The executed originals are kept locally, with their hashes listed in STATE.

---

## Corrected interpretations

Each later record corrected an earlier statement. The earlier documents are left as they were.

| Earlier statement | Where | Correction | Corrected by |
|---|---|---|---|
| "The file write and read aren't observable events" (lineage through tools and files) | README (2026-10-13), schema §12 OPEN text | In the fileobs capture they are observable (`file_write`, `file_read`). The lineage is still not storable, because `delivers` needs an agent-input source | Checkpoint §6–7 (2026-10-13); fixture ambiguity 7 (2026-10-20) |
| Run 621 page-1 `history` text: 130,849 chars, sha `384780…` | 2026-10-14 audit; checkpoint §5.3 | The recorded `tool_end` 25 is the **list form, 145,917 chars, sha `5d37d836…`**. The 130,849 / `38478099…` figures are its joined text, which is what `file_write` 26 stored | STATE 2026-10-20 "Run 621 hash correction" |
| sc3 child exposure to root's file "at 381" | 2026-10-20 audit report | 381 is the tool result. **First delivery is at llm_start 386** | STATE 2026-10-20 |
| `grep` events start at seq 107 | Earlier 621 notes | The tool events span 108–118; 107 is the `llm_end` that issued them | STATE 2026-10-20 |
| One sc3 child eviction (file_write 135) | Earlier sc3 notes | The child had **three** evictions (123, 135, 147). Across 620-fileobs, 621 and sc3 there are 10 | Trace-analyst, 2026-10-20 |
| Schema sha tail `…5c74cd` | Checkpoint | Transcription slip. The verified value is `2273d210…25c01c06` | STATE "RESOLVED" |
| Natural delegation "0 of 6" | Checkpoint 2026-10-13 | 0 of 7 after run 620-fileobs. sc3-B is a declared research condition and is not pooled with the natural runs | Run 620 result |
| Project framed as belief divergence | May README | Gomoku #7 is a delivery failure. The project was reframed (`b448252`) [RETRO in README] | README 2026-10-05 |

## Failed, negative and stopped experiments

| Experiment | Outcome |
|---|---|
| Natural delegation (runs 607–621, 620-fileobs) | Delegation never occurred in 7 runs |
| Run 620-fileobs | S1 FAILED; S5 not met |
| Run 621 TSFM calls | `profile_series` failed twice with ENOENT on virtual paths (not reported in the answer) |
| scenario_3 condition B | BUDGET-STOPPED. Specialists were never used, the handoff never returned, and TSFM `run_plan` failed 7 times. Do not rerun |
| Gomoku #7 fixture gate | BLOCKED by the five MAJOR profile issues |
| Run 621 fixture under profile rev 2 | NO-GO (D1). It was later written as a hand-grounded 0.3 fixture outside the profile |

## Gaps requiring manual confirmation

1. **Belief Explorer dates:**
   - the work between 2026-04-24 and 2026-05-29;
   - what the `v4.4_beliefs` submodule pointer `205d578` refers to;
   - whether a v3 existed.
2. **Gomoku #7 analysis and the 0.3 design:** no dated record exists between 2026-09-22 and 2026-10-05. The 0.2 date is unknown.
3. **Wider MAST failure analysis:** beyond Gomoku #7 and HyperAgent #25 (and the MAST codes in the prototype's traces), no dated record of a broader MAST study is in either repo.
4. **HyperAgent #25 and run 620 validation dates:** only bounded (2026-10-05 … 2026-10-13).
5. **Bring-up runs** (`aob-s1-sonnet5`, `agenttrace-rich-001`, `agenttrace-deep-001`): dated by mtime only, with no recorded purpose.
6. **Origin and date of the base instrumentation** (`_subagent_capture.py`, schema `instrumented/0.1`): it existed by 2026-10-05.
7. **Viz profile:** the dates of revisions 1 and 2, and of decisions D1–D6.
8. **History rewrite:** the date and scope of the rewrite (tag `pre-rewrite-backup`, branch `backup-before-remove-claude-coauthor`).
9. **sc3-B actual cost:** the Console figure has not been checked.
10. **Annotator 2:** not named, so sc3-B has a single annotator only.

## Key evidence index

| Item | Location |
|---|---|
| Current state and decisions | [`STATE.md`](STATE.md) |
| Canonical schema 0.3 | [`../agenttrace.semantic.0.3.md`](../agenttrace.semantic.0.3.md) |
| Viz profile 0.1 rev 2 | [`agenttrace-viz-profile-0.1.md`](agenttrace-viz-profile-0.1.md) |
| Experiment records and scripts | [`../experiments/`](../experiments/) |
| Checkpoint and handoff | Fork `docs/` (links under Conventions) |
| Fixtures, comparison spec and code | Fork `src/agent/deep_agent/` (`tests/fixtures/agenttrace_semantic_0_3/`, `tests/fixtures/agenttrace_compare_0_1/`) |
| Raw runs (local only) | `AP/data/assetopsbench/runs/`: `aob-{607,612,615,617,620}-sonnet5-deep-20261005*`, `aob-620-sonnet5-deep-fileobs-20261013*`, `aob-621-sonnet5-deep-fileobs-20261013*`, `aob-sc3-sonnet5-deep-spec-B-20261014.instrumented.json`, `otel-*.jsonl`, `preflight/` |
| Early prototype | Repo root (`src/`, `tests/`, [`BELIEF_EVOLUTION_README.md`](../../BELIEF_EVOLUTION_README.md)); history at `32acc00`, `df8cd9c`, `dbfc036` |
