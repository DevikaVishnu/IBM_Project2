# Cross-trace scorecard

Traces checked:

- MAST / ChatDev trace 7: 25 turns, repeated work and incomplete checking.
- AssetOpsBench 607: two failed Chiller lookups, then an unsupported pump-data fallback.
- AssetOpsBench 620: sensor and date-range lookup, but no trip-detection test.
- AssetOpsBench delegated retry 002: manager delegates an asset lookup to a
  helper; helper gets an invalid-site error, retries at `MAIN`, and returns a
  supported conclusion.

This is a decision record, not a promise that every item belongs in the final
schema. `UNKNOWN` is a valid result when a trace did not log the needed fact.

## Keep in the semantic core

- **`raw_ref` / `source_trace`**: needed in all three traces to return from a
  claim or finding to the recorded source.
- **`produced_by`**: needed for tool results, messages, and final answers.
- **`delivers`**: needed by MAST trace 7 to explain a missed requirement. It
  is `UNKNOWN` for AssetOpsBench because exact rendered prompts were not saved.
- **`checks`**: needed by MAST trace 7 to distinguish real checking from a
  bare completion claim. AssetOpsBench 620 has no observed trip-detection
  check, so no such link is created.
- **`supported_by` / `contradicted_by`**: needed for the AssetOpsBench 607
  finding that pump evidence does not establish a Chiller 6 fact.

## Keep as raw-adapter helpers, not new core objects

- **`tool_status`**: `ok`, `error`, or `unknown`. It makes failed tool output
  easy to find. The core still stores the tool output as evidence.
- **`tool_error`**: the recorded error string, when present. It appears in
  607 but needs another failure trace before becoming a permanent requirement.
- **`check_target` and `check_result`**: useful adapter labels when a visible
  test/review actually evaluates something. They map to a `checks` link plus
  its evidence; they are not separate semantic objects.

## Do not add yet

- **`visibility`**: no audience rule is visible in these local files.
- **`delivery_status`, `input_coverage`, `truncated_at`**: AssetOpsBench does
  not save the exact model prompt, so full/partial delivery cannot be proved.
- **`artifact_version`, `content_hash`, `read_by`, `propagates_to`**: the
  chosen runs contain no observed file handoff or version change.
- **`branch_id`, `merge_event`**: two tool calls occur in one 620 turn, but no
  branch identity or merge operation is recorded.
- **`decision_basis`**: the helper's natural-language report says why it
  retried, but the field needs another independent run before it is promoted.
- **`state_changed_at`**: a state is already anchored to its producing event;
  adding another timestamp would duplicate it unless future telemetry needs it.
- **`run.outputs` from AssetOpsBench's `answer` field**: keep the answer as
  evidence for now. Whether a benchmark runner's answer marker defines the
  formal run output remains unresolved.

## What to instrument before the next paid run

1. Save each agent's exact rendered prompt, with an event ID and order.
2. Save full tool output plus whether it was shortened before reaching the
   model.
3. Save sub-agent creation, parent ID, handoff content, and return message.
4. Save file writes and reads with a version and content hash.
5. Save visible reviewer/test commands, target, and result.

## New delegated-retry result

The instrumented run proves that `delegated_by`, `parent_task`,
`attempt_number`, `failure_reason`, `tool_status`, `outcome`, and an
event-anchored state change can all be collected. `delegated_by` and
`parent_task` are now raw-trace fields worth retaining for a second delegated
run. They are not yet final core schema fields. `visibility`, file lineage,
and reviewer checks remain untested.

## Best next paid experiment

Run a small delegated retry task: a manager asks a helper to use a tool; the
tool fails once; the helper retries successfully; the manager receives the
result and must cite it. This one run can test delivery, delegation, retry,
provenance, and a final supported claim.
