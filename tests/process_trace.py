#!/usr/bin/env python3
"""
AgentTrace — Trace Processor
Reads a raw trace JSON (AG2 or ChatDev/HuggingFace format),
runs the parsing + failure location + belief extraction pipeline,
and writes a processed JSON ready for the viewer.

Usage:
    python process_trace.py <input.json> [output.json]

If output is omitted, writes to <input>_processed.json
"""

import json
import re
import sys
from pathlib import Path


# ─────────────────────────────────────────────
# MAST FAILURE MODE REGISTRY
# ─────────────────────────────────────────────
MAST_REGISTRY = {
    "1.1": {"label": "Disobey task specification",     "category": "FC1: System Design"},
    "1.2": {"label": "Disobey role specification",     "category": "FC1: System Design"},
    "1.3": {"label": "Step repetition",                "category": "FC1: System Design"},
    "1.4": {"label": "Loss of conversation history",   "category": "FC1: System Design"},
    "1.5": {"label": "Unaware of stopping conditions", "category": "FC1: System Design"},
    "2.1": {"label": "Conversation reset",             "category": "FC2: Inter-Agent Misalignment"},
    "2.2": {"label": "Fail to ask for clarification",  "category": "FC2: Inter-Agent Misalignment"},
    "2.3": {"label": "Task derailment",                "category": "FC2: Inter-Agent Misalignment"},
    "2.4": {"label": "Information withholding",         "category": "FC2: Inter-Agent Misalignment"},
    "2.5": {"label": "Ignored other agent's input",    "category": "FC2: Inter-Agent Misalignment"},
    "2.6": {"label": "Reasoning-action mismatch",      "category": "FC2: Inter-Agent Misalignment"},
    "3.1": {"label": "Premature termination",          "category": "FC3: Task Verification"},
    "3.2": {"label": "No or incomplete verification",  "category": "FC3: Task Verification"},
    "3.3": {"label": "Incorrect verification",         "category": "FC3: Task Verification"},
}

NOTE_LABEL_TO_CODE = {
    "Fail to detect ambiguities/contradictions": "1.1",
    "Proceed with incorrect assumptions": "1.1",
    "Fail to elicit clarification": "2.2",
    "Tendency to overachieve": "1.2",
    "Underperform by waiting on instructions": "1.5",
    "Withholding relevant information": "2.4",
    "Derailing from task objectives": "2.3",
    "Waiting on agents to discover known insights for increased confidence": "2.5",
    "Redundant conversation turns for iterative tasks rather than batching": "1.3",
    "Unaware of stopping conditions": "1.5",
    "Difficulty in agreeing with agents": "2.5",
    "No attempt to verify outcome": "3.2",
    "Evaluator agent fails to be critical": "3.3",
    "Poor adherence to specified constraints": "1.1",
    "Misalignment between internal thoughts and response message": "2.6",
    "Claiming that a task is done while it is not true.": "3.3",
    "Ignoring good suggestions from other agent": "2.5",
    "Discontinued reasoning": "3.1",
    "Trajectory restart": "2.1",
    "Step repetition": "1.3",
    "Invented content": "1.1",
    "Blurring roles": "1.2",
}


# ─────────────────────────────────────────────
# PARSERS
# ─────────────────────────────────────────────
def parse_ag2_trajectory(trajectory: list) -> list:
    """Parse AG2-style JSON array of turn objects."""
    turns = []
    for i, turn in enumerate(trajectory):
        content = turn.get("content", "")
        if isinstance(content, list):
            content = "\n".join(str(c) for c in content)
        content = content.strip()
        turns.append({
            "index": i,
            "agent": turn.get("name", turn.get("role", f"agent_{i % 2}")),
            "role": turn.get("role", "unknown"),
            "content": content,
            "content_hash": re.sub(r"\s+", " ", content.lower().strip()),
            "phase": "",
            "short": _summarize(content, 30),
        })
    return turns


