"""Build agent × model-call matrix data (contract agenttrace-matrix/0.2) from any instrumented trace.

    env -u OTEL_TRACES_FILE PYTHONPATH=<worktree>/src <worktree>/.venv/bin/python \
        scripts/demo/build_matrix.py --trace <instrumented.json> --run-id <id> [--fixture <0.3 json>]

Pipeline: frozen structural adapter -> independent verifier (any error rejects the run) -> matrix
data -> independent matrix validator (any error rejects the run) -> write <run-id>.matrix.json and
update the manifest.  No model, network or database; the raw trace is only read.  Nothing semantic is
derived: the matrix records observed model calls, their agent origin as the adapter assigns it,
issued tool calls and positive structural deliveries.  An optional hand-grounded fixture contributes
only its delivers links, matched to adapter links by locator and sha256; its claims are ignored.
Output is canonical JSON (sorted keys, compact) and byte-identical across reruns.

Exit codes: 0 ok · 2 adapter rejected the record or the verifier found errors · 3 fixture unusable ·
4 matrix validation failed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

AP_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = AP_ROOT / "src/demo/data/matrices"
CONTRACT = "agenttrace-matrix/0.2"
EXCERPT = 300  # display-only excerpt length (viz profile §6)
SCHEMA_PATH = AP_ROOT / "docs/agenttrace.semantic.0.3.md"
_ISSUED = re.compile(r"^events\[seq=(\d+)\]")
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")


class Rejected(Exception):
    def __init__(self, code: int, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.code, self.errors = code, errors or []


def sha(data: bytes | str) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def canonical(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def text_of(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(p, dict) for p in value):
        return "".join(p.get("text", "") for p in value if p.get("type") == "text")
    return json.dumps(value, ensure_ascii=False, default=str)


def display_path(path: Path, worktree: Path | None = None) -> str:
    """AP-relative path, "worktree:<relative path>" inside the AssetOpsBench worktree, else the file name
    only, so no home path is written into the output."""
    p = path.resolve()
    if p.is_relative_to(AP_ROOT):
        return p.relative_to(AP_ROOT).as_posix()
    if worktree is not None and p.is_relative_to(worktree.resolve()):
        return "worktree:" + p.relative_to(worktree.resolve()).as_posix()
    return path.name


_HOME = re.compile(r"/(?:Users|home)/[^/\s\"']+")


def error_summary(err):
    """Type and message of a recorded run error; never the traceback.  Home directories are replaced by ~."""
    if err is None:
        return None
    if isinstance(err, dict):
        out = {k: _HOME.sub("~", str(err[k]))[:200] for k in ("type", "message") if err.get(k) is not None}
        return out or {"message": "error recorded (no type or message field)"}
    return {"message": _HOME.sub("~", str(err).splitlines()[0] if str(err) else "")[:200]}


def evidence_kind(x: dict) -> str:
    rr = x["raw_ref"]
    if rr.get("external"):
        return "question"
    if x["id"].startswith("evi:evict_sub:"):
        return "eviction_substitute"
    if "argument" in rr:
        return "tool_argument"
    return "tool_result"


def build(record: dict, raw_bytes: bytes, run_id: str, trace_display: str, *, adapter, verify, locator,
          fixture: dict | None = None, fixture_display: str | None = None, fixture_bytes: bytes | None = None,
          worktree_head: str = "") -> dict:
    if not _RUN_ID.match(run_id):
        raise Rejected(2, f"run id {run_id!r} must match {_RUN_ID.pattern}")
    raw_sha = sha(raw_bytes)
    try:
        doc = adapter.adapt(record, trace_ref=trace_display, trace_sha256=raw_sha)
    except (ValueError, KeyError, TypeError) as e:
        raise Rejected(2, f"adapter rejected the record: {e}") from e
    errors = verify(doc, record, trace_sha256=raw_sha)
    if errors:
        raise Rejected(2, f"verifier found {len(errors)} error(s) in the adapter output", errors)
    sem, pl = doc["semantic"], doc["profile_local"]
    events = {e["id"]: e for e in sem["events"]}
    model = sorted((e for e in sem["events"] if e["id"].startswith("ev:llm:")), key=lambda e: e["order"])
    model_ids = {e["id"] for e in model}
    evidence = {x["id"]: x for x in sem["evidence"]}

    fixture_links = []
    if fixture is not None:
        fsem = fixture.get("semantic", fixture)
        f_sha = ((fsem.get("run") or {}).get("raw_ref") or {}).get("trace_sha256")
        if f_sha != raw_sha:
            raise Rejected(3, f"fixture trace_sha256 {f_sha!r} does not match the trace ({raw_sha})")
        for l in fsem.get("links", []):
            if l.get("relation") != "delivers":
                continue
            loc, lsha = l["raw_ref"].get("locator"), l["raw_ref"].get("sha256")
            hit = [x for x in sem["links"] if x["raw_ref"]["locator"] == loc and x["raw_ref"].get("sha256") == lsha]
            if len(hit) != 1:
                raise Rejected(3, f"fixture delivers link {l['source']} -> {l['target']} is not reproduced by exactly one adapter link ({len(hit)})")
            fixture_links.append({"fixture_source": l["source"], "fixture_target": l["target"], "locator": loc, "sha256": lsha,
                                  "adapter_link": [hit[0]["source"], hit[0]["target"]]})

    links_by_source = defaultdict(list)
    for l in sem["links"]:
        links_by_source[l["source"]].append(l)
    issued_by = defaultdict(list)
    for e in sem["events"]:
        m = _ISSUED.match(e["raw_ref"].get("issued_at") or "")
        if m:
            issued_by[int(m.group(1))].append(e["id"])
    overlaps = defaultdict(set)
    for a, b in pl["order"]["overlaps"]:
        if a in model_ids and b in model_ids:
            overlaps[a].add(b)
            overlaps[b].add(a)

    seen = defaultdict(set)
    columns, referenced = [], set()
    for e in model:
        rr = e["raw_ref"]
        unresolved = not isinstance(e["origin"], str)
        ob = rr.get("origin_basis") or {}
        out_seq = max(rr["seq"])
        links = links_by_source.get(e["id"], [])
        first = []
        if not unresolved:
            for l in links:
                if l["target"] not in seen[e["origin"]]:
                    seen[e["origin"]].add(l["target"])
                    first.append([l["target"], l["raw_ref"]["locator"]])
        delegated = sorted(x["id"] for x in sem["evidence"] if x.get("produced_by") == e["id"] and x["raw_ref"].get("tool") == "task")
        col = {
            "id": e["id"], "order": e["order"], "start_seq": rr["start_seq"], "end_seq": rr["end_seq"],
            "row": "$unresolved" if unresolved else e["origin"], "origin": e["origin"],
            "origin_label": ob.get("label"), "origin_rule": ob.get("rule"),
            "raw_agent_id": rr.get("raw_agent_id") if unresolved else e["origin"].split(":", 1)[1],
            "input_locator": rr.get("input_locator") or (ob.get("raw_refs") or {}).get("input_locator"),
            "output_locator": rr.get("output_locator"),
            "issued_tool_events": sorted(issued_by.get(out_seq, []), key=lambda x: events[x]["order"]),
            "issued_delegations": delegated,
            "delivers": [l["target"] for l in links],
            "first_delivered_here": first,
            "delegation_input": [l["target"] for l in links if "delegation_id" in (l["raw_ref"].get("join") or {})],
            "overlaps_with": sorted(overlaps.get(e["id"], ()), key=lambda x: events[x]["order"]),
            "fixture_links": [f["fixture_target"] for f in fixture_links if f["adapter_link"][0] == e["id"]],
        }
        columns.append(col)
        referenced.update(t for t, _ in first)
        referenced.update(delegated)

    ev_out = {}
    for xid in sorted(referenced):
        x = evidence[xid]
        rr = x["raw_ref"]
        try:
            t = text_of(locator.resolve(record, rr["locator"])) if not rr.get("external") else record.get(rr["locator"])
        except Exception:  # noqa: BLE001 -- an unresolvable locator is reported, never repaired
            t = None
        keep = ("seq", "locator", "sha256", "size", "tool", "tool_call_id", "argument", "external")
        ev_out[xid] = {"source": x["source"], "produced_by": x.get("produced_by"), "kind": evidence_kind(x),
                       "raw_ref": {k: rr[k] for k in keep if k in rr},
                       "excerpt": None if t is None else t[:EXCERPT],
                       "excerpt_complete": t is not None and len(t) <= EXCERPT}
    other = {eid: {"origin": e["origin"], "order": e["order"],
                   "raw_ref": {k: e["raw_ref"][k] for k in ("seq", "tool_call_id", "issued_at", "file_path") if k in e["raw_ref"]}}
             for eid, e in events.items() if eid not in model_ids}

    agents = record.get("agents") or []
    rows = [{"id": f"agent:{a['agent_id']}", "agent_id": a["agent_id"], "name": a.get("name"), "kind": a.get("kind"),
             "parent_agent_id": a.get("parent_agent_id"), "delegation_id": a.get("delegation_id"), "status": a.get("status")}
            for a in agents]
    last = max(record.get("events") or [{"seq": None, "type": None}], key=lambda r: r["seq"] if r["seq"] is not None else -1)
    ad = pl["adapter"]
    per_row = {r["id"]: sum(c["row"] == r["id"] for c in columns) for r in rows}
    per_row["$unresolved"] = sum(c["row"] == "$unresolved" for c in columns)
    return {
        "contract": CONTRACT,
        "run": {"run_id": run_id, "record_run_id": record.get("run_id"), "scenario_id": record.get("scenario_id"),
                "runner": record.get("runner"), "model": record.get("model"), "status": record.get("status"),
                "error": error_summary(record.get("error")),
                "started_at": record.get("started_at"), "ended_at": record.get("ended_at"),
                "terminal_event": {"seq": last["seq"], "type": last["type"]}, "question_present": bool(record.get("question")),
                "versions": record.get("versions") or {}},
        "telemetry": {"delivery": ad["delivery_telemetry"], "offered_tools": ad["offered_tools_telemetry"], "limits": ad.get("telemetry_limits", [])},
        "provenance": {"raw_trace": trace_display, "raw_trace_sha256": raw_sha, "adapter": f"{doc['profile']} increment {ad['increment']}",
                       "verifier": "agent.deep_agent._semantic_verify (0 errors)", "worktree_head": worktree_head,
                       "schema_sha256": sha(SCHEMA_PATH.read_bytes()) if SCHEMA_PATH.exists() else None,
                       "fixture": None if fixture is None else {"path": fixture_display, "sha256": sha(fixture_bytes or b"")}},
        "semantic": {"claims_extracted": ad["claims_extracted"], "claims": len(sem["claims"]), "propositions": len(sem["propositions"]), "states": len(sem["states"])},
        "rows": rows,
        "columns": columns,
        "evidence": ev_out,
        "other_events": other,
        "fixture_links": fixture_links,
        "ambiguities": pl["ambiguities"],
        "skipped": [{"kind": s["kind"], "seq": s["seq"], "reason": s["reason"]} for s in ad["skipped"]],
        "counts": {"model_calls": len(columns), "per_row": per_row, "delivers": len(sem["links"]), "evidence": len(sem["evidence"]),
                   "tool_events": sum(1 for e in sem["events"] if e["id"].startswith("ev:tool:")),
                   "eviction_events": sum(1 for e in sem["events"] if e["id"].startswith("ev:evict:")), "overlapping_pairs": len(pl["order"]["overlaps"])},
        "order_caveat": pl["order"]["caveat"],
    }


def update_manifest(out_dir: Path, run_id: str, file_name: str, body: str, matrix: dict) -> None:
    path = out_dir / "index.json"
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"contract": "agenttrace-matrix-manifest/0.1", "runs": []}
    runs = [r for r in manifest["runs"] if r["run_id"] != run_id]
    runs.append({"run_id": run_id, "file": file_name, "sha256": sha(body), "contract": CONTRACT,
                 "agents": len(matrix["rows"]), "model_calls": matrix["counts"]["model_calls"],
                 "delivery_telemetry": matrix["telemetry"]["delivery"], "status": matrix["run"]["status"]})
    manifest["runs"] = sorted(runs, key=lambda r: r["run_id"])
    path.write_text(canonical(manifest), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--trace", required=True, type=Path)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--fixture", type=Path)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--worktree", type=Path, default=AP_ROOT.parent / "AssetOpsBench-agenttrace-spec")
    args = ap.parse_args(argv)
    from agent.deep_agent import _semantic_adapter as adapter, _semantic_locator as locator
    from agent.deep_agent._semantic_verify import verify
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from validate_matrix import validate

    raw_bytes = args.trace.read_bytes()
    record = json.loads(raw_bytes)
    fixture = fixture_bytes = None
    if args.fixture:
        fixture_bytes = args.fixture.read_bytes()
        fixture = json.loads(fixture_bytes)
    head = subprocess.run(["git", "-C", str(args.worktree), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    try:
        matrix = build(record, raw_bytes, args.run_id, display_path(args.trace), adapter=adapter, verify=verify, locator=locator,
                       fixture=fixture, fixture_display=display_path(args.fixture, args.worktree) if args.fixture else None,
                       fixture_bytes=fixture_bytes, worktree_head=head)
        body = canonical(matrix)
        problems = validate(body, record, raw_bytes, fixture=fixture)
        if problems:
            raise Rejected(4, f"matrix validation failed with {len(problems)} error(s)", problems)
    except Rejected as r:
        print(f"REJECTED {args.run_id}: {r}", file=sys.stderr)
        for e in r.errors[:25]:
            print(f"  - {e}", file=sys.stderr)
        if len(r.errors) > 25:
            print(f"  … {len(r.errors) - 25} more", file=sys.stderr)
        return r.code
    args.out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{args.run_id}.matrix.json"
    (args.out_dir / name).write_text(body, encoding="utf-8")
    update_manifest(args.out_dir, args.run_id, name, body, matrix)
    c = matrix["counts"]
    print(f"{args.run_id}: {len(matrix['rows'])} agents, {c['model_calls']} model calls ({c['per_row']['$unresolved']} unresolved), "
          f"delivery telemetry {matrix['telemetry']['delivery']}, {c['delivers']} delivers, "
          f"{len(matrix['fixture_links'])} fixture links reproduced -> {display_path(args.out_dir / name)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
