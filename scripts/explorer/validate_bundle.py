"""Validate a Belief Explorer trace bundle (agenttrace-explorer-bundle/0.1, src/explorer/CONTRACT.md).

    python3 scripts/explorer/validate_bundle.py [--manifest src/explorer/data/index.json]

Plain Python (no worktree needed).  Checks form, origin tags, referential integrity and the honesty
rules; shares no code with the builder.  Exit 0 if every listed bundle passes and its sha256 matches
the manifest, else 1 with the problems.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

AP_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = "agenttrace-explorer-bundle/0.1"
ORIGINS = {"observed", "computed", "hand-annotated", "hand-reconstructed", "unresolved"}
TOP = ("contract", "trace", "honesty", "provenance", "layers", "skeleton", "matrix", "evidence", "propositions", "claims", "non_claims", "flags", "facts")
LAYERS = ("skeleton", "matrix", "claims", "evidence", "delivery", "o3", "flags")
DELIVERY = {"DELIVERED", "UNKNOWN", "UNRESOLVED", "NOT_APPLICABLE", "NOT_DELIVERED", "WHOLE_NOT_DELIVERED"}
STATES = {"TRUE", "FALSE", "UNCERTAIN", "UNKNOWN"}
O3_STATUS = {"computed", "not computable", "rule-dependent"}
SEMANTIC_KEYS = {"claims", "propositions", "states", "beliefs", "disagreements"}
# Optional column kind (absent = model_call).  A deterministic_execution column is code that made no model call.
COLUMN_KINDS = {"model_call", "deterministic_execution"}
DET = "deterministic_execution"
HOME = re.compile(r"/(?:Users|home)/[^/\s\"']+/")
# Optional finding fields on flags[] and the optional top-level `assessment` (CONTRACT.md, "Findings").
FINDING_CATEGORIES = {"cross_agent_assertion_incompatibility", "direct_evidence_contradiction",
                      "recorded_coordination_disagreement", "position_decision_inconsistency"}
ASSESSMENT_STATUS = {"hand-validated", "not_assessed"}
AUTO_WORDS = re.compile(r"\b(automatic(ally)? detected|auto-detected|detector found)\b", re.I)


def validate(b: dict) -> list[str]:
    p: list[str] = []

    def chk(cond, msg):
        if not cond:
            p.append(msg)

    def tagged(obj, where):
        chk(isinstance(obj, dict) and obj.get("origin") in ORIGINS, f"{where}: missing or invalid origin tag {obj.get('origin') if isinstance(obj, dict) else obj!r}")

    if not isinstance(b, dict):
        return ["bundle is not an object"]
    chk(b.get("contract") == CONTRACT, f"contract is {b.get('contract')!r}, expected {CONTRACT}")
    for k in TOP:
        chk(k in b, f"missing top-level key {k}")
    if p:
        return p
    chk(set(b["layers"]) == set(LAYERS) and all(isinstance(v, bool) for v in b["layers"].values()), "layers must map exactly the known layers to booleans")
    chk(HOME.search(json.dumps(b, ensure_ascii=False)) is None, "a home-directory path appears in the bundle")
    chk(b["trace"].get("kind") in ("single-agent", "multi-agent"), "trace.kind must be single-agent or multi-agent")
    chk(bool(b["honesty"].get("annotations")), "honesty.annotations label is missing")

    sk, mx = b["skeleton"], b["matrix"]
    ev_ids = set()
    if sk:
        tagged(sk, "skeleton")
        for a in sk.get("agents", []):
            tagged(a, f"skeleton agent {a.get('id')}")
        sk_kind = {}
        for e in sk.get("events", []):
            tagged(e, f"skeleton event {e.get('id')}")
            ev_ids.add(e["id"])
            sk_kind[e["id"]] = e.get("kind")
        for h in sk.get("handoffs", []):
            tagged(h, f"handoff {h.get('from')}->{h.get('to')}")
    rows, cols = set(), {}
    if mx:
        tagged(mx, "matrix")
        chk(not (SEMANTIC_KEYS & set(mx)), "the matrix layer must stay claim-free (no claims/propositions/states keys)")
        for r in mx.get("rows", []):
            tagged(r, f"row {r.get('id')}")
            rows.add(r["id"])
        orders = [c["order"] for c in mx.get("columns", [])]
        chk(orders == sorted(orders), "columns are not in observation order")
        for c in mx.get("columns", []):
            tagged(c, f"column {c.get('id')}")
            chk(c.get("row") in rows, f"column {c.get('id')}: row {c.get('row')!r} is not a matrix row")
            chk(not ev_ids or c["id"] in ev_ids, f"column {c['id']} is not a skeleton event")
            kind = c.get("kind", "model_call")
            chk(kind in COLUMN_KINDS, f"column {c['id']}: kind {kind!r}")
            if kind == DET:
                # Code, not a model call: no model input to deliver into, no tool or delegation of its own, and it is a
                # column only because it posted at least one recorded message.
                chk(c.get("delivers") is None and c.get("first") is None, f"column {c['id']}: a deterministic execution has no model input (delivers/first must be null)")
                chk(not c.get("tools") and not c.get("delegation_out") and not c.get("delegation_in"), f"column {c['id']}: a deterministic execution has no tools or delegations")
                chk(isinstance(c.get("execution"), dict) and bool(c["execution"].get("id")) and bool(c["execution"].get("locator")), f"column {c['id']}: execution id and locator required")
                chk(bool(c.get("messages")) and all(m.get("id") and m.get("evidence") for m in c["messages"]), f"column {c['id']}: deterministic execution columns list the messages they posted")
                chk(not ev_ids or sk_kind.get(c["id"]) == DET, f"column {c['id']}: its skeleton event must have kind {DET}")
            # delivers/first are None together when the call's input is not recorded (delivery UNKNOWN).
            if c.get("delivers") is None or c.get("first") is None:
                chk(c.get("delivers") is None and c.get("first") is None, f"column {c['id']}: delivers and first must both be unknown")
            else:
                chk(c["delivers"] >= c["first"] >= 0, f"column {c['id']}: first > delivers")
            cols[c["id"]] = c
        for e in mx.get("edges", []):
            tagged(e, f"edge {e.get('from')}->{e.get('to')}")
            chk(e.get("from") in cols and e.get("to") in cols, f"edge {e.get('from')}->{e.get('to')} references unknown columns")
            # An edge is a recorded delivery into a model input; code has none, so no edge may end at a code execution.
            chk(cols.get(e.get("to"), {}).get("kind", "model_call") != DET, f"edge {e.get('from')}->{e.get('to')} ends at a deterministic execution (no model input)")

    evidence = b["evidence"] or {}
    for k, x in evidence.items():
        tagged(x, f"evidence {k}")
        chk(x.get("id") == k, f"evidence key {k} != id {x.get('id')}")
        ex = x.get("excerpt") or {}
        t = ex.get("text") or ""
        chk(len(t) <= 2000, f"evidence {k}: excerpt longer than 2000 characters")
        for s, e in ex.get("spans", []):
            chk(0 <= s < e <= len(t), f"evidence {k}: excerpt span [{s},{e}] out of range")

    props = {}
    for pr in b["propositions"]:
        tagged(pr, f"proposition {pr.get('id')}")
        props[pr["id"]] = pr
        for l in pr.get("links", []):
            chk(l.get("relation") in ("supported_by", "contradicted_by"), f"proposition {pr['id']}: link relation {l.get('relation')!r}")
            chk(l.get("evidence") in evidence, f"proposition {pr['id']}: link evidence {l.get('evidence')} missing from evidence")

    claims = {}
    for c in b["claims"]:
        w = f"claim {c.get('id')}"
        tagged(c, w)
        claims[c["id"]] = c
        chk(bool(c.get("words")), f"{w}: exact words missing")
        chk(c.get("proposition") in props, f"{w}: proposition {c.get('proposition')} missing")
        chk(not ev_ids or c.get("event") in ev_ids, f"{w}: event {c.get('event')} is not a skeleton event")
        if c.get("state") is None and "state" in c:
            # A framework-authored claim: no belief state, with a stated reason; made by a code-execution column; never an O3 input.
            sa, au = c.get("state_absent") or {}, c.get("author") or {}
            tagged(sa, f"{w} state_absent")
            chk(bool(sa.get("reason")), f"{w}: state is null without a state_absent.reason")
            tagged(au, f"{w} author")
            chk(au.get("kind") == DET, f"{w}: only a framework-authored claim (author.kind {DET}) may have no state")
            col = cols.get(c.get("event"))
            chk(col is not None and col.get("kind") == DET and col.get("execution", {}).get("id") == au.get("execution"),
                f"{w}: a state-less claim must sit on the code-execution column of its author")
            chk((c.get("o3") or {}).get("status") == "not computable", f"{w}: a claim with no state is not an O3 input (o3 must be 'not computable')")
            for l in c.get("links", []):
                d = l.get("delivery")
                chk(d is None or d.get("value") == "NOT_APPLICABLE", f"{w}: delivery into a code execution must be NOT_APPLICABLE")
        else:
            st = c.get("state") or {}
            tagged(st, f"{w} state")
            chk(st.get("value") in STATES, f"{w}: state value {st.get('value')!r}")
            chk(cols.get(c.get("event"), {}).get("kind", "model_call") != DET, f"{w}: a code execution holds no belief state")
        chk(c.get("speaker_origin") in ORIGINS, f"{w}: speaker_origin missing")
        for l in c.get("links", []):
            tagged(l, f"{w} link")
            chk(l.get("evidence") in evidence, f"{w}: link evidence {l.get('evidence')} missing from evidence")
            d = l.get("delivery")
            if d is not None:
                tagged(d, f"{w} delivery")
                chk(d.get("value") in DELIVERY, f"{w}: delivery value {d.get('value')!r}")
                chk(d.get("value") != "NOT_DELIVERED" or d.get("coverage"), f"{w}: NOT_DELIVERED without established coverage")
        o3 = c.get("o3")
        if o3 is not None:
            tagged(o3, f"{w} o3")
            chk(o3.get("status") in O3_STATUS, f"{w}: o3 status {o3.get('status')!r}")
            if o3.get("status") == "computed":
                chk(bool(o3.get("comparison")) and bool(o3.get("meaning")) and o3.get("computed_from"), f"{w}: computed o3 lacks comparison, meaning or computed_from")
            else:
                chk(bool(o3.get("reason")), f"{w}: {o3.get('status')} o3 lacks a reason")
    for n in b["non_claims"]:
        tagged(n, f"non-claim {n.get('label')}")
    flags = {}
    for f in b["flags"]:
        tagged(f, f"flag {f.get('id')}")
        flags[f["id"]] = f
        for e in f.get("events", []):
            chk(e in ev_ids or e in cols, f"flag {f['id']}: event {e} unknown")
        for c in f.get("columns", []):
            chk(c in cols, f"flag {f['id']}: column {c} unknown")
        for x in f.get("evidence", []):
            chk(x in evidence, f"flag {f['id']}: evidence {x} missing")
        for c in f.get("computed", []):
            tagged(c, f"flag {f['id']} computed item")
    for x in b["facts"]:
        tagged(x, f"fact {x.get('id')}")
    if mx:
        for o in mx.get("overlays", []):
            tagged(o, f"overlay {o.get('id')}")
            chk(o.get("column") in cols, f"overlay {o.get('id')}: column {o.get('column')} unknown")
            chk(o.get("column") not in cols or cols[o["column"]]["row"] == o.get("row"), f"overlay {o.get('id')}: row does not match its column")
            ref = o.get("ref")
            chk(o.get("kind") in ("claim", "flag", "lane"), f"overlay {o.get('id')}: kind {o.get('kind')!r}")
            chk(ref is None or ref in claims or ref in flags, f"overlay {o.get('id')}: ref {ref} unknown")
    deliv = (sk or {}).get("delivery")
    if deliv:
        for d in deliv.get("delivered", []) + deliv.get("not_delivered", []):
            tagged(d, f"delivery {d.get('item')}")
            chk(d.get("value") in DELIVERY, f"delivery {d.get('item')}: value {d.get('value')!r}")
            chk(d.get("value") != "NOT_DELIVERED" or d.get("coverage"), f"delivery {d.get('item')}: NOT_DELIVERED without coverage")
    w = b.get("walkthrough")
    if w is not None:
        chk(w.get("claim") in claims, f"walkthrough claim {w.get('claim')} is not a claim")
        chk(w.get("evidence") in evidence, f"walkthrough evidence {w.get('evidence')} missing from evidence")
        for k in ("tool_event", "first_receiver"):
            chk(not ev_ids or w.get(k) in ev_ids, f"walkthrough {k} {w.get(k)} is not a skeleton event")
        for part in ("raw", "adapter", "comparator"):
            tagged(w.get(part), f"walkthrough {part}")
        for d in (w.get("adapter") or {}).get("delivers", []):
            chk(not ev_ids or d.get("event") in ev_ids, f"walkthrough delivers event {d.get('event')} unknown")
        for o in (w.get("comparator") or {}).get("o2", []):
            chk(o.get("value") in DELIVERY, f"walkthrough O2 value {o.get('value')!r}")
        chk(bool(w.get("note")), "walkthrough note missing")
    if "positions" in b:
        p.extend(_positions(b["positions"], rows, cols, evidence, claims))
    p.extend(_findings(b, cols, evidence, claims))
    # Layer flags must not claim data that is absent.
    chk(not b["layers"]["claims"] or b["claims"], "layers.claims is true but there are no claims")
    chk(not b["layers"]["flags"] or b["flags"], "layers.flags is true but there are no flags")
    return p


# Optional C4 field `positions`: framework-computed scores, never beliefs.  Holder kind is fixed per observation kind.
POSITIONS_LABEL = "Framework-computed positions — not agent beliefs"
POSITION_HOLDER = {"agent_position": "agent", "joint_ranking": "council", "hypothesis_scores": "framework", "final_decision": "framework"}


def _top(scores):
    if not scores:
        return None
    m = max(scores.values())
    return sorted(k for k, x in scores.items() if x == m)


def _positions(P, rows, cols, evidence, claims) -> list[str]:
    p: list[str] = []

    def chk(cond, msg):
        if not cond:
            p.append(f"positions: {msg}")

    if not isinstance(P, dict):
        return ["positions: must be an object"]
    chk(P.get("origin") in ORIGINS, "layer origin tag missing")
    chk(P.get("label") == POSITIONS_LABEL, f"label must read {POSITIONS_LABEL!r}")
    obs = P.get("observations") or []
    chk(bool(obs), "no observations")

    def no_semantic(obj, where):
        if isinstance(obj, dict):
            chk(not (SEMANTIC_KEYS & set(obj)), f"{where} carries a claims/propositions/states/beliefs key")
            for k, x in obj.items():
                if k not in ("scores", "member_positions"):  # score maps are keyed by diagnosis labels
                    no_semantic(x, where)
        elif isinstance(obj, list):
            for x in obj:
                no_semantic(x, where)

    no_semantic({k: x for k, x in P.items() if k != "observations"}, "layer")
    segs = {s.get("id") for s in P.get("segments", [])}
    states = {s.get("id"): s for s in P.get("score_states", [])}
    ids, last = set(), None
    for o in obs:
        w = o.get("id")
        chk(w not in ids, f"duplicate observation id {w}")
        ids.add(w)
        chk(o.get("origin") in ORIGINS, f"{w}: origin tag missing")
        no_semantic(o, w)
        k = o.get("kind")
        chk(k in POSITION_HOLDER, f"{w}: kind {k!r}")
        h = o.get("holder") or {}
        chk(h.get("kind") == POSITION_HOLDER.get(k), f"{w}: a {k} is held by {POSITION_HOLDER.get(k)}, not {h.get('kind')!r}")
        chk((h.get("agent") is not None) == (k == "agent_position"), f"{w}: only an agent_position names an agent holder")
        chk(k != "agent_position" or not rows or h.get("agent") in rows, f"{w}: agent {h.get('agent')} is not a matrix row")
        seq = o.get("seq")
        chk(seq is None or last is None or seq >= last, f"{w}: observations are not in seq order")
        last = seq if seq is not None else last
        sc = o.get("scores")
        unk = o.get("unknown")
        chk(isinstance(unk, dict), f"{w}: unknown map missing")
        unk = unk or {}
        chk(sc is not None or "scores" in unk, f"{w}: missing scores not marked unknown")
        chk(o.get("confidence") is not None or "confidence" in unk, f"{w}: missing confidence not marked unknown")
        chk(o.get("round") is not None or "round" in unk, f"{w}: missing round not marked unknown")
        if sc is not None:
            chk(isinstance(sc, dict) and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in sc.values()), f"{w}: scores must map labels to numbers")
        ld = o.get("leading")
        chk((ld is None) == (not sc), f"{w}: leading must be present exactly when scores are")
        if ld and sc:
            chk(ld.get("labels") == _top(sc), f"{w}: leading {ld.get('labels')} is not the top recorded score {_top(sc)}")
            chk(ld.get("tie") == (len(_top(sc)) > 1), f"{w}: tie flag wrong")
            chk(ld.get("origin") in ORIGINS, f"{w}: leading origin tag missing")
        chk(bool(o.get("locator")), f"{w}: locator missing")
        chk(o.get("segment") in segs, f"{w}: segment {o.get('segment')} unknown")
        rel = o.get("related") or {}
        chk(rel.get("origin") in ORIGINS and bool(rel.get("join")), f"{w}: related join and origin required")
        for c in rel.get("columns", []) + rel.get("received_in", []):
            chk(c in cols, f"{w}: related column {c} unknown")
        if rel.get("evidence"):
            chk(rel["evidence"] in evidence, f"{w}: related evidence {rel['evidence']} missing")
        st = o.get("score_state")
        if st is not None:
            chk(k == "hypothesis_scores", f"{w}: only overall hypothesis scores belong to a score state")
            chk(st in states and w in states[st].get("observations", []), f"{w}: score state {st} does not list it")
    for sid, s in states.items():
        chk(s.get("origin") in ORIGINS, f"score state {sid}: origin tag missing")
        for oid in s.get("observations", []):
            chk(oid in ids, f"score state {sid}: observation {oid} unknown")
    for c in claims.values():
        chk(not str(c.get("event", "")).startswith("pos:"), f"claim {c.get('id')} points at a position observation")
    return p

def _findings(b, cols, evidence, claims) -> list[str]:
    """Optional finding fields on flags[] (`category` present) and the optional top-level `assessment`."""
    p: list[str] = []

    def chk(cond, msg):
        if not cond:
            p.append(f"findings: {msg}")

    found = [f for f in b["flags"] if "category" in f]
    a = b.get("assessment")
    if a is not None:
        chk(a.get("status") in ASSESSMENT_STATUS, f"assessment status {a.get('status')!r}")
        chk(a.get("origin") in ORIGINS and bool(a.get("text")) and bool(a.get("label")), "assessment needs origin, label and text")
        if a.get("status") == "not_assessed":
            chk(not found, "a not_assessed bundle carries findings")
            chk("not evidence" in (a.get("text") or ""), "not_assessed text must say absence is not evidence of no divergence")
        else:
            chk(a.get("origin") == "hand-annotated" and a.get("source") and a.get("source_sha256"), "hand-validated assessment needs a hand-annotated origin and its source file")
    if found:
        chk(a is not None and a.get("status") == "hand-validated", "findings present without a hand-validated assessment")
    pos_ids = {o["id"] for o in (b.get("positions") or {}).get("observations", [])}
    prios = []
    for f in found:
        w = f"finding {f.get('id')}"
        chk(f["category"] in FINDING_CATEGORIES, f"{w}: category {f['category']!r}")
        chk(f.get("kind") == f["category"], f"{w}: kind must equal category")
        chk(f.get("validation") == "hand-validated" and f.get("origin") == "hand-annotated", f"{w}: must be hand-validated and hand-annotated")
        chk(isinstance(f.get("priority"), int), f"{w}: priority must be an integer")
        prios.append(f.get("priority"))
        chk(bool(f.get("observed")), f"{w}: needs at least one observed anchor")
        for o in f.get("observed", []):
            chk(o.get("origin") == "observed" and bool(o.get("locator")) and "value" in o, f"{w}: observed item needs origin observed, locator and value")
        it = f.get("interpretation")
        chk(isinstance(it, dict) and it.get("origin") == "hand-annotated" and bool(it.get("text")), f"{w}: interpretation must be hand-annotated text")
        for c in f.get("computed", []):
            chk(c.get("origin") == "computed" and bool(c.get("text")), f"{w}: computed item needs origin computed and text")
        for k in ("limitations", "unknowns"):
            chk(isinstance(f.get(k), list), f"{w}: {k} must be a list")
        refs = f.get("refs") or {}
        for c in refs.get("claims", []):
            chk(c in claims, f"{w}: claim {c} unknown")
        for o in refs.get("positions", []):
            chk(o in pos_ids, f"{w}: position observation {o} unknown")
        for c in f.get("anchors", []):
            chk(c in cols, f"{w}: anchor {c} is not a column")
        texts = [f.get("title", ""), f.get("text", ""), (it or {}).get("text", "")]
        chk(not any(AUTO_WORDS.search(t) for t in texts), f"{w}: describes itself as automatic detection")
    chk(prios == sorted(prios), "findings are not in priority order")
    return p



def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--manifest", type=Path, default=AP_ROOT / "src/explorer/data/index.json")
    args = ap.parse_args(argv)
    if not args.manifest.exists():
        print(f"no manifest at {args.manifest}; nothing to validate (bundles are local-only, see docs/DATA.md)")
        return 0
    man = json.loads(args.manifest.read_text(encoding="utf-8"))
    bad = False
    for e in man["bundles"]:
        body = (args.manifest.parent / e["file"]).read_text(encoding="utf-8")
        probs = validate(json.loads(body))
        if hashlib.sha256(body.encode("utf-8")).hexdigest() != e["sha256"]:
            probs.append("sha256 does not match the manifest")
        print(f"{e['trace_id']}: {'OK' if not probs else f'{len(probs)} problem(s)'}")
        for x in probs[:20]:
            print(f"  - {x}")
        bad |= bool(probs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