def _summarize(text: str, max_len: int = 30) -> str:
    """Create a short summary label for compact view."""
    t = text.strip()
    # Check for known patterns
    if re.match(r"^continue\b", t, re.I):
        return "continue"
    if "<INFO>" in t:
        after = t.split("<INFO>")[-1].strip().strip("*").strip()
        return after[:max_len] if after else "<INFO>"
    if "\\boxed" in t:
        return "final answer"
    if re.search(r"cannot|unsolvable|insufficient|not enough", t, re.I):
        return "insufficient data"
    if re.search(r"```python|```java|```", t):
        return "writes code"
    if re.match(r"^(I'm sorry|I really need|Based on the current)", t, re.I):
        return "re-explains"
    # Generic: first meaningful words
    words = re.sub(r"[*#\[\]`]", "", t).split()[:5]
    s = " ".join(words)
    return s[:max_len] if s else "..."


def parse_chatdev_log(text: str) -> list:
    """Parse ChatDev raw text log into normalized turns."""
    pattern = r'\[([\d\-\s:]+)INFO\]\s+(.*?)(?=\[[\d\-\s:]+INFO\]|\Z)'
    blocks = list(re.finditer(pattern, text, re.DOTALL))

    turns = []
    current_phase = ""
    idx = 0

    for block in blocks:
        body = block.group(2).strip()

        # Skip noise lines
        if any(body.startswith(s) for s in ("flask app", "HTTP Request", "**[OpenAI_Usage")):
            continue

        # Phase marker: System: **[chatting]** or **[RolePlaying]**
        phase_match = re.match(r'System:\s*\*\*\[(\w+)\]\*\*', body)
        if phase_match:
            current_phase = phase_match.group(1)
            continue

        # Skip other System messages
        if body.startswith("System:"):
            continue

        # Seminar conclusion
        conclusion_match = re.match(r'\*\*\[Seminar Conclusion\]\*\*:?\s*\n?(.*)', body, re.DOTALL)
        if conclusion_match:
            content = conclusion_match.group(1).strip()
            if content and len(content) > 3:
                short = _summarize(content)
                turns.append({
                    "index": idx, "agent": "Conclusion", "role": "conclusion",
                    "content": content[:800],
                    "content_hash": re.sub(r"\s+", " ", content.lower()[:800]),
                    "phase": current_phase, "short": short,
                })
                idx += 1
            continue

        # Agent message: "AgentName: **header**\ncontent"
        agent_match = re.match(r'([\w\s]+?):\s*\*\*(.*?)\*\*\s*\n?(.*)', body, re.DOTALL)
        if agent_match:
            agent = agent_match.group(1).strip()
            header = agent_match.group(2).strip()
            raw_content = agent_match.group(3).strip()

            # Extract phase from header
            conv_match = re.search(r'on\s*:\s*(\w+)', header)
            if conv_match:
                current_phase = conv_match.group(1)

            # Get useful content
            content = _extract_useful_content(raw_content)
            if not content or len(content) < 3:
                content = header

            short = _summarize(content)
            turns.append({
                "index": idx, "agent": agent, "role": "speaker",
                "content": content,
                "content_hash": re.sub(r"\s+", " ", content.lower().strip()),
                "phase": current_phase, "short": short,
            })
            idx += 1

    return turns


def _extract_useful_content(raw: str) -> str:
    """Extract actual agent response, skipping echoed system prompts."""
    if len(raw) < 400:
        return raw.strip()

    markers = [
        "Here is a new customer's task:",
        "do not use any",
        "followed by our final",
        "Note that we must ONLY",
        "Please note that the code should be fully functional",
        "<INFO>",
    ]

    best_pos = -1
    for marker in markers:
        pos = raw.lower().rfind(marker.lower())
        if pos > best_pos:
            best_pos = pos

    if best_pos > 0:
        nl = raw.find("\n", best_pos)
        if 0 < nl < len(raw) - 10:
            after = raw[nl:].strip()
            if len(after) > 20:
                return after[:1500]

    return raw[-1500:].strip()


