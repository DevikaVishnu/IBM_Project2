"""Hand-validated findings and compare/0.1 O3 for agent-council bundles (local display tooling).

Not agenttrace.semantic/0.3, not O4 and not automatic detection.  Two jobs, both read-only:

  * ``apply_o3``: run ``agenttrace.compare/0.1`` O3 (state_vs_evidence) over the run's hand-grounded 0.3
    slice and attach the result to each agent claim of the bundle.  The compare module is loaded from the
    AssetOpsBench worktree by file path; if it is absent, O3 stays "not computable" with that reason.
  * ``findings``: read ``local/agent-council/<trace id>/*.findings.json`` (``agenttrace-explorer-findings/0.1``)
    for this exact run and map each finding onto a bundle ``flags[]`` entry with the optional finding fields
    (src/explorer/CONTRACT.md, "Findings").  Every ``observed`` locator is re-resolved against the raw trace and
    must equal (or contain) the stated value; every reference must resolve in the bundle; every ``computed`` item
    is recomputed here.  Any mismatch fails the build.  Without a findings file the run's assessment reads
    "Not assessed", never "no divergence".

Nothing in the findings file is trusted except its hand-written prose (shown as hand-annotated).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

import council_adapter as ca

FINDINGS_CONTRACT = "agenttrace-explorer-findings/0.1"
CATEGORIES = {
    "cross_agent_assertion_incompatibility": ("Cross-agent assertion incompatibility",
                                              "Two agents' annotated assertions cannot both be true."),
    "direct_evidence_contradiction": ("Direct-evidence contradiction",
                                      "An agent's annotated assertion disagrees with the recorded values it cites (O3 DIFFERS_FROM_DIRECT)."),
    "recorded_coordination_disagreement": ("Recorded coordination disagreement",
                                           "The framework itself records a challenge, reply or resolution between agents."),
    "position_decision_inconsistency": ("Recorded position / decision inconsistency",
                                        "Framework records of positions, labels, dispute status or the final decision do not agree."),
}
HAND_LABEL = "Hand-validated findings: checked by a person against the source, not automatic detection"
NOT_ASSESSED = "Not assessed"
MEANING = {
    "AGREES": "The stored direct evidence gives the same value as the state the claim expresses.",
    "DIFFERS_FROM_DIRECT": "The stored direct evidence gives the opposite value to the state the claim expresses.",
    "UNKNOWN": "No stored direct link settles the proposition, so there is no comparison (not a contradiction).",
    "UNRESOLVED": "An input to the comparison is unresolved in the trace.",
    "AMBIGUOUS": "The stored direct links point both ways.",
    "NOT_APPLICABLE": "The state is not TRUE or FALSE, so it is not compared with the evidence.",
}


class FindingsError(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise FindingsError(msg)


def short(x: str) -> str:
    return re.sub(r"^(evi|ev|clm|prop):\d+:", "", x)


# ------------------------------------------------------------------------------------------------ compare / O3


def load_compare(path: Path | None):
    """The compare module, loaded by file path (no package import), or None if the file is absent."""
    if path is None or not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("agenttrace_compare_0_1", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def compare_ref(path: Path, root: Path) -> str:
    try:
        shown = str(path.resolve().relative_to(root.parent.resolve()))
        shown = f"../{shown}"
    except ValueError:
        shown = path.name
    return f"{shown} (sha256 {hashlib.sha256(path.read_bytes()).hexdigest()[:12]}…)"


def apply_o3(bundle: dict, slice_path: Path, compare) -> dict | None:
    """Attach compare/0.1 O3 to every agent claim that grounds a state of the slice.  Returns the comparator."""
    if compare is None:
        for c in bundle["claims"]:
            if c["state"] is not None:
                c["o3"] = {"status": "not computable", "origin": "computed",
                           "reason": "agenttrace.compare/0.1 module not found (AssetOpsBench worktree absent); O3 not run"}
        return None
    s = json.loads(slice_path.read_text(encoding="utf-8"))
    comp = compare.Comparator(s, {}, {})
    state_of = {cid: i for i, st in enumerate(s["states"]) for cid in st["claims"]}
    computed = 0
    for c in bundle["claims"]:
        if c["state"] is None:
            continue
        sid = (c.get("fixture") or {}).get("claim")
        need(sid in state_of, f"claim {c['id']}: no slice state grounds it")
        try:
            res = comp.state_vs_evidence(state_of[sid])
        except compare.InvalidInput as e:
            c["o3"] = {"status": "not computable", "origin": "computed", "reason": f"agenttrace.compare/0.1 rejects this state: {e}"}
            continue
        need(res["inputs"]["value"] == c["state"]["value"], f"claim {c['id']}: slice state value differs from the bundle")
        o3 = {"status": "computed", "origin": "computed", "computed_from": "hand-annotated 0.3 slice (claims, states, direct links, delivers)",
              "operation": f"{compare.PROFILE} state_vs_evidence (O3)", "comparison": res["comparison"], "direct": res["direct"]["value"],
              "delivered_direct": res["delivered_direct"]["value"], "testimonial": res["testimonial"]["value"],
              "meaning": MEANING.get(res["comparison"], ""), "raw": res}
        pend = [p for p in res["delivered_direct"].get("pending", []) if p.get("reason") == "link raw_ref names no grounding"]
        if res["delivered_direct"]["value"] == "UNKNOWN" and pend:
            o3["delivered_direct_note"] = ("UNKNOWN because the slice's direct links ground on joint arithmetic (slice gap G2) and name neither "
                                           "whole_item nor spans, which compare/0.1 needs to count a link. This is not a non-delivery result.")
        c["o3"] = o3
        computed += 1
    bundle["layers"]["o3"] = computed > 0
    bundle["provenance"]["compare"] = compare.PROFILE
    return comp


# ------------------------------------------------------------------------------------------------ findings


def find_findings(ann_root: Path, tid: str, explicit: Path | None) -> Path | None:
    if explicit:
        return explicit
    d = ann_root / tid
    hits = sorted(d.glob("*.findings.json")) if d.is_dir() else []
    need(len(hits) <= 1, f"{len(hits)} *.findings.json files in {ca.rel(d)}")
    return hits[0] if hits else None


def not_assessed(reason: str) -> dict:
    return {"status": "not_assessed", "label": NOT_ASSESSED, "origin": "computed", "method": None, "source": None, "source_sha256": None,
            "text": f"{NOT_ASSESSED}: {reason} The absence of findings here is not evidence that the agents did not diverge."}


def _resolve(raw, item):
    v = ca.resolve(raw, item["locator"])
    if item.get("span") is not None:
        need(isinstance(v, str), f"{item['locator']}: span on a non-string value")
        s, e = item["span"]
        need(0 <= s < e <= len(v), f"{item['locator']}: span {item['span']} outside the value")
        v = v[s:e]
    return v


def _num(raw, op):
    text = _resolve(raw, op)
    m = re.search(op["regex"], text)
    need(m, f"{op['locator']}: pattern {op['regex']!r} not found")
    return float(m.group(1)), m.group(1)


def _observed(raw, item):
    v = _resolve(raw, item)
    if "contains" in item:
        need(isinstance(v, str) and item["contains"] in v, f"observed {item['locator']}: does not contain {item['contains']!r}")
        shown = item["contains"]
    else:
        need(v == item["expect"], f"observed {item['locator']}: {json.dumps(v)[:120]} != {json.dumps(item['expect'])[:120]}")
        shown = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    loc = item["locator"] + (f" [{item['span'][0]}:{item['span'][1]}]" if item.get("span") else "")
    return {"text": item["text"], "value": shown, "locator": loc, "origin": "observed"}


def _computed(op, raw, rec, bundle, comp, slice_, names):
    k = op["op"]
    claims = {c["id"]: c for c in bundle["claims"]}
    if k == "o2":
        need(comp is not None, "o2 check needs agenttrace.compare/0.1")
        ev = next((e for e in slice_["events"] if e["id"] == op["event"]), None)
        need(ev, f"o2: slice event {op['event']} unknown")
        vals = [(it, comp.exposure_at(op["event"], it)["whole_item"]) for it in op["items"]]
        who = names.get(ev.get("origin"), ev.get("origin"))
        return {"op": "o2", "origin": "computed", "values": dict(vals),
                "text": f"O2 (compare/0.1 exposure_at, whole item) at {short(op['event'])} ({who}): " + ", ".join(f"{short(i)} {v}" for i, v in vals) + "."}
    if k == "o3":
        c = claims.get(op["claim"])
        need(c and c["state"] is not None, f"o3: claim {op['claim']} is not an agent claim in the bundle")
        o = c["o3"]
        need(o["status"] == "computed", f"o3: {op['claim']} was not computed ({o.get('reason')})")
        return {"op": "o3", "origin": "computed", "claim": c["id"], "comparison": o["comparison"],
                "text": f"O3 (compare/0.1) for {c['label']}: state {c['state']['value']}, direct {o['direct']} → {o['comparison']}; "
                        f"delivered direct {o['delivered_direct']}; testimonial {o['testimonial']}."}
    if k == "o3_testimonial":
        c = claims.get(op["claim"])
        need(c and c["o3"]["status"] == "computed", f"o3_testimonial: {op['claim']} not computed")
        t = c["o3"]["raw"]["testimonial"]
        why = (" No claim by another speaker on this proposition or its stored negation; compare/0.1 does not relate different propositions "
               "(no conflicts_with or depends_on is stored)." if t["value"] == "UNKNOWN" and not t["contributions"] else "")
        return {"op": "o3_testimonial", "origin": "computed", "claim": c["id"], "value": t["value"],
                "text": f"O3 testimonial for {c['label']}: {t['value']}.{why}"}
    if k == "closer":
        x, xs = _num(raw, op["x"])
        a, as_ = _num(raw, op["a"])
        b, bs = _num(raw, op["b"])
        da, db = abs(x - a), abs(x - b)
        r = op.get("rounding", 0)
        verdict = "a" if da < db else "b" if db < da else "tie"
        robust = abs(da - db) > 4 * r
        if "expect" in op:
            need(verdict == op["expect"] and robust, f"closer: computed {verdict} (robust {robust}) != expected {op['expect']}")
        near = op["a"]["label"] if verdict == "a" else op["b"]["label"] if verdict == "b" else "neither (tie)"
        return {"op": "closer", "origin": "computed", "verdict": verdict, "robust": robust,
                "text": f"From the recorded values: |{xs} − {as_}| = {da:.3f} and |{xs} − {bs}| = {db:.3f}, so the reading is closer to the {near}"
                        + (f"; this holds under ±{r} rounding of each value." if robust else "; NOT robust to rounding.")}
    if k == "message_mechanism":
        msgs = {m["id"]: m for m in rec["messages"]}
        parts = []
        for mid in op["messages"]:
            m = msgs.get(mid)
            need(m, f"message_mechanism: {mid} unknown")
            rd = [d for d in m["deliveries"] if d["class"] == "recorded_delivery"]
            code = [d for d in m["deliveries"] if d["class"].startswith("code_access")]
            mech = (f"text LLM-voiced by model call {m['producer']['call']}" if m["text_mechanism"] == "llm_voice" and m["producer"]
                    else f"text built by deterministic code (execution {m['sender_execution']}, no model call)" if m["text_mechanism"] == "deterministic"
                    else f"text mechanism {m['text_mechanism']}")
            parts.append(f"{mid} {m['type']} from {names.get(m['sender'], m['sender'])} @{m['seq']}: {mech}; recorded deliveries into a model input: {len(rd)}"
                         + (f" ({', '.join(d['call'] for d in rd)})" if rd else "")
                         + f"; code-only reads: {len(code)}" + (f" ({', '.join(f'{names.get(d['receiver'], d['receiver'])} {d['via']} @{d['seq']}' for d in code)})" if code else ""))
        return {"op": k, "origin": "computed", "text": " · ".join(parts) + "."}
    if k == "agent_calls_after":
        calls = sorted((c for c in rec["model_calls"] if c["agent"] == op["agent"]), key=lambda c: c["order"])
        after = [c for c in calls if c["order"] > op["seq"]]
        last = [c for c in calls if c["order"] <= op["seq"]][-1:] or [None]
        return {"op": k, "origin": "computed", "count": len(after),
                "text": f"{names.get(op['agent'], op['agent'])} model calls after seq {op['seq']}: {len(after)}"
                        + (f" ({', '.join(c['id'] for c in after)})" if after else "")
                        + (f"; last before it: {last[0]['id']} at seq {last[0]['order']}." if last[0] else ".")}
    if k == "positions_after":
        P = bundle.get("positions")
        need(P, "positions_after: bundle has no positions")
        mine = [o for o in P["observations"] if o["kind"] == "agent_position" and o["holder"].get("agent") == op["agent"] and o["seq"] is not None]
        after = [o for o in mine if o["seq"] > op["seq"]]
        before = [o for o in mine if o["seq"] <= op["seq"]][-1:]
        lt = (f"; last before it: {before[0]['related'].get('message') or before[0]['id']} at seq {before[0]['seq']}, recorded label {before[0]['recorded_label']}"
              f" (top score {before[0]['leading']['score']})" if before and before[0].get("leading") else "")
        return {"op": k, "origin": "computed", "count": len(after),
                "text": f"{names.get(op['agent'], op['agent'])} framework-computed positions recorded after seq {op['seq']}: {len(after)}{lt}."}
    raise FindingsError(f"unknown computed op {k!r}")


def findings(raw: dict, rec: dict, bundle: dict, path: Path, comp, slice_path: Path | None) -> tuple[list, dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    need(doc.get("contract") == FINDINGS_CONTRACT, f"{ca.rel(path)}: contract {doc.get('contract')!r}")
    tid = rec["run"]["trace_id"]
    need(doc["run"]["id"] == tid, f"{ca.rel(path)} is for run {doc['run']['id']!r}")
    src_sha = rec["source"].get("member_sha256") or rec["source"].get("sha256")
    need(doc["run"]["member_sha256"] == src_sha, f"{ca.rel(path)} was validated on a different source")
    need(doc["validation"]["method"] == "hand-validated", "findings must be hand-validated")
    slice_ = json.loads(slice_path.read_text(encoding="utf-8")) if slice_path else {"events": []}
    names = {a["id"]: a["name"] or a["id"] for a in rec["agents"]}
    names.update({f"agent:{k}": v for k, v in list(names.items())})
    cols = {c["id"]: c for c in bundle["matrix"]["columns"]}
    claims = {c["id"] for c in bundle["claims"]}
    P = bundle.get("positions") or {"observations": []}
    out, seen = [], set()
    for f in sorted(doc["findings"], key=lambda f: f["priority"]):
        need(f["id"] not in seen, f"duplicate finding {f['id']}")
        seen.add(f["id"])
        need(f["category"] in CATEGORIES, f"{f['id']}: unknown category {f['category']!r}")
        refs = f.get("refs", {})
        for c in refs.get("claims", []):
            need(c in claims, f"{f['id']}: claim {c} not in the bundle")
        columns = []
        for x in refs.get("executions", []):
            hit = [c["id"] for c in rec["model_calls"] if c["execution"] == x] + ([f"exec:{x}"] if f"exec:{x}" in cols else [])
            need(hit and all(h in cols for h in hit), f"{f['id']}: execution {x} has no matrix column")
            columns += hit
        evidence = []
        for m in refs.get("messages", []):
            need(f"msg:{m}" in bundle["evidence"], f"{f['id']}: message {m} not in the bundle evidence")
            evidence.append(f"msg:{m}")
        for x in refs.get("evidence", []):
            need(x in bundle["evidence"], f"{f['id']}: evidence {x} not in the bundle")
            evidence.append(x)
        positions = []
        for p in refs.get("positions", []):
            hit = [o["id"] for o in P["observations"] if o["kind"] == p["kind"] and (o.get("related") or {}).get("message") == p["message"]]
            need(len(hit) == 1, f"{f['id']}: position {p} matches {len(hit)} observations")
            positions += hit
        observed = [_observed(raw, it) for it in f["observed"]]
        computed = [_computed(op, raw, rec, bundle, comp, slice_, names) for op in f.get("computed", [])]
        label, definition = CATEGORIES[f["category"]]
        out.append({"id": f["id"], "title": f["title"], "kind": f["category"], "category": f["category"], "category_label": label, "category_definition": definition,
                    "priority": f["priority"], "validation": "hand-validated", "origin": "hand-annotated",
                    "text": f["summary"], "caveat": None, "observed": observed,
                    "interpretation": {"text": f["interpretation"], "origin": "hand-annotated"},
                    "computed": computed, "limitations": f.get("limitations", []), "unknowns": f.get("unknowns", []),
                    "events": list(dict.fromkeys(columns)), "columns": list(dict.fromkeys(columns)), "anchors": list(dict.fromkeys(columns))[:2],
                    "evidence": list(dict.fromkeys(evidence)), "refs": {"claims": refs.get("claims", []), "positions": positions}})
    assessment = {"status": "hand-validated", "label": HAND_LABEL, "origin": "hand-annotated", "method": "hand-validated",
                  "source": ca.rel(path), "source_sha256": ca.sha(path.read_bytes()), "ground_truth": doc["validation"].get("ground_truth"),
                  "text": f"{len(out)} hand-validated finding(s). Each was checked by hand against the source; observed values are re-resolved and computed checks "
                          "re-run at build time. They are not automatically detected, not O4 results, and not a complete search: other divergences may exist."}
    return out, assessment
