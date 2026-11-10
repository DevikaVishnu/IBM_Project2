#!/usr/bin/env python3
"""Build a small, checked display draft from one IDA trace.

This is deliberately not an ``agenttrace-explorer-bundle/0.1`` yet.  It is a
local hand-annotation format for validating a few observable claims and
disagreements before we add an IDA-trace adapter to the Explorer UI.

Usage:
    python3 tests/build_multiagent_trace_draft.py RAW.json EVENTS.json ANNOTATIONS.json OUTPUT.json
"""

import json
import sys
from pathlib import Path


def _fail(message: str) -> None:
    raise ValueError(message)


def build(raw: dict, events: list[dict], annotations: dict, source_path: Path) -> dict:
    trace = raw.get("trace", {})
    trace_id = trace.get("trace_id")
    if not trace_id or annotations.get("trace_id") != trace_id:
        _fail("annotation trace_id must match raw trace.trace_id")

    messages = {item.get("message_id"): item for item in raw.get("messages", [])}
    checked_claims = []
    for item in annotations.get("claims", []):
        message = messages.get(item.get("message_id"))
        if not message:
            _fail(f"claim {item.get('id')}: unknown message_id")
        quote = item.get("quote", "")
        if not quote or quote not in (message.get("message_content") or ""):
            _fail(f"claim {item.get('id')}: quote is not in its source message")
        if item.get("agent") != message.get("sender_agent_id"):
            _fail(f"claim {item.get('id')}: agent does not match source message")
        cited = set(message.get("evidence_ids") or [])
        if not set(item.get("evidence_ids") or []).issubset(cited):
            _fail(f"claim {item.get('id')}: evidence_ids are not cited by source message")
        checked_claims.append({**item, "source_trace": f"ida.agenttrace:{source_path.name}#/messages/{raw['messages'].index(message)}"})

    checked_disagreements = []
    raw_disagreements = {item.get("message_id"): item for item in raw.get("disagreements", []) if item}
    for item in annotations.get("disagreements", []):
        source = raw_disagreements.get(item.get("message_id"))
        if not source:
            _fail(f"disagreement {item.get('id')}: message_id is not a recorded disagreement")
        checked_disagreements.append({**item, "recorded": source})

    return {
        "schema": "ida.agenttrace-draft/0.1",
        "origin": "observed trace plus hand annotations",
        "run": {
            "id": trace_id,
            "status": trace.get("status"),
            "label": trace.get("final_label"),
            "confidence": trace.get("final_confidence"),
            "review_decision": trace.get("review_decision"),
            "source_trace": f"ida.agenttrace:{source_path.name}",
        },
        "agents": [
            {"id": agent_id, "name": info.get("name", agent_id), "role": info.get("role")}
            for agent_id, info in (raw.get("agents") or {}).items()
        ],
        "events": events,
        "claims": checked_claims,
        "disagreements": checked_disagreements,
        "limitations": [
            "Provider-call records contain response excerpts, not every full raw provider response.",
            "This draft records only observable claims; it does not infer hidden agent beliefs.",
        ],
    }


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit("Usage: build_multiagent_trace_draft.py RAW.json EVENTS.json ANNOTATIONS.json OUTPUT.json")
    raw_path, events_path, annotation_path, output_path = map(Path, sys.argv[1:])
    draft = build(
        json.loads(raw_path.read_text()), json.loads(events_path.read_text()),
        json.loads(annotation_path.read_text()), raw_path,
    )
    output_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
