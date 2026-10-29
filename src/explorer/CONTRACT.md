# agenttrace-explorer-bundle/0.1: Belief Explorer trace bundle

One JSON file per trace. `BeliefExplorerPage` renders a bundle and nothing else, so any framework (DeepAgents, ChatDev, …) can be shown once it is converted to this shape. The contract is display data. It is **not** part of `agenttrace.semantic/0.3`, adds nothing to it, and never edits adapter output.

- Builder: `scripts/explorer/build_bundle.py` (local only; see `docs/DATA.md`, "Belief Explorer data").
- Validator: `scripts/explorer/validate_bundle.py`. It shares no code with the builder.
- Manifest: `src/explorer/data/index.json` (`agenttrace-explorer-manifest/0.1`). It lists `{trace_id, file, sha256, contract, label, kind}` per bundle. The loader checks each file's sha256 against the manifest before use.
- Bundles and annotations are local-only. `src/explorer/data/` and `src/explorer/annotations/` are gitignored.

## Origin tags

Every item that carries information has an `origin`:

| `origin` | Meaning |
|---|---|
| `observed` | Recorded in the raw trace and resolved by locator (events, tool results, run status). |
| `computed` | Derived deterministically by code: adapter joins (agent origin, `delivers`), the matrix pipeline, O2/O3 from `agenttrace.compare/0.1`, counts and string checks. A computed result over hand input says so in `computed_from`. |
| `hand-annotated` | Written by a person in `src/explorer/annotations/<trace>.json`: claims, propositions, states, direct links and flags. Always shown as **"hand-annotated, illustrative, not gold"**. |
| `hand-reconstructed` | Rebuilt by hand from a document. Currently only the Gomoku skeleton, from schema §14, with every cited log line checked by the builder. |
| `unresolved` | The trace does not establish it (e.g. an agent origin). Nothing semantic is derived from it. |

## Top level

| Key | Content |
|---|---|
| `contract` | `"agenttrace-explorer-bundle/0.1"` |
| `trace` | `id`, `label`, `kind` (`single-agent` or `multi-agent`), `framework`, `model`, `scenario`, `status`, `answer` (event and step of the final answer, if any) |
| `honesty` | `annotations` (label shown on every hand layer, or `"Not annotated"`), `skeleton` (where the skeleton comes from), `rules` (display rules, shown verbatim) |
| `provenance` | Raw trace path and sha256, adapter and increment, verifier result, compare profile, worktree HEAD, schema sha256, matrix file and sha256, annotation file and sha256, builder |
| `layers` | Booleans: `skeleton`, `matrix`, `claims`, `evidence`, `delivery`, `o3`, `flags`. The page shows a "not available" state for a false layer and never fails on one. |
| `skeleton` | See below |
| `matrix` | See below |
| `evidence` | Map `id` → evidence item |
| `propositions`, `claims`, `non_claims` | The annotation layer, plus computed results attached to it |
| `flags` | Annotated observations worth attention, with their computed checks |
| `facts` | Short dashboard statements: computed figures, lanes, the handoff, run status |
| `checks` | Builder self-checks (adapter counts, verifier errors, fixture agreement) |

Any of `skeleton` and `matrix` may be `null`, and any list may be empty.

### `skeleton`

- `agents[]`: `{id, label, sub, kind (agent|framework|unresolved), parent, origin}`.
- `events[]`: `{id, kind (model_call|tool_call|framework_eviction|check), order, steps [first, last], agent, label, origin}`.
- `handoffs[]`: `{from, to, via, item, origin}`.
- `counts` (with `counts_origin`) and `skipped` (records the adapter did not represent).
- `delivery`: Gomoku only. Hand-reconstructed `delivered` and `not_delivered` lists. `not_delivered` requires a `coverage` statement.

### `matrix`: the interaction grid

| Field | Meaning |
|---|---|
| `origin`, `source_contract` | `computed` from `agenttrace-matrix/0.2` (`scripts/demo/build_matrix.py`, validated by `validate_matrix.py`), or `hand-reconstructed` with `source_contract: null` |
| `rows[]` | Agents, plus `$unresolved` (or `$not_reconstructed`) when needed: `{id, label, sub, kind, origin}` |
| `columns[]` | Model calls in observation order: `{id, order, row, steps, delivers, first, delegation_out, delegation_in, overlaps, tools, origin}` |
| `edges[]` | Handoffs between rows: `{from, to, via, item, origin}` |
| `delivery_track`, `max_delivers` | Whether rendered-input counts exist |
| `overlays[]` | Annotation-layer markers `{id, kind (claim|flag|lane), column, row, ref, label, origin}`. `ref` points to a claim or flag id |
| `note`, `order_caveat` | Shown under the grid |

