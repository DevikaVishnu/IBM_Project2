# AgentTrace research

AgentTrace (`agenttrace.semantic`) is a framework-independent semantic observability layer for agentic AI. It is part of IBM Research *Mission Control for Agentic AI* and of CSE 523. It records what content existed, what reached each agent's rendered model input, what agents claimed, what was verified, how content propagated, and where the answer must be UNKNOWN. The current work stress-tests schema 0.3 against real DeepAgents traces.

## Session start

Read `docs/research/STATE.md` first. It holds the current question, the verified findings, the single next action and the open decisions.

## Repositories

- **AP** (this repo, branch `main`): the research repo. It holds the canonical schema `docs/agenttrace.semantic.0.3.md`, the scenarios in `data/assetopsbench/scenarios/` and the raw runs in `data/assetopsbench/runs/`.
- **AssetOpsBench** (`/Users/devikavishnu/projects/AssetOpsBench`, branch `local/direct-provider-models`): the execution repo. It holds the DeepAgents runner, the instrumentation and its tests, and the full research checkpoint. Its `origin` is IBM upstream.

## Context budget

The main session works from `STATE.md` and the subagent reports. Load the full checkpoint, the canonical schema or any raw run file only when a task explicitly requires it. Each of them costs thousands of tokens.

- **Schema audits** (is X representable under 0.3, which rule applies): delegate them to the schema-audit subagent once one is configured. Until then, read only the cited § of the schema.
- **Trace analysis** (seq numbers, joins by `tool_call_id` and sha, delivery into `llm_start`): delegate it to the trace-analysis subagent once one is configured. Until then, use the built-in `Explore` or `general-purpose` agent and ask for a short report.
- **Code lookups**: use the built-in `Explore` agent.

## Research constraints

- Schema 0.3 is frozen for this work: no edits to it, and no 0.4 design.
- Raw runs and `traces.jsonl` are read-only evidence. Write each new run to a new run ID and a fresh per-run `OTEL_TRACES_FILE`, set in that one command's environment. Leave `.env` unchanged.
- Agent behavior stays production: use the unchanged prompt, tools and model route. Scenarios are used verbatim, and facts and tool outputs are never planted or fabricated.
- Label evidence **[OBS]** (observed), **[INF]** (inferred by a stated rule) or **[HYP]** (untested). Contribution is at most a hypothesis.
- Documents carry no secrets and no complete model inputs.
- The installed site-packages stay untouched.

## Paid experiments

Every real-model run costs money and changes shared state. Before any `deep-agent` invocation:

1. Write a pre-registration: the scenario, the success criteria, the stopping rule, the run ID, the OTEL file and the WO DB count check.
2. Show it to the user and wait for explicit approval.
3. Execute exactly one run, then report honestly.

## Git

- Stage only named files, and only when the user asks.
- Commit or push only on the user's explicit instruction. Never push AssetOpsBench.
- Commit messages carry no Claude attribution or co-author trailers.
- `data/assetopsbench/runs/` stays untracked.
- In AssetOpsBench, `src/agent/claude_agent/runner.py`, `src/llm/litellm.py` and `_subagent_capture.py.bak` are the user's unrelated work in progress; leave them as they are.
