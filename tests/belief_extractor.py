"""
AgentTrace — Belief Extractor & Divergence Detector

Produces per-turn belief snapshots and divergence events from processed traces.
Integrates with process_trace.py output.

Belief model:
  Each agent has a "belief state" at every turn — an inferred summary of
  what that agent currently thinks the task status is. This state persists
  (is "sticky") until the agent speaks again and we re-infer from their
  content. Non-speaking agents retain their last known state.

  States: idle, asking, proposing, building, reviewing, requesting_changes,
          approving, blocked, pushing, completing

Divergence model:
  At each turn boundary, we compare active agents' belief states and flag
  meaningful conflicts. Some divergences are visible in real-time (one agent
  says "blocked" while another says "continue"), others are only visible
  in hindsight (reviewer approves but the code has bugs).

  We distinguish:
    - live divergence: detectable at the moment it happens
    - hindsight divergence: only detectable once we know the outcome
"""

import re
import json


# ─────────────────────────────────────────────
# BELIEF STATE DEFINITIONS
# ─────────────────────────────────────────────

BELIEF_STATES = {
    "idle":       {"label": "Idle",        "color": "#d1d5db", "order": 0},
    "asking":     {"label": "Asking",      "color": "#60a5fa", "order": 1},
    "proposing":  {"label": "Proposing",   "color": "#34d399", "order": 2},
    "building":   {"label": "Building",    "color": "#3b82f6", "order": 3},
    "reviewing":  {"label": "Reviewing",   "color": "#a78bfa", "order": 4},
    "req_change": {"label": "Wants Change","color": "#fbbf24", "order": 5},
    "approving":  {"label": "Approving",   "color": "#10b981", "order": 6},
    "blocked":    {"label": "Blocked",     "color": "#ef4444", "order": 7},
    "pushing":    {"label": "Pushing",     "color": "#f97316", "order": 8},
    "completing": {"label": "Completing",  "color": "#06b6d4", "order": 9},
}


# ─────────────────────────────────────────────
# PER-TURN BELIEF CLASSIFICATION
# ─────────────────────────────────────────────

def classify_belief(content, phase, agent, prev_state):
    """
    Given a turn's content, phase, and the agent's previous state,
    infer what the agent currently believes / is doing.

    The heuristics are ordered from most-specific to least-specific:
    1. Explicit conversation markers (<INFO>, \\boxed, "Continue")
    2. Content-based signals (code blocks, questions, blocking language)
    3. Phase-based defaults (Coding → building, CodeReviewComment → reviewing)
    4. Fallback to previous state
    """
    cl = content.lower().strip()

    # ── 1. Explicit markers ──

    # AG2-style "Continue" pushing pattern
    if re.match(r'^continue\.?\s*(please)?\s*(keep)?', cl) and len(cl) < 200:
        return "pushing"

    # ChatDev <INFO> decision markers
    if "<info>" in cl:
        after = cl.split("<info>")[-1].strip().strip("*").strip()
        if re.search(r'finished|complete|done|approved', after):
            return "approving"
        return "proposing"

    # Math answer marker
    if re.search(r'\\boxed\{', cl):
        return "proposing"

    # ── 2. Blocking / inability signals ──
    block_phrases = [
        r'cannot\s+(?:be\s+)?(?:solved|determined|calculated)',
        r'(?:is|are)\s+(?:unsolvable|impossible|insufficient)',
        r'not\s+enough\s+(?:information|data)',
        r'(?:missing|need)\s+(?:more|additional|crucial)\s+(?:info|data|context)',
        r'(?:I|we)\s+(?:really\s+)?need\s+more\s+info',
    ]
    if any(re.search(p, cl) for p in block_phrases) and len(cl) < 600:
        return "blocked"

    # ── 3. Code production signals ──
    has_code = bool(re.search(r'```|^(def |class |import |from \w+ import )', content, re.M))

    if has_code:
        if phase in ("CodeReviewModification", "Coding"):
            # Check if they're actually changing anything
            if re.search(r'no\s+changes?|returned\s+as.?is|same\s+code|unchanged', cl):
                return "approving"  # not actually building
            return "building"
        return "building"

    # ── 4. Review / approval signals ──
    if phase in ("CodeReviewComment", "Reflection"):
        if re.search(r'finished|looks?\s+good|lgtm|approved|no\s+(?:issues?|problems?|errors?)', cl):
            return "approving"
        if re.search(r'bug|error|issue|fix|change|modif|improv|missing|incorrect|wrong', cl):
            return "req_change"
        return "reviewing"

    # ── 5. Question detection ──
    if '?' in content and len(content) < 400:
        # Distinguish asking from rhetorical
        if re.search(r'(?:which|what|how|should|do you|can you|could)', cl):
            return "asking"

    # ── 6. Phase-based defaults ──
    phase_map = {
        "DemandAnalysis": "proposing",
        "LanguageChoose": "proposing",
        "Coding":         "building",
        "CodeReviewModification": "building",
        "CodeReviewComment":      "reviewing",
        "EnvironmentDoc": "completing",
        "Reflection":     "reviewing",
        "Manual":         "completing",
    }
    if phase in phase_map:
        return phase_map[phase]

    # ── 7. Fallback ──
    return prev_state if prev_state != "idle" else "proposing"


