# AgentTrace

**Visual Sensemaking of Multi-Agent Interaction & World-Model Divergence**

> CSE 523 Advanced Project in Computer Science — Devika Vishnu, Komalika Acharya

---

## What is AgentTrace?

AgentTrace is an interactive visual analytics system that makes multi-agent LLM system (MAS) behaviour legible to human observers. It addresses a core observability gap: existing frameworks like ChatDev and AG2 produce rich conversation logs, but offer no mechanism for inspecting how individual agents' reasoning states change turn-by-turn, or where those states diverge across agents.

Multi-agent systems fail at surprisingly high rates — ChatDev achieves only 33% correctness on straightforward programming benchmarks (Cemri et al., 2025). Many of these failures arise not from individual agent incompetence but from **misaligned beliefs**: agents hold fundamentally different views of task state, completeness, or feasibility, yet continue interacting without resolving the divergence.

AgentTrace answers:
- Which agent believed what, at each point in time?
- When did agent beliefs first diverge from each other?
- How did the divergence propagate into downstream failures?

---

## Architecture

The system consists of three sequential stages:

```
Raw MAS trace  ──►  process_trace.py  ──►  belief_extractor.py  ──►  BeliefEvolution.jsx
                    (Stage 1)               (Stage 2)                  (Stage 3)
                    Normalise to            Classify belief             Render interactive
                    standard JSON           states + detect             timeline grid
                                            divergences
```

### Stage 1 — Trace Processor (`process_trace.py`)
Converts raw ChatDev and AG2 JSON traces into a common schema. Handles framework-specific quirks such as ChatDev's `<INFO>` conclusion markers, role-based phase boundaries, and the Counselor's Reflection phase. Output: `{ turns[], failures{} }`.

### Stage 2 — Belief Extractor (`belief_extractor.py`)
Takes the normalised trace and produces per-turn belief snapshots for every agent. Two sequential operations:

**Timeline construction** (`build_belief_timeline`) — Agent states are *sticky*: speaking agents are classified by `classify_belief()`; silent agents retain their last known state. `classify_belief` applies seven heuristics in priority order:
1. Explicit markers — `<INFO>`, AG2 `Continue`, LaTeX `\boxed{}`
2. Blocking phrases — "cannot be solved", "not enough information"
3. Code blocks — triple-backtick fences, `def`, `import`
4. Review signals — "LGTM", "bug", "fix", "error"
5. Question detection — `?` + wh-word
6. Phase defaults — e.g. Coding → `building`, EnvironmentDoc → `completing`
7. Fallback — retain previous state or assign `proposing`

**Divergence detection** (`detect_divergences`) — Six conflict patterns:

| Pattern | Type | Description |
|---|---|---|
| P1 Blocked vs pushing | Live | One agent blocked, another pushing — feasibility deadlock |
| P2 Approval without substance | Hindsight | Approves while unaddressed change requests remain |
| P3 Step repetition | Live | Content hash matches a prior turn |
| P4 Reasoning–action mismatch | Live | Approving state + unchanged code |
| P5 Fuzzy repetition | Live | Jaccard word similarity > 0.85 to a recent turn |
| P6 Persistent complaint | Live | Same complaint keywords across consecutive review cycles |

Output keys: `belief_agents`, `belief_timeline`, `divergence_events`, `belief_states`.

### Stage 3 — React Visualiser (`BeliefEvolution.jsx`)
A single self-contained React component (~1,360 lines) that consumes the enriched JSON and renders an interactive timeline grid. No build step required beyond a standard Vite/React environment.

---

## Belief State Taxonomy

Ten mutually exclusive states covering both task-activity and epistemic dimensions:

