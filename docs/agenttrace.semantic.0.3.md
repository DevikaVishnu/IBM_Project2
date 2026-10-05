# agenttrace.semantic/0.3

**Status: EXPERIMENTAL. Not frozen. Not stable.** This version may change without a compatibility guarantee. See [§13 Validation limits](#13-validation-limits).

---

## 1. Purpose and scope

`agenttrace.semantic` is a framework-independent semantic layer over raw agent telemetry. It records:

- what observable content existed in a run;
- which content was actually delivered to which agent;
- what agents observably asserted and believed;
- what was observably verified;
- how content was carried from one piece of evidence to another.

From these stored facts, a separate inference layer derives non-delivery, verification gaps, lineage, persistence and contribution hypotheses.

The motivating failure pattern:

> A requirement exists in configuration → it is never delivered → no agent reasons about it → review and test never check it → incorrect output is accepted.

### Scope constraints

- **Framework-independent core.** The core contains no framework or benchmark concepts: no phase or role enums, no framework completion markers (for example ChatDev's `<INFO> Finished`), and no MAST failure codes. Framework details live in adapters and in `raw_ref`.
- **Raw is separate from inference.** Raw telemetry is never modified. Every semantic object points back to it.
- **Only observable content.** Nothing is derived from hidden reasoning.

### Relation to raw telemetry

Raw telemetry (for example runs declared as `assetopsbench.deepagent.instrumented/0.1`, or MAST/ChatDev logs) is input to this layer. It is not part of this schema.

---

## 2. Experimental status

- This document is the first written specification. Version 0.2 was never written down. 0.3 was derived by reconstructing 0.2's concepts and validating them against four gaps.
- **No 0.2 field list survives.** This document lists only fields that validation exercised. No other 0.2 field carries over by default.
- The schema is justified mainly by one real trace (§14) plus framework-independent thought experiments. It is **not proven complete** and **must not be frozen** until the validation in §13 is done.

Status labels used in this document:

| Label | Meaning |
|---|---|
| EXISTING FROM 0.2 | Concept present in reconstructed 0.2, meaning unchanged |
| NEW IN 0.3 | Added by validation |
| CLARIFIED IN 0.3 | Present in 0.2, meaning now made precise |
| REMOVED FROM 0.3 | Present in 0.2, absent from 0.3 |
| INFERRED ONLY | Derived by the inference layer, never stored |
| DEFERRED | Consciously postponed until a real trace requires it |
| required by validation; presence in 0.2 unconfirmed | A field that validation showed to be necessary. 0.2 was never written down, so whether 0.2 had this field cannot be confirmed |

Object-level and relation-level continuity with 0.2 is claimed only where the reconstructed 0.2 handoff names the concept explicitly (the object list in §3 and the relation names in §5). No field-level continuity is claimed. Two 0.2 principles do constrain fields: every inferred object keeps provenance (`raw_ref`), and states take `TRUE | FALSE | UNKNOWN | UNCERTAIN`. They are noted where they apply.

---

## 3. Stored object model

0.3 stores eight object collections:

| Object | Status |
|---|---|
| `run` | EXISTING FROM 0.2 (`outputs` NEW IN 0.3) |
| `entities` | EXISTING FROM 0.2 (kinds CLARIFIED IN 0.3) |
| `events` | EXISTING FROM 0.2 (CLARIFIED IN 0.3) |
| `evidence` | EXISTING FROM 0.2 (CLARIFIED IN 0.3; `produced_by` NEW IN 0.3) |
| `claims` | EXISTING FROM 0.2 (CLARIFIED IN 0.3) |
| `propositions` | EXISTING FROM 0.2 (CLARIFIED IN 0.3) |
| `states` | EXISTING FROM 0.2 (CLARIFIED IN 0.3) |
| `links` | EXISTING FROM 0.2 (relation set changed) |

`segments` is **REMOVED FROM 0.3** (§6).

Every stored object that is itself inferred from raw data (claims, propositions, states, links) carries a `raw_ref` that leads back to raw telemetry.

---

## 4. Stored fields and their semantics

### 4.1 `run`

| Field | Status | Semantics |
|---|---|---|
| `id` | required by validation; presence in 0.2 unconfirmed | Run identifier |
| `raw_ref` | required by validation; presence in 0.2 unconfirmed | The raw telemetry source and its declared raw schema |
| `outputs` | **NEW IN 0.3** | List of entries `{evidence, raw_ref}` naming the run's final product items |

Rules for `outputs`:

- Entries are set **only** from the framework's own raw product markers. They are **never** derived from event order. (For example, the last item to appear is not assumed to be the product.)
- Each entry's `raw_ref` points to the product marker.
- If a marked product never appears in the trace, the entry's `evidence` is `UNKNOWN`.

### 4.2 `entities`

| Field | Status | Semantics |
|---|---|---|
| `id` | required by validation; presence in 0.2 unconfirmed | Entity identity |
| `kind` | required by validation; presence in 0.2 unconfirmed | `agent \| tool \| service \| framework \| environment` |
| `role` (agents only) | required by validation; presence in 0.2 unconfirmed | Free text taken from raw data. An attribute, not an identity. Never an enum |
| `model` (agents only) | required by validation; presence in 0.2 unconfirmed | Free text taken from raw data. An attribute, not an identity |
| `raw_ref` | required by validation; presence in 0.2 unconfirmed | Provenance |

Rules:

- Agent identity is distinct from role, model, tool and service.
- Whether separate framework instances count as one agent is an adapter decision. It is recorded in `raw_ref`, not in the core.
- `user` and `benchmark` as entity kinds are **DEFERRED**. In 0.3 they appear only as evidence `source` values.

### 4.3 `events`

An event is an **observable, atomic unit with an input and an output**.

| Field | Status | Semantics |
|---|---|---|
| `id` | required by validation; presence in 0.2 unconfirmed | Event identity |
| `origin` | required by validation; presence in 0.2 unconfirmed | Zero or one entity, of any kind. Events need not originate with an agent |
| `order` | required by validation; presence in 0.2 unconfirmed | Temporal order. Partial order for parallel events is DEFERRED |
| `raw_ref` | required by validation; presence in 0.2 unconfirmed | Provenance |

There is **no** event `type` field and **no** phase field. Two terms are definitions, not stored types:

- **Agent-input event:** an event whose `origin` is an agent. Its input is the actual rendered model input.
- **Verification event:** any event that is the source of a `checks` link.

### 4.4 `evidence`

Evidence is **observable content in the trace, independent of any role**. Examples: messages, code, files, config values, tool results, retrieved chunks, reports, task briefs, final answers.

- Evidence does **not** intrinsically mean "supports a proposition". Support and contradiction exist only through `supported_by` / `contradicted_by` links.
- **Granularity:** an evidence item is a unit that can be produced and delivered on its own (a file, a message, a tool result, a config value). A whole rendered prompt is not one item.

| Field | Status | Semantics |
|---|---|---|
| `id` | required by validation; presence in 0.2 unconfirmed | Evidence identity |
| `source` | required by validation; presence in 0.2 unconfirmed | Author class: `user \| agent \| tool \| service \| framework \| environment \| benchmark`. Identifies who authored the content. It does **not** decide whether the evidence is testimonial (§7) |
| `produced_by` | **NEW IN 0.3** | The event in whose output the item first observably occurs |
| `raw_ref` | required by validation; presence in 0.2 unconfirmed | That first output occurrence, or the external location if there is no producing event |

Rules:

- **`produced_by` is single-valued.** It is not a link, because each item has exactly one producer. It is not derived from where text appears, because the same content appears in many places.
- **It is about production, not authorship.** `source` and `produced_by` may differ on purpose. For example, if a user task first appears in a framework log line, then it is `source: user`, and its `produced_by` is the framework event whose output contains that log line. (This is a conditional illustration of the rule. It does not establish the producer of any particular item, including the Gomoku Task in §14.)
- **Other occurrences** of the item (for example copies inside later prompts) are reached through `delivers`, not through `produced_by`.
- **Identity is per production, not per content.** Re-emitting identical content creates a new evidence item. It is connected to the earlier item by `propagates_to` when the conditions of §5.3 hold.
- **External evidence.** `produced_by` is absent whenever no event in the trace outputs the item (for example benchmark ground truth). Such evidence may still be delivered.
- **The value `verifier` is REMOVED** from the source list. It was a role, which the core forbids.

### 4.5 `claims`

A claim is **an assertion extracted from a span of exactly one evidence item**, using only observable text.

| Field | Status | Semantics |
|---|---|---|
| `id` | required by validation; presence in 0.2 unconfirmed | Claim identity |
| `evidence` | required by validation; presence in 0.2 unconfirmed | Exactly one evidence item |
| `raw_ref` | required by validation; presence in 0.2 unconfirmed | The span inside that evidence item |
| `proposition` | required by validation; presence in 0.2 unconfirmed | The proposition the claim asserts |

Rules:

- **Every assertion is extracted as a claim**, whatever the evidence's `source`. A claim is the representation of testimony (§7).
- **Claims are not delivery targets.** Whether a claim reached an event is inferred from delivery of its evidence (§10, claim delivery).
- **Claims have no `produced_by`.** They inherit production from their evidence.
- **The speaker is derived, not stored.** It is the `origin` of the evidence's producing event when `source = agent`, and otherwise the `source` class.
- **Negation** is expressed in the proposition's logical form (a claim that not-P asserts the proposition ¬P).
- **Hedging is not a claim field.** It shows up only as the holder state's value `UNCERTAIN` (§8).
- How claims represent stance (negation, hedging) has **not been exercised by a real trace**.

### 4.6 `propositions`

| Field | Status | Semantics |
|---|---|---|
| `id` | required by validation; presence in 0.2 unconfirmed | Proposition identity |
| `form` | required by validation; presence in 0.2 unconfirmed | Canonical logical form |

Rules:

- Propositions are canonical and **independent of any holder**.
- Requirements are recorded in logical form. For conditional or alternative requirements, the proposition is the compound itself.
- **A logical form may take evidence items as arguments.** For example, G(v1) = "v1 presents a GUI". This is how truth relative to an artifact is expressed (§9). The form shows when two propositions apply the same predicate to different items, for example G(v1) and G(v2).

### 4.7 `states`

A state is **a holder's observable stance on one proposition at one event** (§8).

| Field | Status | Semantics |
|---|---|---|
| `proposition` | required by validation; presence in 0.2 unconfirmed | The proposition the stance is about |
| `value` | required by validation; presence in 0.2 unconfirmed | `TRUE \| FALSE \| UNKNOWN \| UNCERTAIN`. The value set itself is stated in reconstructed 0.2 |
| `claims` | required by validation; presence in 0.2 unconfirmed | One or more grounding claims |

Derived, not stored:

- **holder:** the shared speaker of the grounding claims. It must be an entity.
- **event:** the shared `produced_by` event of the grounding claims' evidence.

All grounding claims of one state must share one speaker and one producing event.

### 4.8 `links`

| Field | Status | Semantics |
|---|---|---|
| `relation` | required by validation; presence in 0.2 unconfirmed | One of the relations in §5 |
| `source` | required by validation; presence in 0.2 unconfirmed | Source endpoint |
| `target` | required by validation; presence in 0.2 unconfirmed | Target endpoint |
| `raw_ref` | required by validation; presence in 0.2 unconfirmed | Provenance. Specific requirements per relation in §5 |

---

## 5. Relation definitions

| Relation | Status | Endpoints |
|---|---|---|
| `delivers` | NEW IN 0.3 | agent-input event → evidence |
| `checks` | NEW IN 0.3 | event → proposition |
| `propagates_to` | CLARIFIED IN 0.3 (named in 0.2, first defined here) | evidence → evidence |
| `depends_on` | CLARIFIED IN 0.3 | proposition → proposition |
| `supported_by` | CLARIFIED IN 0.3 | proposition → evidence |
| `contradicted_by` | CLARIFIED IN 0.3 | proposition → evidence |

No other relation exists in 0.3.

### 5.1 `delivers`

**`delivers(E, X)`** holds iff the **actual rendered input** of agent-input event E contains an occurrence of evidence item X.

- The target is **evidence only**. Claims are never targets. A claim is delivered only by containment, which is inferred (§10).
- **Config, templates and placeholders never count as delivery.** Only the actual rendered input does.
- **Delivered does not mean attended to.** Uptake shows only through claims and states.
- Positive delivery is observed directly. Non-delivery is never stored. It is inferred only under established coverage (§10).

### 5.2 `checks`

**`checks(V, P)`** holds iff the observable output or execution of event V evaluates proposition P.

- **Any event may be the source** if its observable behaviour evaluates the proposition. "Verification event" is only a name for such an event.
- **The target** is the proposition actually evaluated (for example "test i passes" or one specific assertion), not a general requirement.
- **What can ground a `checks` link:**
  - explicit evaluator text;
  - executed checks whose meaning is visible;
  - a framework procedure whose fixed meaning appears in the trace.
- **What can never ground a `checks` link:**
  - the instruction itself;
  - a bare verdict (for example "Pass" or "Finished");
  - evidence that merely bears on the proposition.
- The check's **result** is a claim, or evidence produced by the same event.
- The **artifact version** under evaluation is the artifact evidence delivered to V.
- The **verification scope** of V is the set of its `checks` links. A bare verdict gives **UNKNOWN** scope, which is different from an **empty** scope.

### 5.3 `propagates_to`

**`A propagates_to B`** holds iff all of the following are true:

1. **Production:** `B.produced_by = E`.
2. **Exposure:** `delivers(E, A)`.
3. **Carryover:** there is a non-empty set S of spans in B, each of which reproduces content of A, either verbatim, near-verbatim, or as a restatement of A's specific details.
4. **Specificity:** every span in S is specific to A:
   - **(a) Not generic.** Boilerplate that E's task would produce anyway does not count.
   - **(b) Tie rule.** If another item A′ delivered to E contains the same content:
     - if A′ comes after A in A's own `propagates_to` lineage, the span goes to A′ only (the nearest copy wins);
     - if A′ is independent of A, the span supports no link at all, because its source is ambiguous.

**Provenance:** the link's `raw_ref` names S in B and the matching spans in A.

**Meaning:** **content lineage only.** It means B's content was derived from A, and nothing more.

- It does **not** mean causal contribution.
- It does **not** mean semantic equivalence. A carried span may be reused with a different meaning or truth value.
- It does **not** mean failure or defect persistence. Those are inferred (§10).

**Never sufficient on their own:** timing, names, roles, framework labels, size counters.

Further rules:

- **Endpoints:** evidence → evidence only.
- **A and B have different producers, by definition.** A is part of E's input and B first occurs in E's output, so A cannot have been produced by E. If A has a producing event, that event precedes E.
- **Identical re-emission:** if the earlier item was delivered to the event that produced the new copy, `propagates_to` holds.
- **Substantial change:** the link still holds as long as at least one specific carried span exists. There is **no similarity threshold**. If no specific content was carried, there is no link, even when B serves the same purpose or has the same name.
- **Chains** are composed by inference and never stored.
- **The tie rule is well-founded.** It relies only on links whose events come earlier in order.
- **Known limit:** because `delivers` must start at an agent-input event, lineage cannot pass through events that aren't agent inputs, such as a tool writing a file that another tool reads (§12).

### 5.4 `depends_on`

**`A depends_on B`** holds iff proposition A cannot be TRUE unless proposition B is TRUE.

- It expresses **logical necessity only**: not causal, not evidential, not specific to a holder, and not a scope relation.
- It is **not** used to express obligation.
- No inference rule in 0.3 requires it, and no real trace has exercised it. Possible future use (**DEFERRED**): deciding whether a check discharges an obligation (for example, whether checking "is a tkinter window" covers "has a GUI").

### 5.5 `supported_by`

**`P supported_by X`** holds iff the observable content of evidence X **directly** bears in favour of proposition P being TRUE.

- **Endpoints:** proposition → evidence only.
- **Direct bearing only.** The content is, or records, what P is about (§7). Bearing through assertion is represented by claims, never by this link.
- **Provenance:** `raw_ref` names the grounding spans. When grounding rests on absence (§9), it names the whole item.
- The link says nothing about delivery to anyone, and nothing about any holder.
- **Span constraint:** the grounding spans must not be a claim span that asserts P or ¬P.
- **No relation between propositions.** Evidential bearing between two propositions is never stored (§7.4).

### 5.6 `contradicted_by`

**`P contradicted_by X`** holds iff the observable content of evidence X **directly** bears against proposition P being TRUE.

Same endpoint, direct-bearing, provenance and span-constraint rules as `supported_by`.

---

## 6. Not in 0.3

| Concept | Status | Reason |
|---|---|---|
| `segments` | REMOVED FROM 0.3 | Never defined. No inference in any validated gap requires grouping events. An undefined object would invite adapters to fill it with framework phases. It is not kept as a reserved name |
| `revises` | REMOVED FROM 0.3 (DEFERRED) | Never defined or validated. Must not be used for artifact versions (that is `propagates_to`). May be needed later for belief revision |
| `conflicts_with` | REMOVED FROM 0.3 (DEFERRED) | Never defined or validated. In the Gomoku trace (§14), the conflict between the R2 verdict "Finished" and R3's defect report could not be asserted, because a bare verdict has UNKNOWN scope |

Any of these may come back only with a formal definition that a real trace has justified.

---

## 7. Direct vs testimonial evidence

### 7.1 Two ways evidence bears on a proposition

| How the evidence bears on P | Kind | Represented by | Examples |
|---|---|---|---|
| The content is, or records, what P is about | **Direct** | `supported_by` / `contradicted_by` | tool output `row_count = 42`; code v1 for G(v1); "test_login PASSED" for passes(test_login) |
| Someone asserts P | **Testimonial** | a claim | an agent's report; a retrieved document stating a fact; a reviewer's comment |

`source` does **not** decide which kind applies:

- **Agent-authored code** is direct evidence about itself.
- **A retrieved document** returned by a tool is testimony.

`source` identifies **the testifier**: an agent in the run, a user, a document, a benchmark.

### 7.2 The testimony rule

1. Every assertion is extracted as a claim, regardless of source.
2. The claim is the testimonial evidence.
3. `supported_by` / `contradicted_by` represent direct bearing only.
4. Agent-authored evidence may be direct evidence when its content is itself the object or record being evaluated (for example code, structured output, files).
5. Assertion spans are not duplicated as direct support links.
6. Direct and testimonial assessments remain separate (§9).
7. When judging holder H, H's own claims are excluded.
8. Testimony is deduplicated by testifier and by lineage. Relayed or repeated testimony counts once.
9. `source` identifies the testifier, not whether the evidence is testimonial.

### 7.3 Delivery of testimony

When one agent receives another agent's assertion, two things are recorded:

- `delivers` of the containing evidence;
- claim delivery by containment, which is inferred.

If the receiving agent restates the assertion, the restatement is its own claim and state. Its evidence normally `propagates_to` from the original, so it is not independent corroboration.

### 7.4 Reasoning from one proposition to another

- **Logical necessity** uses `depends_on`, and only then.
- **Evidential bearing between propositions is never stored.** If an evidence item observably bears on both propositions, each gets its own direct link to that item. Otherwise any bridge between them is inference.

Example (test_login):

- Evidence E: the test output, `produced_by` test-run event T.
- Stored:
  - P_test = passes(test_login);
  - P_test `supported_by` E, with `raw_ref` = the "test_login … PASSED" span;
  - `checks(T, P_test)`;
  - P_req as a proposition, only if it appears as a requirement in some evidence item.
- Not stored:
  - any link between P_test and P_req;
  - P_req `supported_by` E, unless E's content observably concerns the required login behaviour.
- Whether passing test_login satisfies P_req is inference. Discharge is DEFERRED.

---

## 8. State semantics

- **Specific to a holder.** Every state has a holder, which is an entity. Artifacts and evidence items are **never** state anchors.
- **Anchored to an event through claims.** The anchor (holder, event) is derived from the grounding claims (§4.7).
- **No hidden beliefs:**
  - every state requires at least one claim by its holder;
  - silence never produces a state;
  - a belief is **never carried forward** to later events. A holder's belief at an event where it made no claim is not stored. If needed, it is inferred and is UNKNOWN unless grounded again.
- **Value meanings:**

| Value | Meaning |
|---|---|
| `TRUE` / `FALSE` | The holder's text takes that stance |
| `UNCERTAIN` | The holder's text hedges (for example "I think…") |
| `UNKNOWN` | Stored only when the holder's own text says it does not know |

- **Never stored as states:** diagnoses, obligations, verification gaps, persistence, contribution, or any other inference result.
- **Users cannot hold states in 0.3**, because `user` is not an entity kind (DEFERRED).

---

## 9. Truth relative to an artifact (assessment)

A statement such as "the GUI requirement is false of v1" is **not** a state. It is represented as:

1. a proposition that names the item, for example G(v1) = "v1 presents a GUI";
2. direct links from that proposition to evidence, for example G(v1) `contradicted_by` v1.

The truth value is **inferred** as an assessment in two separate parts.

**Direct assessment** (from `supported_by` / `contradicted_by`):

| Links present | Direct assessment |
|---|---|
| only `supported_by` | TRUE |
| only `contradicted_by` | FALSE |
| both | UNCERTAIN |
| neither | UNKNOWN |

**Testimonial assessment** (from claims):

- Inputs: claims on P or ¬P.
- **PROVISIONAL** (§12): also counting claims on propositions that imply P through `depends_on` is a generalization, not established by validation.
- Testimony is counted per testifier after lineage deduplication.
- When the assessment is used to judge holder H, H's own claims are excluded.

The two assessments are **never merged**. A consumer may fall back to testimony when the direct assessment is UNKNOWN, but the result is labelled testimonial.

### Span-grounded vs absence-grounded

| Grounding | `raw_ref` names | Example |
|---|---|---|
| Span-grounded | specific spans | a wrong value `$900` in an answer |
| Absence-grounded | the whole item that was searched | no GUI library or window code anywhere in v1 |

### Applying requirements to items

A requirement is usually stated about "the product". Applying it to a specific item (G(v_k)) is **inference**:

- for an evaluator, the item is the artifact delivered to it;
- for the final product, the item is the corresponding entry in `run.outputs`.

---

## 10. Inference layer (INFERRED ONLY, never stored)

Every inference result keeps provenance back to raw telemetry, including the basis for coverage. None of these concepts may be turned into a stored object, field or link.

### 10.1 Exposure

| Inference | Inputs | Output and values | Required condition |
|---|---|---|---|
| **Coverage established(E)** | Raw reconstruction of E's input: rendered messages, tokenization with the model's tokenizer compared to logged token counts, memory flags, turn limits, template slots, placeholder keys | established / not established. The basis goes into inference provenance, not the schema | Stable reconstruction residual across all calls |
| **Non-delivery(E, X)** | E's `delivers` links; X's content | TRUE / UNKNOWN (delivery itself is the stored `delivers`) | Coverage of E established. Otherwise UNKNOWN |
| **Claim delivery(E, C)** | `delivers(E, C.evidence)`; C's span is present in the delivered occurrence | TRUE / FALSE (only under coverage) / UNKNOWN | Same as delivery of its evidence |

Exposure ladder:

1. Exists (evidence).
2. Available to an agent (**DEFERRED**).
3. Delivered (`delivers`).
4. Claimed or believed (claims, states).

### 10.2 Verification

| Inference | Inputs | Output and values | Required condition |
|---|---|---|---|
| **Verification scope(V)** | V's `checks` links | a set of propositions, possibly empty / UNKNOWN for a bare verdict | V's evaluation is observable |
| **Instruction scope** | Grounded readings of instruction text delivered to V | one set of propositions per supported reading / UNKNOWN | A textual hook is required (see below) |
| **Obligated(V, P)** | Instruction scope across supported readings | see table below | — |
| **Unverified(V, P)** | Obligated(V, P), `checks`, `delivers`, implication | takes the obligation's state: TRUE / UNCERTAIN; otherwise UNKNOWN | see clauses (a) and (b) below |

**Instruction scope grounding rules:**

- An instruction denotes the propositions it asks to be **evaluated**. That is a duty to evaluate, not a duty for the proposition to be true.
- **The text fixes which set is meant; facts in the run fix what is in that set.** A member may therefore be a requirement the evaluator never received.
- Readings with no textual hook (for example "what the designers probably meant") are forbidden.
- A definite description resolves first to an antecedent in the delivered text.
- Open-ended instructions such as "review the code" denote no set that can be listed, so they create no obligation.

**Obligated(V, P):**

| Membership of P across supported readings | Obligated |
|---|---|
| In scope under every reading | TRUE |
| In scope under some readings, out under others | UNCERTAIN |
| Out of scope under every reading | absent (**not** FALSE) |
| Membership itself unresolved | UNKNOWN |

**Unverified(V, P)** is inferred when P is obligated, there is no observable `checks(V, P)`, and either:

- **(a)** V's evaluation is fully observable; or
- **(b)** P was not delivered to V under established coverage, **and** P is not implied by V's delivered content.

Otherwise the result is UNKNOWN. "Implied by" is an informal judgment, recorded with provenance; its formal account is DEFERRED.

### 10.3 Lineage and persistence

| Inference | Inputs | Output and values | Required condition |
|---|---|---|---|
| **Lineage(A, B)** | Chains of `propagates_to` | holds / not established | Positive links only |
| **Claim carryover(C_A, C_B)** | `A propagates_to B`; claim spans | holds / not established | C_B's span is in S and matches C_A's span |
| **Persisted(P, A→B)** | `A propagates_to B`; direct assessment and grounding of P(A) and P(B) | holds / does not hold / UNKNOWN if either assessment is UNKNOWN | Both FALSE; P(B)'s grounding spans are in S and match P(A)'s grounding spans. **Span-grounded only** |
| **Reintroduced(P, A→B)** | same | same | P(B) is FALSE, grounded by new spans that were not carried |
| **Fixed(P, A→B)** | same | same | P(A) is FALSE and P(B) is TRUE |

For absence-grounded FALSE, persistence is **undefined**: missing content has no spans to carry. Each producing event then explains the absence on its own, through Unexposed or Delivered-but-not-acted-on.

### 10.4 Contribution hypotheses

| Inference | Inputs | Output and values | Required condition |
|---|---|---|---|
| **Unexposed(E, X, P)** | `produced_by`, `delivers`, assessment, implication | contribution hypothesis: TRUE / UNKNOWN | Event E produced B and the assessment of P(B) is wrong; X bears on P; X was not delivered to E under established coverage; E's delivered content does not imply X |
| **Delivered-but-not-acted-on(E, X, P)** | `delivers(E, X)`; P(B) wrong for B produced by E | contribution hypothesis: TRUE / UNKNOWN | **PROVISIONAL** (§12): the condition "E's evaluation is observable" is a generalization, not established by validation |
| **Gate-miss(V, P)** | Unverified(V, P); `delivers`; lineage; `run.outputs` | takes the obligation's state: TRUE / UNCERTAIN; otherwise UNKNOWN | Unverified(V, P) holds; V received evidence A with P(A) FALSE; A's lineage reaches an item in `run.outputs` with P still FALSE |
| **Contribution grade** | the hypotheses above + contrast evidence | hypothesized → supported contribution. A grade, not a state value | Ceiling is **supported contribution**, never sufficient or deterministic cause |

Notes:

- **"X bears on P"** in Unexposed means one of three things:
  - a direct link between P and X;
  - a claim in X on P;
  - **PROVISIONAL** (§12): a claim in X on a proposition that implies P. This is the same implication-based testimony extension that is provisional in §9, and the current validation set does not establish it.
  X can be a requirement for P or evidence for P's correct value.
- **Unexposed applies to producing events and evaluating events alike.**
- **Gate-miss is a combination of existing rules, not a new rule.**
- **What raises support (contrast or counterfactual evidence):**
  - the same agent honouring requirements it did receive;
  - delivered comments being acted on;
  - explicit agent text;
  - replays or sibling runs.
  It never raises support above "supported contribution".

### 10.5 Repetition and workflow structure

| Inference | Inputs | Output and values | Required condition |
|---|---|---|---|
| **InputEquivalent(E1, E2)** | `delivers` sets of both events | TRUE / FALSE / UNKNOWN | Item-by-item content equality (items may be different productions); coverage of both inputs |
| **Reiteration(E1, E2)** | `order`; delivered instruction content; lineage of the work objects | TRUE / FALSE / UNKNOWN | E1 precedes E2; the instruction evidence delivered to each has equal content once the work objects are excluded; the work objects are the same item or share `propagates_to` lineage. **No requirement that both events have the same origin** |
| **UnchangedReemission(A, B)** | `propagates_to`; content | TRUE / FALSE | `A propagates_to B` and B's content equals A's |
| **Refinement(A, B)** | `propagates_to`; content; optional feedback F | TRUE / FALSE; driven by feedback if F `propagates_to` B through the changed spans | `A propagates_to B` and B differs from A |
| **Unprompted change(A, B)** | changed spans in B; E's `delivers` | TRUE / UNKNOWN | No delivered item accounts for the changed spans; coverage of E's input |

Structure vs diagnosis:

- "The same step ran three times" is observable structure, given by the inferences above.
- "This repetition was unnecessary or pathological" is a diagnosis. It needs a counterfactual and is never stored.
- Benchmark labels (for example MAST 1.3) may come in only as `benchmark`-source evidence, never as core concepts.

---

## 11. Provenance and observability rules

1. Every stored object that is itself inferred (claims, propositions, states, links), and every inference result, keeps provenance back to raw telemetry.
2. Delivery is decided only by the actual rendered input.
3. Config, templates, placeholders and other merely available content never count as delivery. Availability is DEFERRED.
4. Absence (non-delivery, unprompted change, input equivalence) can be inferred only when input coverage is established. Otherwise the answer is UNKNOWN.
5. Delivered does not mean attended to. Uptake shows only through claims and states.
6. Claims come only from observable text, never from hidden reasoning.
7. Verification counts only when it is observable. A bare verdict gives UNKNOWN scope, which is not an empty scope.
8. Scope readings need a textual hook. The text fixes which set is meant; facts in the run fix what is in that set.
9. Framework labels stay in `raw_ref` and are never semantic structure. This covers phase and step names, cycle and iteration indices, completion markers and role names.
10. Product identity comes from framework product markers, never from event order.
11. Timing, names, roles, labels and counters never establish lineage or causation on their own.
12. Causal conclusions are at most "supported contribution", produced only by inference. Nothing causal is stored.
13. Testimony is represented by claims. Direct bearing is represented by links. The two are never merged (§7).

---

## 12. Deferred concepts and known limits

**DEFERRED (not in 0.3):**

- partial delivery;
- availability or access relations;
- explicit omission or failure nodes; modelling non-delivery as an event;
- obligation objects or an `obligates` link; a `requires_verification` property;
- an `intended_for_agent` field;
- a verification event type or verifier entity kind; per-check result fields; verification-target fields;
- stored verification scope or a stored `scopes` relation;
- storing audit or open-ended instruction scope (revisit only if inference proves unreliable);
- coverage metadata or a coverage-basis field; verification-coverage metadata;
- delivery status labels; `via` or orchestrator fields;
- causal edges (`causes`, `enables`, `contributes_to`);
- acceptance, gate or phase objects;
- strength or confidence fields on links;
- stored counterfactuals; stored transitive closure; a materialized Unverified list;
- propagation between propositions, states or events;
- lineage through dataflow that isn't agent input (tool → file → tool), including call-ID correlation for parallel tool calls;
- hierarchy and nested runs;
- partial ordering of events (parallel branches);
- `segments`;
- workflow phases, cycles, loops, iteration numbers, parent steps, `repeats`, `same_objective_as`;
- `revises` and `conflicts_with`;
- `user` and `benchmark` as entity kinds;
- a formal account of "implies" (used informally in Unverified (b) and Unexposed);
- check discharge of obligations (possible future use of `depends_on`);
- MAST-specific concepts, including direct encoding of MAST codes.

**PROVISIONAL (plausible inference extensions, not established by the current validation set):**

- **Delivered-but-not-acted-on requiring "E's evaluation is observable" (§10.4).** The condition comes from the budget thought experiment, where it applied to the supervisor's Unverified clause (a). Making it the general condition for this hypothesis was a generalization made while drafting. No real trace has tested it.
- **Testimonial assessment counting claims that imply P through `depends_on` (§9).** This extends testimony from claims on P to claims on stronger propositions. No real trace has tested it, and `depends_on` itself is unexercised.
- **Unexposed counting "a claim in X on a proposition that implies P" as bearing on P (§10.4).** This is the same implication-based extension, applied to the "X bears on P" condition. No real trace has tested it.

None of these may be relied on as a locked rule until a trace establishes it.

**Known limits:**

- `propagates_to` cannot cross events that aren't agent inputs.
- `depends_on` is defined, but no established rule uses it and no real trace has exercised it.
- How claims represent stance (negation in the logical form, hedging as an UNCERTAIN state) has not been exercised by a real trace.
- The coverage method (tokenizer residuals) depends on the model and the adapter. It belongs in adapters and inference provenance, not in the core.

---

## 13. Validation limits

This candidate is justified mainly by **one real trace**: the MAST/ChatDev Gomoku trace (§14). The rest comes from framework-independent thought experiments:

- a supervisor drops a budget constraint;
- a RAG answer goes wrong after the decisive document is truncated;
- a tool call is retried after errors;
- a planner/executor/reviewer loop;
- the verification test set: unit tests, fact-checking, a bare LLM-judge PASS, "satisfy all requirements", "factual correctness", mandatory, conditional, alternative and optional requirements, "run the test suite", "audit optional features";
- the testimony examples A–E.

**The schema is not proven complete.** Future traces should challenge it with:

- genuine multi-agent delegation;
- conflicting instructions;
- partial delivery and truncation;
- parallel branches;
- merged outputs;
- information flowing through tools (file write/read, shared memory stores);
- shared artifacts edited by several agents;
- retractions and revisions of beliefs (this tests the removal of `revises` and `conflicts_with`);
- implicit requirements;
- ambiguous provenance (one content, several possible producers);
- nested sub-agent runs;
- frameworks other than ChatDev.

**Minimum before freezing:** each of the following must be representable with no core change, or must justify a specific change:

- at least one trace from a framework other than ChatDev that uses tools (for example the AssetOpsBench deepagent runs in this repository);
- one trace with genuine delegation;
- one with parallel branches or merged outputs;
- one with information flowing through tools;
- one with belief revision or retraction.

---

## 14. Worked example: the Gomoku trace

**Source:** `data/mast/MAD_full_dataset.json`, list index `[7]`.

| Property | Value |
|---|---|
| `mas_name` | ChatDev |
| benchmark | ProgramDev |
| `llm` | GPT-4o |
| `trace_id` | 7 |
| MAST annotations | 1.3 = 1, 3.2 = 1 |

Line numbers refer to `trace.trajectory` split on `\n`, 1-indexed (3395 lines). The log says `model_type GPT_45`; both GPT_45 and GPT-4o use the o200k tokenizer.

### 14.1 The requirement and the config

| Line | Content |
|---|---|
| L21 | `with_memory: False` |
| L23 | `gui_design: True` |
| L240 | The Coding `phase_prompt` has no `{gui}` slot |
| L244 | `chat_turn_limit: 1` |
| L245 | The Coding placeholders include the `gui` sentence |
| L13, L236 | The user task contains no GUI requirement |

A whole-word search for `gui`, `graphical`, `tkinter` and `pygame` hits only L245, plus the `gui_design` key at L23.

### 14.2 Events and coverage

Coverage method: reconstruct the system and user messages, tokenize with o200k, add the chat overhead (3 tokens per message × 2, plus 3), and compare with the logged `prompt_tokens`.

- The o200k residual is a constant **+2** on all 12 LLM calls. That is a format quirk, so coverage is **COMPLETE**.
- The cl100k residual drifts (−1 to −18), which signals a tokenizer mismatch.
- Corroborated by the memory flags, the chat-turn limit, the template slots and the placeholder keys.

| Event | Call / messages | Reported tokens | o200k count |
|---|---|---|---|
| Coding (produces v1) | messages L265–310 | 561 (L314) | 550 + 9 = 559 |
| R1 (cycle 1 review) | Start Chat L734; messages L736–833 | 1133 (L838) | 1122 + 9 = 1131 |
| M1 (cycle 1 modification, produces v2) | call L899 | +2 residual | — |
| R2 (cycle 2 review) | Start Chat L1306; messages L1308–1405 | 1150 (L1410) | 1139 + 9 = 1148 |
| M2 (cycle 2 modification, produces v3) | call L1471 | +2 residual | — |
| R3 (cycle 3 review) | Start Chat L1846; messages L1848–1945 | 1150 (L1950) | 1139 + 9 = 1148 |
| M3 (cycle 3 modification, produces v4) | call L2051 | +2 residual | — |
| Test gate (TestErrorSummary) | L2457–2468; no LLM call | — | — |

Supporting evidence for the review events:

- The cycles start at L698, L1270 and L1810.
- The review rules are at L826–833, L1403–1404 and L1943–1944.
- The template slots are task, modality, language, ideas, codes and `assistant_role` (L709, L1281, L1821).
- There is no `gui` key in any placeholder set (L714, L1286, L1826, and the modification calls).
- "No existed memory" appears twice per cycle (L715/729, L1287/1301, L1827/1841).
- Each cycle makes one call with a "turn 0" reply (L845, L1417, L1957).

### 14.3 Stored objects (illustrative)

**Evidence:**

| Item | `source` | `produced_by` | Notes |
|---|---|---|---|
| config `gui_design: True` (L23) and the `gui` placeholder sentence (L245) | framework | UNRESOLVED (not validated) | never delivered |
| Task (L13) | user | UNRESOLVED (not validated) | delivered to Coding, R1–R3 and M1–M3 |
| v1 | agent | Coding reply | console loop L415 |
| v2 | agent | M1 reply | console loop L1086 |
| v3 | agent | M2 reply | console loop L1658 |
| v4 | agent | M3 reply | console loop L2260; conclusion L2280 |
| R1 verdict `<INFO> Finished` (L853–858) | agent | R1 | bare verdict |
| R2 verdict `<INFO> Finished` (L1425–1430) | agent | R2 | bare verdict |
| R3 comment (L1965ff, conclusion L1988ff) | agent | R3 | invalid moves don't tell the user why |
| Test report (L2462 "The software run successfully without errors.", L2468 "Test Pass!") | UNRESOLVED (framework or environment; not validated) | test gate event | — |
| manual.md (L2881–L3351), requirements.txt | not examined | not examined | in `run.outputs` |

The `source` and `produced_by` values marked UNRESOLVED were not established during validation. They are left unresolved rather than guessed.

The copies of the code delivered to the reviewers (L806, L1378, L1918) and to the test input (L2586) are occurrences reached through `delivers`, not new items.

**`run.outputs`:**

- v4, `manual.md` and `requirements.txt`.
- Markers: the WareHouse path at L17 and L3390; Post Info at L3354–3384 (`version_updates=5.0`, `num_code_files=2`, `code_lines=71`, `manual_lines=85`). The run ends at L3388.
- v4 is identified by corroboration (there is no later code-producing event, and the line counter matches), not by a byte-level match.
- The manual comes after the code, so the product cannot be identified as "the last item".

**`delivers`:**

- Task → Coding (L275), R1 (L742–743), R2 (L1315), R3 (L1855), M1 (L908), M2 (L1480), M3 (L2060). Each line is inside the event's actual rendered input. The phase-config and RolePlaying log tables (for example L1442, L1464) also show the task, but they are config/log content and **never** prove delivery.
- v1 → R1 and M1 (for example L919 inside the M1 call).
- v2 → R2 (code block L1319–1397) and M2 (code block L1484–1562).
- v3 → R3 (code block L1859–1937) and M3 (code block L2064–2142).
- Each code block is inside the event's actual rendered input. The M2 and M3 blocks are line-for-line identical to the R2 and R3 blocks (the only difference is a trailing space after `Codes:`).
- R1's verdict → M1 (`Comments on Codes: " Finished"`, L991–992).
- R2's verdict → M2 (`Comments on Codes: " Finished"`, L1563–1564).
- R3's comment → M3 (`Comments on Codes:`, L2143–2144).
- The GUI config (L23, L245) is delivered to **no** event, with coverage COMPLETE in every case.

**`propagates_to`:**

| Link | Carried content |
|---|---|
| Task → v1 | "typical 15x15 board" restated as `size=15` (L754); the five-in-a-row check (L784) |
| v1 → v2 | most of the code. **v2 changed three `print` strings** (for example "Invalid move. Try again." → "Invalid move. The cell is either occupied or out of bounds. Try again.") |
| v2 → v3 | the whole code, unchanged |
| v3 → v4 | most of the code (69 → 71 lines) |
| R3 comment → v4 | the fix for feedback on rejected moves |

Not asserted:

- **Task → v2/v3/v4:** under the tie rule, "15" goes to the nearer copy v_n.
- **R1/R2 "Finished" → v2/v3:** there is no specific content to carry.
- **GUI config → anything:** it was never delivered.
- **v4 → manual.md:** not examined.

The `code_lines` counter reads 69 at L674, L1251 and L1791, and 71 at L2438, L2851 and L3368. It hid the v1 → v2 change, which shows why counters are insufficient. The reviewer prompt grows from 1133 tokens (R1) to 1150 tokens (R2, R3), which corroborates the longer strings in v2.

**Propositions and direct links:**

- G(v_k) = "v_k presents a GUI", for k = 1..4.
- G(v_k) `contradicted_by` v_k, **absence-grounded**: `raw_ref` names the whole item, because no GUI library or window code appears in it. The console loop supports FALSE but does not settle it.

**`checks`:**

- The test gate checks "runs without errors" only.
- R1 and R2 return bare verdicts, so their scope is UNKNOWN.
- `checks(R3, "v3 adequately reports why a move is invalid")`. This is valid under the locked grounding rule, because R3's output contains explicit evaluator text (L1965ff). **Derived while writing this document**: it is not one of the originally locked validation decisions.

**States:**

- R3 holds FALSE on "v3 adequately reports why a move is invalid", grounded by R3's claims at L1965ff.
- R1 and R2 make no claim on any proposition. "Finished" is a bare verdict.

### 14.4 Inferred results

**Exposure:** the GUI requirement was **NOT DELIVERED** to:

- the producing events: Coding, M1, M2, M3;
- the review events: R1, R2, R3.

Coverage was COMPLETE in every case.

**Instruction scope and obligation:**

- **Rule 5** ("The entire project conforms to the tasks proposed by the user"): its only supported reading points back to `Task: "…"` (L742–743). The GUI obligation is **absent**.
- **Rule 6** ("…without losing any feature in the requirement") has two readings:
  - (i) "requirement" points back to the Task, so GUI is out of scope;
  - (ii) "the requirements in force", so GUI is in scope via L23 and L245.
  The GUI obligation is **UNCERTAIN**.
- "Modality: application" (L744) does not imply GUI.
- **Unverified(R_k, G(v_k)) = UNCERTAIN** for k = 1..3, via clause (b).
- **Test gate:** it evaluated only "runs without errors", so it has no GUI obligation.
- EnvironmentDoc, Reflection and Manual are not verification checks of the product.

**Assessment and lineage:**

- The direct assessment of G(v_k) is FALSE for k = 1..4.
- Lineage Task → v1 → v2 → v3 → v4, and v4 is in `run.outputs`.
- **Persistence is undefined** for G, because its FALSE rests on absence. Each producer explains the absence on its own.

**Contribution:**

- **Unexposed(E, GUI config, G)** holds at Coding, M1, M2 and M3: four separate omissions, not one defect carried forward.
- **Gate-miss(R_k, G) = UNCERTAIN** for k = 1..3: each R_k received v_k with G FALSE, and the lineage reaches v4 with G still FALSE.
- **Contrast evidence** raises Unexposed to **supported contribution**, the ceiling:
  - the delivered requirements were implemented (`size=15` at L754, the five-in-a-row check at L784);
  - R3's comment was carried into v4.

**Shape of the failure:** the same rendering omission (config never rendered into any template) separately hit the producing events and the review events. The paths converge on v4, a fork that converges, not a linear chain. The earlier arrow "console-only code → GUI not delivered to reviewers" was only temporal order and is not part of the analysis.

**Primary confirmed failure:** non-delivery on the framework side.

**Repetition:**

| Cycle | Reviewer input | Verdict | Modification output |
|---|---|---|---|
| 1 | v1 | "Finished" | **Unprompted change** v1 → v2 (three strings), although the delivered comment was "Finished" |
| 2 | v2 (differs from R1's input) | "Finished" | **UnchangedReemission** v2 → v3 |
| 3 | v3; **byte-identical to R2's input** (L1308–1405 = L1848–1945) | substantive defect | **Refinement** v3 → v4, driven by the R3 comment |

- R1–R3 and M1–M3 are **Reiterations**: the same review rules, and work objects in one lineage.
- R2 and R3 are **InputEquivalent** but returned different verdicts. Cycle 3 differs only in its output claims, not in its structure or input.
- No conflict between the R2 and R3 verdicts is asserted, because R2's scope is UNKNOWN.
- Framework labels (`cycle_index` 1–3, L714 and the other placeholder lines) only corroborate, through `raw_ref`.
- Repetition added no exposure: the GUI requirement was absent from all six delivered sets, so no repetition could have surfaced it.

---

## 15. Exact 0.2 → 0.3 delta

**New fields:**

- `run.outputs`
- `evidence.produced_by`

**New relations:**

- `delivers` (agent-input event → evidence)
- `checks` (event → proposition)

**Removed:**

- object `segments`
- relation `revises`
- relation `conflicts_with`
- evidence `source` value `verifier`

**Clarified semantics (structure unchanged):**

- **Evidence:** observable content independent of any role; granularity; identity per production; `source` = authorship, not production; external evidence and its delivery.
- **Events:** atomic input/output unit; origin of any entity kind, zero or one.
- **Entities:** kinds `agent | tool | service | framework | environment`; role and model are free-text attributes.
- **Claims:** exactly one evidence item; never delivery targets; every assertion becomes a claim; speaker derived.
- **Propositions:** requirements in logical form; forms may take evidence items as arguments.
- **States:** holder-specific; anchored to an event through `claims` (holder and event derived); no carry-forward; meaning of each value.
- **`propagates_to`:** formally defined as content lineage only.
- **`depends_on`:** formally defined as logical necessity only.
- **`supported_by` / `contradicted_by`:** proposition → evidence; direct bearing only.
- **Testimony:** represented by claims; testimonial and direct assessments kept separate.
- **Assessment relative to an artifact:** inferred, not stored as a state.
- **Framework labels:** live only in `raw_ref`.

---

## 16. What this schema deliberately does NOT claim

- It does not claim to know what an agent attended to, intended or believed beyond its observable claims.
- It does not claim causation. Contribution is a hypothesis, capped at "supported contribution".
- It does not claim that content carried between items kept its meaning, its truth or its defects.
- It does not claim that an omission happened unless input coverage is established.
- It does not claim what a bare verdict checked.
- It does not claim that a repetition was unnecessary or pathological.
- It does not claim that testimony is true, or that several reports from one origin are independent.
- It does not claim completeness: it rests on one real trace (§13).
- It does not reproduce any framework's workflow model or any benchmark's failure taxonomy.
