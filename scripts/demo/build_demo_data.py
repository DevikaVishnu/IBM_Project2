"""Build the read-only demo data for the AgentTrace demo view (runs 621 and 620-fileobs).

No model, network or database.  Reads the raw instrumented traces (never writes them), runs the
deterministic structural adapter and the agenttrace.compare/0.1 operations from the AssetOpsBench
specialist worktree, and copies the hand-grounded comparison fixtures unchanged.  Nothing semantic
is derived here: claims, propositions, states and direct links come only from the fixtures.

Run with the worktree's interpreter, from the AP root:

    env -u OTEL_TRACES_FILE PYTHONPATH=<worktree>/src <worktree>/.venv/bin/python \
        scripts/demo/build_demo_data.py --worktree <worktree>

Writes src/demo/data/<run>.demo.json.  Output is deterministic (no timestamps).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

AP_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_REL = "src/agent/deep_agent/tests/fixtures/agenttrace_compare_0_1"
OUT_DIR = AP_ROOT / "src/demo/data"
SCHEMA_SHA = "2273d210090d19c17f75e98bb06875e0c55ef10b9c26528ea2471cee25c01c06"
EXCERPT = 800  # display-only head excerpt for long tool results

RUNS = {
    "aob-621": {"fixture": "aob-621-compare", "role": "positive control"},
    "aob-620f": {"fixture": "aob-620-compare", "role": "abstention control"},
}


def sha(data: bytes | str) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def as_text(value, text_form):
    if text_form == "content_list_text":
        return "".join(p.get("text", "") for p in value if isinstance(p, dict) and p.get("type") == "text")
    return value


def subset(expected, actual) -> bool:
    """True if every key and value in expected is present, equal, in actual (lists compared item by item)."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and subset(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(map(subset, expected, actual))
    return expected == actual


