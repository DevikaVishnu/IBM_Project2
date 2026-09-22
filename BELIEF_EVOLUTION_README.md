# AgentTrace — Belief Evolution System

## What's New

### 1. `belief_extractor.py` (Python)
Extracts per-turn belief states and divergence events from processed traces.

**Usage:**
```bash
# First process the raw trace
python process_trace.py trace_1_ChatDev.json trace_1_processed.json

# Then enrich with belief data  
python belief_extractor.py trace_1_processed.json trace_1_enriched.json
```

**What it produces:**
- `belief_timeline`: For every turn, every agent's inferred belief state
- `divergence_events`: Moments where agents' beliefs conflict
- Each divergence is tagged as "live" (visible as it happens) or "hindsight" (only visible after outcome)

### 2. `BeliefEvolution.jsx` (React)
Interactive visualization with:
- **Belief grid**: Rows = agents, columns = turns, color = belief state
- **Playhead scrubber**: Step through the conversation turn by turn
- **Divergence markers**: Red dots and ⚡ symbols where beliefs conflict
- **Detail panel**: Click any cell or marker for full context
- **Live vs hindsight detection**: Distinguishes what's detectable in real-time vs. only in retrospect

### 3. Pre-enriched data files
- `trace_1_ChatDev_enriched.json` through `trace_4_ChatDev_enriched.json`
- Load these via the "Load enriched JSON" button in the viewer

## How to Run

```bash
cd v3_graph
npm run dev
```

The app now has a toggle at the top:
- **⚡ Belief Evolution** — new belief timeline view
- **Timeline + Graph** — original view

## Belief States

| State | Meaning | When |
|-------|---------|------|
| Idle | Not yet active | Before agent's first turn |
| Asking | Posing a question | Agent asks or requests action |
| Proposing | Suggesting approach | Design decisions, answers |
| Building | Writing code/artifacts | Coding, implementing |
| Reviewing | Evaluating work | Code review, reflection |
| Wants Change | Requesting modifications | Review found issues |
| Approving | Accepting as complete | "Finished", "looks good" |
| Blocked | Believes task stuck | "Cannot solve", "insufficient" |
| Pushing | Insisting despite issues | "Continue" patterns |
| Completing | Final documentation | Env docs, manuals |

## Divergence Types

| Type | Detection | Example |
|------|-----------|---------|
| blocked_vs_pushing | Live | Agent A says "unsolvable", Agent B says "continue" |
| repetition_loop | Live | Agent produces identical content to earlier turn |
| reasoning_action_mismatch | Live | Agent asked to modify code but returns it unchanged |
| approval_after_unresolved_changes | Hindsight | Agent approves despite recent unaddressed change requests |
| incorrect_verification | Hindsight | Reviewer approves but output has known errors (from MAST) |

## Next Steps

1. **Fix parser** — system prompts still leak into turn content (`_extract_useful_content`)
2. **Refine classifier** — add more patterns for each belief state
3. **Add more divergence patterns** — FM-2.4 (info withholding), FM-2.2 (no clarification)
4. **Belief detail text** — show what specifically each agent believes, not just the state label
5. **Causal chain view** — connect divergence events to downstream failures
