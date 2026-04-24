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

# Well-known ChatDev system prompt fragments
_SYSTEM_PROMPT_FRAGMENTS = [
    "ChatDev is a software company powered by multiple intelligent agents",
    "Here is a new customer's task:",
    "do not use any external libraries",
    "Note that we must ONLY discuss",
    "followed by our final",
    "Please note that the code should be fully functional",
    "You report to the CEO and collaborate",
    "with a multi-agent organizational structure",
    "changing the digital world through programming",
    "According to the new user's task and our software designs listed below",
    "Our developed source codes and samples are listed below",
]


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

        if any(body.startswith(s) for s in ("flask app", "HTTP Request", "**[OpenAI_Usage")):
            continue

        phase_match = re.match(r'System:\s*\*\*\[(\w+)\]\*\*', body)
        if phase_match:
            current_phase = phase_match.group(1)
            continue

        if body.startswith("System:"):
            continue

        conclusion_match = re.match(r'\*\*\[Seminar Conclusion\]\*\*:?\s*\n?(.*)', body, re.DOTALL)
        if conclusion_match:
            content = conclusion_match.group(1).strip()
            if content and len(content) > 3:
                content = _extract_useful_content(content)
                short = _summarize(content)
                turns.append({
                    "index": idx, "agent": "Conclusion", "role": "conclusion",
                    "content": content,
                    "content_hash": re.sub(r"\s+", " ", content.lower().strip()),
                    "phase": current_phase, "short": short,
                })
                idx += 1
            continue

        agent_match = re.match(r'([\w\s]+?):\s*\*\*(.*?)\*\*\s*\n?(.*)', body, re.DOTALL)
        if agent_match:
            agent = agent_match.group(1).strip()
            header = agent_match.group(2).strip()
            raw_content = agent_match.group(3).strip()

            # [Start Chat] turns are framework scaffolding — the content is a
            # system prompt template, not an actual agent response. Skip them.
            if header == "[Start Chat]" or header.startswith("[Start Chat"):
                # But still extract phase if present in the prompt
                phase_in_prompt = re.search(r'phase_name.*?:\s*(\w+)', raw_content)
                if phase_in_prompt:
                    current_phase = phase_in_prompt.group(1)
                continue

            conv_match = re.search(r'on\s*:\s*(\w+)', header)
            if conv_match:
                current_phase = conv_match.group(1)

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
    """
    Extract actual agent response, skipping echoed system prompts.
    
    Strategy (FIXED ORDER):
      1. Short content → return as-is
      2. Strip bracket-delimited system prompt [...]  ← do this FIRST
      3. Then check for <INFO> in the CLEANED text
      4. Fallback: return full text
    """
    raw = raw.strip()

    # Short content is almost never a prompt echo
    if len(raw) < 300:
        return raw

    # FIRST: try to strip the system prompt
    # This must happen before <INFO> check because the system prompt
    # contains <INFO> as an example instruction (e.g., '<INFO> PowerPoint')
    stripped = _strip_system_prompt(raw)
    if stripped and stripped != raw and len(stripped) > 10:
        # Successfully stripped — now check for <INFO> in the CLEAN text
        if "<INFO>" in stripped:
            info_pos = stripped.index("<INFO>")
            before = stripped[:info_pos].strip()
            after = stripped[info_pos:].strip()
            if before and len(before) > 10:
                return before + "\n" + after
            return after
        return stripped

    # If stripping didn't help, check for <INFO> in the raw text
    # but only if the <INFO> appears to be in agent text, not system prompt
    if "<INFO>" in raw:
        info_pos = raw.index("<INFO>")
        # Only use this if <INFO> is not inside a system prompt bracket
        before_info = raw[:info_pos]
        if "[ChatDev" not in before_info and "e.g." not in before_info[-100:]:
            after_info = raw[info_pos:].strip()
            return after_info

    # Fallback: return the raw text
    return raw


