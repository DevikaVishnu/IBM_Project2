#!/usr/bin/env python3
"""Create a conservative, observable belief timeline for AssetOpsBench.

This is a validation helper, not a hidden-reasoning reader.  It only writes a
belief state when a tool result or final answer supplies observable evidence.
"""

import json
import sys
from pathlib import Path


def _tool_text(call: dict) -> str:
    return "\n".join(item.get("text", "") for item in call.get("output", []))


def _tool_status(text: str) -> tuple[str, str | None]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return "unknown", None
    if "error" in payload:
        return "error", str(payload["error"])
    return "ok", None


def extract(raw: dict, source_path: Path) -> dict:
    run_id = raw.get("run_id", source_path.stem)
    started_at = raw.get("trajectory", {}).get("started_at")
    evidence, timeline = [], []

    for turn in raw.get("trajectory", {}).get("turns", []):
        turn_index = turn.get("index", 0)
        for call_index, call in enumerate(turn.get("tool_calls", [])):
            text = _tool_text(call)
            status, error = _tool_status(text)
            evidence_id = f"e-tool-{turn_index}-{call_index}"
            evidence.append({
                "id": evidence_id,
                "source": "tool",
                "produced_by": f"event-tool-{turn_index}-{call_index}",
                "tool_name": call.get("name"),
                "tool_status": status,
                "tool_error": error,
                "raw_ref": f"assetopsbench:{source_path.name}#/trajectory/turns/{turn_index}/tool_calls/{call_index}",
            })

            if status == "error":
                timeline.append({
                    "time": started_at,
                    "holder": "deep-agent",
                    "state_value": "UNKNOWN",
                    "proposition": f"{call.get('name')} produced usable evidence",
                    "evidence_for_state": [evidence_id],
                    "reason": "The recorded tool result is an error; no successful result is observable.",
                })

        if turn.get("text", "").strip():
            evidence_id = f"e-final-{turn_index}"
            evidence.append({
                "id": evidence_id,
                "source": "agent",
                "produced_by": f"event-final-{turn_index}",
                "raw_ref": f"assetopsbench:{source_path.name}#/trajectory/turns/{turn_index}/text",
            })

    # These are trace-specific, conservative findings. They are not guesses
    # about private chain-of-thought.
    if raw.get("scenario_id") == "607":
        timeline.extend([
            {
                "time": started_at,
                "holder": "deep-agent",
                "state_value": "TRUE",
                "proposition": "Chiller 6 has recorded installed-sensor evidence.",
                "evidence_for_state": ["e-tool-1-1"],
                "reason": "installed_sensors returned twelve named Chiller 6 sensors.",
            },
            {
                "time": started_at,
                "holder": "deep-agent",
                "state_value": "UNKNOWN",
                "proposition": "Pump failure modes apply to Chiller 6.",
                "evidence_for_state": ["e-tool-3-0"],
                "reason": "The evidence names asset_class pump, not Chiller 6 or chiller.",
            },
        ])
    elif raw.get("scenario_id") == "620":
        timeline.extend([
            {
                "time": started_at,
                "holder": "deep-agent",
                "state_value": "TRUE",
                "proposition": "Chiller 6 has twelve measured sensors.",
                "evidence_for_state": ["e-tool-0-1"],
                "reason": "measured_sensors returned twelve named sensors.",
            },
            {
                "time": started_at,
                "holder": "deep-agent",
                "state_value": "TRUE",
                "proposition": "Recorded Chiller 6 data spans 2020-06-01 through 2020-06-30.",
                "evidence_for_state": ["e-tool-1-0"],
                "reason": "stream_extent returned those dates and 2,896 records.",
            },
            {
                "time": started_at,
                "holder": "deep-agent",
                "state_value": "UNKNOWN",
                "proposition": "The listed sensors identify a chiller-trip failure.",
                "evidence_for_state": ["e-tool-0-0", "e-tool-0-1", "e-tool-1-0"],
                "reason": "The trace shows sensor names and coverage, but no failure label, values, or evaluation of trip detection.",
            },
        ])

    return {
        "schema": "assetopsbench-belief-draft/0.1",
        "run": {
            "id": run_id,
            "source_trace": f"assetopsbench:{source_path.name}",
            "rendered_agent_input": "UNKNOWN",
            "review_scope": "UNKNOWN",
        },
        "evidence": evidence,
        "belief_timeline": timeline,
        "schema_validation": {
            "keep_now": [
                "source_trace", "produced_by", "tool_status", "supported_by/contradicted_by"
            ],
            "keep_pending_more_traces": ["tool_error", "attempt_number"],
            "not_observable_here": [
                "delivers/using", "checks/check_target/check_result", "delegated_by", "visibility"
            ],
        },
    }


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: extract_assetops_beliefs.py INPUT.json OUTPUT.json")
    source_path = Path(sys.argv[1])
    raw = json.loads(source_path.read_text())
    Path(sys.argv[2]).write_text(json.dumps(extract(raw, source_path), indent=2) + "\n")


if __name__ == "__main__":
    main()