# ─────────────────────────────────────────────
# MAIN PARSE ENTRY POINT
# ─────────────────────────────────────────────
def parse_trace(raw: dict) -> dict:
    """Parse any trace format into normalized structure."""
    trajectory = raw.get("trajectory", [])

    if not trajectory and "trace" in raw:
        trace_field = raw["trace"]
        if isinstance(trace_field, dict) and "trajectory" in trace_field:
            traj_raw = trace_field["trajectory"]
            if isinstance(traj_raw, str):
                try:
                    parsed = json.loads(traj_raw)
                    trajectory = parsed if isinstance(parsed, list) else traj_raw
                except json.JSONDecodeError:
                    trajectory = traj_raw
            elif isinstance(traj_raw, list):
                trajectory = traj_raw

    turns = []
    if isinstance(trajectory, list) and trajectory and isinstance(trajectory[0], dict):
        turns = parse_ag2_trajectory(trajectory)
    elif isinstance(trajectory, str) and trajectory:
        turns = parse_chatdev_log(trajectory)

    # MAST annotations
    active_failures = {}
    for code, val in raw.get("mast_annotation", {}).items():
        if val == 1 and code in MAST_REGISTRY:
            active_failures[code] = MAST_REGISTRY[code]
    note = raw.get("note") if isinstance(raw.get("note"), dict) else {}
    if note and "options" in note:
        for label, val in note["options"].items():
            if val == "yes" and label in NOTE_LABEL_TO_CODE:
                code = NOTE_LABEL_TO_CODE[label]
                if code in MAST_REGISTRY:
                    active_failures[code] = MAST_REGISTRY[code]

    other = raw.get("other_data") if isinstance(raw.get("other_data"), dict) else {}
    trace_d = raw.get("trace") if isinstance(raw.get("trace"), dict) else {}
    ps = raw.get("problem_statement", "")

    meta = {
        "framework": raw.get("mas_name", "unknown"),
        "benchmark": raw.get("benchmark_name", other.get("perturbation_type", "unknown")),
        "llm": raw.get("llm_name", "unknown"),
        "task_correct": other.get("correct"),
        "problem_statement": " ".join(ps) if isinstance(ps, list) else (ps or trace_d.get("key", "")),
        "total_turns": len(turns),
        "note_text": " ".join(note.get("text", [])) if isinstance(note.get("text"), list)
            else str(note.get("text", "")),
    }

    return {"turns": turns, "active_failures": active_failures, "meta": meta}


# ─────────────────────────────────────────────
# FAILURE LOCATOR
# ─────────────────────────────────────────────
def locate_failures(turns: list, active_failures: dict) -> dict:
    if not turns:
        return {"turn_annotations": [], "loop_ranges": []}

    n = len(turns)
    annotations = [[] for _ in range(n)]
    loops = []

    # Detect repeated identical messages from same agent
    visited = set()
    for i in range(n):
        if i in visited:
            continue
        matches = [i]
        for k in range(i + 2, n, 2):
            if (turns[k]["agent"] == turns[i]["agent"]
                    and turns[k]["content_hash"] == turns[i]["content_hash"]
                    and len(turns[i]["content_hash"]) > 20):
                matches.append(k)
            else:
                break
        if len(matches) >= 2:
            s, e = min(matches), max(matches)
            loops.append({"start": max(s, 1), "end": min(e + 1, n - 1)})
            for ti in matches:
                visited.add(ti)
                if "1.5" in active_failures:
                    annotations[ti].append({"code": "1.5", "type": "failure",
                        "detail": f"Repeated {len(matches)}x"})
                if "1.3" in active_failures:
                    annotations[ti].append({"code": "1.3", "type": "failure",
                        "detail": f"Step repetition {len(matches)}x"})
                if "2.5" in active_failures:
                    annotations[ti].append({"code": "2.5", "type": "failure",
                        "detail": "Ignores other agent"})

    # Divergence detection
    assert_re = re.compile(r"cannot|unsolvable|insufficient|impossible|missing|not enough", re.I)
    ignore_re = re.compile(r"^(continue|proceed|keep going|try again)", re.I)
    for t in range(1, n):
        p, c = turns[t - 1], turns[t]
        if p["agent"] != c["agent"]:
            if assert_re.search(p["content"]) and ignore_re.search(c["content"]) and len(c["content"]) < 200:
                annotations[t].append({"code": "divergence", "type": "divergence",
                    "detail": f"Ignores {p['agent']}'s assertion"})
            if assert_re.search(c["content"]) and t > 2:
                annotations[t].append({"code": "re-explain", "type": "divergence",
                    "detail": f"{c['agent']} re-explains"})

    # Place remaining active failures at trace level
    placed_codes = {a["code"] for anns in annotations for a in anns}
    for code in active_failures:
        if code not in placed_codes:
            annotations[-1].append({"code": code, "type": "failure",
                "detail": MAST_REGISTRY.get(code, {}).get("label", code)})

    return {"turn_annotations": annotations, "loop_ranges": loops}