# ─────────────────────────────────────────────
# TIMELINE BUILDER
# ─────────────────────────────────────────────

def build_belief_timeline(turns):
    """
    Walk through turns chronologically, updating each agent's belief state
    when they speak. Non-speaking agents retain their previous state.

    Returns:
      agents: list of agent names (ordered by first appearance)
      timeline: list of snapshots, one per turn, each containing
                the full state of every agent at that moment
    """
    skip = {"System", "Conclusion"}
    agents = list(dict.fromkeys(
        t["agent"] for t in turns if t["agent"] not in skip
    ))

    # Current belief state per agent (sticky between turns)
    current_state = {a: "idle" for a in agents}
    current_detail = {a: "" for a in agents}

    # Track when each agent last spoke (for "staleness")
    last_spoke = {a: -1 for a in agents}

    timeline = []

    for i, turn in enumerate(turns):
        agent = turn["agent"]
        content = turn.get("content", "")
        phase = turn.get("phase", "")
        short = turn.get("short", turn.get("summary", ""))

        # Update the speaking agent's state
        if agent in current_state:
            prev = current_state[agent]
            new_state = classify_belief(content, phase, agent, prev)
            current_state[agent] = new_state
            current_detail[agent] = short if short else content[:80]
            last_spoke[agent] = i

        # Build snapshot — every agent's state at this moment
        snapshot = {
            "turn": i,
            "speaker": agent,
            "phase": phase,
            "agents": {}
        }
        for a in agents:
            snapshot["agents"][a] = {
                "state": current_state[a],
                "detail": current_detail[a],
                "is_speaking": (a == agent),
                "turns_since_spoke": i - last_spoke[a] if last_spoke[a] >= 0 else i,
            }

        timeline.append(snapshot)

    return agents, timeline


# ─────────────────────────────────────────────
# SIMILARITY HELPERS
# ─────────────────────────────────────────────

def _word_set(text):
    """Extract a set of lowercase words (4+ chars) from text."""
    return set(re.findall(r'[a-z_]{4,}', text.lower()))

