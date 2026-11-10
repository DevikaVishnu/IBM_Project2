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
- `events[]`: `{id, kind (model_call|tool_call|framework_eviction|check|deterministic_execution), order, steps [first, last], agent, label, origin}`. `deterministic_execution` is optional (see *Column kinds* below).
- `handoffs[]`: `{from, to, via, item, origin}`.
- `counts` (with `counts_origin`) and `skipped` (records the adapter did not represent).
- `delivery`: Gomoku only. Hand-reconstructed `delivered` and `not_delivered` lists. `not_delivered` requires a `coverage` statement.

### `matrix`: the interaction grid

| Field | Meaning |
|---|---|
| `origin`, `source_contract` | `computed` from `agenttrace-matrix/0.2` (`scripts/demo/build_matrix.py`, validated by `validate_matrix.py`), or `hand-reconstructed` with `source_contract: null` |
| `rows[]` | Agents, plus `$unresolved` (or `$not_reconstructed`) when needed: `{id, label, sub, kind, origin}` |
| `columns[]` | Model calls in observation order: `{id, order, row, steps, delivers, first, delegation_out, delegation_in, overlaps, tools, origin}`, plus the optional `kind` (see *Column kinds*) |
| `edges[]` | Handoffs between rows: `{from, to, via, item, origin}` |
| `delivery_track`, `max_delivers` | Whether rendered-input counts exist |
| `overlays[]` | Annotation-layer markers `{id, kind (claim|flag|lane), column, row, ref, label, origin}`. `ref` points to a claim or flag id |
| `note`, `order_caveat` | Shown under the grid |

The page draws the grid with the matrix component of the earlier demo (`Matrix` and `derive`, exported from `src/demo/MatrixView.jsx`). `toMatrixModel` in `MatrixPanel.jsx` maps this layer onto the matrix/0.2 fields that component reads. Overlays are drawn in a marker band above the grid and a highlight layer over it.

#### Column kinds (optional)

`kind` is `model_call` (the default when the field is absent) or `deterministic_execution`. Bundles without the field are unchanged.

A `deterministic_execution` column is code that made no model call. A builder adds one only for an execution that posted at least one recorded message. The column must satisfy all of the following:

- `delivers` and `first` are `null`, `tools` is empty and both delegation flags are false. Code has no model input, so the input track draws no bar.
- `execution` is `{id, assigned_agent, agent_name, role, kind, stage, round, status, started_at, completed_at, started_event, mechanism, locator}`. `row` is the assigned agent.
- `messages[]` lists what the code posted: `{id, type, seq, evidence, text_mechanism, sent_event, response_to, recorded_deliveries, code_access, disagreements, locator}`. It must be non-empty.
- `code_access[]` lists the messages the code read through an inbox or board: `{message, from, via, seq, received_event, locator}`. A code access is **not** a delivery into a model input, and it is never an edge.
- `events[]` lists the recorded events of this execution, plus the events with no execution that name one of its messages: `{seq, type, event_id, timestamp, actor, message, join, fields, locator}`. `fields` keeps only the payload's scalar fields.
- `order_basis` states what `order` is. For the agent council, `order` is the seq of the execution's first MESSAGE_SENT.
- Its skeleton event has `kind: deterministic_execution`.

Edges keep their meaning: a message recorded in a model call's rendered input. An edge may now **start** at a code-execution column, when code built the message text. It may never **end** at one. Model-call counts (`skeleton.counts.model_calls`, and "model call i of n" in the UI) exclude code-execution columns.

The grid itself stays claim-free: there are no `claims`, `propositions` or `states` keys inside `matrix`, which mirrors the matrix validator rule. Claims reach the grid only as overlays from the annotation layer.

### `evidence[id]`

`{id, step, tool, kind, source, produced_by, locator, sha256, size, excerpt: {text, start, complete, to_end, spans}, origin}`. The excerpt is a display window around the annotated spans (spans re-based into `text`). `start > 0` means text is cut before the window; `to_end: false` means text is cut after it. Gomoku items carry `lines` instead of `step`.

### `claims[]`: the per-claim chain