def _strip_system_prompt(text: str) -> str:
    """
    Find where the system prompt ends and the agent's actual response begins.
    
    ChatDev wraps system prompts in [...] brackets. Check these FIRST because
    they're the most reliable delimiter. Terminators are a fallback for content
    where brackets aren't present.
    """
    if not text:
        return text

    # ── 1. Bracket-delimited system prompt [...]  (most reliable) ──
    # ChatDev always wraps the system prompt in [...], starting with [ChatDev...
    stripped = text.lstrip()
    if stripped.startswith("["):
        bracket_end = -1
        depth = 0
        for i, ch in enumerate(stripped):
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    bracket_end = i
                    break

        if bracket_end > 0 and bracket_end < len(stripped) - 10:
            after = stripped[bracket_end + 1:].lstrip()
            if len(after) > 5:
                return after

    # ── 2. Terminator patterns (fallback for non-bracket prompts) ──
    terminators = [
        r'e\.g\.\s*,?\s*"<INFO>.*?"\.?',
        r'<MODALITY>.*?</MODALITY>',
        r'without any other words.*?\.',
        r'Do not output anything else\.',
        r'any of us must actively terminate',
        r'Now start to give your response\.',
        r'Your response should be plain text',
    ]

    best_end = -1
    for pat in terminators:
        for m in re.finditer(pat, text, re.IGNORECASE | re.DOTALL):
            end_pos = m.end()
            if end_pos > best_end:
                best_end = end_pos

    if best_end > 0 and best_end < len(text) - 10:
        after = text[best_end:].lstrip()
        if len(after) > 10 and not _is_system_prompt(after):
            return after

    # ── 3. System prompt fragments (last resort) ──
    for frag in _SYSTEM_PROMPT_FRAGMENTS:
        pos = text.rfind(frag)
        if pos > 0:
            para_break = text.find("\n\n", pos)
            if para_break > 0 and para_break < len(text) - 20:
                after = text[para_break:].strip()
                if len(after) > 10 and not _is_system_prompt(after):
                    return after

    return text


def _is_system_prompt(text: str) -> bool:
    """Check if text looks like it's still part of a system prompt."""
    first_200 = text[:200].lower()
    prompt_signals = [
        "chatdev is a software company",
        "here is a new customer's task",
        "you are",
        "as the chief",
        "your task is",
        "you report to the",
    ]
    return any(sig in first_200 for sig in prompt_signals)


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

    # Post-process: clean up content for all turns (handles AG2 format too)
    for t in turns:
        t["content"] = _extract_useful_content(t["content"])
        t["short"] = _summarize(t["content"], 30)
        t["content_hash"] = re.sub(r"\s+", " ", t["content"].lower().strip())

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
# FAILURE LOCATOR (improved)
# ─────────────────────────────────────────────

_FAILURE_SIGNALS = {
    "1.1": {
        "patterns": [
            r"(?:doesn't|does not|didn't|did not)\s+(?:match|follow|meet|satisfy|address)",
            r"(?:incorrect|wrong|invalid)\s+(?:output|result|implementation|approach)",
            r"not\s+(?:what was|as)\s+(?:asked|requested|specified)",
            r"deviat(?:es?|ing|ed)\s+from",
        ],
        "phase_hints": ["Coding", "CodeReviewComment", "CodeReviewModification"],
    },
    "1.2": {
        "patterns": [
            r"(?:not|isn't)\s+(?:my|your)\s+(?:role|responsibility|job)",
        ],
        "phase_hints": [],
    },
    "1.3": {"patterns": [], "phase_hints": []},
    "2.3": {
        "patterns": [
            r"(?:instead|rather)\s+(?:of|than)",
            r"(?:off[\s-]?topic|unrelated|irrelevant)",
        ],
        "phase_hints": [],
    },
    "2.5": {
        "patterns": [
            r"(?:already|just)\s+(?:said|mentioned|suggested|told)",
            r"(?:ignor(?:e|ing|ed))\s+(?:my|the|your)\s+(?:suggestion|feedback|comment)",
        ],
        "phase_hints": ["CodeReviewComment", "CodeReviewModification"],
    },
    "2.6": {
        "patterns": [
            r"(?:but|however|yet)\s+(?:the|this)\s+(?:code|implementation|output)",
            r"(?:said|stated|claimed)\s+.*?(?:but|however)",
        ],
        "phase_hints": ["CodeReviewComment", "CodeReviewModification", "Coding"],
    },
    "3.1": {
        "patterns": [
            r"(?:stop|end|finish|done)\s+(?:here|now|early)",
        ],
        "phase_hints": [],
    },
    "3.2": {
        "patterns": [
            r"(?:looks?\s+good|lgtm|approved|no\s+(?:issues?|problems?|errors?))",
            r"(?:without|no)\s+(?:test|check|verif)",
        ],
        "phase_hints": ["CodeReviewComment", "Reflection"],
    },
    "3.3": {
        "patterns": [
            r"(?:everything\s+(?:looks?|seems?|is)\s+(?:correct|fine|good|right))",
            r"(?:no\s+(?:bugs?|errors?|issues?|problems?))\s+(?:found|detected)",
            r"(?:approved|accepted|passed)\s+(?:the|this)\s+(?:code|review)",
        ],
        "phase_hints": ["CodeReviewComment", "Reflection", "Manual"],
    },
}


