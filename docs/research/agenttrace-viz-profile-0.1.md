# agenttrace-viz-profile/0.1: JSON serialization profile for agenttrace.semantic/0.3

Status: **DRAFT, revision 3.**
- Revision 2 applies the schema-auditor corrections M1–M3 and m1–m9, and records the user's decisions D1–D6.
- Revision 3 (2026-10-20) revises D1: start order, observed precedence and overlap, and delegation provenance (Order, §4.1).
- This profile is not part of the canonical schema.

What the profile does:
- **Canonical schema:** `docs/agenttrace.semantic.0.3.md` (sha256 `2273d210…25c01c06`). It is frozen and this profile does not change it.
- **Purpose:** deterministic JSON fixtures for the standalone visualization and for tests of the presentation rules C1–C6.
- **Scope:** serialization only. It adds no stored concept, relation, value or inference.
- **Tags:** every choice that 0.3 does not specify is tagged **[PROFILE-LOCAL]**. Untagged rules restate 0.3 and cite a §.

## 1. File layout [PROFILE-LOCAL]

Each fixture has two files. `<fixture>.trace.json` holds four top-level blocks.

| File and block | Contents | Status |
|---|---|---|
| `trace.json` → `semantic` | the eight 0.3 collections (§2–§4) | **The serialized 0.3 instance** |
| `trace.json` → `raw_sources` | the registry that `raw_ref` values resolve against (§3) | Required companion; provenance resolution only |
| `trace.json` → `vocabulary` | the predicate vocabulary used by proposition forms (§4.2 below) | Required companion: you need it to read `semantic` (D6) |
| `trace.json` → `profile_local` | conformance, extraction, coverage, assumptions, ambiguities, derivations, excerpts (§6) | **Non-canonical** |
| `<fixture>.expected.json` | expected C1–C6 presentation results for tests (§7) | **Non-canonical**, derived, used for tests only |

**Invariant:** deleting `profile_local` and `*.expected.json` must leave a complete, readable serialization of everything 0.3 stores, made of `semantic`, `raw_sources` and `vocabulary`, with nothing derived.

```json
{
  "profile": "agenttrace-viz-profile/0.1",
  "canonical_schema": {"id": "agenttrace.semantic/0.3", "sha256": "2273d210…25c01c06"},
  "fixture_class": "natural | synthetic",
  "raw_sources": [],
  "vocabulary": {"predicates": []},
  "semantic": {"run": {}, "entities": [], "events": [], "evidence": [],
               "claims": [], "propositions": [], "states": [], "links": []},
  "profile_local": {}
}
```

`fixture_class: "synthetic"` (F3–F5) requires `profile_local.synthetic_notice`.
- A synthetic fixture tests presentation rules only. It is never evidence of natural agent behavior.
- Its raw source is the authored synthetic transcript, with `kind: "synthetic"`. It never imitates a natural trace file.

## 2. Value conventions: absent, UNKNOWN and unresolved

JSON `null` is forbidden everywhere [PROFILE-LOCAL].

