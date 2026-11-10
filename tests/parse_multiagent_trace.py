#!/usr/bin/env python3
"""Convert one IDA agent trace into the shared simple event shape.

The input format is ``ida.agenttrace/1.0`` and ``ida.agenttrace/1.1``.  It records model executions,
agent messages, observed inbox reads, and retrieval events.  The parser keeps
only recorded values and never turns a missing value into a claim.

Each output item has exactly this shape:
    time, agent, action, message, target, source_trace

Usage:
    python3 tests/parse_multiagent_trace.py INPUT.json OUTPUT.json
"""

import json
import sys
from pathlib import Path


FIELDS = ("time", "agent", "action", "message", "target", "source_trace")


def _source_trace(path: Path, pointer: str) -> str:
    return f"ida.agenttrace:{path.name}#{pointer}"


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _target(receivers: object) -> str:
    if not isinstance(receivers, list) or not receivers:
        return "broadcast"
    return ",".join(str(receiver) for receiver in receivers)


def _event(
    *,
    time: object,
    agent: object,
    action: str,
    message: object,
    target: object,
    source_trace: str,
) -> dict:
    """Create one shared-shape event, using explicit UNKNOWN placeholders."""
    item = {
        "time": time or "UNKNOWN",
        "agent": agent or "UNKNOWN",
        "action": action,
        "message": message if isinstance(message, str) else _json(message),
        "target": target or "UNKNOWN",
        "source_trace": source_trace,
    }
    assert tuple(item) == FIELDS
    return item


def _seq(value: object, fallback: int) -> tuple[int, int]:
    """Sort by recorded sequence where available, without exporting it."""
    return (value, fallback) if isinstance(value, int) else (10**12, fallback)


def parse_multiagent_trace(raw: dict, source_path: Path) -> list[dict]:
    """Return observed events from one ``ida.agenttrace`` record.

    ``rendered_input`` belongs to an execution rather than each individual
    provider retry. Version 1.1 adds a top-level ``llm_calls`` table with the
    full recorded request and raw response, which is preserved as separate
    events when present.
    """
    pending: list[tuple[tuple[int, int], dict]] = []
    serial = 0

    def add(order: tuple[int, int], **kwargs: object) -> None:
        nonlocal serial
        pending.append((order, _event(**kwargs)))
        serial += 1

    for index, execution in enumerate(raw.get("executions", [])):
        if not isinstance(execution, dict):
            continue
        seq_start = execution.get("seq_start")
        agent = execution.get("agent_id")
        execution_id = execution.get("execution_id", "UNKNOWN")
        calls = execution.get("llm_calls") or []
        base = f"/executions/{index}"

        rendered_input = execution.get("rendered_input")
        if rendered_input:
            add(
                _seq(seq_start, serial),
                time=execution.get("started_at"),
                agent=agent,
                action="model_input",
                message={
                    "system": execution.get("rendered_system"),
                    "input": rendered_input,
                    "execution_id": execution_id,
                    "provider_calls": len(calls),
                },
                target=agent,
                source_trace=_source_trace(source_path, f"{base}/rendered_input"),
            )

        if execution.get("output") is not None:
            add(
                _seq(execution.get("seq_end"), serial),
                time=execution.get("completed_at"),
                agent=agent,
                action="model_output" if calls else "agent_output",
                message={
                    "execution_id": execution_id,
                    "status": execution.get("status"),
                    "output": execution.get("output"),
                    "provider_call_metadata": calls,
                },
                target="user" if execution.get("kind") == "final" else "UNKNOWN",
                source_trace=_source_trace(source_path, f"{base}/output"),
            )

    for index, call in enumerate(raw.get("llm_calls", [])):
        if not isinstance(call, dict):
            continue
        base = f"/llm_calls/{index}"
        order = _seq(call.get("seq"), serial)
        if call.get("request") is not None:
            add(order, time=call.get("ts"), agent=call.get("agent_id"), action="model_request",
                message={"execution_id": call.get("execution_id"), "call_index": call.get("call_index"),
                         "request": call.get("request")}, target=call.get("agent_id"),
                source_trace=_source_trace(source_path, f"{base}/request"))
        if call.get("response_raw") is not None or call.get("error") is not None:
            add(order, time=call.get("ts"), agent=call.get("agent_id"), action="model_response",
                message={"execution_id": call.get("execution_id"), "call_index": call.get("call_index"),
                         "response_raw": call.get("response_raw"), "error": call.get("error"),
                         "ok": call.get("ok")}, target=call.get("agent_id"),
                source_trace=_source_trace(source_path, f"{base}/response_raw"))

    for index, change in enumerate(raw.get("score_changes", [])):
        if not isinstance(change, dict):
            continue
        add(_seq(change.get("seq"), serial), time=change.get("ts"), agent=change.get("actor"),
            action="score_changed", message={"operation": change.get("operation"), "before": change.get("before"),
                                              "after": change.get("after"), "delta": change.get("delta")},
            target="hypothesis_scores", source_trace=_source_trace(source_path, f"/score_changes/{index}"))

    for index, message in enumerate(raw.get("messages", [])):
        if not isinstance(message, dict):
            continue
        base = f"/messages/{index}"
        sender = message.get("sender_agent_id")
        content = message.get("message_content", "")
        add(
            _seq(message.get("seq"), serial),
            time=message.get("timestamp"),
            agent=sender,
            action=f"message_{str(message.get('message_type') or 'sent').lower()}",
            message=content,
            target=_target(message.get("receiver_agent_ids")),
            source_trace=_source_trace(source_path, base),
        )
        for delivery_index, delivery in enumerate(message.get("deliveries") or []):
            if not isinstance(delivery, dict):
                continue
            add(
                _seq(delivery.get("seq"), serial),
                time=delivery.get("timestamp"),
                agent=sender,
                action="message_delivered",
                message=content,
                target=delivery.get("receiver"),
                source_trace=_source_trace(source_path, f"{base}/deliveries/{delivery_index}"),
            )

    for index, event in enumerate(raw.get("events", [])):
        if not isinstance(event, dict) or event.get("event_type") != "EVIDENCE_RETRIEVED":
            continue
        add(
            _seq(event.get("seq"), serial),
            time=event.get("timestamp"),
            agent=event.get("actor"),
            action="evidence_retrieved",
            message={
                "evidence_ids": event.get("evidence_ids", []),
                "payload": event.get("payload", {}),
            },
            target="evidence_store",
            source_trace=_source_trace(source_path, f"/events/{index}"),
        )

    return [item for _, item in sorted(pending, key=lambda pair: pair[0])]


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: parse_multiagent_trace.py INPUT.json OUTPUT.json")
    source_path = Path(sys.argv[1])
    raw = json.loads(source_path.read_text())
    events = parse_multiagent_trace(raw, source_path)
    Path(sys.argv[2]).write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
