"""Build a Belief Explorer bundle (agenttrace-explorer-bundle/0.1) for one agent-council run.

    python3 -I scripts/explorer/build_council_bundle.py --archive data/agent-council/agent_traces_20.zip --run TR-20261102192218-620bef53
    python3 -I scripts/explorer/build_council_bundle.py --input path/to/TR-....json [--annotations path/to/x.semantic.json] [--out DIR]

Local only, stdlib only, no model.  Steps:
  1. scripts/explorer/council_adapter.py reads the run read-only and builds the agent-council-structure/0.1 record.
  2. That record is mapped onto bundle 0.1 using only fields the contract (src/explorer/CONTRACT.md) or the
     existing Gomoku bundle already use.  What 0.1 cannot hold stays in the structure record, written next to
     the bundle (see scripts/explorer/COUNCIL_ADAPTER.md, "Contract decisions").
  3. Annotations: a hand-grounded agenttrace.semantic/0.3 slice is used only if one exists for this exact run
     (default: local/agent-council/<trace_id>/*.semantic.json) and its member sha256 matches the source; every
     claim span is re-checked against the source.  Without one the run is marked "Not annotated" and no claim,
     proposition or state is produced.  The 0.3 file is only read.
  4. The bundle is checked by scripts/explorer/validate_bundle.py; nothing is written on failure.
  Optional contract extensions used here (C1, C2, C4, C5): code-execution columns, edges from code-built messages,
  framework-computed positions (top-level `positions`) and framework-authored claims with state null (src/explorer/CONTRACT.md).

Output (default local/agent-council/bundles/, gitignored by /local/):
  <trace_id>.bundle.json   and   <trace_id>.structure.json
The Belief Explorer manifest (src/explorer/data/index.json) is not touched.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import council_adapter as ca  # noqa: E402
import council_findings as cf  # noqa: E402
from validate_bundle import validate  # noqa: E402

AP_ROOT = HERE.parents[1]
CONTRACT = "agenttrace-explorer-bundle/0.1"
SCHEMA = AP_ROOT / "docs/agenttrace.semantic.0.3.md"
SCHEMA_SHA = "2273d210090d19c17f75e98bb06875e0c55ef10b9c26528ea2471cee25c01c06"
HAND = "hand-annotated, illustrative, not gold"
OUT_DIR = AP_ROOT / "local/agent-council/bundles"
ANN_ROOT = AP_ROOT / "local/agent-council"
# agenttrace.compare/0.1, read by file path from the AssetOpsBench worktree (b9e09f6); optional.
COMPARE = AP_ROOT.parent / "AssetOpsBench-agenttrace-spec/src/agent/deep_agent/_semantic_compare.py"
EXCERPT_MAX = 2000  # validator limit on excerpt text

MECH_LABEL = {"llm_analysis": "LLM analysis", "llm_voice": "LLM voice", "deterministic": "deterministic code"}
OUT_LABEL = {"complete": "output complete", "truncated": "output truncated", "unknown": "output unknown"}


class BuildError(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise BuildError(msg)


def canonical(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1) + "\n"


def excerpt(text: str | None, complete_source: bool, spans=()) -> dict:
    if text is None:
        return {"text": "", "start": 0, "complete": False, "to_end": False, "spans": []}
    cut = text[:EXCERPT_MAX]
    whole = len(cut) == len(text) and complete_source
    return {"text": cut, "start": 0, "complete": whole, "to_end": whole, "spans": [list(s) for s in spans if s[1] <= len(cut)]}


def find_annotations(tid: str, explicit: Path | None) -> Path | None:
    if explicit:
        return explicit
    d = ANN_ROOT / tid
    hits = sorted(d.glob("*.semantic.json")) if d.is_dir() else []
    need(len(hits) <= 1, f"{len(hits)} *.semantic.json files in {ca.rel(d)}; pass --annotations")
    return hits[0] if hits else None


# ------------------------------------------------------------------------------------------- mapping


def build(raw: dict, rec: dict, ann_path: Path | None, findings_path: Path | None = None, compare=None, compare_path: Path | None = None) -> dict:
    tid = rec["run"]["trace_id"]
    calls = rec["model_calls"]
    call_by_id = {c["id"]: c for c in calls}
    ag = {a["id"]: a for a in rec["agents"]}
    xs = {x["id"]: x for x in rec["executions"]}
    msgs = {m["id"]: m for m in rec["messages"]}

    def name(a):
        return (ag.get(a) or {}).get("name") or a

    # ---- evidence map: query, messages, model outputs, evidence records, final decision
    ev = {}
    q = rec["run"]["query"]
    if q["text"] is not None:
        ev["query"] = {"id": "query", "label": "User query", "step": q["event"]["seq"] if q["event"] else None, "tool": None, "kind": "query", "source": "user",
                       "produced_by": None, "locator": q["locator"], "sha256": q["sha256"], "size": q["chars"], "excerpt": excerpt(q["text"], True), "origin": "observed"}
    for m in rec["messages"]:
        text = ca.resolve(raw, m["content"]["locator"]) if m["content"]["chars"] is not None else None
        prod = m["producer"]["call"] if m["producer"] else None
        ev[f"msg:{m['id']}"] = {"id": f"msg:{m['id']}", "label": f"{m['id']} {m['type']} from {name(m['sender'])}", "step": m["seq"], "tool": None, "kind": "message",
                                "source": "agent" if m["text_mechanism"] == "llm_voice" else "framework", "produced_by": prod,
                                "locator": m["content"]["locator"], "sha256": m["content"]["sha256"], "size": m["content"]["chars"],
                                "excerpt": excerpt(text, True), "origin": "observed" if text is not None else "unresolved",
                                "text_mechanism": m["text_mechanism"]}
    for c in calls:
        o = c["output"]
        text = ca.resolve(raw, o["locator"]) if o["excerpt_chars"] is not None else None
        ev[f"out:{c['id']}"] = {"id": f"out:{c['id']}", "label": f"{name(c['agent'])} · {c['execution']} output ({OUT_LABEL[o['status']]})", "step": c["order"], "tool": None,
                                "kind": "model_output", "source": "agent", "produced_by": c["id"], "locator": o["locator"], "sha256": o["excerpt_sha256"],
                                "size": o["response_chars"], "excerpt": excerpt(text, o["status"] == "complete"),
                                "origin": "observed" if text is not None else "unresolved", "output_status": o["status"]}
    for x in rec["evidence"]:
        ev[x["id"]] = {"id": x["id"], "label": f"{x['id']} · {x['kind']} · {x['provenance']}" + (f" · {x['label']}" if x["label"] else ""),
                       "step": x["retrieved_event"]["seq"] if x["retrieved_event"] else None, "tool": None, "kind": f"evidence_{x['kind']}", "source": "framework",
                       "produced_by": None, "locator": x["src"]["locator"], "sha256": None, "size": None,
                       "excerpt": excerpt(x["description"], True), "origin": "observed"}
    fd = rec["final_decision"]
    if fd:
        ev["final"] = {"id": "final", "label": "Final decision (framework marker)", "step": fd["event"]["seq"], "tool": None, "kind": "final_decision", "source": "framework",
                       "produced_by": None, "locator": f"{fd['locator']}.final_diagnosis", "sha256": ca.sha(fd["diagnosis"]) if fd["diagnosis"] else None,
                       "size": len(fd["diagnosis"]) if fd["diagnosis"] else None, "excerpt": excerpt(fd["diagnosis"], True), "origin": "observed"}

    # ---- columns: model calls in observation order (contract: matrix columns are model calls)
    recv = defaultdict(list)  # call -> [(message, delivery)] recorded deliveries
    for m in rec["messages"]:
        for d in m["deliveries"]:
            if d["class"] == "recorded_delivery":
                recv[d["call"]].append((m, d))
    tools_of = defaultdict(list)
    for t in rec["tool_calls"]:
        for cid in xs.get(t["execution"], {}).get("model_calls", []):
            tools_of[cid].append(t["tool"])
    spans = {c["id"]: xs[c["execution"]]["seq"] for c in calls}
    columns, sk_events, seen = [], [], defaultdict(set)
    for c in calls:
        need(c["order"] is not None, f"{c['id']}: no observation order")
        x = xs[c["execution"]]
        known = c["input"]["status"] == "verified"
        items = sorted({f"msg:{m['id']}" for m, _ in recv[c["id"]]})
        first = [i for i in items if i not in seen[c["agent"]]]
        seen[c["agent"]].update(items)
        a, b = spans[c["id"]]
        ov = sum(1 for o in calls if o["id"] != c["id"] and None not in (a, b, *spans[o["id"]]) and spans[o["id"]][0] <= b and a <= spans[o["id"]][1])
        label = f"{x['id']} · {MECH_LABEL[c['mechanism']]}"
        phase = f"{c['model']} · {x['kind']} · {x['stage']}" + (f" · round {x['round']}" if x["round"] is not None else "") + f" · {OUT_LABEL[c['output']['status']]}"
        if not known:
            phase += f" · input {c['input']['status'].replace('_', ' ')}"
        columns.append({"id": c["id"], "order": c["order"], "row": c["agent"], "steps": c["steps"], "label": label, "phase": phase,
                        "delivers": len(items) if known else None, "first": len(first) if known else None,
                        "delegation_out": False, "delegation_in": False, "overlaps": ov, "tools": tools_of[c["id"]], "origin": "observed"})
        sk_events.append({"id": c["id"], "kind": "model_call", "order": c["order"], "steps": c["steps"], "agent": c["agent"], "label": label, "phase": phase,
                          "produces": f"out:{c['id']}", "messages": c["voiced_messages"] or None,
                          "tokens": None, "origin": "observed"})
    for t in rec["tool_calls"]:
        sk_events.append({"id": t["id"], "kind": "tool_call", "order": t["event"]["seq"], "steps": [t["event"]["seq"], t["event"]["seq"]],
                          "agent": xs[t["execution"]]["agent"] if t["execution"] in xs else (t["actor"] or "$framework"), "label": f"tool {t['tool']}",
                          "phase": None, "produces": t["derived_id"], "messages": None, "tokens": None, "origin": "observed"})

    # ---- deterministic-execution columns (C1).  Rule: an execution with no model call that is the recorded sender
    # (messages[].sender_execution_id) of at least one message.  No event id, agent or count is special-cased.
    det_cols = deterministic_columns(raw, rec, calls, spans)
    for dc in det_cols:
        columns.append(dc)
        sk_events.append({"id": dc["id"], "kind": "deterministic_execution", "order": dc["order"], "steps": dc["steps"], "agent": dc["row"], "label": dc["label"],
                          "phase": dc["phase"], "produces": ", ".join(m["evidence"] for m in dc["messages"]), "messages": [m["id"] for m in dc["messages"]],
                          "tokens": None, "origin": "observed"})
        for m in dc["messages"]:  # a code-built message's producing unit is its execution column
            if m["text_mechanism"] == "deterministic" and m["evidence"] in ev:
                ev[m["evidence"]]["produced_by"] = dc["id"]
    columns.sort(key=lambda col: (col["order"], col["id"]))
    sk_events.sort(key=lambda e: (e["order"], e["id"]))

    # ---- edges: a message reaching another agent's model call through a recorded delivery (rendered_prompt, verified).
    # The edge starts at the message's producing unit: the model call for LLM-voiced text (C0), or the deterministic
    # execution column for code-built text (C2).  Code-only reads (inbox/board) never become edges, and no edge ends
    # at a deterministic execution: it has no model input.
    det_of_exec = {dc["execution"]["id"]: dc["id"] for dc in det_cols}
    edges, reached = [], set()
    for c in calls:
        for m, d in sorted(recv[c["id"]], key=lambda md: md[1]["seq"] or 0):
            if m["text_mechanism"] == "llm_voice":
                src = m["producer"]["call"] if m["producer"] else None
                src_agent = call_by_id[src]["agent"] if src else None
                made = ""
            else:
                src = det_of_exec.get(m["sender_execution"])
                src_agent = xs[m["sender_execution"]]["agent"] if src else None
                made = "template text built by code, "
            if not src or src_agent == c["agent"] or (m["id"], c["agent"]) in reached:
                continue
            reached.add((m["id"], c["agent"]))
            edges.append({"from": src, "to": c["id"], "item": f"msg:{m['id']}", "origin": "computed",
                          "via": f"{m['id']} {m['type']} ({made}rendered_prompt, {d['extent']}: {d['delivered_chars']} of {m['content']['chars']} chars in the hash-verified input)"})
    order_of = {col["id"]: col["order"] for col in columns}
    edges.sort(key=lambda e: (order_of[e["to"]], order_of[e["from"]]))

    rows = [{"id": a["id"], "label": a["name"] or a["id"], "kind": "agent", "origin": "observed",
             "sub": f"{a['model_calls']} model calls ({a['llm_analysis_calls']} analysis, {a['llm_voice_calls']} voice) · {a['deterministic_executions']} deterministic executions"}
            for a in rec["agents"]]
    agents_sk = [dict(r, parent=None) for r in rows]

    # ---- annotations (hand-grounded 0.3 slice for this exact run), else none
    claims, props, overlays, notes = [], [], [], []
    annotated = False
    ann_meta = {"annotation_file": None, "annotation_sha256": None}
    if ann_path is not None:
        claims, props, overlays, notes, extra_ev, cspans = annotations(raw, rec, ann_path, call_by_id, {dc["id"]: dc for dc in det_cols})
        ev.update(extra_ev)
        for key, sp in cspans:  # mark each claim span in its source excerpt
            ex = ev[key]["excerpt"]
            if sp[1] <= len(ex["text"]) and list(sp) not in ex["spans"]:
                ex["spans"].append(list(sp))
        annotated = True
        ann_meta = {"annotation_file": ca.rel(ann_path), "annotation_sha256": ca.sha(ann_path.read_bytes())}

    c = rec["counts"]
    dc = c["deliveries_by_class"]
    pos = positions_layer(raw, rec, columns)  # optional C4 field
    det_ids = {d["id"] for d in det_cols}
    n_llm_edges = sum(e["from"] not in det_ids for e in edges)
    facts = [
        {"id": "fact:final", "origin": "observed", "title": "Final decision",
         "text": (f"{fd['label']} (confidence {fd['confidence']}), review {fd['review_decision']}; framework marker FINAL_SYNTHESIS_GENERATED at seq {fd['event']['seq']}."
                  if fd else "No final-decision marker recorded.")
                 + "".join(f" {e['type']} at seq {e['seq']}" + (f" (message {e['message_id']})" if e["message_id"] else "") + "." for e in rec["events"] if e["type"] in REVIEW_EVENTS)},
        {"id": "fact:mechanisms", "origin": "computed", "title": "How each step was produced",
         "text": f"{c['model_calls']} model calls: {c['model_calls_by_mechanism'].get('llm_analysis', 0)} LLM analysis, {c['model_calls_by_mechanism'].get('llm_voice', 0)} LLM voice "
                 f"(rewording a code-built draft). {c['deterministic_executions']} of {c['executions']} executions are deterministic code with no model call. "
                 f"Messages: {c['messages_by_text_mechanism'].get('llm_voice', 0)} LLM-voiced, {c['messages_by_text_mechanism'].get('deterministic', 0)} code/template text. "
                 f"{len(det_cols)} deterministic executions posted messages and are shown as code-execution columns (no model input); they are not counted as model calls."},
        {"id": "fact:outputs", "origin": "computed", "title": "Model outputs",
         "text": f"Logged response: {c['model_output'].get('complete', 0)} complete, {c['model_output'].get('truncated', 0)} truncated (unlogged tail UNKNOWN), "
                 f"{c['model_output'].get('unknown', 0)} unknown. Model input: {c['model_input'].get('verified', 0)} hash-verified, "
                 f"{c['model_input'].get('not_recorded_per_call', 0)} not recorded per call (multi-call execution), {c['model_input'].get('mismatch', 0)} mismatched, {c['model_input'].get('absent', 0)} absent."},
        {"id": "fact:delivery", "origin": "computed", "title": "Message delivery vs code access",
         "text": f"{c['delivery_records']} delivery records: {dc.get('recorded_delivery', 0)} recorded in a model's rendered input "
                 f"({c['recorded_deliveries_by_extent'].get('whole', 0)} whole, {c['recorded_deliveries_by_extent'].get('prefix', 0)} prefix only); "
                 f"{dc.get('code_access', 0) + dc.get('code_access_no_execution', 0)} code-only reads (inbox/board), not model input; "
                 f"{dc.get('rendered_prompt_unverified', 0) + dc.get('rendered_prompt_content_not_found', 0)} rendered_prompt records not verified. Only recorded deliveries are counted in the grid. "
                 f"Grid edges: {n_llm_edges} carry an LLM-voiced message from a model call, {len(edges) - n_llm_edges} a code-built message from a code-execution column; code-only reads are never edges."},
        {"id": "fact:positions", "origin": "computed", "title": "Framework-computed positions",
         "text": f"{c['positions']} per-agent positions, {c['joint_positions']} joint rankings and {c.get('hypothesis_score_records', 0)} overall hypothesis-score records "
                 f"({len(pos['score_states']) if pos else 0} distinct score states) are computed by the council code, not expressed claims. "
                 "They are shown in the Computed positions view, apart from claims, and never as beliefs or states."},
        {"id": "fact:council", "origin": "observed", "title": "Rounds and disagreements",
         "text": f"{c['rounds']} timeline rounds; {c['disagreements']} framework-recorded disagreement(s)"
                 + (": " + "; ".join(f"{d.get('message_id')} {d.get('challenger')} → {', '.join(d.get('challenged') or [])} ({d.get('challenge_status')}, {d.get('resolution_status')})" for d in rec["disagreements"]) if rec["disagreements"] else "") + "."},
        {"id": "fact:annotation", "origin": "hand-annotated" if annotated else "computed", "title": "Annotation",
         "text": (f"Claims come from the hand-grounded 0.3 slice {ann_meta['annotation_file']}; every span re-checked against the source. " + " ".join(notes))
                 if annotated else "Not annotated: no claim, proposition or state is derived from the natural-language text of this run."},
    ]
    bundle = {
        "contract": CONTRACT,
        "trace": {"id": tid, "label": f"Agent council · {tid[3:7]}-{tid[7:9]}-{tid[9:11]} {tid[11:13]}:{tid[13:15]}:{tid[15:17]} · {fd['label'] if fd else 'no final decision'}",
                  "kind": "multi-agent", "framework": f"IDA agent council ({rec['source']['raw_schema']})",
                  "model": f"{rec['run']['llm_model']} (analysis); {rec['run']['council_llm_model']} (council voice)",
                  "scenario": (q["text"] or "")[:160], "status": rec["run"]["status"],
                  "answer": {"event": None, "step": fd["event"]["seq"], "evidence": "final"} if fd else None, "summary": None},
        "honesty": {"annotations": HAND if annotated else "Not annotated",
                    "skeleton": "computed by scripts/explorer/council_adapter.py from the recorded executions, model calls, messages and events",
                    "rules": ["Delivered means present in a model call's hash-verified rendered input, not used.",
                              "Inbox and board reads are code-only access: the message reached agent code, not a model input.",
                              "A call whose input is not recorded per call has delivery UNKNOWN; non-delivery is never asserted.",
                              "Framework-computed positions are scores, not claims or beliefs.",
                              "LLM voice calls reword a code-built draft; their wording is not independent testimony.",
                              "Columns are framework event order (seq) only."]},
        "provenance": {"raw_trace": (f"{rec['source']['archive']}!{rec['source']['member']}" if "archive" in rec["source"] else rec["source"]["file"]),
                       "raw_trace_sha256": rec["source"].get("member_sha256") or rec["source"].get("sha256"),
                       "archive_sha256": rec["source"].get("archive_sha256"), "adapter": "scripts/explorer/council_adapter.py", "adapter_output": ca.STRUCTURE,
                       "verifier": None, "compare": None, "worktree_head": None, "schema_sha256": SCHEMA_SHA, "matrix_file": None, "matrix_sha256": None,
                       **ann_meta, "builder": "scripts/explorer/build_council_bundle.py"},
        "layers": {"skeleton": True, "matrix": bool(columns), "claims": bool(claims), "evidence": True,
                   "delivery": any(col["delivers"] is not None for col in columns), "o3": False, "flags": False},
        "skeleton": {"origin": "computed", "agents": agents_sk, "events": sk_events, "handoffs": edges,
                     "counts": {**{k: v for k, v in c.items() if not isinstance(v, dict)},
                                "evidence": sum(1 for x in ev.values() if x["kind"] != "annotated_item"),
                                "delivers": dc.get("recorded_delivery", 0)}, "counts_origin": "computed",
                     "skipped": [{"kind": "deterministic_execution", "steps": [x["seq"][0] for x in rec["executions"] if x["mechanism"] == "deterministic" and f"exec:{x['id']}" not in det_ids]},
                                 {"kind": "code_only_message_access", "steps": sorted({d["seq"] for m in rec["messages"] for d in m["deliveries"] if d["class"].startswith("code_access") and d["seq"] is not None})},
                                 {"kind": "framework_computed_position", "steps": sorted({p["seq"] for p in rec["positions"] if p["seq"] is not None})}]},
        "matrix": {"origin": "computed", "source_contract": None,
                   "axis": "model calls (seq of LLM_CALL_COMPLETED) and message-producing code executions (seq of their first MESSAGE_SENT), in framework event order",
                   "rows": rows, "columns": columns, "edges": edges, "delivery_track": True,
                   "max_delivers": max((col["delivers"] or 0 for col in columns), default=0), "overlays": overlays,
                   "note": "Input track: messages in the call's rendered input. Code-execution columns made no model call, so they have no input track. Other deterministic executions and inbox/board reads are not columns or edges (see Skeleton).",
                   "order_caveat": rec["order_caveat"]},
        "evidence": ev, "propositions": props, "claims": claims, "non_claims": [], "flags": [], "facts": facts,
        "checks": {"structure_counts": {k: v for k, v in c.items() if not isinstance(v, dict)}, "ambiguities": len(rec["ambiguities"]), "annotated": annotated,
                   "columns": {"model_call": len(columns) - len(det_cols), "deterministic_execution": len(det_cols)},
                   "edges": {"from_model_call": n_llm_edges, "from_deterministic_execution": len(edges) - n_llm_edges},
                   "claims": {"agent": sum(cl["state"] is not None for cl in claims), "framework_no_state": sum(cl["state"] is None for cl in claims)}},
    }
    if pos:
        bundle["positions"] = pos
    # compare/0.1 O3 over the hand-grounded slice, then hand-validated findings (council_findings.py).
    comp = cf.apply_o3(bundle, ann_path, compare) if annotated else None
    if comp is not None and compare_path is not None:
        bundle["provenance"]["compare_module"] = cf.compare_ref(compare_path, AP_ROOT)
    if findings_path is not None:
        need(annotated, "a findings file needs the run's hand-grounded 0.3 slice")
        flags, assessment = cf.findings(raw, rec, bundle, findings_path, comp, ann_path)
        bundle["flags"] = flags
        bundle["layers"]["flags"] = bool(flags)
        bundle["provenance"]["findings_file"] = assessment["source"]
        bundle["provenance"]["findings_sha256"] = assessment["source_sha256"]
    else:
        assessment = cf.not_assessed("no hand-validated findings exist for this run." if not annotated
                                     else "this run has a hand-grounded slice but no hand-validated findings file.")
    bundle["assessment"] = assessment
    return bundle


POSITIONS_LABEL = "Framework-computed positions — not agent beliefs"
POSITION_KINDS = ("agent_position", "joint_ranking", "hypothesis_scores", "final_decision")


def leader(scores: dict | None) -> dict | None:
    """Top label(s) of a recorded score vector.  Exact ties are kept as ties; nothing is rounded."""
    if not scores:
        return None
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    top = ranked[0][1]
    labels = sorted(k for k, s in ranked if s == top)
    second = next((s for _, s in ranked if s < top), None)
    return {"labels": labels, "score": top, "tie": len(labels) > 1,
            "margin": round(top - second, 6) if second is not None and len(labels) == 1 else (0.0 if len(labels) > 1 else None), "origin": "computed"}


def positions_layer(raw: dict, rec: dict, columns: list) -> dict | None:
    """Optional bundle field `positions` (C4): every framework-computed score observation in the structure record,
    kept apart from claims and states.  Joins are by recorded ids only (message_id, execution_id); never by seq proximity."""
    msgs = {m["id"]: m for m in rec["messages"]}
    xs = {x["id"]: x for x in rec["executions"]}
    col_ids = {c["id"] for c in columns}
    rounds = {r["round"]: r for r in rec["rounds"]}
    ag = {a["id"] for a in rec["agents"]}

    def msg_rel(mid):
        m = msgs.get(mid)
        if not m:
            return {"message": mid, "found": False, "columns": [], "received_in": [], "join": "message_id not among recorded messages", "origin": "computed"}
        prod = (m["producer"] or {}).get("call")
        col = prod if prod in col_ids else (f"exec:{m['sender_execution']}" if f"exec:{m['sender_execution']}" in col_ids else None)
        return {"message": mid, "found": True, "type": m["type"], "sender": m["sender"], "sender_execution": m["sender_execution"], "text_mechanism": m["text_mechanism"],
                "evidence": f"msg:{mid}", "sent_event": m["sent_event"], "columns": [col] if col else [],
                "column_rule": ("producing model call (message producer)" if col == prod else "code-execution column of the sender execution") if col else
                               "no grid column: the producing call is unresolved and the sender execution has no column",
                "received_in": [d["call"] for d in m["deliveries"] if d["class"] == "recorded_delivery"],
                "code_access": sum(d["class"].startswith("code_access") for d in m["deliveries"]),
                "join": "message_id", "origin": "computed"}

    def exec_rel(xid):
        x = xs.get(xid)
        if not x:
            return None
        cols = [c for c in x["model_calls"] if c in col_ids] or ([f"exec:{xid}"] if f"exec:{xid}" in col_ids else [])
        return {"execution": xid, "agent": x["agent"], "columns": cols, "join": "execution_id", "origin": "computed",
                "column_rule": "model calls of the execution" if cols and not cols[0].startswith("exec:") else ("code-execution column" if cols else "the execution has no grid column")}

    def payload(mid):
        try:
            return ca.resolve(raw, f"messages[message_id={mid}].payload") or {}
        except KeyError:
            return {}

    obs = []

    def typed(e, t):
        return dict(e, type=t) if e else None

    def add(o, unknown):
        o["unknown"] = {k: r for k, r in unknown.items()}
        o["leading"] = leader(o.get("scores"))
        obs.append(o)

    for p in rec["positions"]:
        pl = payload(p["message_id"])
        unk = {}
        if p["confidence"] is None:
            unk["confidence"] = "not recorded in this position"
        if not p["position"]:
            unk["scores"] = "no score vector recorded"
        if p["round"] is None:
            unk["round"] = "no round recorded"
        add({"kind": "agent_position", "holder": {"kind": "agent", "agent": p["agent"]}, "seq": p["seq"], "seq_basis": "position seq (equals its message's seq)",
             "round": p["round"], "phase": p["phase"], "stage": pl.get("stage"), "draft": p["draft"], "locator": p["src"]["locator"],
             "event": typed(msg_rel(p["message_id"]).get("sent_event"), "MESSAGE_SENT"), "event_join": "MESSAGE_SENT of the position's message_id",
             "scores": p["position"], "recorded_label": p["label"], "confidence": p["confidence"], "confidence_field": "confidence",
             "abstain": p["abstain"], "old_label": p["old_label"], "moved_by": p["moved_by"] or [], "method": pl.get("method"),
             "message_payload": {"locator": f"messages[message_id={p['message_id']}].payload", "same_scores": pl.get("position") == p["position"],
                                 "same_label": pl.get("label") == p["label"], "origin": "computed"},
             "related": msg_rel(p["message_id"]), "origin": "observed"}, unk)
    for j in rec["joint_positions"]:
        pl = payload(j["message_id"])
        also = [e for e in rec["events"] if e["type"] == "JOINT_FINDING_REACHED"]
        raw_pl = {e["seq"]: e.get("payload") or {} for e in raw["events"]}
        also = [{"seq": e["seq"], "event_id": e["event_id"], "type": e["type"], "locator": e["locator"]} for e in also
                if raw_pl[e["seq"]].get("phase") == j["phase"] and raw_pl[e["seq"]].get("joint") == j["joint"] and raw_pl[e["seq"]].get("label") == j["label"]]
        unk = {} if j["council_confidence"] is not None else {"confidence": "no council_confidence recorded"}
        mp = pl.get("positions") if isinstance(pl.get("positions"), dict) else None
        add({"kind": "joint_ranking", "holder": {"kind": "council", "agent": None}, "seq": j["seq"], "seq_basis": "joint position seq (equals its message's seq)",
             "round": j["round_id"], "phase": j["phase"], "stage": pl.get("stage"), "draft": None, "locator": j["src"]["locator"],
             "event": typed(msg_rel(j["message_id"]).get("sent_event"), "MESSAGE_SENT"), "event_join": "MESSAGE_SENT of the joint position's message_id",
             "scores": j["joint"], "recorded_label": j["label"], "confidence": j["council_confidence"], "confidence_field": "council_confidence",
             "converged": j["converged"], "dissent": j["dissent"] or [],
             "member_positions": {"values": mp, "locator": f"messages[message_id={j['message_id']}].payload.positions",
                                  "note": "per-agent scores as listed in the joint message payload (the labels it lists only)", "origin": "observed"} if mp else None,
             "also_recorded_at": also, "also_rule": "JOINT_FINDING_REACHED events whose payload phase, label and joint scores equal this record (no message_id is recorded on them)",
             "related": msg_rel(j["message_id"]), "origin": "observed"}, unk)
    for h in rec.get("hypothesis_scores", []):
        unk = {"confidence": "no confidence is recorded with a score vector"}
        if h["round"] is None:
            unk["round"] = "no round recorded" + (f"; stage {h['stage']}" if h["stage"] else "")
        if h["event"] is None:
            unk["event"] = "no event joined by execution_id"
        rel_ = exec_rel(h["execution"]) if h["execution"] else None
        add({"kind": "hypothesis_scores", "holder": {"kind": "framework", "agent": None, "recorded_on_execution": h["execution"], "execution_agent": h["actor"] if h["execution"] else None},
             "seq": h["seq"], "seq_basis": {"event": "event seq", "execution_input": "execution seq_start", "execution_output": "seq of the execution's AGENT_OUTPUT_GENERATED"}[h["basis"]],
             "round": h["round"], "phase": None, "stage": h["stage"], "draft": None, "locator": h["src"]["locator"],
             "basis": h["basis"], "part": h["part"], "source": h["source"],
             "event": typed(h["event"], h["event_type"]), "event_join": {"event": "the scoring event itself", "execution_input": "AGENT_STARTED of the execution_id",
                                                 "execution_output": "AGENT_OUTPUT_GENERATED of the execution_id"}[h["basis"]],
             "scores": h["scores"], "recorded_label": None, "confidence": None, "confidence_field": None,
             "execution_finding": h.get("execution_finding"),
             "related": rel_ or {"columns": [], "join": "no execution recorded on the event", "origin": "computed"}, "origin": "observed"}, unk)
    fd = rec["final_decision"]
    if fd:
        m = msgs.get(fd["message_id"])
        add({"kind": "final_decision", "holder": {"kind": "framework", "agent": None, "actor": fd["actor"]}, "seq": fd["event"]["seq"], "seq_basis": "FINAL_SYNTHESIS_GENERATED seq",
             "round": m["round"] if m else None, "phase": None, "stage": m["stage"] if m else None, "draft": None, "locator": fd["locator"],
             "event": dict(fd["event"], type="FINAL_SYNTHESIS_GENERATED"), "event_join": "the final-synthesis event itself",
             "scores": None, "recorded_label": fd["label"], "confidence": fd["confidence"], "confidence_field": "confidence",
             "review_decision": fd["review_decision"], "evidence": "final",
             "related": msg_rel(fd["message_id"]) if fd["message_id"] else {"columns": [], "join": "no message_id on the event", "origin": "computed"}, "origin": "observed"},
            {"scores": "no score vector is recorded with the final decision"} | ({} if m and m["round"] is not None else {"round": "no round recorded"})
            | ({} if fd["confidence"] is not None else {"confidence": "no confidence recorded on the final-synthesis event"}))
    if not obs:
        return None
    obs.sort(key=lambda o: (o["seq"] is None, o["seq"] or 0, POSITION_KINDS.index(o["kind"])))
    for i, o in enumerate(obs):
        o["id"] = f"pos:{i:03d}"

    # Shared score states: hypothesis-score observations grouped by equal recorded values.  Rule: an observation joins
    # the earliest state whose values agree exactly on every shared label, where one label set contains the other.
    # Matching more than one state is recorded as ambiguous.  States are numbered S0, S1, ... in order of first record.
    states = []
    for o in (o for o in obs if o["kind"] == "hypothesis_scores"):
        sc = o["scores"]
        fits = [s for s in states if (set(sc) <= set(s["scores"]) or set(s["scores"]) <= set(sc)) and all(s["scores"][k] == sc[k] for k in set(sc) & set(s["scores"]))]
        if len(fits) > 1:
            o["score_state"], o["score_state_ambiguous"] = None, [s["id"] for s in fits]
            continue
        if fits:
            s = fits[0]
            s["scores"].update(sc)
        else:
            s = {"id": f"S{len(states)}", "scores": dict(sc), "observations": [], "origin": "computed"}
            states.append(s)
        s["observations"].append(o["id"])
        o["score_state"] = s["id"]
    byid = {o["id"]: o for o in obs}
    for s in states:
        first = byid[s["observations"][0]]
        s.update(first_seq=first["seq"], first_locator=first["locator"], leading=leader(s["scores"]), labels_recorded=len(s["scores"]))

    # Axis: rounds where recorded (timeline label), else the recorded stage; consecutive observations in seq order
    # with the same key share one segment, so a stage that recurs later gets its own segment.
    segs = []
    for o in obs:
        key = f"round:{o['round']}" if o["round"] is not None else f"stage:{o['stage']}"
        if not segs or segs[-1]["key"] != key:
            r = rounds.get(o["round"]) if o["round"] is not None else None
            segs.append({"id": f"seg:{len(segs)}", "key": key, "round": o["round"], "phase": r["phase"] if r else o["phase"],
                         "label": r["label"] if r else (f"Round {o['round']}" if o["round"] is not None else (f"{o['stage']} (no round recorded)" if o["stage"] else "no round or stage recorded")),
                         "first_seq": o["seq"], "origin": "computed"})
        o["segment"] = segs[-1]["id"]
        segs[-1]["last_seq"] = o["seq"]
    for sg in segs:
        sg.pop("key")

    cand = []
    for o in obs:
        for k in (o["scores"] or {}):
            if k not in cand:
                cand.append(k)
    for o in obs:
        if o["scores"] is not None:
            o["missing_labels"] = [k for k in cand if k not in o["scores"]]
    agents = [a["id"] for a in rec["agents"] if any(o["holder"].get("agent") == a["id"] and o["kind"] == "agent_position" for o in obs)]
    need(all(o["holder"]["agent"] in ag for o in obs if o["kind"] == "agent_position"), "position for an unknown agent")
    return {
        "origin": "computed", "label": POSITIONS_LABEL, "producer": "framework_computed",
        "source": f"{ca.STRUCTURE}: positions, joint_positions, hypothesis_scores, final_decision",
        "candidates": cand, "agents": agents, "segments": segs, "observations": obs, "score_states": states,
        "counts": {k: sum(o["kind"] == k for o in obs) for k in POSITION_KINDS},
        "rules": ["Every value is copied from the raw trace by locator; the council code computed it. None is a claim, a belief or a state.",
                  "Leading diagnosis is the top recorded score (exact ties shown as ties). Where labels are missing, it is the top of the recorded labels only.",
                  "Joint rankings, overall hypothesis scores and the final decision belong to no agent. A change of shared score state is not an agent revising a view.",
                  "Links are recorded joins only (message_id, execution_id, or equal payload values); nothing is linked by seq proximity.",
                  "Score states group overall hypothesis-score records with exactly equal values on shared labels."],
    }


REVIEW_EVENTS = {"HUMAN_REVIEW_TRIGGERED", "DISAGREEMENT_RESOLVED"}  # framework review/resolution records, listed in fact:final
MSG_REF_EVENT_SKIP = {"MESSAGE_RECEIVED"}  # receipts are listed per delivery (code_access), not again as events


def _scalars(payload: dict) -> dict:
    """The payload's scalar fields (short strings, numbers, booleans, null), for display; lists and objects are omitted."""
    return {k: v for k, v in (payload or {}).items() if v is None or isinstance(v, (bool, int, float)) or (isinstance(v, str) and len(v) <= 240)}


