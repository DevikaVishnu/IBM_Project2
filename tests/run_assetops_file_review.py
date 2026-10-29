#!/usr/bin/env python3
"""Instrumented manager -> writer -> reviewer file-handoff experiment."""

import asyncio
import dataclasses
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool

from agent.deep_agent.runner import _build_chat_model, _build_trajectory


ARTIFACT = Path("/private/tmp/assetops-belief-handoff.json")


def _text(message) -> str:
    content = getattr(message, "content", "")
    return content if isinstance(content, str) else json.dumps(content, default=str)


@tool
def write_handoff_artifact() -> str:
    """Write the single controlled Chiller 6 handoff artifact and return its version and hash."""
    content = json.dumps({"asset": "Chiller 6", "status": "READY", "version": 1}, sort_keys=True)
    ARTIFACT.write_text(content + "\n")
    return json.dumps({"artifact_id": ARTIFACT.name, "version": 1,
                       "content_hash": hashlib.sha256(content.encode()).hexdigest()})


@tool
def read_handoff_artifact() -> str:
    """Read the single controlled Chiller 6 handoff artifact and return its content and hash."""
    content = ARTIFACT.read_text().strip()
    return json.dumps({"artifact_id": ARTIFACT.name, "content": json.loads(content),
                       "content_hash": hashlib.sha256(content.encode()).hexdigest()})


class Capture(AgentMiddleware):
    def __init__(self, agent_name: str, sink: list[dict]):
        super().__init__()
        self.agent_name, self.sink = agent_name, sink

    async def awrap_model_call(self, request, handler):
        self.sink.append({"agent": self.agent_name, "kind": "model_input",
                          "messages": [_text(m) for m in request.messages]})
        response = await handler(request)
        self.sink.append({"agent": self.agent_name, "kind": "model_output",
                          "messages": [_text(m) for m in response.result]})
        return response

    async def awrap_tool_call(self, request, handler):
        result = await handler(request)
        self.sink.append({"agent": self.agent_name, "kind": "tool_call",
                          "tool": request.tool_call.get("name"),
                          "input": request.tool_call.get("args", {}),
                          "output": _text(result) if isinstance(result, ToolMessage) else str(result),
                          "tool_status": getattr(result, "status", "unknown")})
        return result


async def run(output: Path) -> None:
    from deepagents import create_deep_agent

    load_dotenv(Path.cwd() / ".env")
    model = _build_chat_model("openai:gpt-4o-mini")
    activity: list[dict] = []
    writer = {
        "name": "artifact-writer",
        "description": "Must be used first to create the controlled handoff artifact.",
        "system_prompt": "Call write_handoff_artifact exactly once. Return its artifact_id, version, and hash.",
        "tools": [write_handoff_artifact], "model": model,
        "middleware": [Capture("artifact-writer", activity)],
    }
    reviewer = {
        "name": "artifact-reviewer",
        "description": "Must be used after the writer to check the controlled handoff artifact.",
        "system_prompt": "Call read_handoff_artifact exactly once. Check the proposition 'status equals READY'. Return CHECKED plus PASS or FAIL, the artifact_id, and hash. Do not say PASS without reading.",
        "tools": [read_handoff_artifact], "model": model,
        "middleware": [Capture("artifact-reviewer", activity)],
    }
    prompt = """You are a manager. You have no direct artifact tools. You MUST:
1. Use artifact-writer once and wait for its report.
2. Then use artifact-reviewer once and wait for its report.
3. State the reviewer result and cite the artifact ID and hash from the reports."""
    agent = create_deep_agent(model=model, tools=[], system_prompt=prompt, subagents=[writer, reviewer])
    question = "Create and review the Chiller 6 handoff artifact. Is status READY?"
    started_at = datetime.now(UTC).isoformat()
    state = await agent.ainvoke({"messages": [{"role": "user", "content": question}]}, config={"recursion_limit": 18})
    messages = state.get("messages", [])
    trajectory = _build_trajectory(messages)
    trajectory.started_at = started_at
    answer = next((_text(m) for m in reversed(messages) if getattr(m, "type", "") == "ai" and _text(m).strip()), "")
    output.write_text(json.dumps({"run_id": "assetops-file-review-001", "runner": "deep-agent-instrumented",
        "model": "openai:gpt-4o-mini", "question": question, "answer": answer,
        "trajectory": dataclasses.asdict(trajectory), "instrumentation": {"activity": activity}}, indent=2) + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: run_assetops_file_review.py OUTPUT.json")
    asyncio.run(run(Path(sys.argv[1])))
