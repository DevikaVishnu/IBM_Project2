#!/usr/bin/env python3
"""Build small Belief Explorer bundles from reviewed IDA trace drafts.

The bundles deliberately show the reviewed story messages, not every execution.
Claims and their links remain hand-annotated; evidence, agents, and messages
are copied from the recorded ``ida.agenttrace/1.0`` raw trace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "agenttrace-explorer-bundle/0.1"


def canonical(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def agent_label(agent_id: str, agents: dict) -> str:
    return agents.get(agent_id, {}).get("name", agent_id.replace("_", " ").title())


def o3_for(claim: dict, message: dict, raw_trace: dict) -> dict:
    """Make only two narrow, trace-backed comparisons.

    This does not decide whether sensor evidence proves a diagnosis.  It only
    compares a selected statement against a recorded verification result or a
    recorded final run decision.
    """
    payload = message.get("payload") or {}
    if message.get("message_type") == "VERIFICATION_RESULT" and payload.get("label_status") == "VERIFIED":
        return {
            "status": "computed", "comparison": "AGREES", "direct": "VERIFIED",
            "delivered_direct": "NOT_APPLICABLE", "testimonial": "NOT_APPLICABLE",
            "meaning": "The trace records this verification result as VERIFIED.",
            "computed_from": "message payload.label_status", "operation": "IDA verification-result check",
            "origin": "computed",
        }
    final_label = raw_trace.get("final_label")
    review = raw_trace.get("review_decision")
    if message.get("message_type") == "SYNTHESIS" and final_label and final_label in message.get("message_content", "") and review and review in message.get("message_content", ""):
        return {
            "status": "computed", "comparison": "AGREES", "direct": "RECORDED_FINAL_DECISION",
            "delivered_direct": "NOT_APPLICABLE", "testimonial": "NOT_APPLICABLE",
            "meaning": "The selected final message exactly matches the trace's final label and review decision.",
            "computed_from": "trace.final_label and trace.review_decision", "operation": "IDA final-decision equality check",
            "origin": "computed",
        }
    return {"status": "not computable", "reason": "This rule does not interpret sensor evidence or choose between competing diagnoses.", "origin": "computed"}


def build(trace_id: str, label: str, raw_root: Path, draft_dir: Path) -> tuple[dict, str]:
    raw_path = raw_root / trace_id / f"{trace_id}.json"
    draft_path = draft_dir / f"{trace_id}-draft.json"
    raw = json.loads(raw_path.read_text())
    draft = json.loads(draft_path.read_text())
    messages = {m["message_id"]: m for m in raw["messages"]}
    executions = {e["execution_id"]: e for e in raw["executions"]}
    flow = {e["evidence_id"]: e for e in raw["evidence_flow"]}
    selected = sorted(draft["claims"], key=lambda c: messages[c["message_id"]]["seq"])
    agents = {c["agent"] for c in selected}

    events, columns = [], []
    for order, claim in enumerate(selected, 1):
        message = messages[claim["message_id"]]
        event_id = f"msg:{claim['message_id']}"
        execution = executions.get(message.get("sender_execution_id"), {})
        model_call = bool(execution.get("llm_calls"))
        events.append({
            "id": event_id, "kind": "model_call" if model_call else "check", "order": order,
            "steps": [message["seq"], message["seq"]], "agent": claim["agent"],
            "label": message["message_type"].replace("_", " ").lower(), "origin": "observed",
        })
        columns.append({
            "id": event_id, "order": order, "row": claim["agent"], "steps": [message["seq"], message["seq"]],
            "delivers": None, "first": None, "delegation_out": False, "delegation_in": False,
            "overlaps": 0, "tools": [], "origin": "observed", "label": message["message_id"],
        })

    evidence_ids = sorted({eid for c in selected for eid in c.get("evidence_ids", [])})
    evidence = {}
    for eid in evidence_ids:
        item = flow[eid]
        text = item.get("description") or f"Recorded evidence {eid}"
        evidence[eid] = {
            "id": eid, "step": None, "tool": item.get("retrieval_method"), "kind": item.get("kind"),
            "label": f"{eid} · {item.get('label', 'record')}", "source": item.get("provenance", "UNKNOWN"),
            "produced_by": "evidence_store", "locator": f"/evidence_flow/{eid}", "sha256": sha(item),
            "size": len(json.dumps(item, ensure_ascii=False)),
            "excerpt": {"text": text, "start": 0, "complete": True, "to_end": True, "spans": []},
            "origin": "observed",
        }

    propositions, claims, overlays = [], [], []
    for claim in selected:
        message = messages[claim["message_id"]]
        event_id = f"msg:{claim['message_id']}"
        execution = executions.get(message.get("sender_execution_id"), {})
        received = set(execution.get("evidence_in_input") or [])
        prop_id = f"prop:{claim['id']}"
        links = []
        for eid in claim.get("evidence_ids", []):
            delivery = {"to_event": event_id, "value": "DELIVERED" if eid in received else "UNKNOWN",
                        "operation": "execution evidence_in_input membership", "origin": "computed"}
            links.append({"relation": "supported_by", "evidence": eid, "values": [], "rule_dependent": False,
                          "origin": "hand-annotated", "delivery": delivery})
        propositions.append({"id": prop_id, "form": claim["proposition"],
                             "links": [{"relation": x["relation"], "evidence": x["evidence"]} for x in links],
                             "origin": "hand-annotated"})
        claims.append({
            "id": claim["id"], "label": claim["proposition"], "words": claim["quote"],
            "event": event_id, "step": message["seq"], "span": [0, len(claim["quote"])],
            "speaker": claim["agent"], "speaker_origin": "observed", "proposition": prop_id,
            "state": {"value": claim["state_value"], "origin": "hand-annotated"}, "links": links,
            "o3": o3_for(claim, message, raw["trace"]),
            "notes": [claim["assessment"]], "origin": "hand-annotated",
        })
        overlays.append({"id": f"overlay:{claim['id']}", "kind": "claim", "column": event_id,
                         "row": claim["agent"], "ref": claim["id"], "label": claim["message_id"], "origin": "hand-annotated"})

    disagreement = draft["run"]["review_decision"] == "REQUIRES_HUMAN_REVIEW"
    flags = []
    if disagreement:
        last = f"msg:{selected[-1]['message_id']}"
        flags.append({"id": "flag:human-review", "title": "Human review required", "kind": "run_status",
                      "text": "The final review gate requires a person because recorded disagreements remain unresolved.",
                      "caveat": "This is the run's recorded decision, not a judgement added by the Explorer.",
                      "events": [last], "columns": [last], "anchors": [last], "evidence": [], "computed": [], "origin": "observed"})
        overlays.append({"id": "overlay:human-review", "kind": "flag", "column": last, "row": selected[-1]["agent"],
                         "ref": "flag:human-review", "label": "human review", "origin": "observed"})
    else:
        last = f"msg:{selected[-1]['message_id']}"
        flags.append({"id": "flag:auto-resolve", "title": "Auto-resolved", "kind": "review_decision",
                      "text": "The recorded review gate auto-resolved this run after verification.", "caveat": None,
                      "events": [last], "columns": [last], "anchors": [last], "evidence": [], "computed": [], "origin": "observed"})
        overlays.append({"id": "overlay:auto-resolve", "kind": "flag", "column": last, "row": selected[-1]["agent"],
                         "ref": "flag:auto-resolve", "label": "auto-resolved", "origin": "observed"})

    bundle = {
        "contract": CONTRACT,
        "trace": {"id": trace_id, "label": label, "kind": "multi-agent", "framework": "IDA AgentTrace",
                  "model": raw["trace"].get("llm_model"), "scenario": raw["trace"].get("dataset_type"),
                  "status": raw["trace"].get("status", "UNKNOWN").lower(), "answer": f"msg:{selected[-1]['message_id']}",
                  "summary": raw["trace"].get("final_diagnosis")},
        "honesty": {"annotations": "hand-annotated, illustrative, not gold",
                    "skeleton": "observed selected agent messages from ida.agenttrace/1.0",
                    "rules": ["This bundle shows only the reviewed story messages, not every execution.",
                              "Claims are hand-annotated exact quotes; they do not reveal hidden beliefs.",
                              "DELIVERED means the evidence ID appears in the source execution's recorded evidence_in_input list."]},
        "provenance": {"raw_trace": raw_path.name, "raw_trace_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                       "draft": draft_path.name, "draft_sha256": hashlib.sha256(draft_path.read_bytes()).hexdigest(),
                       "builder": "tests/build_ida_explorer_bundles.py"},
        "layers": {"skeleton": True, "matrix": True, "claims": True, "evidence": True, "delivery": True, "o3": True, "flags": True},
        "skeleton": {"agents": [{"id": a, "label": agent_label(a, raw["agents"]), "sub": raw["agents"].get(a, {}).get("role"), "kind": "agent", "parent": None, "origin": "observed"} for a in sorted(agents)],
                     "events": events, "handoffs": [], "counts": {"events": len(raw["events"]), "model_calls": len(raw.get("llm_calls") or []) or sum(bool(e.get("llm_calls")) for e in raw["executions"]), "evidence": len(raw["evidence_flow"]), "delivers": sum(len(m.get("deliveries") or []) for m in raw["messages"])},
                     "counts_origin": "computed", "skipped": [{"kind": "not shown in selected-story view", "steps": []}], "origin": "observed"},
        "matrix": {"origin": "observed", "source_contract": raw.get("schema_version", "ida.agenttrace"), "rows": [{"id": a, "label": agent_label(a, raw["agents"]), "sub": raw["agents"].get(a, {}).get("role"), "kind": "agent", "origin": "observed"} for a in sorted(agents)],
                   "columns": columns, "edges": [], "delivery_track": True, "max_delivers": 0, "overlays": overlays,
                   "note": "Selected story messages only; open Skeleton to see full recorded counts.", "order_caveat": "Message sequence is observation order, not proof of causation."},
        "evidence": evidence, "propositions": propositions, "claims": claims, "non_claims": [], "flags": flags,
        "facts": [{"id": "fact:decision", "title": "Recorded review decision", "text": draft["run"]["review_decision"], "origin": "observed"},
                  {"id": "fact:schema", "title": "Trace format", "text": raw.get("schema_version", "UNKNOWN"), "origin": "observed"},
                  {"id": "fact:story", "title": "Selected story messages", "text": str(len(selected)), "origin": "computed"}],
        "checks": {"claim_quotes_checked": len(selected), "disagreements_recorded": len(draft["disagreements"])},
    }
    return bundle, f"{trace_id}.bundle.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--raw-root", required=True, type=Path, help="Folder containing one <trace-id>/<trace-id>.json file per trace")
    parser.add_argument("--draft-dir", type=Path, default=ROOT / "runs/multiagent/drafts", help="Folder containing reviewed draft JSON files")
    parser.add_argument("--out", type=Path, default=ROOT / "src/explorer/data", help="Explorer bundle output folder")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    specs = [("TR-20261104152852-5d046205", "IDA 1.1 · full model calls"),
             ("TR-20261102193128-1f44a781", "IDA trace · agreement"),
             ("TR-20261102191715-4dabe93d", "IDA trace · disagreement")]
    manifest_path = args.out / "index.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"contract": "agenttrace-explorer-manifest/0.1", "bundles": []}
    entries = [e for e in manifest["bundles"] if e["trace_id"] not in {x[0] for x in specs}]
    for trace_id, label in specs:
        bundle, name = build(trace_id, label, args.raw_root, args.draft_dir)
        body = canonical(bundle)
        (args.out / name).write_text(body)
        entries.append({"trace_id": trace_id, "file": name, "sha256": hashlib.sha256(body.encode()).hexdigest(), "contract": CONTRACT, "label": label, "kind": "multi-agent"})
    manifest["bundles"] = sorted(entries, key=lambda x: x["trace_id"])
    manifest["contract"] = "agenttrace-explorer-manifest/0.1"
    manifest_path.write_text(canonical(manifest))


if __name__ == "__main__":
    main()