def locate_failures(turns: list, active_failures: dict) -> dict:
    """Locate where each failure mode most likely occurs in the trace."""
    if not turns:
        return {"turn_annotations": [], "loop_ranges": []}

    n = len(turns)
    annotations = [[] for _ in range(n)]
    loops = []

    # ── Step 1: Detect repeated identical messages (loops) ──
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

    # ── Step 2: Divergence detection ──
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

    # ── Step 3: Content & phase-based failure placement ──
    placed_codes = {a["code"] for anns in annotations for a in anns}

    for code in active_failures:
        if code in placed_codes:
            continue

        signals = _FAILURE_SIGNALS.get(code, {})
        patterns = signals.get("patterns", [])
        phase_hints = signals.get("phase_hints", [])

        best_turn = -1
        best_score = 0

        for i, turn in enumerate(turns):
            score = 0
            content = turn["content"]
            phase = turn.get("phase", "")

            for pat in patterns:
                if re.search(pat, content, re.I):
                    score += 3

            if phase in phase_hints:
                score += 2

            # Position bias based on failure category
            position_ratio = i / max(n - 1, 1)
            if code.startswith("3"):
                if position_ratio > 0.66:
                    score += 3
                elif position_ratio > 0.5:
                    score += 1
            elif code == "1.1" and 0.2 < position_ratio < 0.7:
                score += 1

            if code.startswith("2") and i > 0 and turns[i - 1]["agent"] != turn["agent"]:
                score += 1

            if code.startswith("3") and turn["agent"] in ("Conclusion", "Code Reviewer"):
                score += 2

            if code == "2.6" and phase in ("CodeReviewModification", "Coding"):
                if re.search(r"```", content):
                    score += 2

            if score > best_score:
                best_score = score
                best_turn = i

        # Heuristic fallback
        if best_turn < 0:
            if code.startswith("3"):
                for i in range(n - 1, -1, -1):
                    if turns[i]["agent"] in ("Conclusion", "Code Reviewer") or \
                       turns[i].get("phase", "") in ("Reflection", "CodeReviewComment"):
                        best_turn = i
                        break
                if best_turn < 0:
                    best_turn = n - 1
            elif code.startswith("2"):
                best_turn = n // 2
            elif code.startswith("1"):
                best_turn = max(1, n // 4)
            else:
                best_turn = n - 1

        annotations[best_turn].append({
            "code": code,
            "type": "failure",
            "detail": MAST_REGISTRY.get(code, {}).get("label", code),
        })

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
# AGENT INTERACTION GRAPH
# ─────────────────────────────────────────────
def build_interaction_graph(turns: list) -> dict:
    """
    Build a directed graph of agent interactions from the turn sequence.
    Returns nodes (agents) and edges (who talks to whom, with counts and phases).
    """
    if not turns:
        return {"nodes": [], "edges": []}

    agent_counts = {}
    agent_phases = {}
    for t in turns:
        a = t["agent"]
        agent_counts[a] = agent_counts.get(a, 0) + 1
        phase = t.get("phase", "")
        if phase:
            agent_phases.setdefault(a, set()).add(phase)

    edge_counts = {}
    edge_phases = {}
    for i in range(len(turns) - 1):
        src = turns[i]["agent"]
        dst = turns[i + 1]["agent"]
        if src != dst:
            key = (src, dst)
            edge_counts[key] = edge_counts.get(key, 0) + 1
            phase = turns[i].get("phase", "")
            if phase:
                edge_phases.setdefault(key, set()).add(phase)

    skip_agents = {"System"}
    agents = list(dict.fromkeys(
        t["agent"] for t in turns if t["agent"] not in skip_agents
    ))
    nodes = []
    for a in agents:
        nodes.append({
            "id": a,
            "label": a,
            "turn_count": agent_counts.get(a, 0),
            "phases": sorted(agent_phases.get(a, set())),
        })

    edges = []
    for (src, dst), count in edge_counts.items():
        if src not in skip_agents and dst not in skip_agents:
            edges.append({
                "source": src,
                "target": dst,
                "weight": count,
                "phases": sorted(edge_phases.get((src, dst), set())),
            })

    return {"nodes": nodes, "edges": edges}


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def process(input_path: str, output_path: str = None):
    with open(input_path, "r") as f:
        raw = json.load(f)

    parsed = parse_trace(raw)
    located = locate_failures(parsed["turns"], parsed["active_failures"])
    beliefs = extract_beliefs(parsed["turns"])
    interaction_graph = build_interaction_graph(parsed["turns"])

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
        "interaction_graph": interaction_graph,
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
    print(f"  Interaction graph: {len(interaction_graph['nodes'])} nodes, {len(interaction_graph['edges'])} edges")
    print(f"  Written to: {output_path}")

    for i, ann_list in enumerate(located["turn_annotations"]):
        for ann in ann_list:
            if ann["type"] == "failure":
                print(f"  ⚠ Turn {i} ({parsed['turns'][i]['agent']}, "
                      f"phase={parsed['turns'][i].get('phase','')}): "
                      f"[{ann['code']}] {ann['detail']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python process_trace.py <input.json> [output.json]")
        sys.exit(1)
    inp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    process(inp, out)
