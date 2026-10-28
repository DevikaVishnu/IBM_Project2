#!/usr/bin/env python3
"""Extract conservative schema findings from the file-handoff experiment."""

import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: analyze_assetops_file_review.py INPUT.json OUTPUT.json")
    source = Path(sys.argv[1])
    raw = json.loads(source.read_text())
    tools = [x for x in raw["instrumentation"]["activity"] if x["kind"] == "tool_call"]
    writer = next(x for x in tools if x["agent"] == "artifact-writer")
    reviewer = next(x for x in tools if x["agent"] == "artifact-reviewer")
    written = json.loads(writer["output"])
    read = json.loads(reviewer["output"])
    check_result = "PASS" if read["content"].get("status") == "READY" else "FAIL"
    result = {
        "run_id": raw["run_id"],
        "artifact": {
            "artifact_id": written["artifact_id"], "artifact_version": written["version"],
            "content_hash": written["content_hash"], "produced_by": "artifact-writer/write_handoff_artifact",
            "read_by": "artifact-reviewer/read_handoff_artifact",
        },
        "review": {
            "checks": "status(assetops-belief-handoff.json) equals READY",
            "check_target": "artifact status", "check_result": check_result,
            "evidence": "artifact-reviewer/read_handoff_artifact",
        },
        "delivery": {
            "writer_and_reviewer_inputs_logged": True,
            "manager_received_writer_and_reviewer_reports": True,
            "file_lineage_relation": "UNKNOWN: the reviewer read the file directly; the strict propagates_to rule requires observable agent-input delivery.",
        },
        "schema_result": {
            "supported_now": ["artifact_id", "artifact_version", "content_hash", "read_by", "produced_by", "checks", "check_target", "check_result"],
            "still_not_proved": ["visibility policy", "propagates_to through non-agent file I/O"],
        },
    }
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