| State | Label | Description |
|---|---|---|
| `idle` | Idle | Agent exists but has not yet contributed to the current phase |
| `asking` | Asking | Posing a question or requesting action from another agent |
| `proposing` | Proposing | Suggesting an approach, design decision, or answer |
| `building` | Building | Writing code or producing concrete artefacts |
| `reviewing` | Reviewing | Evaluating or reflecting on work produced by others |
| `req_change` | Wants change | Requesting modifications to current work |
| `approving` | Approving | Accepting work as complete, signalling readiness to proceed |
| `blocked` | Blocked | Believes the task cannot proceed with current information |
| `pushing` | Pushing | Insisting the task continue despite apparent obstacles |
| `completing` | Completing | Producing final documentation or deliverable artefacts |

Colours follow the **IBM Carbon colorblind-safe palette**, distinguishable under deuteranopia, protanopia, and tritanopia.

---

## Dataset

Four pre-enriched traces are included:

| Framework | Task | Turns | MAST Failures |
|---|---|---|---|
| AG2 | GSM-Plus / Monica ribbon problem (unsolvable) | 10 | 3 (FM-1.3, FM-1.5, FM-2.5) |
| ChatDev | Checkers — Trace 0 | 26 | 0 |
| ChatDev | TicTacToe — Trace 6 | 26 | 1 (FM-1.1) |
| ChatDev | Gomoku — Trace 7 | 26 | 2 (FM-1.3, FM-3.3) |

All ChatDev traces use GPT-4o on the ProgramDev benchmark.

---

## Technology Stack

| Component | Technology |
|---|---|
| Visualisation frontend | React 18, Vite, vanilla CSS-in-JS |
| Belief extraction | Python 3, pattern-based NLP, JSON I/O |
| MAS trace data | ChatDev (GPT-4o, ProgramDev), AG2 (GSM-Plus) |
| Data format | Enriched JSON with `belief_timeline` and `divergence_events` |
| Deployment | Local Vite dev server (`npm run dev`) |

---

## Getting Started

### Prerequisites
- Node.js ≥ 18
- Python ≥ 3.9

### Run the visualiser

```bash
cd v4.4_beliefs
npm install
npm run dev
```

Then open `http://localhost:5173` in your browser. Four pre-enriched traces are available from the source selector in the UI.

### Process a new trace

```bash
# Step 1 — normalise a raw ChatDev or AG2 trace
python process_trace.py --input path/to/raw_trace.json --output processed.json

# Step 2 — extract belief states
python belief_extractor.py --input processed.json --output enriched.json
```

Load `enriched.json` into the visualiser using the **↑ Load JSON** button.

---

## Key Features

- **Belief grid** — agents × turns matrix, each cell colour-coded and labelled by reasoning state
- **Phase bar** — colour-coded pipeline phase annotations above the grid
- **Phase tabs** — click any phase to jump the playhead and highlight its columns
- **Playhead scrubber** — step through the conversation turn by turn
- **Sticky labels** — agent names remain fixed while scrolling horizontally
- **Divergence track** — ⚡ markers below the grid at detected conflict turns
- **Detail panel** — click any cell or marker to see state, MAST failure codes, and phase context

---

## Limitations & Future Work

- The pattern-based classifier does not capture semantic nuance; agents describing intent without producing output may be misclassified
- FM-2.4 (Information Withholding) and FM-2.2 (Failure to Ask for Clarification) are not yet implemented as divergence detectors
- The system identifies divergence events at individual turns but does not connect them into a visual causal chain
- Future work: formal evaluation of classification accuracy (Cohen's κ), probabilistic state representations, causal chain view, live streaming integration

---

## References

- Cemri, M. et al. (2025). *Why Do Multi-Agent LLM Systems Fail?* arXiv:2503.13657v2.
- Qian, C. et al. (2023). *ChatDev: Communicative Agents for Software Development.* arXiv:2307.07924.
- Epperson, W. et al. (2025). *Interactive Debugging and Steering of Multi-Agent AI Systems.* CHI 2025. arXiv:2503.02068.
- Wu, Q. et al. (2024). *AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversations.* COLM 2024.

---

## Disclaimer

Reasoning states are inferred from observable conversational behaviour using rule-based extraction. They do not necessarily reflect the latent internal states of language models. AgentTrace provides an interpretable behavioural approximation, not formal belief inference.
