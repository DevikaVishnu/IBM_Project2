# agenttrace-matrix/0.2: matrix data contract

This contract is profile-local display data for the Belief Explorer observation matrix. It is **not** part of `agenttrace.semantic/0.3` and adds nothing to it. `build_matrix.py` produces it. `validate_matrix.py` validates it independently: it re-runs the frozen adapter and verifier and re-derives every field. The builder and the validator share no code.

## Pipeline

```
instrumented trace ── adapter (frozen) ── verifier ──► reject if any error
                                              │
                                              ▼
                       matrix data ── validate_matrix ──► reject if any error
                                              │
                                              ▼
              src/demo/data/matrices/<run-id>.matrix.json + index.json (manifest)
```

The UI loads only runs listed in `index.json`, and checks each file's sha256 against the manifest before use.

## Fields

| Field | Meaning |
|---|---|
| `contract` | `agenttrace-matrix/0.2` |
| `run` | Run id given on the command line, plus the record's run id, scenario, runner, model, status, `error` (type and message only, never a traceback, home paths replaced), start/end times, terminal event, question present, framework versions |
| `telemetry` | Adapter flags `delivery` and `offered_tools` (`present` or `absent`), with their stated limits |
| `provenance` | Trace path (repo-relative or file name only), trace sha256, adapter id and increment, verifier, worktree HEAD, schema sha256, optional fixture (`worktree:`-relative path and sha256) |
| `semantic` | Always `claims_extracted: false` and 0 claims, propositions and states |
| `rows` | Exactly the record's `agents[]`, in order |
| `columns` | Exactly the adapter's model events, in observation order. See the next table |
| `evidence` | Only the items a column references: source, producer, kind (`tool_result`, `tool_argument`, `eviction_substitute`, `question`), locator, sha256, size, and the first 300 characters of the resolved text |
| `other_events` | The adapter's tool and eviction events (origin, order, seqs, `tool_call_id`, `issued_at`) |
| `fixture_links` | Optional. Each delivers link of a hand-grounded fixture for the same trace, reproduced by exactly one adapter link. Fixture claims are never copied |
| `ambiguities`, `skipped` | Copied from the adapter: unresolved fields, and records not represented, with reasons |
| `counts` | Model calls, calls per row (including `$unresolved`), delivers, evidence, tool and eviction events, overlapping pairs |
| `order_caveat` | The adapter's observation-order caveat |

### Column fields

| Field | Meaning |
|---|---|
| `id`, `order`, `start_seq`, `end_seq` | As in the adapter output |
| `row` | The origin agent, or `$unresolved` |
| `origin` | As in the adapter output. An unresolved origin keeps its candidate list |
| `origin_label`, `origin_rule` | How the origin was assigned |
| `raw_agent_id` | The agent id recorded in the raw trace |
| `input_locator`, `output_locator` | Where the call's input and output sit in the raw trace |
| `issued_tool_events` | Tool events issued by this call |
| `issued_delegations` | Argument evidence of a `task` call in this output |
| `delivers` | Targets of the adapter delivers links from this event, in order |
| `first_delivered_here` | `[id, locator]` for each item that first appears in this agent's input here. A display convenience, not a semantic object |
| `delegation_input` | Delivered items joined by `delegation_id` |
| `overlaps_with` | Other model calls whose spans overlap this one |
| `fixture_links` | Fixture items recorded as delivered here |

## Invariants checked by `validate_matrix.py`

1. **Form:**
   - the file is canonical JSON;
   - all required keys are present;
   - there are no top-level `claims`, `propositions`, `states`, `beliefs` or `disagreements` keys;
   - no home-directory path appears.
2. **Source:** the trace sha256 matches, and the frozen adapter output passes the verifier.
3. **Rows and columns:**
   - rows equal `agents[]`;
   - columns equal the adapter's model events, with equal order and start/end seqs;
   - each column's row equals its origin, or `$unresolved` with the adapter's origin object kept.
4. **Recomputed per column:**
   - `delivers` and `first_delivered_here`;
   - `delegation_input` and `issued_delegations`;
   - `issued_tool_events` and `overlaps_with`;
   - with delivery telemetry absent, every column has no deliveries.
5. **Evidence:**
   - the map holds exactly the referenced items;
   - each locator and source equals the adapter's;
   - each excerpt is the first 300 characters of the resolved text, with a correct completeness flag.
6. **Counts, ambiguities and run metadata** recompute: status, record run id, terminal event, error presence, and no traceback.
7. **Fixture (optional):** every fixture delivers link is reproduced as recorded. Without a fixture, no fixture links appear.

## Known behaviour (tested)

| Situation | Result |
|---|---|
| Unknown `agent_id` | Origin `$unresolved` (`agent_id_unattributed`); no row is invented |
| No rendered inputs (e.g. 607) | Delivery telemetry is `absent`, there are no deliveries, and model calls are `$unresolved` (`no_rendered_input`) |
| Malformed tool message where `offered_tools` is present | Only that join is dropped and recorded (`rendered_tool_message_unjoined`) |
| Malformed tool message where `offered_tools` is absent | The agent-loop check fails, so that call and every later call of the agent become `$unresolved` (fail-closed) |
| No model calls | `columns: []`; the UI shows an empty state |
| Invalid adapter output, unknown raw schema, a fixture for another trace, a bad run id | The builder exits non-zero with the errors and writes nothing |