# ─────────────────────────────────────────────
# BELIEF EXTRACTOR
# ─────────────────────────────────────────────
def extract_beliefs(turns: list) -> dict:
    if not turns:
        return {"beliefs": {}, "has_divergence": False}
    skip = {"System", "Conclusion"}
    agents = list(dict.fromkeys(t["agent"] for t in turns if t["agent"] not in skip))
    beliefs = {}
    for agent in agents:
        text = " ".join(t["content"] for t in turns if t["agent"] == agent)
        if re.search(r"cannot|unsolvable|insufficient|not enough|missing", text, re.I):
            beliefs[agent] = "Task is blocked - critical information missing"
        elif re.search(r"continue|keep solving|proceed", text, re.I) and \
                all(len(t["content"]) < 200 for t in turns if t["agent"] == agent):
            beliefs[agent] = "Task should continue - answer must be produced"
        elif re.search(r"completed|finished|done|final|<INFO>|Finished", text):
            beliefs[agent] = "Task complete"
        else:
            beliefs[agent] = "Working on the task"
    has_div = len(set(beliefs.values())) > 1 if len(beliefs) >= 2 else False
    return {"beliefs": beliefs, "has_divergence": has_div}


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def process(input_path: str, output_path: str = None):
    with open(input_path, "r") as f:
        raw = json.load(f)

    parsed = parse_trace(raw)
    located = locate_failures(parsed["turns"], parsed["active_failures"])
    beliefs = extract_beliefs(parsed["turns"])

    # Build output: clean JSON for the viewer
    # Strip content_hash from turns (internal only)
    clean_turns = []
    for i, t in enumerate(parsed["turns"]):
        clean_turns.append({
            "index": t["index"],
            "agent": t["agent"],
            "role": t["role"],
            "content": t["content"],
            "phase": t.get("phase", ""),
            "short": t.get("short", ""),
            "annotations": located["turn_annotations"][i],
        })

    output = {
        "meta": parsed["meta"],
        "agents": list(dict.fromkeys(t["agent"] for t in parsed["turns"] if t["agent"] != "System")),
        "failures": {code: info for code, info in parsed["active_failures"].items()},
        "failure_registry": MAST_REGISTRY,
        "turns": clean_turns,
        "loops": located["loop_ranges"],
        "beliefs": beliefs,
    }

    if output_path is None:
        p = Path(input_path)
        output_path = str(p.parent / (p.stem + "_processed.json"))

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Processed {len(clean_turns)} turns from {parsed['meta']['framework']}")
    print(f"  Failures: {list(parsed['active_failures'].keys())}")
    print(f"  Loops: {len(located['loop_ranges'])}")
    print(f"  Belief divergence: {beliefs['has_divergence']}")
    print(f"  Written to: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python process_trace.py <input.json> [output.json]")
        sys.exit(1)
    inp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    process(inp, out)
