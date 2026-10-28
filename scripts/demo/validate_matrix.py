"""Independent validator for agenttrace-matrix/0.2 data (see MATRIX_CONTRACT.md).

It shares no code with build_matrix.py.  It re-runs the frozen adapter and verifier on the raw trace and
re-derives every matrix property from that output and the raw record:

  * form: canonical bytes, contract id, required keys, no semantic objects (claims, propositions,
    states) and claims_extracted false;
  * provenance: trace sha256, telemetry flags, run status and terminal event equal the record;
  * rows: exactly the record's agents[], in order;
  * columns: exactly the adapter's model events, in observation order, with the adapter's start/end
    seqs; each column's row is its origin agent, or "$unresolved" with the adapter's candidates kept;
  * deliveries: each column lists exactly the adapter delivers links from that event, in order;
    "first delivered here" and delegation inputs are recomputed; with no delivery telemetry every
    column is empty;
  * locators and excerpts: every referenced evidence exists, its locator resolves in the raw record and
    its excerpt is the first 300 characters of the resolved text, flagged complete only if whole;
  * issued tool calls, delegations, overlaps and counts are recomputed;
  * fixture links (optional): each is reproduced by exactly one adapter link and matches the fixture.

    PYTHONPATH=<worktree>/src <worktree>/.venv/bin/python scripts/demo/validate_matrix.py --matrix M --trace T [--fixture F]
    ... validate_matrix.py --manifest src/demo/data/matrices/index.json   (checks every listed run)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

CONTRACT = "agenttrace-matrix/0.2"
REQUIRED = ("contract", "run", "telemetry", "provenance", "semantic", "rows", "columns", "evidence", "other_events",
            "fixture_links", "ambiguities", "skipped", "counts", "order_caveat")
FORBIDDEN = ("claims", "propositions", "states", "beliefs", "disagreements")
LIMIT = 300
AP_ROOT = Path(__file__).resolve().parents[2]


def _sha(b: bytes | str) -> str:
    return hashlib.sha256(b.encode("utf-8") if isinstance(b, str) else b).hexdigest()


def _canon(doc) -> str:
    return json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _resolved_text(record, locator_mod, rr):
    if rr.get("external"):
        v = record.get(rr["locator"])
    else:
        v = locator_mod.resolve(record, rr["locator"])
    if isinstance(v, str):
        return v
    if isinstance(v, list) and all(isinstance(p, dict) for p in v):
        return "".join(p.get("text", "") for p in v if p.get("type") == "text")
    return json.dumps(v, ensure_ascii=False, default=str)


def validate(body: str, record: dict, raw_bytes: bytes, *, fixture: dict | None = None) -> list[str]:
    from agent.deep_agent import _semantic_adapter as adapter, _semantic_locator as locator_mod
    from agent.deep_agent._semantic_verify import verify

    errs: list[str] = []
    e = errs.append
    try:
        m = json.loads(body)
    except json.JSONDecodeError as x:
        return [f"not JSON: {x}"]
    if re.search(r"/(?:Users|home)/[^/\s\"']+/", body):
        e("an absolute home-directory path appears in the matrix data")
    if body != _canon(m):
        e("bytes are not the canonical serialization (sorted keys, compact separators, trailing newline)")
    missing = [k for k in REQUIRED if k not in m]
    if missing:
        return errs + [f"missing keys: {missing}"]
    if m["contract"] != CONTRACT:
        e(f"contract {m['contract']!r} != {CONTRACT!r}")
    bad = [k for k in FORBIDDEN if k in m]
    if bad:
        e(f"semantic objects present at top level: {bad}")
    s = m["semantic"]
    if s.get("claims_extracted") is not False or s.get("claims") or s.get("propositions") or s.get("states"):
        e(f"semantic block must record no extracted claims, propositions or states: {s}")

    raw_sha = _sha(raw_bytes)
    if m["provenance"].get("raw_trace_sha256") != raw_sha:
        e("provenance.raw_trace_sha256 does not match the trace")
    doc = adapter.adapt(record, trace_ref=m["provenance"].get("raw_trace", "trace"), trace_sha256=raw_sha)
    v_errs = verify(doc, record, trace_sha256=raw_sha)
    if v_errs:
        return errs + [f"verifier: {x}" for x in v_errs[:20]]
    sem, pl = doc["semantic"], doc["profile_local"]
    ad = pl["adapter"]

    run = m["run"]
    err = record.get("error")
    if (err is None) != (run.get("error") is None):
        e("run.error presence differs from the record")
    elif isinstance(err, dict) and isinstance(run.get("error"), dict) and "traceback" in run["error"]:
        e("run.error must not carry the traceback")
    if run.get("status") != record.get("status"):
        e("run.status differs from the record")
    if run.get("record_run_id") != record.get("run_id"):
        e("run.record_run_id differs from the record")
    last = max(record.get("events") or [{"seq": None, "type": None}], key=lambda r: r["seq"] if r["seq"] is not None else -1)
    if run.get("terminal_event") != {"seq": last["seq"], "type": last["type"]}:
        e("run.terminal_event is not the record's last event")
    if m["telemetry"].get("delivery") != ad["delivery_telemetry"] or m["telemetry"].get("offered_tools") != ad["offered_tools_telemetry"]:
        e("telemetry flags differ from the adapter")

    want_rows = [f"agent:{a['agent_id']}" for a in record.get("agents") or []]
    if [r.get("id") for r in m["rows"]] != want_rows:
        e(f"rows {[r.get('id') for r in m['rows']]} != record agents {want_rows}")

    model = sorted((x for x in sem["events"] if x["id"].startswith("ev:llm:")), key=lambda x: x["order"])
    cols = m["columns"]
    if [c.get("id") for c in cols] != [x["id"] for x in model]:
        return errs + ["columns are not exactly the adapter's model events in observation order"]
    by_src: dict = {}
    for l in sem["links"]:
        by_src.setdefault(l["source"], []).append(l)
    seen: dict = {}
    model_ids = {x["id"] for x in model}
    ov: dict = {}
    for a, b in pl["order"]["overlaps"]:
        if a in model_ids and b in model_ids:
            ov.setdefault(a, set()).add(b)
            ov.setdefault(b, set()).add(a)
    order_of = {x["id"]: x["order"] for x in sem["events"]}
    issued: dict = {}
    for x in sem["events"]:
        at = x["raw_ref"].get("issued_at") or ""
        if at.startswith("events[seq="):
            issued.setdefault(int(at[len("events[seq="):at.index("]")]), []).append(x["id"])
    referenced = set()
    for c, x in zip(cols, model):
        cid = x["id"]
        rr = x["raw_ref"]
        if (c["order"], c["start_seq"], c["end_seq"]) != (x["order"], rr["start_seq"], rr["end_seq"]):
            e(f"{cid}: order/start/end differ from the adapter")
        if isinstance(x["origin"], str):
            if c["row"] != x["origin"] or c["origin"] != x["origin"]:
                e(f"{cid}: row/origin {c['row']!r} != adapter origin {x['origin']!r}")
            if c["row"] not in want_rows:
                e(f"{cid}: row {c['row']!r} is not an agent of the record")
        else:
            if c["row"] != "$unresolved" or c["origin"] != x["origin"]:
                e(f"{cid}: unresolved origin not preserved")
        links = by_src.get(cid, [])
        if c["delivers"] != [l["target"] for l in links]:
            e(f"{cid}: delivers differ from the adapter links of this event")
        if ad["delivery_telemetry"] == "absent" and c["delivers"]:
            e(f"{cid}: deliveries listed although delivery telemetry is absent")
        first = []
        if isinstance(x["origin"], str):
            got = seen.setdefault(x["origin"], set())
            for l in links:
                if l["target"] not in got:
                    got.add(l["target"])
                    first.append([l["target"], l["raw_ref"]["locator"]])
        if c["first_delivered_here"] != first:
            e(f"{cid}: first_delivered_here does not recompute")
        if c["delegation_input"] != [l["target"] for l in links if "delegation_id" in (l["raw_ref"].get("join") or {})]:
            e(f"{cid}: delegation_input does not recompute")
        want_dlg = sorted(v["id"] for v in sem["evidence"] if v.get("produced_by") == cid and v["raw_ref"].get("tool") == "task")
        if c["issued_delegations"] != want_dlg:
            e(f"{cid}: issued_delegations do not recompute")
        if c["issued_tool_events"] != sorted(issued.get(max(rr["seq"]), []), key=lambda i: order_of[i]):
            e(f"{cid}: issued_tool_events do not recompute")
        if c["overlaps_with"] != sorted(ov.get(cid, ()), key=lambda i: order_of[i]):
            e(f"{cid}: overlaps_with does not recompute")
        referenced.update(t for t, _ in first)
        referenced.update(want_dlg)

    ev = m["evidence"]
    if set(ev) != referenced:
        e(f"evidence map must hold exactly the referenced items ({len(referenced)}), has {len(ev)}")
    adapter_ev = {v["id"]: v for v in sem["evidence"]}
    for xid, item in ev.items():
        src = adapter_ev.get(xid)
        if src is None:
            e(f"{xid}: not adapter evidence")
            continue
        if item.get("raw_ref", {}).get("locator") != src["raw_ref"]["locator"] or item.get("source") != src["source"]:
            e(f"{xid}: locator or source differs from the adapter")
        try:
            text = _resolved_text(record, locator_mod, src["raw_ref"])
        except Exception as x:  # noqa: BLE001
            if item.get("excerpt") is not None:
                e(f"{xid}: locator does not resolve ({x}) but an excerpt is present")
            continue
        if item.get("excerpt") != text[:LIMIT] or item.get("excerpt_complete") != (len(text) <= LIMIT):
            e(f"{xid}: excerpt is not the first {LIMIT} characters of the resolved text, or its completeness flag is wrong")

    want_other = {x["id"] for x in sem["events"] if x["id"] not in model_ids}
    if set(m["other_events"]) != want_other:
        e("other_events are not exactly the adapter's non-model events")

    per_row = {r: sum(c["row"] == r for c in cols) for r in want_rows}
    per_row["$unresolved"] = sum(c["row"] == "$unresolved" for c in cols)
    counts = m["counts"]
    if counts.get("model_calls") != len(cols) or counts.get("per_row") != per_row or counts.get("delivers") != len(sem["links"]):
        e("counts do not recompute")
    if [a["id"] for a in m["ambiguities"]] != [a["id"] for a in pl["ambiguities"]]:
        e("ambiguities differ from the adapter")

    fl = m["fixture_links"]
    if fixture is None:
        if fl or m["provenance"].get("fixture") is not None:
            e("fixture links present without a fixture")
    else:
        fsem = fixture.get("semantic", fixture)
        want = [l for l in fsem.get("links", []) if l.get("relation") == "delivers"]
        if len(fl) != len(want):
            e(f"fixture links {len(fl)} != fixture delivers {len(want)}")
        for f, l in zip(fl, want):
            hits = [x for x in sem["links"] if x["raw_ref"]["locator"] == l["raw_ref"]["locator"] and x["raw_ref"].get("sha256") == l["raw_ref"].get("sha256")]
            if len(hits) != 1 or f.get("adapter_link") != [hits[0]["source"], hits[0]["target"]] or f.get("fixture_target") != l["target"]:
                e(f"fixture link {l['source']} -> {l['target']} is not reproduced as recorded")
    return errs


def _resolve(display: str, worktree: Path) -> Path:
    return worktree / display[len("worktree:"):] if display.startswith("worktree:") else AP_ROOT / display


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--matrix", type=Path)
    ap.add_argument("--trace", type=Path)
    ap.add_argument("--fixture", type=Path)
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--worktree", type=Path, default=AP_ROOT.parent / "AssetOpsBench-agenttrace-spec")
    args = ap.parse_args(argv)
    jobs = []
    if args.manifest:
        man = json.loads(args.manifest.read_text(encoding="utf-8"))
        for r in man["runs"]:
            body = (args.manifest.parent / r["file"]).read_text(encoding="utf-8")
            if _sha(body) != r["sha256"]:
                print(f"FAIL {r['run_id']}: file sha256 does not match the manifest")
                return 1
            m = json.loads(body)
            fx = m["provenance"].get("fixture")
            jobs.append((r["run_id"], body, AP_ROOT / m["provenance"]["raw_trace"], _resolve(fx["path"], args.worktree) if fx else None))
    else:
        jobs.append((args.matrix.name, args.matrix.read_text(encoding="utf-8"), args.trace, args.fixture))
    failed = 0
    for name, body, trace, fixture_path in jobs:
        raw = trace.read_bytes()
        fixture = json.loads(fixture_path.read_bytes()) if fixture_path else None
        problems = validate(body, json.loads(raw), raw, fixture=fixture)
        failed += bool(problems)
        print(f"{'OK  ' if not problems else 'FAIL'} {name}" + "".join(f"\n  - {p}" for p in problems[:25]))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
