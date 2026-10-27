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
HOME = re.compile(r"/(?:Users|home)/[^/\s\"']+/")


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
        for e in sk.get("events", []):
            tagged(e, f"skeleton event {e.get('id')}")
            ev_ids.add(e["id"])
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
            chk(c.get("delivers", 0) >= c.get("first", 0) >= 0, f"column {c['id']}: first > delivers")
            cols[c["id"]] = c
        for e in mx.get("edges", []):
            tagged(e, f"edge {e.get('from')}->{e.get('to')}")
            chk(e.get("from") in cols and e.get("to") in cols, f"edge {e.get('from')}->{e.get('to')} references unknown columns")

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
        st = c.get("state") or {}
        tagged(st, f"{w} state")
        chk(st.get("value") in STATES, f"{w}: state value {st.get('value')!r}")
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
    # Layer flags must not claim data that is absent.
    chk(not b["layers"]["claims"] or b["claims"], "layers.claims is true but there are no claims")
    chk(not b["layers"]["flags"] or b["flags"], "layers.flags is true but there are no flags")
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
