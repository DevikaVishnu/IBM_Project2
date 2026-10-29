"""Build Belief Explorer trace bundles (contract agenttrace-explorer-bundle/0.1, src/explorer/CONTRACT.md).

    WT=../AssetOpsBench-agenttrace-spec
    env -u OTEL_TRACES_FILE PYTHONPATH=$WT/src $WT/.venv/bin/python scripts/explorer/build_bundle.py [--only <trace-id>]

Local only.  No model, network or database; raw traces and the MAST file are only read.

Per AssetOpsBench run: the frozen structural adapter and the verifier run on the raw instrumented trace
(the adapter counts must equal the expected counts and the verifier must report 0 errors, else the build
stops); the agent x model-call grid is taken from the validated agenttrace-matrix/0.2 file built by
scripts/demo/build_matrix.py (sha-checked against its manifest); the hand annotations come from a
separate file (src/explorer/annotations/<trace>.json) and are never mixed into adapter output.  Every
annotated value is checked against the raw trace (the "contains" strings must occur), and where an O3
result is computable it is computed by agenttrace.compare/0.1 over the adapter output plus the
hand-annotated links.

Gomoku (MAST index 7) has no adapter: its skeleton is hand-reconstructed from schema §14, and every cited
log line is checked against the dataset.

Writes src/explorer/data/<trace>.bundle.json and src/explorer/data/index.json (manifest with sha256).
Exit code 1 on any mismatch, with the reason; nothing is written for the failing trace.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

AP_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AP_ROOT / "scripts/demo"))
from build_matrix import canonical, sha, text_of  # noqa: E402  (reused, unchanged)

CONTRACT = "agenttrace-explorer-bundle/0.1"
ANNOTATION_FORMAT = "agenttrace-explorer-annotation/0.1"
OUT_DIR = AP_ROOT / "src/explorer/data"
ANN_DIR = AP_ROOT / "src/explorer/annotations"
MATRIX_DIR = AP_ROOT / "src/demo/data/matrices"
SCHEMA = AP_ROOT / "docs/agenttrace.semantic.0.3.md"
SCHEMA_SHA = "2273d210090d19c17f75e98bb06875e0c55ef10b9c26528ea2471cee25c01c06"
FIXTURE_REL = "src/agent/deep_agent/tests/fixtures/agenttrace_compare_0_1"
HAND = "hand-annotated, illustrative, not gold"
WINDOW = 140  # display excerpt: characters kept around each annotated span

AOB = {
    "aob-621": {
        "label": "Run 621 · single agent",
        "raw": "data/assetopsbench/runs/aob-621-sonnet5-deep-fileobs-20261013.instrumented.json",
        "sha256": "aa8531f2b9771397ecd539fc0bbef8f6da8cfbe681a53fee59b557c3c55c74cd",
        "matrix": "aob-621",
        "expected": {"entities": 21, "events": 61, "evidence": 127, "delivers": 1454},
    },
    "aob-sc3-B": {
        "label": "Scenario 3 · condition B · root + helper",
        "raw": "data/assetopsbench/runs/aob-sc3-sonnet5-deep-spec-B-20261014.instrumented.json",
        "sha256": "4d5759091df0e9bc800f209ff4cffca916a33b06b1441ee086cbf1585c339386",
        "matrix": "aob-sc3-B",
        "expected": {"entities": 24, "events": 159, "evidence": 268, "delivers": 4713},
    },
}
GOMOKU = {"label": "Gomoku · ChatDev (MAST #7)", "raw": "data/mast/MAD_full_dataset.json",
          "sha256": "d636ac63dfc1c6af2d312e862f4b7d383b62d3898d431ccd0e7a79d21d85406f", "index": 7}


class Mismatch(Exception):
    pass


# Stage-by-stage report printed by main() (readable when the build is run live).
REPORT: list[tuple[str, str]] = []
CHECKED = [0]  # annotated values found verbatim in the source


def say(stage: str, msg: str) -> None:
    REPORT.append((stage, msg))


def plural(n: int, word: str) -> str:
    return f"{n:,} {word}" if n == 1 else f"{n:,} {word}s"

# Which claim the "How it's built" walkthrough follows, per trace.
WALKTHROUGH = {"aob-621": "clm:621:june10-sequence"}
WALKTHROUGH_NOTE = "Every other claim follows the same path; the Gomoku skeleton is hand-reconstructed instead of adapter-generated."
RECORD_FIELDS = ("type", "agent_id", "tool", "tool_call_id", "path", "offset", "limit", "window_size", "output_size", "size", "status",
                 "n_input_messages", "differs_from_raw")


def need(cond, msg):
    if not cond:
        raise Mismatch(msg)


def rel(p: Path) -> str:
    p = p.resolve()
    return p.relative_to(AP_ROOT).as_posix() if p.is_relative_to(AP_ROOT) else p.name


def find_one(text: str, needle: str, what: str) -> list[int]:
    """Code-point span of the single occurrence of needle in text."""
    hits = [m.start() for m in re.finditer(re.escape(needle), text)]
    need(len(hits) == 1, f"{what}: expected exactly one occurrence of {needle!r}, found {len(hits)}")
    CHECKED[0] += 1
    return [hits[0], hits[0] + len(needle)]


def window(text: str, spans: list[list[int]]) -> dict:
    """Display excerpt around the spans, with the spans re-based into the excerpt."""
    if not spans:
        return {"text": text[:300], "start": 0, "complete": len(text) <= 300, "to_end": len(text) <= 300, "spans": []}
    lo = max(0, min(s for s, _ in spans) - WINDOW)
    hi = min(len(text), max(e for _, e in spans) + WINDOW)
    return {"text": text[lo:hi], "start": lo, "complete": lo == 0 and hi == len(text), "to_end": hi == len(text), "spans": [[s - lo, e - lo] for s, e in spans]}


def subset(expected, actual) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and subset(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(map(subset, expected, actual))
    return expected == actual


MEANING = {
    "AGREES": "The stored direct evidence gives the same value as the state the claim expresses.",
    "DIFFERS_FROM_DIRECT": "The stored direct evidence gives the opposite value to the state the claim expresses.",
    "UNKNOWN": "No stored direct link settles the proposition, so there is no comparison (not a contradiction).",
    "UNRESOLVED": "An input to the comparison is unresolved in the trace.",
    "AMBIGUOUS": "The stored direct links point both ways.",
    "NOT_APPLICABLE": "The state is not TRUE or FALSE (e.g. UNCERTAIN), so it is not compared with the evidence.",
}


def o3_summary(res: dict) -> dict:
    return {"status": "computed", "origin": "computed", "computed_from": "hand-annotated links",
            "operation": "agenttrace.compare/0.1 state_vs_evidence (O3)",
            "comparison": res["comparison"], "direct": res["direct"]["value"],
            "delivered_direct": res["delivered_direct"]["value"], "testimonial": res["testimonial"]["value"],
            "meaning": MEANING.get(res["comparison"], ""), "raw": res}


# --------------------------------------------------------------------------------------------- AOB


def build_aob(tid: str, cfg: dict, wt: Path, mods) -> dict:
    adapter, verify, locator, compare = mods
    raw_path = AP_ROOT / cfg["raw"]
    need(raw_path.exists(), f"{cfg['raw']} is missing (local-only; see docs/DATA.md §3)")
    raw_bytes = raw_path.read_bytes()
    raw_sha = sha(raw_bytes)
    need(raw_sha == cfg["sha256"], f"{cfg['raw']}: sha256 {raw_sha} does not match docs/DATA.md")
    need(sha(SCHEMA.read_bytes()) == SCHEMA_SHA, "schema 0.3 sha256 changed")
    rec = json.loads(raw_bytes)
    say("trace read", f"{Path(cfg['raw']).name}: {len(rec['events']):,} records, {len(raw_bytes):,} bytes, sha256 {raw_sha[:12]}… matches docs/DATA.md")

    # 1. Frozen adapter + verifier; counts must match exactly.
    doc = adapter.adapt(rec, trace_ref=cfg["raw"], trace_sha256=raw_sha)
    errors = verify(doc, rec, trace_sha256=raw_sha)
    need(not errors, f"verifier reported {len(errors)} error(s): {errors[:3]}")
    sem, pl = doc["semantic"], doc["profile_local"]
    counts = {"entities": len(sem["entities"]), "events": len(sem["events"]), "evidence": len(sem["evidence"]),
              "delivers": sum(l["relation"] == "delivers" for l in sem["links"])}
    need(counts == cfg["expected"], f"adapter counts {counts} != expected {cfg['expected']}")
    say("adapter", f"{counts['entities']} entities, {counts['events']} events, {counts['evidence']} evidence items, {counts['delivers']:,} delivers links (= expected)")
    say("verifier", "0 errors")
    events = {e["id"]: e for e in sem["events"]}
    evidence = {x["id"]: x for x in sem["evidence"]}
    raw_events = {e["seq"]: e for e in rec["events"]}
    model = sorted((e for e in sem["events"] if e["id"].startswith("ev:llm:")), key=lambda e: e["order"])
    delivers = defaultdict(set)
    for l in sem["links"]:
        if l["relation"] == "delivers":
            delivers[l["source"]].add(l["target"])

    def text(xid):
        rr = evidence[xid]["raw_ref"]
        return rec.get(rr["locator"]) if rr.get("external") else text_of(locator.resolve(rec, rr["locator"]))

    def issuer(tool_event_id):
        m = re.match(r"^events\[seq=(\d+)\]", events[tool_event_id]["raw_ref"].get("issued_at") or "")
        return next((e for e in model if m and max(e["raw_ref"]["seq"]) == int(m.group(1))), None)

    def origin_of(e):
        return e["origin"] if isinstance(e["origin"], str) else "$unresolved"

    def receivers(xid):
        return [e for e in model if xid in delivers.get(e["id"], ())]

    # 2. Validated matrix file (agenttrace-matrix/0.2), sha-checked against its manifest.
    manifest = json.loads((MATRIX_DIR / "index.json").read_text(encoding="utf-8"))
    entry = next((r for r in manifest["runs"] if r["run_id"] == cfg["matrix"]), None)
    need(entry is not None, f"matrix {cfg['matrix']} is not in {rel(MATRIX_DIR / 'index.json')}; build it with scripts/demo/build_matrix.py")
    mbody = (MATRIX_DIR / entry["file"]).read_text(encoding="utf-8")
    need(sha(mbody) == entry["sha256"], f"{entry['file']} does not match its manifest sha256")
    m = json.loads(mbody)
    need(m["contract"] == "agenttrace-matrix/0.2", "matrix contract is not agenttrace-matrix/0.2")
    need(m["provenance"]["raw_trace_sha256"] == raw_sha, "matrix was built from a different trace")
    need([c["id"] for c in m["columns"]] == [e["id"] for e in model], "matrix columns differ from the adapter's model events")

    ann_path = ANN_DIR / f"{tid}.json"
    ann = json.loads(ann_path.read_text(encoding="utf-8")) if ann_path.exists() else None
    if ann is not None:
        need(ann.get("annotation_format") == ANNOTATION_FORMAT and ann.get("trace_id") == tid, f"{rel(ann_path)}: wrong format or trace id")

    # 3. Skeleton (observed events; agent origin as the adapter assigns it).
    rows = [{"id": r["id"], "label": r["agent_id"], "sub": " · ".join(x for x in (r["kind"], r["name"]) if x), "kind": "agent",
             "parent": f"agent:{r['parent_agent_id']}" if r.get("parent_agent_id") else None, "status": r.get("status"), "origin": "observed"}
            for r in m["rows"]]
    if any(c["row"] == "$unresolved" for c in m["columns"]):
        rows.append({"id": "$unresolved", "label": "unresolved", "sub": "agent origin not established", "kind": "unresolved", "parent": None, "origin": "unresolved"})
    sk_events = []
    for e in sorted(sem["events"], key=lambda e: e["order"]):
        rr = e["raw_ref"]
        kind = {"llm": "model_call", "tool": "tool_call", "evict": "framework_eviction"}[e["id"].split(":")[1]]
        agent = origin_of(e)
        if kind == "tool_call":
            iss = issuer(e["id"])
            agent = origin_of(iss) if iss else "$unresolved"
        sk_events.append({"id": e["id"], "kind": kind, "order": e["order"], "steps": [min(rr["seq"]), max(rr["seq"])],
                          "agent": agent, "label": e["origin"].split(":", 1)[1] if isinstance(e["origin"], str) and kind != "model_call" else ("model call" if kind == "model_call" else "unresolved"),
                          "origin": "unresolved" if not isinstance(e["origin"], str) else "observed"})

    # 4. Grid from the matrix file, plus delegation edges (same rule as the matrix view).
    col_by = {c["id"]: c for c in m["columns"]}
    edges = []
    for c in m["columns"]:
        for t, _ in c["first_delivered_here"]:
            if t in c["delegation_input"]:
                src = col_by.get(m["evidence"].get(t, {}).get("produced_by"))
                if src and not any(x["from"] == src["id"] and x["to"] == c["id"] for x in edges):
                    edges.append({"from": src["id"], "to": c["id"], "via": "delegation_id join", "item": t, "origin": "computed"})
    received = {x["to"] for x in edges}
    tool_name = lambda t: m["other_events"].get(t, {}).get("origin", "").split(":", 1)[-1]  # noqa: E731
    columns = [{"id": c["id"], "order": c["order"], "row": c["row"], "steps": [c["start_seq"], c["end_seq"]],
                "delivers": len(c["delivers"]), "first": len(c["first_delivered_here"]),
                "delegation_out": bool(c["issued_delegations"]), "delegation_in": c["id"] in received,
                "overlaps": len(c["overlaps_with"]), "tools": [tool_name(t) for t in c["issued_tool_events"]],
                "origin": "unresolved" if c["row"] == "$unresolved" else "observed"} for c in m["columns"]]
    single = len(m["rows"]) == 1
    grid = {"origin": "computed", "source_contract": "agenttrace-matrix/0.2", "axis": "model calls in observation order",
            "rows": rows, "columns": columns, "edges": edges, "delivery_track": m["telemetry"]["delivery"] == "present",
            "max_delivers": max([c["delivers"] for c in columns] or [0]), "overlays": [],
            "note": ("Single-agent trace: one row. The interaction matrix is most informative for multi-agent traces." if single else None),
            "order_caveat": m["order_caveat"]}

    # 5. Evidence entries used by the annotation layer (observed text, windowed).
    ev_out: dict = {}

    def add_evidence(xid, spans=()):
        need(xid in evidence, f"{tid}: evidence {xid} is not in the adapter output")
        x = evidence[xid]
        rr = x["raw_ref"]
        t = text(xid)
        prod = events.get(x.get("produced_by") or "", {})
        cur = ev_out.get(xid)
        allspans = sorted({tuple(s) for s in list(spans) + ([tuple(s) for s in cur["_spans"]] if cur else [])})
        ev_out[xid] = {"id": xid, "step": rr.get("seq"), "tool": rr.get("tool") or (prod.get("origin", "").split(":", 1)[-1] if prod else None),
                       "kind": "tool_argument" if "argument" in rr else ("eviction_substitute" if xid.startswith("evi:evict_sub:") else ("question" if rr.get("external") else "tool_result")),
                       "source": x["source"] if isinstance(x["source"], str) else "$unresolved", "produced_by": x.get("produced_by"),
                       "locator": rr["locator"], "sha256": rr.get("sha256"), "size": rr.get("size"),
                       "excerpt": window(t, [list(s) for s in allspans]), "_spans": [list(s) for s in allspans],
                       "origin": "unresolved" if not isinstance(x["source"], str) else "observed"}
        return t

    say("matrix", f"{entry['file']} sha256 matches its manifest; {len(m['columns'])} model-call columns = adapter model events")
    claims, propositions, flags, facts, non_claims = [], [], [], [], []
    o3_ok = []
    if ann is not None:
        CHECKED[0] = 0
        claims, propositions, non_claims, o3_ok = aob_claims(tid, ann, rec, sem, evidence, events, locator, compare, add_evidence, wt, raw_events)
        flags, facts = aob_flags(tid, ann, rec, sem, m, model, events, evidence, delivers, receivers, issuer, origin_of, text, add_evidence, raw_events, claims)
        say("annotations checked", f"{plural(len(claims), 'claim')}, {plural(len(non_claims), 'non-claim')}, {plural(len(flags), 'flag')}; {plural(CHECKED[0], 'annotated value')} found verbatim in the raw trace")
        say("O3 results", o3_line(claims, o3_ok))
    else:
        say("annotations checked", "none (no annotation file)")

    # Tool results vs the next same-agent call (computed; shown on the dashboard).
    tr = {"total": 0, "reached_next_call": 0, "reached_as_substitute": 0, "no_later_call": [], "lost": []}
    for x in sem["evidence"]:
        if not x["id"].startswith("evi:tool_result:"):
            continue
        tr["total"] += 1
        iss = issuer(x["produced_by"])
        ag = origin_of(iss) if iss else None
        nxt = next((e for e in model if origin_of(e) == ag and e["order"] > x["raw_ref"]["seq"]), None)
        evict = next((e for e in sem["events"] if e["id"].startswith("ev:evict:") and e["raw_ref"].get("tool_call_id") == x["raw_ref"].get("tool_call_id")), None)
        subst = next((y["id"] for y in sem["evidence"] if evict and y.get("produced_by") == evict["id"]), None)
        if nxt is None:
            tr["no_later_call"].append(x["raw_ref"]["seq"])
        elif x["id"] in delivers.get(nxt["id"], ()):
            tr["reached_next_call"] += 1
        elif subst and subst in delivers.get(nxt["id"], ()):
            tr["reached_as_substitute"] += 1
        else:
            tr["lost"].append(x["id"])
    nl = tr["no_later_call"]
    text = (f"{tr['total']} adapter tool results: {tr['reached_next_call']} reached the next same-agent call whole, "
            f"{tr['reached_as_substitute']} reached it only as a move-to-file substitute, "
            + (f"{len(nl)} (step {', '.join(map(str, nl))}) had no later call." if nl else "0 had no later call.")
            + (f" {len(tr['lost'])} did not reach the next same-agent call." if tr["lost"] else
               f" No tool result was lost within an agent; {tr['reached_as_substitute']} reached the model only as substitutes."))
    facts.append({"id": "fact:tool-results", "origin": "computed", "title": "Tool results reaching the next same-agent call", "text": text, "data": tr})
    if m["run"]["status"] != "ok":
        facts.append({"id": "fact:status", "origin": "observed", "title": "Run status",
                      "text": f"Run ended with status \"{m['run']['status']}\" ({(m['run'].get('error') or {}).get('type', '')}: {(m['run'].get('error') or {}).get('message', '')}); last record {m['run']['terminal_event']['type']} at step {m['run']['terminal_event']['seq']}."})

    for x in ev_out.values():
        x.pop("_spans", None)
    grid["overlays"] = overlays(claims, flags, columns, ann, model, events, issuer)
    walk = aob_walkthrough(WALKTHROUGH[tid], claims, sem, events, evidence, raw_events, receivers, compare) if tid in WALKTHROUGH and claims else None
    head = subprocess.run(["git", "-C", str(wt), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    return {
        "contract": CONTRACT,
        "trace": {"id": tid, "label": cfg["label"], "kind": "single-agent" if single else "multi-agent", "framework": "DeepAgents (AssetOpsBench)",
                  "model": m["run"]["model"], "scenario": m["run"]["scenario_id"], "status": m["run"]["status"],
                  "answer": (ann or {}).get("answer"),
                  "summary": None},
        "honesty": {"annotations": HAND if ann else "Not annotated",
                    "skeleton": "observed (raw trace) with agent origin and deliveries computed by the frozen structural adapter",
                    "rules": ["Delivered means byte-identical presence in a model call's rendered input, not use.",
                              "Non-delivery is shown as UNKNOWN unless coverage is established; it is never shown as confirmed.",
                              "Column order is observation order only: it implies no precedence, causation or belief persistence."]},
        "provenance": {"raw_trace": cfg["raw"], "raw_trace_sha256": raw_sha, "adapter": f"{doc['profile']} increment {pl['adapter']['increment']}",
                       "verifier": "agent.deep_agent._semantic_verify: 0 errors", "compare": compare.PROFILE, "worktree_head": head,
                       "schema_sha256": SCHEMA_SHA, "matrix_file": f"src/demo/data/matrices/{entry['file']}", "matrix_sha256": entry["sha256"],
                       "annotation_file": rel(ann_path) if ann else None, "annotation_sha256": sha(ann_path.read_bytes()) if ann else None,
                       "builder": "scripts/explorer/build_bundle.py"},
        "layers": {"skeleton": True, "matrix": True, "claims": bool(claims), "evidence": bool(ev_out), "delivery": m["telemetry"]["delivery"] == "present",
                   "o3": any(c.get("o3", {}).get("status") == "computed" for c in claims), "flags": bool(flags)},
        "skeleton": {"origin": "observed", "agents": rows, "events": sk_events, "handoffs": edges,
                     "counts": dict(counts, model_calls=len(model), tool_events=sum(e["kind"] == "tool_call" for e in sk_events),
                                    eviction_events=sum(e["kind"] == "framework_eviction" for e in sk_events),
                                    unresolved_origin_events=pl["adapter"]["counts"]["unresolved_origin_events"]),
                     "counts_origin": "computed", "skipped": [{"kind": s["kind"], "steps": s["seq"]} for s in pl["adapter"]["skipped"]]},
        "matrix": grid,
        "evidence": ev_out,
        "propositions": propositions,
        "claims": claims,
        "non_claims": non_claims,
        "flags": flags,
        "facts": facts,
        "checks": {"adapter_counts": counts, "verifier_errors": 0, "o3_matches_fixture": o3_ok},
        **({"walkthrough": walk} if walk else {}),
    }


def o3_line(claims, o3_ok=()):
    tally = defaultdict(int)
    for c in claims:
        o = c.get("o3") or {}
        tally[o.get("comparison") if o.get("status") == "computed" else o.get("status", "none")] += 1
    out = " · ".join(f"{k} {v}" for k, v in sorted(tally.items()))
    for x in o3_ok:
        out += f"; {x['claim']} matches the fixture's expected result" if x["matches_fixture_expected"] else f"; {x['claim']} DOES NOT match the fixture"
    return out


def aob_walkthrough(cid, claims, sem, events, evidence, raw_events, receivers, compare):
    """Data for the "How it's built" view: one claim followed from raw records to the screen.  Only record
    metadata (types, ids, sizes, offsets, hash prefixes) is added; the item text stays in bundle.evidence."""
    claim = next((c for c in claims if c["id"] == cid), None)
    need(claim is not None and claim["links"], f"walkthrough claim {cid} is missing or has no evidence link")
    rid = claim["links"][0]["evidence"]
    tool_ev = events[evidence[rid]["produced_by"]]
    rcv = receivers(rid)
    need(rcv and claim["event"] in {e["id"] for e in rcv}, f"walkthrough: {rid} is not delivered to the claiming call")
    first = rcv[0]
    lo, hi = min(tool_ev["raw_ref"]["seq"]), min(first["raw_ref"]["seq"])
    records = []
    for seq in range(lo, hi + 1):
        r = raw_events.get(seq)
        if r is None:
            continue
        rec = {"seq": seq, **{k: r[k] for k in RECORD_FIELDS if r.get(k) is not None}}
        for k in ("offset", "limit", "file_path"):
            if isinstance(r.get("args"), dict) and k in r["args"]:
                rec[f"args.{k}"] = r["args"][k]
        for k in ("sha256", "output_sha256", "window_sha256"):
            if r.get(k):
                rec[f"{k}_prefix"] = r[k][:12]
        records.append(rec)
    links = [l for l in sem["links"] if l["relation"] == "delivers" and l["target"] == rid]
    rsha = evidence[rid]["raw_ref"].get("sha256")
    delivers = [{"event": l["source"], "locator": l["raw_ref"]["locator"],
                 "message_index": int(m.group(1)) if (m := re.search(r"input_batches\[0\]\[(\d+)\]", l["raw_ref"]["locator"])) else None,
                 "byte_identical": l["raw_ref"].get("sha256") == rsha} for l in links]
    need(all(d["byte_identical"] for d in delivers), "walkthrough: a delivers link is not byte-identical")
    comp = compare.Comparator(sem, {}, {})
    o2 = [{"event": e, "item": rid, "value": comp.exposure_at(e, rid)["whole_item"]} for e in dict.fromkeys([first["id"], claim["event"]])]
    say("walkthrough", f"{cid}: records {lo}–{hi}, {rid} delivered to {len(delivers)} calls (first {first['id']}), O2 at the claiming call {o2[-1]['value']}")
    return {"claim": cid, "evidence": rid, "tool_event": tool_ev["id"], "first_receiver": first["id"], "note": WALKTHROUGH_NOTE,
            "raw": {"origin": "observed", "steps": [lo, hi], "records": records},
            "adapter": {"origin": "computed", "delivers": delivers, "verifier_errors": 0},
            "comparator": {"origin": "computed", "operation": f"{compare.PROFILE} exposure_at (O2) and state_vs_evidence (O3)", "o2": o2}}


def answer_text(rec, locator, loc):
    return text_of(locator.resolve(rec, loc))


def aob_claims(tid, ann, rec, sem, evidence, events, locator, compare, add_evidence, wt, raw_events):
    claims, props, non_claims, o3_ok = [], [], [], []
    hand_evidence, hand_claims, hand_props, hand_states, hand_links = [], [], [], [], []
    texts = {}
    by_event_answer = {}
    ans = ann.get("answer")
    if ans:
        by_event_answer[ans["event"]] = (ans["step"], ans["locator"])
    fixture = None

    def answer_item(event_id, step, loc):
        iid = f"evi:hand:{tid}:out:{step}"
        if iid not in texts:
            texts[iid] = answer_text(rec, locator, loc)
            hand_evidence.append({"id": iid, "source": "agent", "produced_by": event_id, "raw_ref": {"seq": step, "locator": loc, "sha256": sha(texts[iid])}})
        return iid

    staged = []
    for c in ann["claims"]:
        if c.get("from_fixture"):
            fdir = wt / FIXTURE_REL
            fb = (fdir / f"{c['from_fixture']}.trace.json").read_bytes()
            fixture = json.loads(fb)
            expected = json.loads((fdir / f"{c['from_fixture']}.expected.json").read_text(encoding="utf-8"))
            fsem = fixture["semantic"]
            need(fsem["run"]["raw_ref"]["trace_sha256"] == sha((AP_ROOT / fsem["run"]["raw_ref"]["trace"]).read_bytes()), "fixture trace sha mismatch")
            fc = next(x for x in fsem["claims"] if x["id"] == c["fixture_claim"])
            fprop = next(p for p in fsem["propositions"] if p["id"] == fc["proposition"])
            fstate = next(s for s in fsem["states"] if fc["id"] in s["claims"])
            fev = next(x for x in fsem["evidence"] if x["id"] == fc["evidence"])
            step, loc = fev["raw_ref"]["seq"], fev["raw_ref"]["locator"]
            ev_event = next(e["id"] for e in sem["events"] if e["id"].startswith("ev:llm:") and max(e["raw_ref"]["seq"]) == step)
            iid = answer_item(ev_event, step, loc)
            need(texts[iid][fc["raw_ref"]["span"][0]:fc["raw_ref"]["span"][1]] == fc["raw_ref"]["text"], "fixture claim span does not resolve to its text")
            links = []
            for fl in fsem["links"]:
                if fl["relation"] in ("supported_by", "contradicted_by") and fl["source"] == fprop["id"]:
                    floc = next(x for x in fsem["evidence"] if x["id"] == fl["target"])["raw_ref"]
                    target = next(x["id"] for x in sem["evidence"] if x["raw_ref"]["locator"] == floc["locator"] and x["raw_ref"].get("sha256") == floc.get("sha256"))
                    links.append({"relation": fl["relation"], "evidence": target, "spans": fl["raw_ref"]["spans"], "grounds": fl["raw_ref"].get("grounds"), "fixture_target": fl["target"]})
            exp_o3 = next(e["expected"] for e in expected["entries"] if e["rule"] == "O3")
            # Fixture ids -> adapter / bundle ids, so the expected result can be compared exactly.
            idmap = {fl["fixture_target"]: fl["evidence"] for fl in links}
            idmap[fc["id"]] = c["id"]
            idmap.update({x["id"]: next(e["id"] for e in sem["events"] if e["id"].startswith("ev:llm:") and min(e["raw_ref"]["seq"]) == min(x["raw_ref"]["seq"]))
                          for x in fsem["events"] if ":llm:" in x["id"]})
            exp_s = json.dumps(exp_o3)
            for a, b in sorted(idmap.items(), key=lambda kv: -len(kv[0])):
                exp_s = exp_s.replace(json.dumps(a), json.dumps(b))
            exp_o3 = json.loads(exp_s)
            staged.append(dict(c, words=fc["raw_ref"]["text"], span=fc["raw_ref"]["span"], proposition=fprop["form"], prop_id=fprop["id"],
                               state=fstate["value"], links=links, event=ev_event, item=iid, origin="hand-annotated",
                               fixture={"file": f"worktree:{FIXTURE_REL}/{c['from_fixture']}.trace.json", "sha256": sha(fb), "claim": fc["id"]},
                               expected_o3=exp_o3))
            continue
        event = c.get("event") or ans["event"]
        step, loc = (c["step"], c["locator"]) if c.get("locator") else by_event_answer[event]
        iid = answer_item(event, step, loc)
        span = find_one(texts[iid], c["words"], f"{c['id']} words in step {step}")
        links = []
        for l in c.get("links", []):
            t = add_evidence(l["evidence"])
            spans = [find_one(t, s, f"{c['id']} evidence {l['evidence']}") for s in l.get("contains", [])]
            add_evidence(l["evidence"], spans)
            texts[l["evidence"]] = t
            links.append(dict(l, spans=spans))
        if c.get("also_in"):
            need(c["also_in"]["contains"] in json.dumps(raw_events[c["also_in"]["step"]], ensure_ascii=False), f"{c['id']}: step {c['also_in']['step']} does not contain {c['also_in']['contains']!r}")
        staged.append(dict(c, links=links, span=span, prop_id=f"prop:{c['id'][4:]}", event=event, item=iid, origin="hand-annotated"))

    for c in staged:
        hand_claims.append({"id": c["id"], "evidence": c["item"], "raw_ref": {"seq": int(c["item"].rsplit(":", 1)[1]), "span": c["span"], "text": c["words"]}, "proposition": c["prop_id"]})
        hand_props.append({"id": c["prop_id"], "form": c["proposition"]})
        hand_states.append({"proposition": c["prop_id"], "value": c["state"], "claims": [c["id"]]})
        for l in c["links"]:
            if l.get("rule_dependent"):
                continue
            hand_links.append({"relation": l["relation"], "source": c["prop_id"], "target": l["evidence"],
                               "raw_ref": {"seq": evidence[l["evidence"]]["raw_ref"]["seq"], "locator": evidence[l["evidence"]]["raw_ref"]["locator"], "spans": l["spans"]}})
            texts.setdefault(l["evidence"], None)

    for k, v in list(texts.items()):
        if v is None:
            texts[k] = text_of(locator.resolve(rec, evidence[k]["raw_ref"]["locator"]))
    slice_ = {"entities": copy.deepcopy(sem["entities"]), "events": copy.deepcopy(sem["events"]),
              "evidence": copy.deepcopy(sem["evidence"]) + hand_evidence, "claims": hand_claims, "propositions": hand_props,
              "states": hand_states, "links": [l for l in sem["links"] if l["relation"] == "delivers"] + hand_links}
    comp = compare.Comparator(slice_, {}, texts)

    for i, c in enumerate(staged):
        chain_links = []
        for l in c["links"]:
            t = add_evidence(l["evidence"], l.get("spans") or [])
            d = comp.exposure_at(c["event"], l["evidence"])["whole_item"]
            chain_links.append({"relation": l["relation"], "evidence": l["evidence"], "origin": "hand-annotated",
                                "rule_dependent": bool(l.get("rule_dependent")), "step_label": l.get("step_label"), "grounds": l.get("grounds"),
                                "values": [t[s:e] for s, e in (l.get("spans") or [])][:8],
                                "delivery": {"to_event": c["event"], "value": d, "origin": "computed", "operation": "O2 exposure_at (whole item)"}})
        if c.get("rule_dependent"):
            o3 = {"status": "rule-dependent", "origin": "hand-annotated", "reason": c["rule_dependent"]}
        else:
            try:
                res = comp.state_vs_evidence(i)
                o3 = o3_summary(res)
                if c.get("expected_o3") is not None:
                    ok = subset(c["expected_o3"], {k: res[k] for k in res})
                    need(ok, f"{c['id']}: computed O3 does not match the fixture's expected result")
                    o3_ok.append({"claim": c["id"], "matches_fixture_expected": ok})
                    o3["fixture_expected"] = c["expected_o3"]["comparison"]
            except compare.InvalidInput as e:
                o3 = {"status": "not computable", "origin": "computed", "reason": f"agenttrace.compare/0.1 rejects this state: {e}"}
        if c.get("hand_comparison"):
            o3["hand_comparison"] = c["hand_comparison"]
        ev = events[c["event"]]
        speaker = ev["origin"] if isinstance(ev["origin"], str) else "$unresolved"
        claims.append({"id": c["id"], "label": c["label"], "words": c["words"], "event": c["event"], "step": int(c["item"].rsplit(":", 1)[1]),
                       "span": c["span"], "speaker": speaker, "speaker_origin": "unresolved" if speaker == "$unresolved" else "computed",
                       "assertive": True, "origin": "hand-annotated", "proposition": c["prop_id"],
                       "state": {"value": c["state"], "origin": "hand-annotated"}, "links": chain_links, "o3": o3,
                       "notes": c.get("notes", []), "fixture": c.get("fixture")})
        props.append({"id": c["prop_id"], "form": c["proposition"], "origin": "hand-annotated", "links": [{"relation": l["relation"], "evidence": l["evidence"]} for l in c["links"]]})

    for nc in ann.get("non_claims", []):
        iid = answer_item(ans["event"], ans["step"], ans["locator"])
        span = find_one(texts[iid], nc["words"], f"non-claim {nc['label']}")
        non_claims.append({"label": nc["label"], "words": nc["words"], "event": ans["event"], "step": ans["step"], "span": span, "reason": nc["reason"], "origin": "hand-annotated"})
    return claims, props, non_claims, o3_ok


def aob_flags(tid, ann, rec, sem, m, model, events, evidence, delivers, receivers, issuer, origin_of, text, add_evidence, raw_events, claims):
    flags, facts = [], []
    ans = ann.get("answer")
    ans_text = answer_text_from(rec, ans) if ans else None
    order = {e["id"]: e["order"] for e in sem["events"]}
    for f in ann.get("flags", []):
        out = {"id": f["id"], "title": f["title"], "kind": f["kind"], "text": f["text"], "origin": "hand-annotated", "caveat": f.get("caveat"),
               "events": list(f.get("events", [])), "anchors": list(f.get("events", [])), "evidence": [], "computed": []}
        for e in f.get("evidence", []):
            t = add_evidence(e["evidence"])
            spans = [find_one(t, s, f"{f['id']} {e['evidence']}") for s in e.get("contains", [])]
            add_evidence(e["evidence"], spans)
            out["evidence"].append(e["evidence"])
        if f["kind"] == "delivered_not_mentioned":
            for e in f["evidence"]:
                hit = f["to_event"] in {x["id"] for x in receivers(e["evidence"])}
                need(hit, f"{f['id']}: {e['evidence']} is not delivered to {f['to_event']}")
                out["computed"].append({"origin": "computed", "text": f"{e['evidence']} (step {evidence[e['evidence']]['raw_ref']['seq']}) is in the rendered input of {f['to_event']}: DELIVERED (adapter delivers link)."})
            found = [w for w in f.get("absent_from_answer", []) if w in ans_text]
            need(not found, f"{f['id']}: answer text mentions {found}")
            out["computed"].append({"origin": "computed", "text": "The answer text contains none of: " + ", ".join(f"“{w}”" for w in f["absent_from_answer"]) + " (exact, case-sensitive string check)."})
            out["events"] = out["anchors"] = [f["to_event"]] + [evidence[e["evidence"]]["produced_by"] for e in f["evidence"]]
        elif f["kind"] == "available_not_delivered":
            for ev_id in f["evictions"]:
                e = events[ev_id]
                tcid = e["raw_ref"].get("tool_call_id")
                orig = next((x for x in sem["evidence"] if x["id"].startswith("evi:tool_result:") and x["raw_ref"].get("tool_call_id") == tcid), None)
                subst = next((x for x in sem["evidence"] if x.get("produced_by") == ev_id), None)
                need(orig is not None and subst is not None, f"{f['id']}: cannot join eviction {ev_id}")
                n_orig, n_sub = len(receivers(orig["id"])), len(receivers(subst["id"]))
                out["computed"].append({"origin": "computed", "text": f"Step {e['raw_ref']['seq'][0]}: tool result {orig['id']} ({orig['raw_ref'].get('size'):,} chars) moved to {e['raw_ref'].get('file_path')}; delivered whole to {n_orig} model calls; the {subst['raw_ref'].get('size')}-char substitute was delivered to {n_sub}."})
            for r_id in f["reads"]:
                args = {x["raw_ref"]["argument"]: text(x["id"]) for x in sem["evidence"]
                        if x.get("raw_ref", {}).get("argument") and x["raw_ref"].get("tool") == "read_file" and x["produced_by"] == (issuer(r_id) or {}).get("id")
                        and x["raw_ref"]["locator"].startswith(f"events[seq={max((issuer(r_id) or {'raw_ref': {'seq': [0]}})['raw_ref']['seq'])}]")}
                out["computed"].append({"origin": "observed", "text": f"Step {events[r_id]['raw_ref']['seq'][0]}: read_file {args.get('file_path', '?')} offset {args.get('offset', '?')} limit {args.get('limit', '?')}."})
            out["events"] = out["anchors"] = list(f["evictions"])
        elif f["kind"] == "error_delivered":
            xid = f["evidence"][0]["evidence"]
            rc = receivers(xid)
            helper = sum(origin_of(e) != "agent:root" and origin_of(e) != "$unresolved" for e in rc)
            root = sum(origin_of(e) == "agent:root" for e in rc)
            need(helper == f["expect"]["helper_calls"] and root == f["expect"]["root_calls"], f"{f['id']}: computed {helper} helper / {root} root calls, expected {f['expect']}")
            out["computed"].append({"origin": "computed", "text": f"{xid} is delivered to {helper} helper calls (steps {rc[0]['order']}–{rc[-1]['order']}) and {root} root calls."})
            out["events"] = [evidence[xid]["produced_by"]] + [e["id"] for e in rc]
            out["anchors"] = [evidence[xid]["produced_by"]]
        elif f["kind"] == "dropped_after_summary":
            xid = f["evidence"][0]["evidence"]
            rc = receivers(xid)
            x = f["expect"]
            later = [e for e in model if e["order"] >= x["absent_from_step"] and origin_of(e) == origin_of(rc[0])]
            need(len(rc) == x["delivered_calls"] and rc[0]["order"] == x["first_step"] and rc[-1]["order"] == x["last_step"]
                 and not any(xid in delivers.get(e["id"], ()) for e in later), f"{f['id']}: computed {len(rc)} calls {rc[0]['order']}–{rc[-1]['order']}, expected {x}")
            out["computed"].append({"origin": "computed", "text": f"Delivered to {len(rc)} helper calls (steps {rc[0]['order']}–{rc[-1]['order']}); delivered to none of the {len(later)} helper calls from step {x['absent_from_step']} on."})
            out["events"] = [e["id"] for e in rc] + [e["id"] for e in later]
            out["anchors"] = [rc[0]["id"], rc[-1]["id"]] + [e["id"] for e in later[:1]]
        flags.append(out)

    # Lanes and handoff (sc3).
    for lane in ann.get("lanes", []):
        facts.append({"id": f"lane:{lane['label']}", "origin": "hand-annotated", "title": "Lane", "text": f"{lane['label']}: step {lane.get('step') or '–'.join(map(str, lane['steps']))}", "lane": lane})
    h = ann.get("handoff")
    if h:
        d_text = add_evidence(h["description_evidence"])
        need(d_text == h["description_text"], "handoff description text differs from the annotation")
        link = next(l for l in sem["links"] if l["source"] == h["received_by"] and l["target"] == h["description_evidence"])
        need(link["raw_ref"].get("sha256") == evidence[h["description_evidence"]]["raw_ref"]["sha256"], "description at 96 is not byte-identical")
        items = []
        for it in h["not_in_description"]:
            if it.get("contains"):
                need(it["contains"] in json.dumps(raw_events[it["step"]], ensure_ascii=False), f"handoff: step {it['step']} does not contain {it['contains']!r}")
            if it.get("check_absent"):
                need(it["check_absent"] not in d_text, f"handoff: description contains {it['check_absent']!r}")
            where = f"step {it['step']}" if it.get("step") else (f"steps {it['steps'][0]}–{it['steps'][1]}" if it.get("steps") else "step not annotated")
            items.append({"label": it["label"], "where": where, "origin": "hand-annotated",
                          "check": ("value found at that step and absent from the description (string check)" if it.get("check_absent") else None),
                          "formal_non_delivery": "UNKNOWN"})
        instr = next((x for x in sem["evidence"] if x["id"] == h["description_evidence"].replace(":description", ":instructions")), None)
        observed = []
        if instr:
            t = text(instr["id"])
            observed.append({"origin": "observed", "text": f"The task call's other argument, instructions, is {json.dumps(t)} ({len(t)} chars) and is delivered to {len(receivers(instr['id']))} model calls."})
        facts.append({"id": "fact:handoff", "origin": "hand-annotated", "title": "Handoff root → helper",
                      "text": h["note"], "handoff": {"issued_by": h["issued_by"], "received_by": h["received_by"], "description": d_text,
                                                       "description_evidence": h["description_evidence"],
                                                       "delivered": {"value": "DELIVERED", "byte_identical": True, "origin": "computed", "via": "delegation_id join, sha256 equal"},
                                                       "not_in_description": items, "observed": observed}})
    return flags, facts


def answer_text_from(rec, ans):
    from agent.deep_agent import _semantic_locator as locator
    return text_of(locator.resolve(rec, ans["locator"]))


def overlays(claims, flags, columns, ann, model, events, issuer):
    cols = {c["id"]: c for c in columns}
    out = []

    def col_for(eid):
        if eid in cols:
            return eid
        e = events.get(eid) if events else None
        if e and eid.startswith("ev:tool:"):
            iss = issuer(eid)
            return iss["id"] if iss else None
        if e and eid.startswith("ev:evict:"):
            nxt = next((c for c in columns if c["order"] > e["order"]), None)
            return nxt["id"] if nxt else None
        return None

    for c in claims:
        cid = col_for(c["event"])
        if cid:
            out.append({"id": f"ov:{c['id']}", "kind": "claim", "column": cid, "row": cols[cid]["row"], "ref": c["id"], "label": c["label"], "origin": "hand-annotated"})
    for f in flags:
        f["columns"] = list(dict.fromkeys(c for c in (col_for(e) for e in f["events"]) if c))
        seen = set()
        for eid in f.get("anchors", f["events"]):
            cid = col_for(eid)
            if cid and cid not in seen:
                seen.add(cid)
                out.append({"id": f"ov:{f['id']}:{cid}", "kind": "flag", "column": cid, "row": cols[cid]["row"], "ref": f["id"], "label": f["title"], "origin": "hand-annotated"})
    for lane in (ann or {}).get("lanes", []):
        step = lane.get("step") or lane["steps"][0]
        cid = col_for(lane["event"]) if lane.get("event") else None
        after = False
        if not cid:
            prior = [c for c in columns if c["order"] <= step]
            nxt = next((c for c in columns if c["order"] >= step), None)
            cid = (nxt or prior[-1])["id"]
            after = nxt is None
        out.append({"id": f"ov:lane:{lane['label']}", "kind": "lane", "column": cid, "row": cols[cid]["row"], "ref": None,
                    "label": f"{lane['label']} (step {lane.get('step') or '–'.join(map(str, lane['steps']))})" + (" — after the last model call" if after else ""), "origin": "hand-annotated"})
    return out


# ------------------------------------------------------------------------------------------ Gomoku


def build_gomoku(compare) -> dict:
    path = AP_ROOT / GOMOKU["raw"]
    need(path.exists(), f"{GOMOKU['raw']} is missing (fetch with data/mast/fetch.sh; see docs/DATA.md §2)")
    raw = path.read_bytes()
    need(sha(raw) == GOMOKU["sha256"], f"{GOMOKU['raw']}: sha256 does not match docs/DATA.md")
    need(sha(SCHEMA.read_bytes()) == SCHEMA_SHA, "schema 0.3 sha256 changed")
    rec = json.loads(raw)[GOMOKU["index"]]
    say("trace read", f"{Path(GOMOKU['raw']).name} [index {GOMOKU['index']}]: ChatDev trace {rec['trace_id']}, sha256 {sha(raw)[:12]}… matches docs/DATA.md")
    CHECKED[0] = 0
    need(rec["mas_name"] == "ChatDev" and rec["trace_id"] == 7, "MAST index 7 is not the ChatDev Gomoku trace")
    lines = rec["trace"]["trajectory"].split("\n")
    ann_path = ANN_DIR / "gomoku.json"
    need(ann_path.exists(), f"{rel(ann_path)} is missing")
    ann = json.loads(ann_path.read_text(encoding="utf-8"))
    need(len(lines) == ann["dataset"]["lines"], f"trajectory has {len(lines)} lines, expected {ann['dataset']['lines']}")

    cited = set()

    def cite(c, what):
        need(c["contains"] in lines[c["line"] - 1], f"{what}: line {c['line']} does not contain {c['contains']!r}")
        cited.add(c["line"])
        return {"line": c["line"], "text": lines[c["line"] - 1][:200], "to_end": len(lines[c["line"] - 1]) <= 200}

    start_chats = [i + 1 for i, l in enumerate(lines) if "**[Start Chat]**" in l]
    need(len(start_chats) == 12, f"expected 12 [Start Chat] lines, found {len(start_chats)}")
    usages = [i + 1 for i, l in enumerate(lines) if "**[OpenAI_Usage_Info Receive]**" in l]
    say("adapter", "none for ChatDev: skeleton hand-reconstructed from schema §14 and the full-log reconstruction")
    # The full-log reconstruction (gomoku.full.json) extends §14 to every LLM call, role and framework record;
    # gomoku.json (the §14 annotation) is read unchanged.
    full_path = ANN_DIR / "gomoku.full.json"
    need(full_path.exists(), f"{rel(full_path)} is missing")
    full = json.loads(full_path.read_text(encoding="utf-8"))
    need(full["dataset"] == ann["dataset"], "gomoku.full.json describes a different dataset")
    calls = {c["id"]: c for c in full["calls"]}
    need(sorted(c["usage"] for c in calls.values()) == usages, f"reconstructed LLM calls do not match the {len(usages)} usage records")
    need(sorted(c["start_chat"] for c in calls.values() if c["start_chat"]) == start_chats, "reconstructed calls do not match the [Start Chat] lines")
    role_full = {r["id"]: r for r in ann["roles"]} | {r["id"]: r for r in full["roles"]}
    label_of = {r["id"]: r.get("name", r["label"]) for r in role_full.values()}
    ann_ev_by_id = {e["id"]: e for e in ann["events"]}
    evs = []
    for e in ann["events"]:
        if e["role"] == "$not_reconstructed":
            need(e["id"] in calls and "role" in calls[e["id"]], f"{e['id']}: §14 left it unreconstructed and the full reconstruction does not attribute it")
            continue
        evs.append(dict(e))
    for c in full["calls"]:
        if c["id"] not in ann_ev_by_id or ann_ev_by_id[c["id"]]["role"] == "$not_reconstructed":
            evs.append({"id": c["id"], "role": c["role"], "label": c["label"], "phase": c["phase"], "produces": c.get("produces"), "line": c["start_chat"] or c["usage"],
                        "cite": {"line": c["start_chat"] or c["usage"], "contains": "**[Start Chat]**" if c["start_chat"] else "**[OpenAI_Usage_Info Receive]**"}})
    evs.sort(key=lambda e: e["line"])
    for e in evs:
        c = calls.get(e["id"])
        if not c:
            need(e.get("llm_call") is False, f"{e['id']}: LLM event without a usage record")
            continue
        # Each call: its usage record, its reply header naming the replying role and the chat pair, and nothing between.
        need(lines[c["usage"]].strip() == f"prompt_tokens: {c['prompt_tokens']}", f"{e['id']}: prompt_tokens at L{c['usage'] + 1} is not {c['prompt_tokens']}")
        reply = lines[c["reply"] - 1]
        partner = label_of[c["opened_by"] or c["reply_to"]]
        phase = c.get("phase") or ann_ev_by_id[e["id"]]["phase"].split(",")[0]
        need(f"INFO] {label_of[e['role']]}: **" in reply and f"on : {phase}, turn 0**" in reply and {f"{label_of[e['role']]}<->{partner}", f"{partner}<->{label_of[e['role']]}"} & {reply.split("**")[1].split(" on : ")[0]},
             f"{e['id']}: reply header at L{c['reply']} does not name {label_of[e['role']]} replying to {partner} in {phase}")
        if c["start_chat"]:
            need(f"INFO] {label_of[c['opened_by']]}: **[Start Chat]**" in lines[c["start_chat"] - 1], f"{e['id']}: [Start Chat] at L{c['start_chat']} is not by {label_of[c['opened_by']]}")
            need(not any(u for u in usages if c["start_chat"] < u < c["usage"]), f"{e['id']}: another usage record precedes its own")
        cited.update(x for x in (c["start_chat"], c["usage"], c["reply"]) if x)
        who = f"opened by {label_of[c['opened_by']]} (L{c['start_chat']})" if c["start_chat"] else f"reply to {label_of[c['reply_to']]}; input not logged"
        e["phase"] = f"{e.get('phase') or c['phase']} · {who}"
        e["tokens"] = e.get("tokens") or f"{c['prompt_tokens']} reported (L{c['usage'] + 1})"
        e["unknown_input"] = c["start_chat"] is None
    for t in full["token_totals"]:
        need(t["contains"] in lines[t["line"] - 1], f"token total at L{t['line']} does not contain {t['contains']!r}")
        total = sum(c["prompt_tokens"] for c in sorted(calls.values(), key=lambda c: c["usage"])[:t["calls"]])
        need(t["contains"].endswith(f"={total}"), f"token total at L{t['line']}: the first {t['calls']} calls sum to {total}")
        cited.add(t["line"])
    for x in full["framework_events"]:
        cite({"line": x["line"], "contains": x["contains"]}, x["id"])
    has_claim = {next(e["role"] for e in evs if e["id"] == c["event"]) for c in ann["claims"]}
    n_calls = defaultdict(int)
    for e in evs:
        if e["id"] in calls:
            n_calls[e["role"]] += 1
    roles = []
    for rid in full["role_order"]:
        r = role_full[rid]
        sub = full["role_notes"].get(rid) or r.get("note") or r["kind"]
        if r["kind"] == "agent" and rid not in has_claim:
            sub += " · claims not annotated"
        roles.append({"id": rid, "label": r["label"], "sub": sub, "kind": r["kind"], "name": r.get("name"), "parent": None, "origin": "hand-reconstructed",
                      "llm_calls": n_calls[rid], "claims_annotated": rid in has_claim, "cite": cite(r["cite"], rid) if r.get("cite") else None})
    need(not any(e["role"] == "$not_reconstructed" for e in evs), "an event is still unreconstructed")
    ev_out = {}
    for x in ann["evidence"]:
        c = cite(x["cite"], x["id"])
        ev_out[x["id"]] = {"id": x["id"], "label": x["label"], "step": None, "lines": x["lines"], "tool": None, "kind": "log_item",
                           "source": x["source"], "produced_by": x.get("produced_by"), "locator": f"trace.trajectory L{x['lines'][0]}",
                           "sha256": None, "size": None, "excerpt": {"text": c["text"], "start": 0, "complete": c["to_end"], "to_end": c["to_end"], "spans": []},
                           "origin": "unresolved" if x["source"] == "$unresolved" else "hand-reconstructed"}
    for x in full["evidence"]:
        c = cite(x["cite"], x["id"])
        ev_out[x["id"]] = {"id": x["id"], "label": x["label"], "step": None, "lines": x["lines"], "tool": None, "kind": "log_item",
                           "source": x["source"], "produced_by": x["produced_by"], "locator": f"trace.trajectory L{x['lines'][0]}",
                           "sha256": None, "size": None, "excerpt": {"text": c["text"], "start": 0, "complete": c["to_end"], "to_end": c["to_end"], "spans": []},
                           "origin": "hand-reconstructed", "note": x.get("note")}
    deliv = defaultdict(set)
    for d in ann["delivers"]:
        for t in d["to"]:
            deliv[t].add(d["item"])
    # Full-log deliveries: the item's text must be inside the receiving call's logged [Start Chat] input.
    def in_input(target, a, b=None):
        c = calls[target]
        need(c["start_chat"] and c["start_chat"] < a <= (b or a) < c["usage"], f"{target}: L{a} is outside its logged input")
    full_delivers = []
    for d in full["delivers"]:
        need(d["item"] in ev_out, f"delivers item {d['item']} unknown")
        for t, ln in d["to"].items():
            in_input(t, ln)
            need(d["contains"] in lines[ln - 1], f"{d['item']} -> {t}: L{ln} does not contain {d['contains']!r}")
            cited.add(ln)
            deliv[t].add(d["item"])
        full_delivers.append({"item": d["item"], "to": list(d["to"]), "lines": ", ".join(f"L{v}" for v in d["to"].values()), "at": {t: f"L{v}" for t, v in d["to"].items()}})

    def code_lines(a, b):
        out, inside = [], False
        for i in range(a, b + 1):
            if lines[i - 1].strip().startswith("```"):
                inside = not inside
            elif inside and lines[i - 1].strip():
                out.append(lines[i - 1].rstrip())
        return out
    for d in full["block_delivers"]:
        src = code_lines(*d["from_reply"])
        need(src, f"{d['item']}: no code lines in L{d['from_reply'][0]}-{d['from_reply'][1]}")
        for t, (a, b) in d["to"].items():
            in_input(t, a, b)
            need(code_lines(a, b) == src, f"{d['item']} -> {t}: L{a}-{b} does not hold its {len(src)} code lines in order")
            cited.update((a, b))
            deliv[t].add(d["item"])
        full_delivers.append({"item": d["item"], "to": list(d["to"]), "lines": ", ".join(f"L{a}–{b}" for a, b in d["to"].values()) + f" ({d['check']})",
                              "at": {t: f"L{a}–{b}, {d['check']}" for t, (a, b) in d["to"].items()}})
    # Columns: events in log-line order.
    columns, sk_events = [], []
    seen_by_role = defaultdict(set)
    for i, e in enumerate(evs):
        c = cite(e["cite"], e["id"])
        first = [x for x in sorted(deliv[e["id"]]) if x not in seen_by_role[e["role"]]]
        seen_by_role[e["role"]].update(deliv[e["id"]])
        origin = "unresolved" if e["role"] == "$not_reconstructed" else "hand-reconstructed"
        unknown = e.get("unknown_input", False)
        columns.append({"id": e["id"], "order": e["line"], "row": e["role"], "steps": [e["line"], e["line"]], "label": e["label"],
                        "delivers": None if unknown else len(deliv[e["id"]]), "first": None if unknown else len(first), "delegation_out": False, "delegation_in": False,
                        "overlaps": 0, "tools": [], "origin": origin, "phase": e.get("phase")})
        sk_events.append({"id": e["id"], "kind": "model_call" if e.get("llm_call", True) else "check", "order": e["line"], "steps": [e["line"], e["line"]],
                          "agent": e["role"], "label": e["label"], "phase": e.get("phase"), "produces": e.get("produces"),
                          "messages": e.get("messages"), "tokens": e.get("tokens"), "cite": c, "origin": origin})
    col_ids = {c["id"] for c in columns}
    row_of = {c["id"]: c["row"] for c in columns}
    order_of = {c["id"]: c["order"] for c in columns}
    # A handoff is drawn where an item produced in one row first reaches another row (the matrix's "new to that
    # agent" rule); later deliveries of the same item to that row are counted in the input track, not drawn.
    edges, reached = [], set()
    for d in sorted([*ann["delivers"], *full_delivers], key=lambda d: min(order_of[t] for t in d["to"])):
        src = ev_out[d["item"]].get("produced_by")
        for t in sorted(d["to"], key=order_of.get):
            need(t in col_ids, f"delivers target {t} unknown")
            if src and src in col_ids and row_of[src] != row_of[t] and (d["item"], row_of[t]) not in reached:
                edges.append({"from": src, "to": t, "via": f"{ev_out[d['item']]['label']} delivered ({d.get('at', {}).get(t, d['lines'])})", "item": d["item"], "origin": "hand-reconstructed"})
            reached.add((d["item"], row_of[t]))
    edges.sort(key=lambda e: (order_of[e["to"]], order_of[e["from"]]))
    for x in full["framework_events"]:
        sk_events.append({"id": x["id"], "kind": x["kind"], "order": x["line"], "steps": [x["line"], x["line"]], "agent": x.get("agent", "framework"),
                          "label": x["label"], "phase": x.get("phase"), "produces": None, "messages": None, "tokens": None,
                          "cite": cite({"line": x["line"], "contains": x["contains"]}, x["id"]), "origin": "hand-reconstructed"})
    sk_events.sort(key=lambda e: e["order"])
    grid = {"origin": "hand-reconstructed", "source_contract": None, "axis": "LLM calls (usage records) and the test gate in log-line order",
            "rows": [{k: v for k, v in r.items() if k != "cite"} for r in roles], "columns": columns, "edges": edges, "delivery_track": True,
            "max_delivers": max(c["delivers"] or 0 for c in columns), "overlays": [],
            "note": "No matrix builder exists for ChatDev logs: this grid is hand-reconstructed (roles × LLM calls) from schema §14 and the full log, with every cited log line checked. "
                    "Each column is one LLM call (one usage record) or the test gate; the opening message of each chat is a framework phase prompt, not a call. Columns are log-line order.",
            "order_caveat": "Log-line order only; it implies no precedence beyond what §14 states."}

    # Claims and O3 over a hand-built 0.3 slice.
    claims, props, non_claims = [], [], []
    ents = [{"id": r["id"], "kind": "agent" if r["kind"] == "agent" else "framework"} for r in roles]
    s_events = [{"id": e["id"], "origin": e["role"], "order": e["line"], "raw_ref": {"line": e["line"]}} for e in evs]
    s_evidence = [{"id": x["id"], "source": x["source"] if x["source"] != "$unresolved" else {"$unresolved": True, "candidates": ["framework", "environment"]},
                   "produced_by": x.get("produced_by"), "raw_ref": {"line": x["lines"][0]}} for x in ann["evidence"]]
    s_links = [{"relation": "delivers", "source": t, "target": d["item"], "raw_ref": {"lines": d["lines"]}} for d in ann["delivers"] for t in d["to"]]
    texts = {}
    s_claims, s_props, s_states = [], [], []
    for c in ann["claims"]:
        line = lines[c["line"] - 1]
        span = find_one(line, c["words"], f"{c['id']} at L{c['line']}")
        texts[c["evidence"]] = line
        s_claims.append({"id": c["id"], "evidence": c["evidence"], "raw_ref": {"line": c["line"], "span": span}, "proposition": f"prop:{c['id'][4:]}"})
        s_props.append({"id": f"prop:{c['id'][4:]}", "form": c["proposition"]})
        s_states.append({"proposition": f"prop:{c['id'][4:]}", "value": c["state"], "claims": [c["id"]]})
    for p in ann["propositions"]:
        s_props.append({"id": p["id"], "form": p["form"]})
        for l in p["links"]:
            s_links.append({"relation": l["relation"], "source": p["id"], "target": l["evidence"], "raw_ref": {"whole_item": True, "grounding": l["grounding"]}})
    comp = compare.Comparator({"entities": ents, "events": s_events, "evidence": s_evidence, "claims": s_claims, "propositions": s_props,
                               "states": s_states, "links": s_links}, {}, texts)
    say("annotations checked", f"{plural(len(cited), 'cited log line')} checked; {len(calls)} LLM calls match the {len(usages)} usage records "
                               f"({len(start_chats)} with a logged [Start Chat] input); {len(roles)} roles, {len(full['framework_events'])} framework, config and test records; "
                               f"{plural(len(ann['claims']), 'claim')}, {plural(len(ann['flags']), 'flag')}; {plural(CHECKED[0], 'claim span')} found verbatim")
    for i, c in enumerate(ann["claims"]):
        try:
            o3 = o3_summary(comp.state_vs_evidence(i))
            o3["computed_from"] = "hand-annotated claim and hand-reconstructed links (§14)"
        except compare.InvalidInput as e:
            o3 = {"status": "not computable", "origin": "computed", "reason": str(e)}
        claims.append({"id": c["id"], "label": c["label"], "words": c["words"], "event": c["event"], "step": None, "line": c["line"],
                       "span": s_claims[i]["raw_ref"]["span"], "speaker": next(e["role"] for e in evs if e["id"] == c["event"]),
                       "speaker_origin": "hand-reconstructed", "assertive": True, "origin": "hand-annotated", "proposition": f"prop:{c['id'][4:]}",
                       "state": {"value": c["state"], "origin": "hand-annotated"}, "links": [], "o3": o3, "notes": c.get("notes", []) + [c["checks"]], "fixture": None})
        props.append({"id": f"prop:{c['id'][4:]}", "form": c["proposition"], "origin": "hand-annotated", "links": []})
        ev_out[c["evidence"]]["excerpt"] = window(line, [span])
    for p in ann["propositions"]:
        props.append({"id": p["id"], "form": p["form"], "origin": "hand-reconstructed",
                      "links": [{"relation": l["relation"], "evidence": l["evidence"], "grounding": l["grounding"]} for l in p["links"]]})
    for nc in ann["non_claims"]:
        non_claims.append(dict(nc, origin="hand-annotated"))
    flags = [{"id": f["id"], "title": f["title"], "kind": f["kind"], "text": f["text"], "origin": "hand-reconstructed", "caveat": None,
              "events": f["events"], "anchors": f["events"], "evidence": f.get("evidence", []), "computed": []} for f in ann["flags"]]
    nd = ann["not_delivered"][0]
    merged = {}
    for d in [*ann["delivers"], *full_delivers]:
        m = merged.setdefault(d["item"], {"item": d["item"], "to": [], "lines": [], "value": "DELIVERED", "origin": "hand-reconstructed"})
        m["to"] += [t for t in d["to"] if t not in m["to"]]
        m["lines"].append(d["lines"])
    delivery = {"source": "§14 and the full-log reconstruction",
                "delivered": [dict(m, to=sorted(m["to"], key=order_of.get), lines="; ".join(m["lines"])) for m in merged.values()],
                "not_delivered": [{"item": nd["item"], "to": nd["to"], "value": "NOT_DELIVERED", "coverage": nd["coverage"], "origin": "hand-reconstructed"}]}
    grid["overlays"] = overlays(claims, flags, columns, None, None, None, None)
    return {
        "contract": CONTRACT,
        "trace": {"id": "gomoku", "label": GOMOKU["label"], "kind": "multi-agent", "framework": "ChatDev (MAST / MAD, ProgramDev)", "model": "GPT-4o",
                  "scenario": "Gomoku (ProgramDev)", "status": "completed (run ends L3388)", "answer": None, "summary": None},
        "honesty": {"annotations": HAND, "skeleton": "hand-reconstructed from schema §14 and the full log; every cited log line is checked against the dataset",
                    "rules": ["Delivered means presence in an LLM call's rendered input, not use.",
                              "NOT DELIVERED is shown only where coverage is COMPLETE (§14.2); elsewhere non-delivery would be UNKNOWN.",
                              "Columns are log-line order only.",
                              "A call whose input is not logged has delivery UNKNOWN; a role with no annotated claim is shown as not annotated, and its silence is not read as agreement."]},
        "provenance": {"raw_trace": f"{GOMOKU['raw']} [index {GOMOKU['index']}]", "raw_trace_sha256": GOMOKU["sha256"], "adapter": None, "verifier": None,
                       "compare": compare.PROFILE, "worktree_head": None, "schema_sha256": SCHEMA_SHA, "matrix_file": None, "matrix_sha256": None,
                       "annotation_file": rel(ann_path), "annotation_sha256": sha(ann_path.read_bytes()), "builder": "scripts/explorer/build_bundle.py",
                       "skeleton_source": "docs/agenttrace.semantic.0.3.md §14", "skeleton_extension_file": rel(full_path), "skeleton_extension_sha256": sha(full_path.read_bytes())},
        "layers": {"skeleton": True, "matrix": True, "claims": True, "evidence": True, "delivery": True, "o3": True, "flags": True},
        "skeleton": {"origin": "hand-reconstructed", "agents": roles, "events": sk_events, "handoffs": edges,
                     "counts": {"llm_calls": len(calls), "start_chat_calls": len(start_chats), "unlogged_input_calls": sum(1 for c in calls.values() if not c["start_chat"]),
                                "reconstructed_llm_calls": sum(1 for e in ann["events"] if e.get("llm_call", True) and e["role"] != "$not_reconstructed"),
                                "roles": len(roles), "framework_records": len(full["framework_events"]),
                                "checks": sum(1 for e in evs if not e.get("llm_call", True)), "evidence": len(ev_out), "delivers": sum(len(v) for v in deliv.values())},
                     "counts_origin": "hand-reconstructed", "skipped": [], "delivery": delivery},
        "matrix": grid,
        "evidence": ev_out,
        "propositions": props,
        "claims": claims,
        "non_claims": non_claims,
        "flags": flags,
        "facts": [{"id": "fact:coverage", "origin": "hand-reconstructed", "title": "Coverage",
                   "text": "o200k token residual is a constant +2 on all 12 LLM calls, so coverage is COMPLETE (§14.2)."},
                  {"id": "fact:calls", "origin": "hand-reconstructed", "title": "LLM calls in the log", "discrepancy": True,
                   "text": f"The log records {len(calls)} usage records (one per LLM call); the framework's prompt-token totals at L2448 and L3378 equal their sums. "
                           f"{len(start_chats)} calls open with a logged [Start Chat] input, which is what §14.2 counts as its 12 calls. "
                           "In DemandAnalysis two usage records (L101, L110) precede the CPO's and the CEO's replies (L118, L131) and are paired with them in log order. "
                           "The CEO's DemandAnalysis reply (usage L110) has no logged input, so what reached it is UNKNOWN."},
                  {"id": "fact:roles", "origin": "hand-reconstructed", "title": "Roles",
                   "text": "; ".join(f"{r['label']}: {plural(r['llm_calls'], 'LLM call')}{'' if r['claims_annotated'] or r['kind'] != 'agent' else ', claims not annotated'}" for r in roles)
                           + ". The Counselor only opens Reflection with the framework's prompt; the test gate's output is fixed text. A role without annotated claims holds no state here: silence is not agreement."},
                  *({"id": f"fact:unresolved:{i}", "origin": "hand-reconstructed", "title": "Not established", "text": t} for i, t in enumerate(full["unresolved"]))],
        "checks": {"cited_lines_checked": True, "llm_calls": len(calls), "start_chat_calls": len(start_chats)},
    }


def ann_ev(ann, xid):
    return next((x for x in ann["evidence"] if x["id"] == xid), {})


# --------------------------------------------------------------------------------------------- main


def write(bundle: dict) -> tuple[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    body = canonical(bundle)
    name = f"{bundle['trace']['id']}.bundle.json"
    (OUT_DIR / name).write_text(body, encoding="utf-8")
    return name, sha(body)


def show_report() -> None:
    w = max((len(st) for st, _ in REPORT), default=0)
    for st, msg in REPORT:
        print(f"  {st.ljust(w)}  {msg}")


def update_manifest(entries: dict) -> None:
    path = OUT_DIR / "index.json"
    man = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"contract": "agenttrace-explorer-manifest/0.1", "bundles": []}
    keep = [b for b in man["bundles"] if b["trace_id"] not in entries]
    man["bundles"] = sorted(keep + list(entries.values()), key=lambda b: ["aob-621", "aob-sc3-B", "gomoku"].index(b["trace_id"]) if b["trace_id"] in ("aob-621", "aob-sc3-B", "gomoku") else 99)
    path.write_text(canonical(man), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", choices=[*AOB, "gomoku"])
    ap.add_argument("--worktree", type=Path, default=AP_ROOT.parent / "AssetOpsBench-agenttrace-spec")
    args = ap.parse_args(argv)
    from agent.deep_agent import _semantic_adapter as adapter, _semantic_compare as compare, _semantic_locator as locator
    from agent.deep_agent._semantic_verify import verify

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from validate_bundle import validate

    entries, failed = {}, False
    for tid in [args.only] if args.only else [*AOB, "gomoku"]:
        REPORT.clear()
        print(f"\n== {tid}")
        try:
            bundle = build_gomoku(compare) if tid == "gomoku" else build_aob(tid, AOB[tid], args.worktree.resolve(), (adapter, verify, locator, compare))
            problems = validate(bundle)
            need(not problems, f"bundle validation failed: {problems[:5]}")
        except Mismatch as e:
            show_report()
            print(f"STOPPED {tid}: {e}", file=sys.stderr)
            failed = True
            continue
        name, digest = write(bundle)
        entries[tid] = {"trace_id": tid, "file": name, "sha256": digest, "contract": CONTRACT, "label": bundle["trace"]["label"], "kind": bundle["trace"]["kind"]}
        if tid == "gomoku":
            say("O3 results", o3_line(bundle["claims"]))
        say("bundle written", f"src/explorer/data/{name} ({(OUT_DIR / name).stat().st_size / 1024:.0f} KB, sha256 {digest[:12]}…): "
                              f"{plural(len(bundle['matrix']['rows']), 'row')} × {plural(len(bundle['matrix']['columns']), 'column')}, {plural(len(bundle['claims']), 'claim')}, "
                              f"{plural(len(bundle['flags']), 'flag')}, validator OK")
        show_report()
    if entries:
        update_manifest(entries)
        print(f"\nmanifest: src/explorer/data/index.json ({len(entries)} bundle(s) updated)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