| Field | Meaning |
|---|---|
| `words`, `span`, `event`, `step` | The exact words and their code-point span in the claiming call's output |
| `speaker`, `speaker_origin` | The agent, or `$unresolved` |
| `proposition` | id into `propositions[]` |
| `state` | `{value: TRUE|FALSE|UNCERTAIN|UNKNOWN, origin}`. It may be `null` only for a framework-authored claim, as described below |
| `links[]` | `{relation, evidence, values, rule_dependent, origin, delivery: {to_event, value, operation, origin}}`. `delivery.value` is the O2 whole-item result for the claiming call. **Without established coverage a negative is never computed: absence reads `UNKNOWN`, never "not delivered".** |
| `o3` | `{status: computed|not computable|rule-dependent, comparison, direct, delivered_direct, testimonial, meaning, computed_from, reason, hand_comparison, fixture_expected, origin}` |
| `notes`, `fixture` | Annotation notes; the source fixture if the claim was taken from one |

**Framework-authored claims (optional).** A claim whose words were built by code is framework-authored. It has `state: null` and carries two extra fields:

- `state_absent: {reason, origin}` says why there is no state (for example, a state's holder must be an entity, 0.3 §4.5);
- `author: {kind: "deterministic_execution", execution, assigned_agent, origin}` names the code that built the words.

The validator enforces five rules:

1. `event` is the code-execution column of `author.execution`.
2. `o3.status` is `not computable`: such a claim is never an O3 input.
3. Any link delivery is `NOT_APPLICABLE`, because there is no model input.
4. A state-less claim must be framework-authored.
5. A code-execution column never holds a claim with a state.

The UI counts these claims apart from agent claims and never as belief states.

`non_claims[]` holds annotated words shown for context that are not claims, such as a recommendation. They are never compared.

### `flags[]`

`{id, title, kind, text, caveat, events, anchors, evidence, computed[], origin}`.
- `anchors` are the few columns that get a marker.
- `events` are all the columns highlighted when the flag is selected.
- `computed[]` items are the builder's checks, each with its own origin.

#### Findings (optional fields on `flags[]`) and `assessment` (optional top level)

A **finding** is a flag that has a `category`. It adds the following fields to the flag:

| Field | Content |
|---|---|
| `category`, `category_label`, `category_definition` | One of `cross_agent_assertion_incompatibility`, `direct_evidence_contradiction`, `recorded_coordination_disagreement`, `position_decision_inconsistency`. `kind` equals `category`. Categories are kinds of finding, not severities |
| `priority` | Integer. Findings are listed in priority order |
| `validation` | Always `"hand-validated"`. There is no automatic detection |
| `observed[]` | `{text, value, locator, origin: observed}`. The builder re-resolves every locator against the raw trace and checks the value |
| `interpretation` | `{text, origin: hand-annotated}`. The reading of the observations, kept apart from them |
| `computed[]` | Builder checks: compare/0.1 O2/O3, arithmetic over recorded values, message mechanism and delivery counts, records after a seq. Each has `origin: computed` |
| `limitations[]`, `unknowns[]` | Known limits, and what is UNKNOWN or not established |
| `columns`, `events`, `anchors`, `evidence`, `refs.claims`, `refs.positions` | Navigation targets: matrix columns, messages and evidence items, claims, and computed-position observations |

`assessment` is `{status: "hand-validated" | "not_assessed", label, text, origin, method, source, source_sha256}`. When it is `not_assessed`, the page shows **"Not assessed"**, never "no divergence", and its text must say that the absence of findings is not evidence.

Validator rules:
- every finding is hand-validated and hand-annotated, and has at least one observed anchor;
- the interpretation is hand-annotated, and computed items are tagged computed;
- references resolve, and findings are in priority order;
- no finding describes itself as automatic detection;
- a `not_assessed` bundle carries no findings.

Bundles without these fields are unchanged.

### `positions` (optional): framework-computed positions

Optional top-level object (decision C4). Bundles without it validate and render unchanged; the page shows the **Computed positions** tab only when it is present. It holds scores that framework code computed and recorded. They are never claims, propositions, states or beliefs, and they are never inputs to O3.

| Field | Content |
|---|---|
| `origin`, `label`, `producer`, `source` | `label` must read exactly "Framework-computed positions — not agent beliefs" |
| `candidates[]` | Diagnosis labels in order of first appearance |
| `agents[]` | Agents with at least one `agent_position` |
| `segments[]` | Display axis: `{id, round, phase, label, first_seq, last_seq, origin}`. Consecutive observations (in seq order) with the same recorded round, or with no round and the same recorded stage, share a segment |
| `observations[]` | In seq order; see below |
| `score_states[]` | `{id: S0…, scores, observations[], first_seq, first_locator, leading, labels_recorded, origin}` |
| `counts`, `rules` | Counts per kind; display rules shown verbatim |

Each observation is `{id, kind, holder, seq, seq_basis, round, phase, stage, draft, locator, event, event_join, scores, recorded_label, confidence, confidence_field, leading, missing_labels, unknown, segment, related, origin}` plus kind-specific fields:

| `kind` | `holder.kind` | Source | Extra fields |
|---|---|---|---|
| `agent_position` | `agent` (`holder.agent`) | `positions.agents.<agent>[i]` | `abstain`, `old_label`, `moved_by`, `method`, `message_payload` (same values check) |
| `joint_ranking` | `council` | `positions.joint[i]` | `converged`, `dissent`, `member_positions`, `also_recorded_at` (equal-payload `JOINT_FINDING_REACHED` events) |
| `hypothesis_scores` | `framework` (`recorded_on_execution`, `execution_agent`) | `HYPOTHESES_SCORED` payloads, `executions[].input.scored_hypotheses`, `executions[].output.extras.scores` | `basis`, `part`, `source`, `execution_finding`, `score_state` |
| `final_decision` | `framework` | `FINAL_SYNTHESIS_GENERATED` | `review_decision`, `evidence` |

- **Values** are copied by locator (`origin: observed`). `leading` is computed: the top recorded score, with exact ties kept (`tie: true`) and `margin` from the unrounded recorded values. Missing labels are listed in `missing_labels` and read UNKNOWN, never zero.
- **`unknown`** names every missing value (`scores`, `confidence`, `round`, `event`) with a reason.
- **`related`** is a recorded join only: `message_id` (the message's producing column, the model calls whose verified input holds its text, and its code-only reads) or `execution_id` (the execution's columns). Nothing is linked by seq proximity.
- **Score states** group `hypothesis_scores` observations whose values are exactly equal on every shared label, where one label set contains the other. More than one match is recorded as `score_state_ambiguous`. A state change is not an agent's revision.

Validator rules: the label; origin tags; the holder kind fixed per kind (only an `agent_position` names an agent, and that agent is a matrix row); seq order; `leading` re-computed independently; every missing score, confidence or round named in `unknown`; related columns and evidence exist; score-state membership is consistent and holds only `hypothesis_scores`; no claims/propositions/states/beliefs keys; no claim points at a position.

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

## Guide sidecar (optional, display only)

`src/explorer/data/<trace_id>.guide.json`, contract `agenttrace-explorer-guide/0.1`, is plain-language display copy written by hand for one bundle. It is not part of the bundle, `agenttrace.semantic/0.3` or `compare/0.1`, and it adds no result. Like the bundles it is local-only (the directory is gitignored).

- **Binding.** `trace_id` and `bundle_sha256` must match the manifest entry. Otherwise the host ignores the guide and the page shows only the technical view.
- **Fields.** `overview.{subject, decision, divergence, numbers}`, `agents.<row id>.{role, role_locator, final_label}` (copied from the source agent record), `mechanisms_note`, `assessment`, and `findings.<flag id>.{title, what, who[], compare{columns, rows[{cells, verdict?}]}, why, uncertainty}`.
- **Rendering.** With a guide, the Overview leads with the plain summary and agent popovers, and the original tiles, claims and facts sit behind "Technical overview". Each finding card leads with its plain fields, and the original text, navigation, observed, computed, interpretation, limitations, unknowns and evidence sit behind "Technical evidence". The final decision is read from the bundle's `final_decision` position, not from the guide. With no guide, nothing changes.