def build(key: str, spec: dict, wt: Path, adapter, compare, locator) -> dict:
    fdir = wt / FIXTURE_REL
    trace_bytes = (fdir / f"{spec['fixture']}.trace.json").read_bytes()
    exp_bytes = (fdir / f"{spec['fixture']}.expected.json").read_bytes()
    fx, expected = json.loads(trace_bytes), json.loads(exp_bytes)
    sem = fx["semantic"]
    raw_path = AP_ROOT / sem["run"]["raw_ref"]["trace"]
    raw_bytes = raw_path.read_bytes()
    raw_sha = sha(raw_bytes)
    if raw_sha != sem["run"]["raw_ref"]["trace_sha256"]:
        sys.exit(f"{raw_path}: sha256 {raw_sha} does not match the fixture")
    if sha((AP_ROOT / "docs/agenttrace.semantic.0.3.md").read_bytes()) != SCHEMA_SHA:
        sys.exit("schema 0.3 sha256 does not match")
    rec = json.loads(raw_bytes)

    # Raw observation: the text of each fixture evidence item, resolved and hash-checked.
    texts, display = {}, {}
    for item in sem["evidence"]:
        rr = item["raw_ref"]
        text = as_text(locator.resolve(rec, rr["locator"]), rr.get("text_form"))
        if sha(text) != rr["text_sha256"]:
            sys.exit(f"{item['id']}: resolved text does not match text_sha256")
        texts[item["id"]] = text
        full = item["source"] == "agent" or len(text) <= 2 * EXCERPT
        display[item["id"]] = {"text": text if full else text[:EXCERPT], "complete": full,
                               "length": len(text), "text_sha256": rr["text_sha256"], "verified": True}

    # Deterministic structural layer: the adapter on the raw trace.
    doc = adapter.adapt(rec, trace_ref=sem["run"]["raw_ref"]["trace"], trace_sha256=raw_sha)
    a_events = doc["semantic"]["events"]
    a_links = doc["semantic"]["links"]
    by_start = {e["raw_ref"].get("start_seq", e["order"]): e for e in a_events}
    timeline = []
    for e in a_events:
        rr = e["raw_ref"]
        kind = e["id"].split(":")[1]
        timeline.append({
            "id": e["id"], "kind": {"llm": "model_call", "tool": "tool_call", "evict": "framework_eviction"}.get(kind, kind),
            "origin": e["origin"] if isinstance(e["origin"], str) else "$unresolved",
            "order": e["order"], "start_seq": rr.get("start_seq", e["order"]), "end_seq": rr.get("end_seq", max(rr["seq"])),
            "seq": rr["seq"], "tool_call_id": rr.get("tool_call_id"),
            "origin_basis": (rr.get("origin_basis") or {}).get("label"),
            "origin_rule": (rr.get("origin_basis") or {}).get("rule"),
            "delivers_in": sum(1 for l in a_links if l["source"] == e["id"]),
        })
    # Fixture event -> adapter event: same first raw seq and, for tool calls, the same tool_call_id.
    raw_type = {r["seq"]: r["type"] for r in rec["events"]}
    event_map, event_map_notes = {}, {}
    for e in sem["events"]:
        a = by_start.get(min(e["raw_ref"]["seq"]))
        if a and a["raw_ref"].get("tool_call_id") == e["raw_ref"].get("tool_call_id"):
            event_map[e["id"]] = a["id"]
            extra = sorted(set(e["raw_ref"]["seq"]) - set(a["raw_ref"]["seq"]))
            if extra:
                event_map_notes[e["id"]] = (
                    "The fixture's raw_ref also cites " + ", ".join(f"{s} ({raw_type.get(s)})" for s in extra)
                    + "; the adapter does not make file records part of a tool event.")
    reproduced = []
    for l in sem["links"]:
        if l["relation"] != "delivers":
            continue
        src = event_map.get(l["source"])
        hit = next((x for x in a_links if x["source"] == src and x["raw_ref"]["locator"] == l["raw_ref"]["locator"]
                    and x["raw_ref"].get("sha256") == l["raw_ref"].get("sha256")), None)
        reproduced.append({"fixture_link": [l["source"], l["target"]], "adapter_event": src,
                           "adapter_link": [hit["source"], hit["target"]] if hit else None, "reproduced": hit is not None})

    # Comparison results: computed by agenttrace.compare/0.1, checked against the hand-written expectations.
    comp = compare.Comparator(sem, fx["profile_local"], texts)
    results = []
    for entry in expected["entries"]:
        inp = entry["inputs"]
        if entry["rule"] == "O2":
            got = comp.exposure_at(inp["event"], inp["item"], inp.get("spans"))
        elif entry["rule"] == "claim_delivery":
            got = comp.claim_delivery(inp["event"], inp["claim"])
        elif entry["rule"] == "O3":
            got = comp.state_vs_evidence(inp["state"])
        else:
            continue
        results.append({"rule": entry["rule"], "inputs": inp, "computed": got, "expected": entry["expected"],
                        "basis": entry.get("basis"), "note": entry.get("note"),
                        "matches_expected": subset(entry["expected"], got)})

    head = subprocess.run(["git", "-C", str(wt), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    return {
        "demo_data": "agenttrace-demo/0.1",
        "run_key": key,
        "role": spec["role"],
        "provenance": {
            "raw_trace": sem["run"]["raw_ref"]["trace"], "raw_trace_sha256": raw_sha,
            "schema": "agenttrace.semantic/0.3", "schema_sha256": SCHEMA_SHA,
            "fixture": f"{FIXTURE_REL}/{spec['fixture']}.trace.json", "fixture_sha256": sha(trace_bytes),
            "expected": f"{FIXTURE_REL}/{spec['fixture']}.expected.json", "expected_sha256": sha(exp_bytes),
            "adapter": f"{doc['profile']} increment {doc['profile_local']['adapter']['increment']}",
            "compare": compare.PROFILE, "worktree_head": head,
        },
        "fixture": {"semantic": sem, "profile_local": fx["profile_local"]},
        "texts": display,
        "structural": {"timeline": timeline, "event_map": event_map, "event_map_notes": event_map_notes, "delivers_reproduced": reproduced,
                       "counts": doc["profile_local"]["adapter"]["counts"],
                       "overlaps": len(doc["profile_local"]["order"]["overlaps"]),
                       "order_caveat": doc["profile_local"]["order"]["caveat"],
                       "delivery_status": next((l["raw_ref"].get("evidence_status") for l in a_links), None)},
        "comparison": results,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", default=str(AP_ROOT.parent / "AssetOpsBench-agenttrace-spec"))
    wt = Path(ap.parse_args().worktree).resolve()
    from agent.deep_agent import _semantic_adapter as adapter, _semantic_compare as compare, _semantic_locator as locator

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for key, spec in RUNS.items():
        out = build(key, spec, wt, adapter, compare, locator)
        path = OUT_DIR / f"{key}.demo.json"
        path.write_text(json.dumps(out, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        ok = all(r["matches_expected"] for r in out["comparison"]) and all(r["reproduced"] for r in out["structural"]["delivers_reproduced"])
        print(f"{path.relative_to(AP_ROOT)}: {len(out['structural']['timeline'])} events, "
              f"{len(out['comparison'])} comparison results, all checks {'PASS' if ok else 'FAIL'}")
        if not ok:
            sys.exit(1)


if __name__ == "__main__":
    main()
