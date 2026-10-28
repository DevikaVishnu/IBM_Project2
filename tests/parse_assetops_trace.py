#!/usr/bin/env python3
"""Convert one AssetOpsBench deep-agent trajectory into simple events.

Each output item has exactly this shared shape:
    time, agent, action, message, target, source_trace

Usage:
    python3 tests/parse_assetops_trace.py INPUT.json OUTPUT.json
"""

import json
import sys
from pathlib import Path


def _source_trace(path: Path, pointer: str) -> str:
    return f"assetopsbench:{path.name}#{pointer}"


def parse_assetops_trace(raw: dict, source_path: Path) -> list[dict]:
    """Return ordered, observable events without inventing missing timestamps."""
    started_at = raw.get("trajectory", {}).get("started_at")
    events = []

    for turn in raw.get("trajectory", {}).get("turns", []):
        turn_index = turn.get("index", len(events))
        for call_index, call in enumerate(turn.get("tool_calls", [])):
            message = {
                "input": call.get("input", {}),
                "output": call.get("output", []),
                "call_id": call.get("id"),
            }
            events.append({
                "time": started_at,
                "agent": "deep-agent",
                "action": "tool_call",
                "message": json.dumps(message, sort_keys=True),
                "target": call.get("name", "unknown_tool"),
                "source_trace": _source_trace(
                    source_path, f"/trajectory/turns/{turn_index}/tool_calls/{call_index}"
                ),
            })

        text = turn.get("text", "").strip()
        if text:
            events.append({
                "time": started_at,
                "agent": "deep-agent",
                "action": "final_answer" if turn_index == max(
                    (t.get("index", -1) for t in raw.get("trajectory", {}).get("turns", [])),
                    default=-1,
                ) else "agent_message",
                "message": text,
                "target": "user",
                "source_trace": _source_trace(source_path, f"/trajectory/turns/{turn_index}/text"),
            })

    # Experiment-only helper instrumentation is separate from the parent
    # message list. Include it when present so a hidden helper becomes normal
    # events in the shared shape.
    for activity_index, activity in enumerate(
        raw.get("instrumentation", {}).get("helper_activity", [])
    ):
        kind = activity.get("kind")
        if kind == "helper_model_input":
            events.append({
                "time": started_at,
                "agent": "asset-helper",
                "action": "agent_input",
                "message": json.dumps({
                    "system_prompt": activity.get("system_prompt"),
                    "messages": activity.get("messages", []),
                }, sort_keys=True),
                "target": "asset-helper",
                "source_trace": _source_trace(
                    source_path, f"/instrumentation/helper_activity/{activity_index}"
                ),
            })
        elif kind == "helper_tool_call":
            events.append({
                "time": started_at,
                "agent": "asset-helper",
                "action": "tool_call",
                "message": json.dumps({
                    "input": activity.get("tool_input", {}),
                    "output": activity.get("tool_output", ""),
                    "attempt_number": activity.get("attempt_number"),
                    "tool_status": activity.get("tool_status"),
                }, sort_keys=True),
                "target": activity.get("tool_name", "unknown_tool"),
                "source_trace": _source_trace(
                    source_path, f"/instrumentation/helper_activity/{activity_index}"
                ),
            })

    for activity_index, activity in enumerate(
        raw.get("instrumentation", {}).get("activity", [])
    ):
        kind = activity.get("kind")
        if kind == "model_input":
            events.append({
                "time": started_at,
                "agent": activity.get("agent", "unknown_agent"),
                "action": "agent_input",
                "message": json.dumps({"messages": activity.get("messages", [])}, sort_keys=True),
                "target": activity.get("agent", "unknown_agent"),
                "source_trace": _source_trace(source_path, f"/instrumentation/activity/{activity_index}"),
            })
        elif kind == "tool_call":
            events.append({
                "time": started_at,
                "agent": activity.get("agent", "unknown_agent"),
                "action": "tool_call",
                "message": json.dumps({
                    "input": activity.get("input", {}), "output": activity.get("output", ""),
                    "tool_status": activity.get("tool_status"),
                }, sort_keys=True),
                "target": activity.get("tool", "unknown_tool"),
                "source_trace": _source_trace(source_path, f"/instrumentation/activity/{activity_index}"),
            })

    return events


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: parse_assetops_trace.py INPUT.json OUTPUT.json")
    source_path = Path(sys.argv[1])
    raw = json.loads(source_path.read_text())
    events = parse_assetops_trace(raw, source_path)
    Path(sys.argv[2]).write_text(json.dumps(events, indent=2) + "\n")


if __name__ == "__main__":
    main()