The page draws the grid with the matrix component of the earlier demo (`Matrix` and `derive`, exported from `src/demo/MatrixView.jsx`). `toMatrixModel` in `MatrixPanel.jsx` maps this layer onto the matrix/0.2 fields that component reads. Overlays are drawn in a marker band above the grid and a highlight layer over it.

The grid itself stays claim-free: there are no `claims`, `propositions` or `states` keys inside `matrix`, which mirrors the matrix validator rule. Claims reach the grid only as overlays from the annotation layer.

### `evidence[id]`

`{id, step, tool, kind, source, produced_by, locator, sha256, size, excerpt: {text, start, complete, to_end, spans}, origin}`. The excerpt is a display window around the annotated spans (spans re-based into `text`). `start > 0` means text is cut before the window; `to_end: false` means text is cut after it. Gomoku items carry `lines` instead of `step`.

### `claims[]`: the per-claim chain

| Field | Meaning |
|---|---|
| `words`, `span`, `event`, `step` | The exact words and their code-point span in the claiming call's output |
| `speaker`, `speaker_origin` | The agent, or `$unresolved` |
| `proposition` | id into `propositions[]` |
| `state` | `{value: TRUE|FALSE|UNCERTAIN|UNKNOWN, origin}` |
| `links[]` | `{relation, evidence, values, rule_dependent, origin, delivery: {to_event, value, operation, origin}}`. `delivery.value` is the O2 whole-item result for the claiming call. **Without established coverage a negative is never computed: absence reads `UNKNOWN`, never "not delivered".** |
| `o3` | `{status: computed|not computable|rule-dependent, comparison, direct, delivered_direct, testimonial, meaning, computed_from, reason, hand_comparison, fixture_expected, origin}` |
| `notes`, `fixture` | Annotation notes; the source fixture if the claim was taken from one |

`non_claims[]` holds annotated words shown for context that are not claims, such as a recommendation. They are never compared.

### `flags[]`

`{id, title, kind, text, caveat, events, anchors, evidence, computed[], origin}`.
- `anchors` are the few columns that get a marker.
- `events` are all the columns highlighted when the flag is selected.
- `computed[]` items are the builder's checks, each with its own origin.

### `walkthrough` (optional)

Data for the "How it's built" view, which follows one claim from raw records to the screen. Present only for traces listed in `WALKTHROUGH` in the builder (currently run 621's June 10 claim).

| Field | Content |
|---|---|
| `claim`, `evidence`, `tool_event`, `first_receiver` | Ids into `claims`, `evidence` and `skeleton.events` |
| `raw` | `{origin: observed, steps: [first, last], records[]}`. Record **metadata only** for the steps from the tool call to the first model call that received the item: type, agent, tool, tool_call_id, offset and limit, sizes, status, and sha256 prefixes. No record content beyond what `evidence` already holds |
| `adapter` | `{origin: computed, delivers[]: {event, locator, message_index, byte_identical}, verifier_errors}`: every delivers link of the item |
| `comparator` | `{origin: computed, operation, o2[]: {event, item, value}}`: O2 at the first receiving call and at the claiming call. O3 is read from the claim itself |
| `note` | One line shown under the stepper |

Everything else the view shows (claim, proposition, state, links, O3, run totals) is read from the existing bundle fields, so the view holds no values of its own.

## Validator rules (`validate_bundle.py`)

1. **Form.** The contract string, all top-level keys, `layers` booleans, a valid `trace.kind`, and no home-directory path.
2. **Origins.** Every row, column, edge, overlay, evidence item, proposition, claim, state, link, delivery, O3 result, non-claim, flag, computed check and fact has a valid origin tag.
3. **Referential integrity.**
   - Columns reference rows, and are skeleton events.
   - Edges, overlays and flags reference known columns or events. An overlay's row equals its column's row.
   - Claims reference known propositions and events. Links reference evidence in the map. Overlay `ref` is a known claim or flag.
4. **Honesty.**
   - Delivery values come from the O2 vocabulary, and `NOT_DELIVERED` requires a coverage statement.
   - A computed O3 has a comparison, a meaning and `computed_from`; any other O3 status has a reason.
   - The matrix layer is claim-free, and columns are in observation order.
5. **Layers.** A layer flagged present is not empty.