def deterministic_columns(raw: dict, rec: dict, calls: list, spans: dict) -> list[dict]:
    """Columns for deterministic executions that posted at least one recorded message (bundle column kind
    `deterministic_execution`).  Structural only: the rule reads execution mechanism and message sender ids."""
    raw_payload = {e["seq"]: e.get("payload") for e in raw["events"]}
    sent_by = defaultdict(list)
    for m in rec["messages"]:
        sent_by[m["sender_execution"]].append(m)
    ev_by_exec, ev_by_msg = defaultdict(list), defaultdict(list)
    for e in rec["events"]:
        if e["execution_id"]:
            ev_by_exec[e["execution_id"]].append(e)
        elif e["message_id"]:
            ev_by_msg[e["message_id"]].append(e)
    reads = defaultdict(list)  # execution -> code-only reads of messages by that execution
    for m in rec["messages"]:
        for d in m["deliveries"]:
            if d["class"] == "code_access" and d["execution"]:
                reads[d["execution"]].append((m, d))
    dis_by_msg = defaultdict(list)
    for d in rec["disagreements"]:
        dis_by_msg[d.get("message_id")].append(d)

    def ev_entry(e, join):
        return {"seq": e["seq"], "type": e["type"], "event_id": e["event_id"], "timestamp": e["timestamp"], "actor": e["actor"], "message": e["message_id"],
                "join": join, "fields": _scalars(raw_payload.get(e["seq"])), "locator": e["locator"]}

    out = []
    for x in rec["executions"]:
        ms = sorted(sent_by.get(x["id"], []), key=lambda m: m["seq"])
        if x["mechanism"] != "deterministic" or not ms:
            continue
        a, b = x["seq"]
        sent = [m["sent_event"]["seq"] for m in ms if m["sent_event"]]
        order = min(sent) if sent else ms[0]["seq"]
        mids = {m["id"] for m in ms}
        events = [ev_entry(e, "execution") for e in ev_by_exec.get(x["id"], []) if e["type"] not in MSG_REF_EVENT_SKIP]
        events += [ev_entry(e, "message") for mid in sorted(mids) for e in ev_by_msg.get(mid, [])]
        events.sort(key=lambda e: e["seq"])
        ov = sum(1 for c in calls if None not in (a, b, *spans[c["id"]]) and spans[c["id"]][0] <= b and a <= spans[c["id"]][1])
        out.append({
            "id": f"exec:{x['id']}", "kind": "deterministic_execution", "order": order, "row": x["agent"], "steps": [a, b],
            "label": f"{x['id']} · code execution",
            "phase": f"{x['kind']} · {x['stage']}" + (f" · round {x['round']}" if x["round"] is not None else "") + " · no model call",
            "delivers": None, "first": None, "delegation_out": False, "delegation_in": False, "overlaps": ov, "tools": [], "origin": "observed",
            "order_basis": "seq of the execution's first MESSAGE_SENT event" if sent else "seq of its first message record (no MESSAGE_SENT event)",
            "execution": {"id": x["id"], "assigned_agent": x["agent"], "agent_name": x["agent_name"], "role": x["role"], "kind": x["kind"], "stage": x["stage"],
                          "round": x["round"], "status": x["status"], "started_at": x["started_at"], "completed_at": x["completed_at"],
                          "started_event": x["started_event"], "mechanism": x["mechanism"], "mechanism_rule": x["mechanism_rule"], "locator": x["src"]["locator"]},
            "messages": [{"id": m["id"], "type": m["type"], "seq": m["seq"], "evidence": f"msg:{m['id']}", "text_mechanism": m["text_mechanism"], "voice_raw": m["voice_raw"],
                          "sent_event": m["sent_event"], "response_to": m["response_to"], "parent": m["parent"], "receivers": m["receivers"],
                          "recorded_deliveries": [d["call"] for d in m["deliveries"] if d["class"] == "recorded_delivery"],
                          "code_access": sum(d["class"].startswith("code_access") for d in m["deliveries"]), "locator": m["src"]["locator"],
                          "disagreements": [{"original_assertion": d.get("original_assertion"), "challenger": d.get("challenger"), "challenged": d.get("challenged"),
                                             "challenge_status": d.get("challenge_status"), "resolution_status": d.get("resolution_status"),
                                             "replies": [r.get("message_id") for r in d.get("replies") or []], "locator": d["src"]["locator"]} for d in dis_by_msg.get(m["id"], [])]}
                         for m in ms],
            "code_access": [{"message": m["id"], "type": m["type"], "from": m["sender"], "via": d["via"], "seq": d["seq"], "received_event": d["received_event"],
                             "locator": d["src"]["locator"]} for m, d in sorted(reads.get(x["id"], []), key=lambda md: md[1]["seq"] or 0)],
            "events": events,
        })
    return out