def _jaccard(a, b):
    """Jaccard similarity between two sets."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ─────────────────────────────────────────────
# DIVERGENCE DETECTION
# ─────────────────────────────────────────────

def detect_divergences(timeline, agents, turns, active_failures=None):
    """
    Scan the timeline for moments where agents' beliefs conflict.

    Returns a list of divergence events, each with:
      turn, type, severity, agents, description, related_failures,
      detection_type ("live" or "hindsight")
    """
    active_failures = active_failures or {}
    events = []

    for i, snap in enumerate(timeline):
        states = snap["agents"]
        active = {a: s for a, s in states.items()
                  if s["state"] != "idle"}

        if len(active) < 2:
            continue

        # ── Pattern 1: Blocked vs Pushing ──
        # One agent says "can't do this", another says "continue"
        # This is LIVE detectable — you see it as it happens
        blocked = [a for a, s in active.items() if s["state"] == "blocked"]
        pushing = [a for a, s in active.items() if s["state"] == "pushing"]
        if blocked and pushing:
            events.append({
                "turn": i,
                "type": "blocked_vs_pushing",
                "severity": "high",
                "agents": pushing + blocked,
                "description": (
                    f"{', '.join(pushing)} insists the task continue, "
                    f"but {', '.join(blocked)} believes it cannot proceed. "
                    f"The agents have fundamentally different views of task feasibility."
                ),
                "related_failures": ["1.5", "2.5"],
                "detection": "live",
            })

        # ── Pattern 2: Approval without substance ──
        # Reviewer says "Finished" but hasn't actually tested anything
        # HINDSIGHT: we know it's wrong because MAST says FM-3.3
        approving = [a for a, s in active.items() if s["state"] == "approving"]
        if approving and snap["speaker"] in approving:
            # Check: was there a recent change request that wasn't addressed?
            recent_change_req = False
            for j in range(max(0, i - 4), i):
                for a, s in timeline[j]["agents"].items():
                    if s["state"] == "req_change" and a != snap["speaker"]:
                        recent_change_req = True

            if recent_change_req:
                events.append({
                    "turn": i,
                    "type": "approval_after_unresolved_changes",
                    "severity": "medium",
                    "agents": approving,
                    "description": (
                        f"{', '.join(approving)} approves the work, but there were "
                        f"recent unresolved change requests. The approval may be premature."
                    ),
                    "related_failures": ["3.3"],
                    "detection": "hindsight",
                })

            # If MAST says 3.3 exists and someone is approving, flag it
            if "3.3" in active_failures:
                # Check if this approval is in a review phase
                if snap["phase"] in ("CodeReviewComment", "Reflection", "Manual"):
                    events.append({
                        "turn": i,
                        "type": "incorrect_verification",
                        "severity": "high",
                        "agents": approving,
                        "description": (
                            f"{', '.join(approving)} verifies the output as correct, "
                            f"but the final result contains errors. The verification "
                            f"was superficial or missed critical issues."
                        ),
                        "related_failures": ["3.3"],
                        "detection": "hindsight",
                    })

        # ── Pattern 3: Step repetition ──
        # Agent produces identical content to a recent turn
        # LIVE detectable by content hash comparison
        if i >= 2 and i < len(turns):
            current_hash = turns[i].get("content_hash", "")
            if current_hash and len(current_hash) > 30:
                for j in range(max(0, i - 8), i):
                    if (turns[j]["agent"] == turns[i]["agent"] and
                            turns[j].get("content_hash", "") == current_hash):
                        events.append({
                            "turn": i,
                            "type": "repetition_loop",
                            "severity": "medium",
                            "agents": [turns[i]["agent"]],
                            "description": (
                                f"{turns[i]['agent']} produces identical content "
                                f"to turn {j + 1}. The system is stuck in a loop."
                            ),
                            "related_failures": ["1.3"],
                            "detection": "live",
                        })
                        break

        # ── Pattern 4: Reasoning-action mismatch ──
        # Agent describes a fix but returns unchanged code
        # LIVE detectable: agent says "I'll fix X" then produces same code
        if snap["speaker"] in states:
            speaker_state = states[snap["speaker"]]
            if (speaker_state["state"] == "approving" and
                    snap["phase"] in ("CodeReviewModification", "Coding")):
                content = turns[i]["content"] if i < len(turns) else ""
                if re.search(r'no\s+changes?|returned?\s+as.?is|same\s+code|unchanged', content.lower()):
                    events.append({
                        "turn": i,
                        "type": "reasoning_action_mismatch",
                        "severity": "medium",
                        "agents": [snap["speaker"]],
                        "description": (
                            f"{snap['speaker']} was asked to modify the code but "
                            f"returned it unchanged. The modification phase produced "
                            f"no actual changes."
                        ),
                        "related_failures": ["2.6"],
                        "detection": "live",
                    })

        # ── Pattern 5: Fuzzy repetition (near-duplicate content) ──
        # Agent produces very similar but not identical content to a recent turn.
        # Uses word-level Jaccard similarity to catch "changed a few lines but
        # didn't fix the actual issue" patterns.
        if i >= 2 and i < len(turns) and snap["speaker"] in agents:
            current_words = _word_set(turns[i].get("content", ""))
            if len(current_words) > 20:  # only for substantial turns
                for j in range(max(0, i - 10), i):
                    if turns[j]["agent"] != turns[i]["agent"]:
                        continue
                    if turns[j].get("phase", "") != turns[i].get("phase", ""):
                        continue
                    prev_words = _word_set(turns[j].get("content", ""))
                    if len(prev_words) < 20:
                        continue
                    sim = _jaccard(current_words, prev_words)
                    if sim > 0.85:
                        pct = int(sim * 100)
                        events.append({
                            "turn": i,
                            "type": "near_duplicate",
                            "severity": "medium",
                            "agents": [turns[i]["agent"]],
                            "description": (
                                f"{turns[i]['agent']} produces content {pct}% similar "
                                f"to turn {j + 1}. The agent appears to be making "
                                f"superficial changes without addressing core issues."
                            ),
                            "related_failures": ["1.3"],
                            "detection": "live",
                        })
                        break

    # ── Pattern 6 (post-loop): Persistent reviewer complaints ──
    # Scan for reviewer turns in CodeReviewComment that share complaint keywords
    # across review cycles. If the same complaint persists 3+ times, the review
    # process is failing to drive actual fixes.
    review_turns = [(i, turns[i]) for i in range(len(turns))
                    if turns[i].get("phase") == "CodeReviewComment"
                    and turns[i]["agent"] not in ("System", "Conclusion")]
    if len(review_turns) >= 2:
        complaint_sets = []
        for idx, t in review_turns:
            words = set(re.findall(r'[a-z]{4,}', t.get("content", "").lower()))
            # Filter to substantive words (skip common ones)
            noise = {"this", "that", "with", "from", "have", "been", "should",
                     "which", "their", "about", "would", "could", "these",
                     "into", "also", "does", "will", "each", "make", "need",
                     "code", "implementation", "current", "comment", "priority",
                     "following", "ensure", "task", "user"}
            words -= noise
            complaint_sets.append((idx, t["agent"], words))

        for k in range(1, len(complaint_sets)):
            prev_idx, prev_agent, prev_words = complaint_sets[k - 1]
            cur_idx, cur_agent, cur_words = complaint_sets[k]
            if prev_agent != cur_agent:
                continue
            overlap = prev_words & cur_words
            if len(overlap) > 5 and len(overlap) / max(len(prev_words), 1) > 0.4:
                shared = sorted(list(overlap))[:6]
                events.append({
                    "turn": cur_idx,
                    "type": "persistent_complaint",
                    "severity": "high",
                    "agents": [cur_agent],
                    "description": (
                        f"{cur_agent} repeats the same complaint from turn {prev_idx + 1}. "
                        f"Key recurring concerns: {', '.join(shared)}. "
                        f"The review cycle is not producing actual fixes."
                    ),
                    "related_failures": ["1.3", "3.3"],
                    "detection": "live",
                })

    # Deduplicate: same type at same turn
    seen = set()
    deduped = []
    for e in events:
        key = (e["turn"], e["type"])
        if key not in seen:
            seen.add(key)
            deduped.append(e)

    return deduped


# ─────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────

def enrich_with_beliefs(processed_data):
    """
    Takes the output of process_trace.py and adds:
      - belief_timeline: per-turn belief snapshots
      - belief_agents: ordered agent list
      - divergence_events: detected belief conflicts
      - belief_states: state definitions (for the viewer)

    Returns the enriched data dict.
    """
    turns = processed_data.get("turns", [])
    active_failures = processed_data.get("failures", {})

    agents, timeline = build_belief_timeline(turns)
    divergences = detect_divergences(timeline, agents, turns, active_failures)

    processed_data["belief_agents"] = agents
    processed_data["belief_timeline"] = timeline
    processed_data["divergence_events"] = divergences
    processed_data["belief_states"] = BELIEF_STATES

    return processed_data


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python belief_extractor.py <processed.json> [output.json]")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        data = json.load(f)

    enriched = enrich_with_beliefs(data)

    out_path = sys.argv[2] if len(sys.argv) > 2 else sys.argv[1].replace(".json", "_beliefs.json")
    with open(out_path, "w") as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)

    print(f"Enriched {len(enriched['belief_timeline'])} turns for {len(enriched['belief_agents'])} agents")
    print(f"  Divergence events: {len(enriched['divergence_events'])}")
    for d in enriched["divergence_events"]:
        det = "🔴 LIVE" if d["detection"] == "live" else "🔵 HINDSIGHT"
        print(f"  {det} Turn {d['turn']+1}: {d['type']} [{', '.join(d['agents'])}]")
        print(f"         {d['description'][:90]}...")