| Case | Encoding | Allowed where |
|---|---|---|
| **Absent.** 0.3 defines the field as not applying. | Field omitted | Only where 0.3 defines absence: `produced_by` for external evidence (§4.4), `role` and `model` on non-agent entities (§4.2), `origin` for an event with zero origin entities (§4.3) |
| **UNKNOWN.** A value 0.3 itself defines. | String `"UNKNOWN"` | Only `run.outputs` (whole list), `run.outputs[].evidence` (§4.1), and `states[].value` (§8: the holder's own text says it does not know) |
| **Unresolved** [PROFILE-LOCAL]. The extractor could not decide among values 0.3 allows. | `{"$unresolved": "<amb id>", "candidates": [...]}` | Any required field except `order` (§4.1 below). `candidates` ⊆ the field's allowed values. The reserved token `"$absent"` is a valid candidate **only** for fields where the Absent row applies (m1). The id must exist in `profile_local.ambiguities` |

Rules:
- `$unresolved` is an extraction status, not a semantic value. Any occurrence sets `conformance.canonical_complete: false` and is listed in `conformance.unresolved`.
- Consumers show it as unresolved. They never read it as UNKNOWN.
- **Inferred UNKNOWN is never serialized:** silence, uncovered delivery and bare-verdict scope are computed by consumers (§8, §10.1, §5.2).

## 3. Identifiers, references, `raw_sources` and `raw_ref`

**IDs [PROFILE-LOCAL].**
- Each ID is an opaque string matching `^(run|ent|evt|evd|clm|prp|stt|lnk):[A-Za-z0-9._-]+$`.
- IDs are unique per fixture and never renumbered.
- No semantics may be read from the part after the prefix.
- `stt:` and `lnk:` IDs exist for UI and test references only. 0.3 gives states and links no `id` (§4.7, §4.8), and these IDs carry no meaning.

**References.**
- A reference is the referenced object's ID string.
- Endpoint kinds and structural checks for each relation are given in §4.3 below.

**`raw_sources` [PROFILE-LOCAL].** Each entry has these fields:

| Field | Meaning |
|---|---|
| `id` | the source ID |
| `kind` | `natural` or `synthetic` |
| `path` | repo-relative path |
| `sha256` | hash of the file |
| `raw_schema` | the raw source's own schema |
| `selector` | for example `{"index": 7, "field": "trace.trajectory"}` |
| `text_model` | for example `"split on \\n, 1-indexed lines"`, the §14 convention |

**`raw_ref` encoding [PROFILE-LOCAL].** A `raw_ref` is one locator object or a non-empty array of them:

| `kind` | Fields | Resolves to |
|---|---|---|
| `lines` | `source, start, end` (1-indexed, inclusive) | a `raw_sources` location |
| `chars` | `source, line?, start, end` (0-indexed, half-open) | a `raw_sources` location |
| `record` | `source, seq?, path` (JSON path in a structured raw record) | a `raw_sources` location |
| `whole_item` | `evidence` | the evidence item, whose own `raw_ref` resolves (absence-grounded provenance, §9, §5.5) |
| `external` | `description` | an external location; no producing event (§4.4) |

**Optional locator fields [PROFILE-LOCAL]:**
- `note`: free text, used for the adapter decisions that 0.3 places in `raw_ref` (§4.2 instance identity, §11 r9 framework labels).
- `anchor`: used only on propositions (§4.2 below).
- `occurrence`: `"produced"` (default) or `{"delivered_via": "lnk:…"}`, used only on claims (§4.2 below).

**Provenance rule (m3).** Every `raw_ref` must satisfy one of these:
- it resolves to a `raw_sources` location;
- it resolves to an evidence item whose `raw_ref` does (`whole_item`);
- it is `external` (§4.4).

**`raw_ref` on propositions and states (m5).**
- §3 and §11 r1 require provenance on every inferred stored object, propositions and states included. The §4.6 and §4.7 field tables omit the field.
- The profile **serializes it as a required field.** This is a serialization resolution of a gap in the documentation, not a change to 0.3, and the requirement itself comes from §3.
- **State `raw_ref`:** it must equal the union of the grounding claims' spans, which the validator checks, so it adds no information.
- **Proposition `raw_ref`:** see §4.2 (D2).

## 4. The eight collections

### 4.1 Mapping

| 0.3 collection (§) | JSON fields; types | Notes |
|---|---|---|
| `run` (§4.1) | `id`; `raw_ref`; `outputs`: `[{evidence: evd-id \| "UNKNOWN", raw_ref}]` or `"UNKNOWN"` | `outputs` comes only from framework product markers, and `[]` means observably no products (§4.1). Benchmark-harness markers (OPEN, §4.1) are kept only in `run.raw_ref`; serializing them as an extra array entry with a `note` is [PROFILE-LOCAL] (m6) |
| `entities` (§4.2) | `id`; `kind` ∈ {agent, tool, service, framework, environment}; `role`, `model` (agents only, free text from raw); `raw_ref` | There is no `user` or `benchmark` kind, and `role` is never an enum |
| `events` (§4.3) | `id`; `origin` (ent-id, or omitted when there is none); `order`: integer; `raw_ref` | There is no type or phase field |
| `evidence` (§4.4) | `id`; `source` ∈ {user, agent, tool, service, framework, environment, benchmark}; `produced_by` (evt-id, or omitted when external); `raw_ref` = the first output occurrence, or `external` | The enum is exactly as in 0.3 |
| `claims` (§4.5) | `id`; `evidence`; `raw_ref` (the span); `proposition` | There is no speaker, stance or hedge field |
| `propositions` (§4.6) | `id`; `form`; `raw_ref` (required by §3, see §3 above) | Form and identity are in §4.2 |
| `states` (§4.7) | `id` [PROFILE-LOCAL]; `proposition`; `value` ∈ {TRUE, FALSE, UNKNOWN, UNCERTAIN}; `claims` (≥1); `raw_ref` | Holder and event are derived, never serialized. Validity rule below |
| `links` (§4.8) | `id` [PROFILE-LOCAL]; `relation` ∈ the six §5 relations; `source`; `target`; `raw_ref` | No other relation exists |

**Event boundaries [PROFILE-LOCAL].**

| Raw format | One event per | `origin` |
|---|---|---|
| Instrumented DeepAgents | model call (`llm_start`…`llm_end`) | the agent |
| Instrumented DeepAgents | tool call (`tool_start`…`tool_end`) | the tool entity |
| MAST/ChatDev | delimited utterance, following the §14.2 spans | the agent |
| Any | framework procedure with observable output | the framework entity |

- **D4:** the ChatDev rule assumes one model call per utterance. Each fixture records it in `profile_local.assumptions` with `basis: INF`.
- The boundary rule used for each source is recorded in `profile_local.extraction`.

**Order [PROFILE-LOCAL] (D1 rev 3, m2).**
- `order` is a unique integer: the raw seq of the event's first raw record (start order). Gaps are allowed. It is a valid "temporal order" (§4.3).
- `$unresolved` is **not** permitted on `order`.
- `order` is observation order only. `order(X) < order(Y)` alone never establishes that X preceded, caused or enabled Y, or that Y reiterated X (§11).
- **Spans.** Each event's `raw_ref` carries `start_seq` and `end_seq`. An event with a start record and no end record is open: its span runs to the end of the trace.
- **Observed precedence** [PROFILE-LOCAL], a conservative reading of the partial order 0.3 defers (§4.3, §12): X precedes Y iff `end_seq(X) < start_seq(Y)`.
- **Overlap.** Events whose spans intersect, including containment (a `task` tool event spans its subagent's events), are **overlapping observations**. Overlap records only that the spans intersect in the raw sequence. It is **not** evidence of simultaneous execution, and it supports no precedence between the events.
- `profile_local.order` records `basis: "first_raw_seq"` and lists every overlapping event pair.
- **Where 0.3 requires precedence** (§5.3 producer-precedes-E and tie rule; §10.5 Reiteration), the profile requires observed precedence:
  - a stored link whose structural check depends on precedence that is not observed fails the check and is not stored;
  - a §5.3(b) tie span whose precedence can't be determined supports no link and is recorded in `profile_local.ambiguities`;
  - an inference whose precedence condition is not observed, or that would rely on the absence of a link withheld under this rule, takes its own non-committal value: UNKNOWN where the inference defines it (for example §10.5), and "not established" for Lineage (§10.3), which has no UNKNOWN value.
- This is strictly more conservative than 0.3: observed precedence implies order precedence, so the rule can only turn a 0.3 pass into a failure, UNKNOWN or "not established", never the reverse.
- **Delegation provenance.** Producer, carrier and recipient are kept separate:
  - **producer:** the parent's model event is `produced_by` of delegation arguments only where raw provenance establishes it (the arguments first observably occur in that event's output, for example its `tool_calls[]`). Otherwise `produced_by` is `$unresolved`, with an entry in `profile_local.ambiguities`;
  - **carrier:** the `task` tool event transports the arguments and is never recorded as their producer;
  - **recipient:** a subagent model event receives them only through a stored `delivers`, which requires an observed occurrence in its rendered input (§5.1). Delivery is never derived from the delegation, the carrier, `order` or precedence.
- Raw traces whose start sequence can't be determined remain **excluded** from fixtures.

**Evidence boundaries.**
- Follow §4.4: one item per unit that can be produced and delivered on its own. A rendered prompt is never one item.
- Re-emitting identical content creates a new item, linked only by a stored `propagates_to` when §5.3 holds.
- "A multi-file code output gives one item per file" is an interpretation of §4.4's "a file" [PROFILE-LOCAL] (m6).
- Other boundary decisions, such as whether a config key and a template placeholder are one item or two, are recorded in `profile_local.assumptions`, and in `ambiguities` when material.

**Claim spans [PROFILE-LOCAL] (M3).**
- 0.3 requires only "the span inside that evidence item" (§4.5). The profile locates the span inside the item's **produced** occurrence, which is its `raw_ref`.
- For **external** evidence, which has no produced occurrence, the span is located in a delivered occurrence (`occurrence: {"delivered_via": "lnk:<delivers link>"}`). If there is none, the claim's `raw_ref` is `$unresolved`.
- One assertion gives one claim (§4.5). A sentence asserting two propositions gives two claims, and their spans may overlap.

**State validity (M1).** A state is serialized only if all of the following hold (§4.5, §4.7, §8):
1. every grounding claim's evidence has `source: "agent"`;
2. every such evidence item has a `produced_by` event;
3. all those events are one and the same event, and its `origin` is an agent entity, which is the holder.

Consequences:
- Claims on user, tool, service, framework, environment or benchmark evidence never ground a state. Neither does agent evidence with no producer.
- If any condition is unresolved or not met, **omit the state and keep the claims.**
- An omitted state for which the source text shows a stance is recorded in `profile_local.ambiguities`, with `field_path: "semantic.states[omitted:<clm ids>]"`, and listed in `conformance.unresolved`.
- **No hidden persistence:** a state is never copied, extended or defaulted to another event. Each serialized state rests only on claims from its own event (§8).

### 4.2 Propositions: form, vocabulary, identity and anchors

**Grammar [PROFILE-LOCAL] (D3, m7, m8).**
- `form := Pred "(" arg ("," arg)* ")" | "not(" form ")" | ("and"|"or") "(" form "," form ("," form)* ")" | "implies(" form "," form ")"`
- `arg := evd-id | "'" literal "'"`
- **Deterministic syntax:** the arguments of `and` and `or` are sorted in ascending code-point order of their serialized form strings, and there is no whitespace. This is syntax only and adds no semantics.
- **Literals:** each literal must appear verbatim in one of the proposition's `requirement_text` or `claim_text` anchors. Literals are never paraphrased.

**Vocabulary (D6, M2).**
- Each `Pred` must be declared in `vocabulary.predicates` as `{name, arity, gloss, raw_ref}`. The gloss is free text, and its `raw_ref` is the raw text it was read from.
- The vocabulary is required to read `semantic` and is not part of `profile_local`.
- The vocabulary gives the meaning of predicate names only. It stores no relation between predicates; implication and equivalence stay undefined (§12).

**Identity (D3).**
- One proposition object per distinct form string. Identity is **syntactic**.
- Two syntactically different but logically equivalent forms, for example from double negation, are a **known fixture defect**. They are never evidence that the propositions are distinct, and no equivalence is computed or displayed as identity.
- `G(evd:v2)` and `G(evd:v3)` are distinct propositions (§4.6). Grouping them across versions is C3, which is derived [PROFILE-LOCAL] (m6).

**Negation and hedging (D5, m9).**
- ¬P is its own proposition, `not(F)` (§4.5). Hedging appears only as the state value `UNCERTAIN` (§4.5, §8).
- Both conventions are **provisional**, because no real trace has exercised them (§4.5, §12 known limit).
- Treating (P, FALSE) and (¬P, TRUE) as equivalent is a semantic claim 0.3 never makes. The profile stores no such equivalence.
- Any C2 output that uses it must be labeled **profile-derived, not 0.3-derived**. Synthetic tests of C2 must be labeled synthetic.

**Proposition anchors (D2).** A proposition's `raw_ref` is an array of locators, each with an `anchor` field [PROFILE-LOCAL]:

| `anchor` | Names |
|---|---|
| `requirement_text` | the raw span stating the requirement or predicate application |
| `argument_item` | a `whole_item` locator for each evidence item that appears as an argument |
| `claim_text` | the claim span the form was extracted from, when the proposition was extracted from a claim |

- Anchors are **source anchors only.** They do **not** establish delivery, satisfaction, verification, or any agent's claim or state. Those come only from stored `delivers`, `checks`, `supported_by`/`contradicted_by`, claims and states.
- **The extractor's derivation** is recorded in `profile_local.derivations`, **outside** `semantic`. For example: "requirement applied to item by §9; item = artifact delivered to V, or the `run.outputs` entry".
- No relation is added to represent derivation.

### 4.3 Link endpoints and structural checks (m4)

| Relation | Source → target | Structural checks (from §5) |
|---|---|---|
| `delivers` | evt → evd | The source event's `origin` is an agent entity, making it an agent-input event (§4.3, §5.1). `raw_ref` names the occurrence in the rendered input |
| `checks` | evt → prp | `raw_ref` names the grounding: evaluator text, executed check, or framework procedure. It is never a bare verdict or the instruction itself (§5.2) |
| `propagates_to` | evd A → evd B | B has a `produced_by` E, and a stored `delivers(E, A)` exists (§5.3 conditions 1–2). A ≠ B, and if A has a producer it observably precedes E (Order, observed precedence). `raw_ref` = `{"in_target": [...], "in_source": [...]}` |
| `depends_on` | prp → prp | none beyond endpoint kinds (§5.4) |
| `supported_by`, `contradicted_by` | prp → evd | `raw_ref` names the grounding spans, or `whole_item` for absence-grounded links. No grounding span may be a claim span that asserts P or ¬P (§5.5, §5.6) |

## 5. Provenance and ambiguous evidence

- Canonical fields carry identifiers, enums, forms and `raw_ref` only. Raw content is never paraphrased into them [PROFILE-LOCAL] (m6).
- Framework labels, such as phases, rounds, completion markers and role strings, appear only in `raw_ref.note` or `profile_local`, never as structure (§11 r9).
- **Ambiguous evidence** is represented in three places at once:
  - the affected required field carries `$unresolved` with `candidates` (including `"$absent"` where allowed);
  - `profile_local.ambiguities` holds `{id, field_path, candidates, reason, raw_ref, basis: OBS|INF|HYP}`;
  - `conformance.unresolved` lists the field path.
- **No object is invented to work around an ambiguity.** Examples from §14.3:
  - the Gomoku Task `produced_by` is UNRESOLVED, so it gets candidates `["$absent", "evt:<framework event>"]`;
  - the test report's `source` is UNRESOLVED.

## 6. `profile_local`: non-canonical, stored separately

```json
"profile_local": {
  "conformance": {"canonical_complete": false, "unresolved": ["semantic.evidence[evd:task].produced_by"]},
  "extraction": {"event_boundary": {"src:mad7": "ChatDev utterance spans per §14.2"}, "extractor": "manual | <tool+version>", "date": "YYYY-MM-DD"},
  "coverage": [{"event": "evt:…", "status": "established | not_established | unassessed", "method": "…", "basis": "…", "raw_ref": {}}],
  "assumptions": [{"id": "asm:…", "statement": "…", "applies_to": ["…"], "basis": "OBS|INF|HYP", "raw_ref": {}}],
  "ambiguities": [{"id": "amb:…", "field_path": "…", "candidates": [], "reason": "…", "raw_ref": {}, "basis": "…"}],
  "derivations": [{"proposition": "prp:…", "rule": "…", "inputs": ["…"], "basis": "OBS|INF|HYP"}],
  "excerpts": [{"of": "clm:… | evd:…", "text": "≤ 300 chars", "sha256": "…"}],
  "synthetic_notice": "required iff fixture_class = synthetic"
}
```

- **Coverage:** `established` and `not_established` are the values of the §10.1 inference. `unassessed` [PROFILE-LOCAL] means the inference was not run. Coverage is inference provenance and is never stored (§10.1, §12).
- **Excerpts:** display-only copies of raw spans, not canonical content, since 0.3 stores none. They never include a complete model input.
- No other inference result is stored here. Exposure, verification, persistence and contribution are computed by consumers.

## 7. Derived presentation comparisons (C1–C6) are never stored

- C1–C6 results are never written to `semantic.links` or anywhere in `semantic`.
- They never use a relation name outside §5. `conflicts_with` and `revises` stay unrepresented (§6, §12).
- Expected results for tests live only in `<fixture>.expected.json` as `{"rule", "inputs", "expected", "basis"}`.
- **C2 entries must state `"basis": "profile-derived"`.**

## 8. Decisions

| ID | Decision | Status |
|---|---|---|
| D1 | Parallel or undeterminable raw order | **Decided (rev 3):** `order` = first raw seq, observation order only. Spans in `raw_ref`, overlaps in `profile_local.order`, observed precedence where 0.3 requires precedence, otherwise UNKNOWN or ambiguity. Only traces whose start sequence can't be determined are excluded. There is no `$unresolved` on `order` |
| D2 | Provenance of a derived proposition | **Decided:** `requirement_text`, `argument_item` and `claim_text` source anchors. The derivation goes in `profile_local.derivations`. Anchors establish nothing semantic, and no new relation is added |
| D3 | Form grammar and identity | **Decided:** syntactic identity with deterministic argument order. Duplicates that are logically equivalent are fixture defects |
| D4 | One event per ChatDev utterance | **Decided:** a PROFILE-LOCAL boundary rule with an inferred (`INF`) assumption per fixture |
| D5 | Negation and hedging | **Provisional:** conventions as in §4.2. C2 normalization is labeled profile-derived, and synthetic tests are labeled synthetic |
| D6 | Predicate vocabulary | **Decided:** the required `vocabulary` companion block |

**Changes to canonical semantics: none were required.** Every correction is a tag, a serialization rule, or a restatement of 0.3. D1 rev 3's observed precedence is a PROFILE-LOCAL, strictly more conservative reading of 0.3's deferred partial order (§12), not a change to 0.3.