def annotations(raw, rec, path: Path, call_by_id, det_cols: dict):
    """Map a hand-grounded 0.3 slice for this run onto bundle claims.  Read-only; every span re-checked."""
    s = json.loads(path.read_text(encoding="utf-8"))
    rr = s.get("run", {}).get("raw_ref", {})
    need(s.get("run", {}).get("id") == rec["run"]["trace_id"], f"{ca.rel(path)} is for run {s.get('run', {}).get('id')!r}")
    src_sha = rec["source"].get("member_sha256") or rec["source"].get("sha256")
    need(rr.get("member_sha256") == src_sha, f"{ca.rel(path)} was grounded on a different source (sha256 {str(rr.get('member_sha256'))[:12]}…)")
    events = {e["id"]: e for e in s["events"]}
    evidence = {x["id"]: x for x in s["evidence"]}
    states = {c: st for st in s["states"] for c in st["claims"]}
    delivers = {(l["source"], l["target"]) for l in s["links"] if l["relation"] == "delivers"}
    plinks = defaultdict(list)
    for l in s["links"]:
        if l["relation"] in ("supported_by", "contradicted_by"):
            plinks[l["source"]].append(l)
    forms = {p["id"]: p["form"] for p in s["propositions"]}
    # Fixture model-call events join to adapter columns by (execution_id, LLM_CALL_COMPLETED seq).
    by_exec_seq = {(c["execution"], c["order"]): c["id"] for c in call_by_id.values()}

    det_by_exec = {dc["execution"]["id"]: cid for cid, dc in det_cols.items()}

    def det_column_of(eid):
        """A fixture event for a deterministic execution (raw_ref.execution_id, no event_type) -> its column, if one exists."""
        r = events[eid]["raw_ref"]
        cid = det_by_exec.get(r.get("execution_id")) if r.get("event_type") is None else None
        need(cid is None or list(r.get("seq") or []) == det_cols[cid]["steps"], f"fixture event {eid}: seq {r.get('seq')} != execution steps {cid and det_cols[cid]['steps']}")
        return cid

    def column_of(eid):
        e = events[eid]
        r = e["raw_ref"]
        if r.get("event_type") != "LLM_CALL_COMPLETED":
            return None
        cid = by_exec_seq.get((r.get("execution_id"), r.get("seq")))
        need(cid, f"fixture event {eid} (seq {r.get('seq')}) matches no model call")
        return cid

    extra, claims, props, overlays, skipped, spans, fw = {}, [], {}, [], [], [], []
    out_by_loc = {f"out:{c['id']}": c["output"]["locator"] for c in call_by_id.values()}
    loc_to_out = {v: k for k, v in out_by_loc.items()}
    for x in s["evidence"]:
        loc = x["raw_ref"].get("locator")
        if loc in loc_to_out:
            continue  # same item as an adapter model output; claims point at that entry
        text = ca.resolve(raw, loc)
        span = x["raw_ref"].get("span")
        piece = text[span[0]:span[1]] if span else text
        need(ca.sha(piece) == x["raw_ref"].get("sha256", ca.sha(piece)), f"{x['id']}: sha256 does not match the source")
        extra[x["id"]] = {"id": x["id"], "label": f"{x['id']} (hand-grounded)", "step": x["raw_ref"].get("seq"), "tool": None, "kind": "annotated_item",
                          "source": x["source"], "produced_by": None, "locator": loc + (f" [{span[0]}:{span[1]}]" if span else ""),
                          "sha256": x["raw_ref"].get("sha256"), "size": x["raw_ref"].get("size"), "excerpt": excerpt(piece, True), "origin": "observed"}

    def ev_key(xid):
        loc = evidence[xid]["raw_ref"].get("locator")
        return loc_to_out.get(loc, xid)

    for cl in s["claims"]:
        r = cl["raw_ref"]
        text = ca.resolve(raw, r["locator"])
        need(text[r["span"][0]:r["span"][1]] == r["text"], f"{cl['id']}: span text does not match the source")
        st = states.get(cl["id"])
        pb = evidence[cl["evidence"]].get("produced_by")
        col = column_of(pb) if pb in events else None
        det = det_column_of(pb) if pb in events else None
        pid = cl["proposition"]
        if st is None and det is not None:
            # C5: a framework-authored claim, produced by a deterministic execution.  It keeps no state (a state's holder
            # must be an entity, 0.3 §4.5): `state` is null and `state_absent` says why.  It is not an agent claim and
            # is never an O3 input.
            fw.append(cl["id"])
            x = det_cols[det]["execution"]
            links = [{"relation": l["relation"], "evidence": ev_key(l["target"]), "values": None, "rule_dependent": False, "origin": "hand-annotated",
                      "delivery": {"to_event": det, "value": "NOT_APPLICABLE", "operation": "the claiming unit is a code execution: it has no model input", "origin": "computed"}}
                     for l in plinks.get(pid, [])]
            claims.append({"id": cl["id"], "label": f"{pid.split(':')[-1]} · framework under {rec_name(rec, x['assigned_agent'])} · {x['id']} code", "words": r["text"],
                           "span": r["span"], "event": det, "step": det_cols[det]["order"], "speaker": "framework", "speaker_origin": "hand-annotated",
                           "assertive": True, "origin": "hand-annotated", "proposition": pid, "state": None,
                           "state_absent": {"reason": r.get("speaker_note") or "framework-authored template: no agent holds a state", "origin": "hand-annotated"},
                           "author": {"kind": "deterministic_execution", "execution": x["id"], "assigned_agent": x["assigned_agent"], "origin": "observed"},
                           "links": links,
                           "o3": {"status": "not computable", "origin": "computed", "reason": "framework-authored claim with no agent belief state; not an O3 input"},
                           "notes": [n for n in (r.get("not_extracted"),) if n], "fixture": {"file": ca.rel(path), "claim": cl["id"]}})
            props.setdefault(pid, {"id": pid, "form": forms[pid], "origin": "hand-annotated",
                                   "links": [{"relation": l["relation"], "evidence": ev_key(l["target"])} for l in plinks.get(pid, [])]})
            overlays.append({"id": f"ov:{cl['id']}", "kind": "claim", "column": det, "row": x["assigned_agent"], "ref": cl["id"],
                             "label": f"framework claim · {pid.split(':')[-1]}", "origin": "hand-annotated"})
            spans.append((ev_key(cl["evidence"]), r["span"]))
            continue
        if st is None or col is None:
            skipped.append(cl["id"])  # no state and no deterministic producer, or a state on a non-model-call unit
            continue
        speaker = call_by_id[col]["agent"]
        links = []
        for l in plinks.get(pid, []):
            delivered = (evidence[cl["evidence"]]["produced_by"], l["target"]) in delivers
            links.append({"relation": l["relation"], "evidence": ev_key(l["target"]), "values": None, "rule_dependent": False, "origin": "hand-annotated",
                          "delivery": {"to_event": col, "value": "DELIVERED" if delivered else "UNKNOWN", "operation": "lookup of the slice's hash-verified delivers links",
                                       "origin": "computed"}})
        key = ev_key(cl["evidence"])
        claims.append({"id": cl["id"], "label": claim_label(cl["id"], pid, rec_name(rec, speaker), call_by_id[col]), "words": r["text"], "span": r["span"], "event": col,
                       "step": call_by_id[col]["order"], "speaker": speaker, "speaker_origin": "observed", "assertive": True, "origin": "hand-annotated",
                       "proposition": pid, "state": {"value": st["value"], "origin": "hand-annotated"}, "links": links,
                       "o3": {"status": "not computable", "origin": "computed", "reason": "agenttrace.compare/0.1 is not run in this increment"},
                       "notes": [r.get("completeness")] if r.get("completeness") else [], "fixture": {"file": ca.rel(path), "claim": cl["id"]}})
        props.setdefault(pid, {"id": pid, "form": forms[pid], "origin": "hand-annotated",
                               "links": [{"relation": l["relation"], "evidence": ev_key(l["target"])} for l in plinks.get(pid, [])]})
        overlays.append({"id": f"ov:{cl['id']}", "kind": "claim", "column": col, "row": speaker, "ref": cl["id"], "label": f"claim · {pid.split(':')[-1]}", "origin": "hand-annotated"})
        spans.append((key, r["span"]))
    for pid in forms:
        if pid not in props and any(c["proposition"] == pid for c in claims):
            props[pid] = {"id": pid, "form": forms[pid], "origin": "hand-annotated", "links": []}
    notes = ([f"{len(fw)} framework-authored claim(s) ({', '.join(fw)}) are shown at their code-execution columns with no state; they are not agent claims and not O3 inputs."] if fw else []) \
        + ([f"{len(skipped)} claim(s) are not shown ({', '.join(skipped)}): no state on a model call, and no deterministic execution column."] if skipped else [])
    return claims, list(props.values()), overlays, notes, extra, spans


