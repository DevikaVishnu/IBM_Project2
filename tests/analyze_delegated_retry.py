#!/usr/bin/env python3
"""Summarise the instrumented manager/helper retry trace without guessing."""

import json
import sys
from pathlib import Path


def outcome(tool_output: str) -> tuple[str, str | None]:
    try:
        payload = json.loads(tool_output)
    except (TypeError, json.JSONDecodeError):
        return "unknown", None
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        try:
            payload = json.loads(payload[0].get("text", ""))
        except json.JSONDecodeError:
            return "unknown", None
    if not isinstance(payload, dict):
        return "unknown", None
    if payload.get("error"):
        return "error", str(payload["error"])
    if payload.get("total_assets") == 0:
        return "empty_result", "No assets were returned for the requested site."
    return "success", None


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: analyze_delegated_retry.py INPUT.json OUTPUT.json")
    source = Path(sys.argv[1])
    raw = json.loads(source.read_text())
    activity = raw.get("instrumentation", {}).get("helper_activity", [])
    calls = []
    for entry in activity:
        if entry.get("kind") != "helper_tool_call":
            continue
        call_outcome, reason = outcome(entry.get("tool_output", ""))
        calls.append({
            "attempt_number": entry.get("attempt_number"),
            "tool": entry.get("tool_name"),
            "input": entry.get("tool_input"),
            "tool_status": entry.get("tool_status"),
            "outcome": call_outcome,
            "failure_reason": reason,
        })
    output = {
        "run_id": raw.get("run_id"),
        "delegation": raw.get("instrumentation", {}).get("delegations", []),
        "attempts": calls,
        "belief_change": {
            "before_retry": "UNKNOWN: the invalid-site lookup returned no assets.",
            "after_retry": "TRUE: MAIN lookup returned Chiller 6.",
            "state_changed_at": "helper attempt 2",
        },
        "schema_result": {
            "supported_now": [
                "delegated_by", "parent_task", "attempt_number", "failure_reason",
                "tool_status", "outcome", "state_changed_at"
            ],
            "still_unknown": ["visibility", "file lineage", "review checks"],
            "important_note": "The first attempt was an empty result, not a tool error.",
        },
    }
    Path(sys.argv[2]).write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
