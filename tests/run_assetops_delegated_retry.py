#!/usr/bin/env python3
"""One small, fully logged AssetOpsBench manager/helper retry experiment.

Run from the AssetOpsBench checkout:
  PYTHONPATH=src uv run python /path/to/run_assetops_delegated_retry.py OUTPUT.json

It intentionally asks the helper to retry an asset lookup after an empty
result, then requires the manager to cite the helper's returned evidence.
"""

import asyncio
import dataclasses
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage

from agent._prompts import AGENT_SYSTEM_PROMPT
from agent.deep_agent.runner import _build_chat_model, _build_mcp_connections, _build_trajectory


def _text(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    return json.dumps(content, default=str)


class HelperCapture(AgentMiddleware):
    """Record observable helper inputs, outputs, and tool attempts."""

    def __init__(self, sink: list[dict]):
        super().__init__()
        self.sink = sink

    async def awrap_model_call(self, request, handler):
        self.sink.append({
            "kind": "helper_model_input",
            "system_prompt": request.system_prompt,
            "messages": [_text(message) for message in request.messages],
        })
        response = await handler(request)
        self.sink.append({
            "kind": "helper_model_output",
            "messages": [_text(message) for message in response.result],
        })
        return response

    async def awrap_tool_call(self, request, handler):
        attempt = 1 + sum(
            item.get("kind") == "helper_tool_call"
            and item.get("tool_name") == request.tool_call.get("name")
            for item in self.sink
        )
        result = await handler(request)
        self.sink.append({
            "kind": "helper_tool_call",
            "attempt_number": attempt,
            "tool_name": request.tool_call.get("name"),
            "tool_input": request.tool_call.get("args", {}),
            "tool_status": getattr(result, "status", "unknown"),
            "tool_output": _text(result) if isinstance(result, ToolMessage) else str(result),
        })
        return result


async def run(output_path: Path) -> None:
    from deepagents import create_deep_agent
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from agent.runner import DEFAULT_SERVER_PATHS

    # The normal CLI loads this file before constructing its model. This
    # standalone experiment runner must do the same.
    load_dotenv(Path.cwd() / ".env")
    client = MultiServerMCPClient(_build_mcp_connections(DEFAULT_SERVER_PATHS))
    tools = await client.get_tools()
    capture: list[dict] = []
    model = _build_chat_model("openai:gpt-4o-mini")

    helper = {
        "name": "asset-helper",
        "description": "Must be used to verify a small asset lookup and report exact tool evidence.",
        "system_prompt": """You are the asset helper. Do exactly this:
1. Call asset_ids with site_name NOT_A_SITE. Record the empty/error result.
2. Retry asset_ids with site_name MAIN.
3. Report whether Chiller 6 appears, including both attempts and why the retry was needed.
Do not make claims beyond your tool results.""",
        "tools": tools,
        "model": model,
        "middleware": [HelperCapture(capture)],
    }
    manager_prompt = AGENT_SYSTEM_PROMPT + """

For this task you MUST call the `task` tool once with subagent_type
`asset-helper`. Do not perform the lookup yourself. In your final answer,
state the helper's two lookup attempts and cite its returned result."""
    agent = create_deep_agent(
        model=model,
        # Deliberately give domain tools only to the helper. This makes the
        # manager-to-helper handoff observable and prevents a direct bypass.
        tools=[],
        system_prompt=manager_prompt,
        subagents=[helper],
    )
    question = "Ask the asset helper to verify whether Chiller 6 is at MAIN, using its required retry procedure. Return only the helper-backed conclusion."
    started_at = datetime.now(UTC).isoformat()
    state = await agent.ainvoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"recursion_limit": 14},
    )
    messages = state.get("messages", [])
    trajectory = _build_trajectory(messages)
    trajectory.started_at = started_at
    answer = next((
        _text(message) for message in reversed(messages)
        if getattr(message, "type", "") == "ai" and _text(message).strip()
    ), "")
    delegations = []
    for turn in trajectory.turns:
        for call in turn.tool_calls:
            if call.name == "task":
                delegations.append({
                    "delegated_by": "manager",
                    "agent": "asset-helper",
                    "parent_task": call.input.get("description"),
                    "return_message": call.output,
                    "source_turn": turn.index,
                })
    output_path.write_text(json.dumps({
        "run_id": "assetops-delegated-retry-001",
        "runner": "deep-agent-instrumented",
        "model": "openai:gpt-4o-mini",
        "question": question,
        "answer": answer,
        "trajectory": dataclasses.asdict(trajectory),
        "instrumentation": {
            "delegations": delegations,
            "helper_activity": capture,
            "note": "Helper model inputs and helper tool calls are recorded; this is deliberate experiment-only instrumentation.",
        },
    }, indent=2, default=str) + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: run_assetops_delegated_retry.py OUTPUT.json")
    asyncio.run(run(Path(sys.argv[1])))