def claim_label(cid, pid, speaker, call):
    """`<proposition> · <speaker> · <execution> <mechanism>[ · <part>]`.  <part> is the slice's own claim-id
    qualifier after the proposition key (e.g. narrative / statement), which separates two claims of one call."""
    key = pid.split(":")[-1]
    tail = cid.split(f":{key}", 1)[1].lstrip(":") if f":{key}" in cid else ""
    mech = {"llm_analysis": "analysis", "llm_voice": "voice"}.get(call["mechanism"], call["mechanism"])
    return f"{key} · {speaker} · {call['execution']} {mech}" + (f" · {tail}" if tail else "")


def rec_name(rec, a):
    return next((x["name"] for x in rec["agents"] if x["id"] == a), a) or a


# ------------------------------------------------------------------------------------------- main


def run(archive=None, run_id=None, input_path=None, ann=None, out=OUT_DIR, write=True, findings=None, compare_path=COMPARE) -> dict:
    need(ca.sha(SCHEMA.read_bytes()) == SCHEMA_SHA, "schema 0.3 sha256 changed")
    raw, src = ca.load_run(archive, run_id, input_path)
    rec = ca.adapt(raw, src)
    ann_path = find_annotations(rec["run"]["trace_id"], ann)
    find_path = cf.find_findings(ANN_ROOT, rec["run"]["trace_id"], findings) if ann_path else None
    if findings and not ann_path:
        raise BuildError("a findings file needs the run's hand-grounded 0.3 slice")
    inputs = [p for p in (ann_path, find_path) if p]
    before = [ca.sha(p.read_bytes()) for p in inputs]
    compare = cf.load_compare(compare_path) if ann_path else None
    bundle = build(raw, rec, ann_path, find_path, compare, compare_path if compare else None)
    need([ca.sha(p.read_bytes()) for p in inputs] == before, "annotation or findings file changed during the build")
    problems = validate(bundle)
    need(not problems, f"bundle validation failed: {problems[:5]}")
    if write:
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{rec['run']['trace_id']}.bundle.json").write_text(canonical(bundle), encoding="utf-8")
        (out / f"{rec['run']['trace_id']}.structure.json").write_text(canonical(rec), encoding="utf-8")
    return {"bundle": bundle, "structure": rec}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--archive", type=Path)
    ap.add_argument("--run")
    ap.add_argument("--input", type=Path)
    ap.add_argument("--annotations", type=Path)
    ap.add_argument("--findings", type=Path, help="hand-validated findings file (default: local/agent-council/<trace id>/*.findings.json)")
    ap.add_argument("--compare", type=Path, default=COMPARE, help="path to agenttrace.compare/0.1 (_semantic_compare.py)")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    a = ap.parse_args(argv)
    try:
        r = run(a.archive, a.run, a.input, a.annotations, a.out, findings=a.findings, compare_path=a.compare)
    except (ca.AdapterError, BuildError, cf.FindingsError, KeyError) as e:
        print(f"STOPPED: {e}", file=sys.stderr)
        return 1
    b, s = r["bundle"], r["structure"]
    print(f"{b['trace']['id']}: {len(b['matrix']['rows'])} rows x {len(b['matrix']['columns'])} columns, {len(b['matrix']['edges'])} edges, "
          f"{len(b['evidence'])} evidence items, {len(b['claims'])} claims ({b['honesty']['annotations']}), {len(s['ambiguities'])} ambiguities; "
          f"O3 computed {sum(c['o3']['status'] == 'computed' for c in b['claims'])}; findings: {b['assessment']['label']} ({len(b['flags'])}); validator OK -> {ca.rel(a.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
