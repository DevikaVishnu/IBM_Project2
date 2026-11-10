"""Structural adapter for agent-council traces (export format ida.agenttrace.export/1.0).

    python3 -I scripts/explorer/council_adapter.py --archive data/agent-council/agent_traces_20.zip --run TR-20261102192218-620bef53
    python3 -I scripts/explorer/council_adapter.py --input path/to/TR-....json

Reads one run, read-only (an archive member is read in place through zipfile, never extracted), and returns
an `agent-council-structure/0.1` record: local research display data. It is NOT agenttrace.semantic/0.3 and
NOT an explorer bundle; scripts/explorer/build_council_bundle.py maps it onto agenttrace-explorer-bundle/0.1.

What the adapter does:
  * preserves every agent, execution, model call, message (with each delivery record), evidence record, tool
    call, framework-computed position, overall hypothesis score vector, disagreement, round and the final decision, each with a `src`
    locator (and seq / event_id / timestamp where the raw trace has them);
  * classifies, by stated rules only:
      - model-call mechanism: llm_voice | llm_analysis; executions without model calls are deterministic;
      - message text mechanism: llm_voice | deterministic (raw payload.voice kept);
      - delivery class: recorded_delivery (extent whole | prefix) | rendered_prompt_unverified |
        rendered_prompt_content_not_found | code_access | code_access_no_execution | unknown_channel;
      - model input: verified | mismatch | not_recorded_per_call | absent;
      - model output: complete | truncated | unknown;
  * keeps framework-computed positions apart from anything an agent expressed.

What it never does: read meaning from natural-language text, create claims, propositions, states or semantic
links, or run a model.  Required fields missing -> AdapterError (fail closed); optional fields missing ->
recorded in `ambiguities`.  Stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

FORMAT = "ida.agenttrace.export/1.0"
STRUCTURE = "agent-council-structure/0.1"
AP_ROOT = Path(__file__).resolve().parents[2]
FRAMEWORK_ACTORS = {"harness"}  # actor values the export uses for the framework itself, not for an agent


class AdapterError(Exception):
    """The input cannot be adapted without guessing."""


def sha(b: bytes | str) -> str:
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode("utf-8")).hexdigest()


def rel(p: Path) -> str:
    p = Path(p).resolve()
    try:
        return str(p.relative_to(AP_ROOT))
    except ValueError:
        return p.name  # never a home-directory path


# ------------------------------------------------------------------------------------------- loading


def list_runs(archive: Path) -> list[str]:
    with zipfile.ZipFile(archive) as z:
        return sorted(n for n in z.namelist() if n.count("/") == 1 and n.endswith(".json") and n.split("/")[0] == Path(n).stem)


def load_run(archive: Path | None = None, run: str | None = None, input_path: Path | None = None) -> tuple[dict, dict]:
    """Return (raw trace, source provenance).  `run` is a trace id or a unique substring of one."""
    if input_path is not None:
        data = Path(input_path).read_bytes()
        return _parse(data), {"file": rel(input_path), "sha256": sha(data)}
    if archive is None or not run:
        raise AdapterError("give --input, or --archive with --run")
    members = list_runs(archive)
    hits = [m for m in members if m.split("/")[0] == run] or [m for m in members if run in m.split("/")[0]]
    if len(hits) != 1:
        raise AdapterError(f"run {run!r} matches {len(hits)} archive members" + (f": {[h.split('/')[0] for h in hits]}" if hits else f"; runs: {[m.split('/')[0] for m in members]}"))
    arch = Path(archive).read_bytes()
    with zipfile.ZipFile(archive) as z:
        data = z.read(hits[0])
    raw = _parse(data)
    tid = (raw.get("trace") or {}).get("trace_id")
    if tid != hits[0].split("/")[0]:
        raise AdapterError(f"member {hits[0]} holds trace {tid!r}, not the run its path names")
    return raw, {"archive": rel(archive), "archive_sha256": sha(arch), "member": hits[0], "member_sha256": sha(data)}


def _parse(data: bytes) -> dict:
    try:
        raw = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise AdapterError(f"not JSON: {e}") from None
    if not isinstance(raw, dict) or raw.get("export_format") != FORMAT:
        raise AdapterError(f"export_format is {raw.get('export_format') if isinstance(raw, dict) else None!r}, expected {FORMAT}")
    return raw


# ------------------------------------------------------------------------------------------- locators

_TOKEN = re.compile(r"([A-Za-z_]\w*)|\[(\w+)=([^\]]+)\]|\[(\d+)\]|\.")


def resolve(raw: dict, locator: str):
    """Resolve `a.b[key=value][0].c` against the raw trace.  Raises KeyError if it does not resolve uniquely."""
    cur, pos = raw, 0
    while pos < len(locator):
        m = _TOKEN.match(locator, pos)
        if not m or m.end() == pos:
            raise KeyError(f"bad locator {locator!r} at {pos}")
        pos = m.end()
        name, key, val, idx = m.groups()
        if name is not None:
            cur = cur[name]
        elif key is not None:
            hits = [x for x in cur if isinstance(x, dict) and str(x.get(key)) == val]
            if len(hits) != 1:
                raise KeyError(f"{locator}: {len(hits)} items with {key}={val}")
            cur = hits[0]
        elif idx is not None:
            cur = cur[int(idx)]
    return cur


# ------------------------------------------------------------------------------------------- adapter


def _escaped_forms(text: str) -> list[str]:
    return [text, json.dumps(text)[1:-1], json.dumps(text, ensure_ascii=False)[1:-1]]


_DECODER = json.JSONDecoder()


def _find_in_input(ri: str, mid: str, text: str) -> tuple[bool, str | None, int | None]:
    """Is message `mid`'s content in the rendered input?  Returns (found, extent, delivered characters).

    1. The whole content occurs verbatim (raw or JSON-escaped)            -> (True, "whole", len)
    2. A JSON object {"id": mid, ..., "text": t} is embedded and the content starts with t (t non-empty)
                                                                          -> (True, "whole" | "prefix", len(t))
    Otherwise (False, None, None).  Structural string checks only; no meaning is read.
    """
    if any(f in ri for f in _escaped_forms(text)):
        return True, "whole", len(text)
    best = None
    for m in re.finditer(r'\{"id":\s*' + re.escape(json.dumps(mid)), ri):
        try:
            obj, _ = _DECODER.raw_decode(ri, m.start())
        except json.JSONDecodeError:
            continue
        t = obj.get("text") if isinstance(obj, dict) else None
        if isinstance(t, str) and t and text.startswith(t) and (best is None or len(t) > best):
            best = len(t)
    if best is None:
        return False, None, None
    return True, "whole" if best == len(text) else "prefix", best


def adapt(raw: dict, source: dict) -> dict:
    amb: list[dict] = []

    def missing(where, field, effect):
        amb.append({"where": where, "field": field, "effect": effect})

    def get(obj, key, where, effect="recorded as null", default=None):
        if not isinstance(obj, dict) or key not in obj:
            missing(where, key, effect)
            return default
        return obj[key]

    if raw.get("export_format") != FORMAT:
        raise AdapterError(f"export_format is {raw.get('export_format')!r}, expected {FORMAT}")
    trace = raw.get("trace")
    if not isinstance(trace, dict) or not trace.get("trace_id"):
        raise AdapterError("trace.trace_id is required")
    tid = trace["trace_id"]

    # ---- events: the observation order (framework-assigned seq).  seq must exist and be unique.
    raw_events = raw.get("events")
    if not isinstance(raw_events, list):
        raise AdapterError("events[] is required (it carries the observation order)")
    events = []
    for i, e in enumerate(raw_events):
        if not isinstance(e, dict) or not isinstance(e.get("seq"), int):
            raise AdapterError(f"events[{i}] has no integer seq")
        events.append({"seq": e["seq"], "event_id": e.get("event_id"), "type": e.get("event_type"), "timestamp": e.get("timestamp"), "actor": e.get("actor"),
                       "execution_id": e.get("execution_id"), "message_id": e.get("message_id"), "evidence_ids": list(e.get("evidence_ids") or []),
                       "locator": f"events[seq={e['seq']}]"})
        for k in ("event_id", "event_type", "timestamp"):
            if e.get(k) is None:
                missing(f"events[seq={e['seq']}]", k, "kept as null")
    dup = [s for s, n in Counter(e["seq"] for e in events).items() if n > 1]
    if dup:
        raise AdapterError(f"duplicate event seq {dup[:5]}: observation order is ambiguous")
    events.sort(key=lambda e: e["seq"])
    by_type = defaultdict(list)
    for e, r in zip(events, sorted(raw_events, key=lambda r: r["seq"])):
        by_type[e["type"]].append((e, r.get("payload") or {}))

    def ref(e):
        return {"seq": e["seq"], "event_id": e["event_id"], "timestamp": e["timestamp"], "locator": e["locator"]} if e else None

    # ---- executions and model calls
    raw_execs = get(raw, "executions", "run", "no executions", []) or []
    for i, x in enumerate(raw_execs):
        if not isinstance(x, dict) or not x.get("execution_id") or not x.get("agent_id"):
            raise AdapterError(f"executions[{i}] lacks execution_id or agent_id")
    exec_ids = [x["execution_id"] for x in raw_execs]
    if len(set(exec_ids)) != len(exec_ids):
        raise AdapterError("duplicate execution_id")
    xmap = {x["execution_id"]: x for x in raw_execs}
    raw_msgs = get(raw, "messages", "run", "no messages", []) or []
    voiced_by = defaultdict(list)  # execution -> its messages whose payload.voice == "llm"
    for m in raw_msgs:
        if (m.get("payload") or {}).get("voice") == "llm" and m.get("sender_execution_id"):
            voiced_by[m["sender_execution_id"]].append(m.get("message_id"))
    completed = {}
    for e, p in by_type.get("LLM_CALL_COMPLETED", []):
        completed.setdefault((e["execution_id"], p.get("index")), []).append(e)
    started = {e["execution_id"]: e for e, _ in by_type.get("AGENT_STARTED", []) if e["execution_id"]}

    executions, calls = [], []
    for x in raw_execs:
        xid = x["execution_id"]
        w = f"executions[execution_id={xid}]"
        lcs = x.get("llm_calls")
        if lcs is None:
            missing(w, "llm_calls", "treated as no model calls")
            lcs = []
        if lcs:
            mech, rule = ("llm_voice", "sent_llm_voiced_message") if voiced_by.get(xid) else ("llm_analysis", "model_calls_without_llm_voiced_message")
        else:
            mech, rule = "deterministic", "no_model_calls"
        rs, ri = x.get("rendered_system"), x.get("rendered_input")
        input_hash = sha((rs or "") + "\n\n" + (ri or "")) if (rs is not None or ri is not None) else None
        call_ids = []
        for j, c in enumerate(lcs):
            idx = c.get("index", j + 1)
            if "index" not in c:
                missing(f"{w}.llm_calls[{j}]", "index", f"position used ({j + 1})")
            cid = f"llm:{xid}:{idx}"
            call_ids.append(cid)
            loc = f"{w}.llm_calls[{j}]"
            ev = completed.get((xid, idx), [])
            if len(ev) != 1:
                missing(loc, "LLM_CALL_COMPLETED event", f"{len(ev)} matching events; order falls back to the execution's seq_end")
            if input_hash is None:
                inp = "absent"
            elif c.get("input_sha256") == input_hash:
                inp = "verified"
            elif len(lcs) > 1:
                inp = "not_recorded_per_call"
            else:
                inp = "mismatch"
            exc, n = c.get("response_excerpt"), c.get("response_chars")
            if c.get("ok") is False or exc is None or not isinstance(n, int):
                out = "unknown"
            elif len(exc) == n:
                out = "complete"
            elif len(exc) < n:
                out = "truncated"
            else:
                out = "unknown"
                missing(loc, "response_chars", f"excerpt ({len(exc)}) is longer than response_chars ({n})")
            calls.append({"id": cid, "execution": xid, "agent": x["agent_id"], "index": idx, "mechanism": mech, "mechanism_rule": rule,
                          "provider": c.get("provider"), "model": c.get("model"), "ok": c.get("ok"), "error": c.get("error"), "duration_ms": c.get("duration_ms"),
                          "input": {"status": inp, "sha256": c.get("input_sha256"), "chars": c.get("input_chars"),
                                    "locator": f"{w}.rendered_system + '\\n\\n' + {w}.rendered_input" if inp == "verified" else None},
                          "output": {"status": out, "response_chars": n, "excerpt_chars": len(exc) if isinstance(exc, str) else None,
                                     "excerpt_sha256": sha(exc) if isinstance(exc, str) else None, "locator": f"{loc}.response_excerpt"},
                          "completed_event": ref(ev[0]) if len(ev) == 1 else None,
                          "order": ev[0]["seq"] if len(ev) == 1 else x.get("seq_end"),
                          "steps": [x.get("seq_start"), ev[0]["seq"] if len(ev) == 1 else x.get("seq_end")],
                          "voiced_messages": list(voiced_by.get(xid, [])) if mech == "llm_voice" else [],
                          "src": {"locator": loc}})
        for k in ("seq_start", "seq_end", "kind", "stage"):
            if x.get(k) is None and not (k == "stage"):
                missing(w, k, "kept as null")
        executions.append({"id": xid, "agent": x["agent_id"], "agent_name": x.get("agent_name"), "role": x.get("role"), "kind": x.get("kind"), "stage": x.get("stage"),
                           "round": x.get("round_id"), "pass": x.get("pass_number"), "seq": [x.get("seq_start"), x.get("seq_end")],
                           "started_at": x.get("started_at"), "completed_at": x.get("completed_at"), "status": x.get("status"), "error": x.get("error"),
                           "mechanism": mech, "mechanism_rule": rule, "model_calls": call_ids, "rendered_input_sha256": input_hash,
                           "rendered_input_chars": len(ri) if isinstance(ri, str) else None,
                           "evidence_in_state": list(x.get("evidence_in_input") or []), "started_event": ref(started.get(xid)), "src": {"locator": w}})
    call_of_exec = {x["id"]: x["model_calls"] for x in executions}
    calls.sort(key=lambda c: (c["order"] is None, c["order"] or 0, c["id"]))

    # ---- messages and their delivery records
    sent_ev = {e["message_id"]: e for e, _ in by_type.get("MESSAGE_SENT", []) if e["message_id"]}
    recv_ev = defaultdict(list)
    for e, p in by_type.get("MESSAGE_RECEIVED", []):
        recv_ev[(e["message_id"], e["actor"], p.get("via"), e["execution_id"])].append(e)
    messages, used_recv = [], set()
    for i, m in enumerate(raw_msgs):
        mid = m.get("message_id")
        if not mid or not isinstance(m.get("seq"), int):
            raise AdapterError(f"messages[{i}] lacks message_id or seq")
        w = f"messages[message_id={mid}]"
        p = m.get("payload") or {}
        if "payload" not in m:
            missing(w, "payload", "voice and position unknown")
        voice = p.get("voice")
        sx = m.get("sender_execution_id")
        text = m.get("message_content")
        if text is None:
            missing(w, "message_content", "content unknown; no delivery can be verified")
        if voice == "llm":
            cands = call_of_exec.get(sx, [])
            prod = {"call": cands[0], "rule": "single_call_execution"} if len(cands) == 1 else {"call": None, "rule": "unresolved", "candidates": cands}
            tm = "llm_voice"
        else:
            prod, tm = None, "deterministic"
        dels = []
        for j, d in enumerate(m.get("deliveries") or []):
            via, dx = d.get("via"), d.get("execution_id")
            x = xmap.get(dx)
            dcalls = call_of_exec.get(dx, [])
            verified = len(dcalls) == 1 and next(c for c in calls if c["id"] == dcalls[0])["input"]["status"] == "verified"
            found, extent = None, None
            if verified and text:
                found, extent, n_chars = _find_in_input(x.get("rendered_input") or "", mid, text)
            if via == "rendered_prompt":
                cls = "rendered_prompt_unverified" if not verified or text is None else ("recorded_delivery" if found else "rendered_prompt_content_not_found")
            elif via in ("inbox_read", "board_read"):
                cls = "code_access" if dx else "code_access_no_execution"
            else:
                cls = "unknown_channel"
            key = (mid, d.get("receiver"), via, dx)
            rev = [e for e in recv_ev.get(key, []) if e["seq"] not in used_recv]
            rev = rev[0] if rev else None
            if rev:
                used_recv.add(rev["seq"])
            dels.append({"receiver": d.get("receiver"), "via": via, "class": cls, "seq": d.get("seq"), "timestamp": d.get("timestamp"),
                         "execution": dx, "call": dcalls[0] if cls == "recorded_delivery" else None,
                         "extent": extent if cls == "recorded_delivery" else None,
                         "delivered_chars": n_chars if cls == "recorded_delivery" else None,
                         "content_in_verified_input": found, "content_extent_in_verified_input": extent,
                         "received_event": ref(rev), "src": {"locator": f"{w}.deliveries[{j}]"}})
        pos = {k: p[k] for k in ("label", "confidence", "position", "abstain") if k in p}
        messages.append({"id": mid, "global_id": m.get("global_message_id"), "round": m.get("round_id"), "seq": m["seq"], "stage": m.get("stage"),
                         "type": m.get("message_type"), "timestamp": m.get("timestamp"), "topic": m.get("topic"), "sender": m.get("sender_agent_id"),
                         "sender_execution": sx, "receivers": list(m.get("receiver_agent_ids") or []), "voice_raw": voice, "text_mechanism": tm, "producer": prod,
                         "content": {"chars": len(text) if isinstance(text, str) else None, "sha256": sha(text) if isinstance(text, str) else None, "locator": f"{w}.message_content"},
                         "evidence_ids": list(m.get("evidence_ids") or []), "hypothesis_ids": list(m.get("related_hypothesis_ids") or []),
                         "parent": m.get("parent_message_id"), "response_to": m.get("response_to_message_id"),
                         "challenge_status": m.get("challenge_status"), "resolution_status": m.get("resolution_status"),
                         "computed_position": dict(pos, origin="framework_computed", locator=f"{w}.payload") if pos else None,
                         "sent_event": ref(sent_ev.get(mid)), "deliveries": dels, "src": {"locator": w}})
    messages.sort(key=lambda m: m["seq"])

    # ---- evidence records, tool calls
    evidence = []
    retrieved = {}
    for e, _ in by_type.get("EVIDENCE_RETRIEVED", []):
        for x in e["evidence_ids"]:
            retrieved.setdefault(x, e)
    tools = []
    derived_by = {}
    for e, p in by_type.get("TOOL_CALLED", []):
        res = p.get("result") or {}
        tid_ = f"tool:{e['seq']}"
        tools.append({"id": tid_, "tool": p.get("tool"), "execution": e["execution_id"], "actor": e["actor"], "evidence_ids": e["evidence_ids"],
                      "derived_id": res.get("derived_id"), "event": ref(e)})
        if res.get("derived_id"):
            derived_by[res["derived_id"]] = tid_
    for i, x in enumerate(get(raw, "evidence_flow", "run", "no evidence records", []) or []):
        xid = x.get("evidence_id")
        if not xid:
            raise AdapterError(f"evidence_flow[{i}] lacks evidence_id")
        evidence.append({"id": xid, "kind": x.get("kind"), "provenance": x.get("provenance"), "dataset": x.get("dataset"), "record_id": x.get("record_id"),
                         "label": x.get("label"), "description": x.get("description"),
                         "retrieval": {k: x.get(f"retrieval_{k}") for k in ("action", "method", "round", "score")},
                         "framework_reported": {"received_by": x.get("received_by"), "in_rendered_input": x.get("in_rendered_input"),
                                                "not_in_rendered_input": x.get("not_in_rendered_input"), "rendered_status": x.get("rendered_status"),
                                                "cited_by": x.get("cited_by"), "verification_status": x.get("verification_status"),
                                                "note": "agent-level values reported by the framework; not per-call delivery and not verified here"},
                         "framework_claims": len(x.get("claims") or []), "retrieved_event": ref(retrieved.get(xid)), "produced_by_tool": derived_by.get(xid),
                         "src": {"locator": f"evidence_flow[evidence_id={xid}]"}})

    # ---- agents: declared ones first, then any other actor in executions, messages, deliveries or events
    declared = raw.get("agents") or {}
    if not declared:
        missing("run", "agents", "agents taken from executions, messages and events")
    first_seen = {}
    for x in executions:
        first_seen.setdefault(x["agent"], x["seq"][0] or 0)
    for m in messages:
        for a in [m["sender"], *(d["receiver"] for d in m["deliveries"])]:
            if a:
                first_seen.setdefault(a, m["seq"])
    for e in events:
        if e["actor"] and e["actor"] not in FRAMEWORK_ACTORS:
            first_seen.setdefault(e["actor"], e["seq"])
    ids = list(declared) + sorted((a for a in first_seen if a not in declared), key=lambda a: first_seen[a])
    # An undeclared id that is only ever an addressee (never a sender, actor, executor or delivery receiver)
    # is an address group (e.g. a broadcast), not an agent: no row is invented for it.
    addressees = sorted({r for m in messages for r in m["receivers"] if r not in ids})
    agents = []
    for a in ids:
        d = declared.get(a) or {}
        xs = [x for x in executions if x["agent"] == a]
        cs = [c for c in calls if c["agent"] == a]
        agents.append({"id": a, "name": d.get("name") or next((x["agent_name"] for x in xs if x["agent_name"]), None),
                       "role": next((x["role"] for x in xs if x["role"]), None), "declared": a in declared,
                       "executions": len(xs), "deterministic_executions": sum(x["mechanism"] == "deterministic" for x in xs),
                       "model_calls": len(cs), "llm_analysis_calls": sum(c["mechanism"] == "llm_analysis" for c in cs),
                       "llm_voice_calls": sum(c["mechanism"] == "llm_voice" for c in cs),
                       "messages_sent": sum(m["sender"] == a for m in messages),
                       "delivery_records": sum(d["receiver"] == a for m in messages for d in m["deliveries"]),
                       "framework_final_label": d.get("final_label"),
                       "src": {"locator": f"agents.{a}"} if a in declared else None})

    # ---- framework-computed positions, disagreements, rounds, final decision
    positions = []
    pa = (raw.get("positions") or {}).get("agents") or {}
    for a, rows in pa.items():
        for i, r in enumerate(rows):
            positions.append({"agent": a, "seq": r.get("seq"), "round": r.get("round_id"), "phase": r.get("phase"), "draft": r.get("draft"),
                              "message_id": r.get("message_id"), "message_type": r.get("message_type"), "label": r.get("label"),
                              "confidence": r.get("confidence"), "position": r.get("position"), "abstain": r.get("abstain"),
                              "moved_by": r.get("moved_by"), "old_label": r.get("old_label"), "origin": "framework_computed",
                              "src": {"locator": f"positions.agents.{a}[{i}]"}})
    positions.sort(key=lambda r: (r["seq"] is None, r["seq"] or 0, r["agent"]))
    joint = [dict({k: r.get(k) for k in ("seq", "round_id", "phase", "message_id", "label", "council_confidence", "converged", "dissent", "joint")},
                  origin="framework_computed", src={"locator": f"positions.joint[{i}]"}) for i, r in enumerate((raw.get("positions") or {}).get("joint") or [])]
    # Overall hypothesis score vectors recorded by the framework (not per agent): HYPOTHESES_SCORED events
    # (payload.hypotheses, or a pair adjustment's payload.before / payload.after), the score list an execution was
    # given (input.scored_hypotheses) and the one it returned (output.extras.scores).  Values are copied, never derived.
    def _vec(items, where):
        out = {}
        for k, it in enumerate(items):
            lab, sc = (it[0], it[1]) if isinstance(it, list) and len(it) == 2 else ((it or {}).get("label"), (it or {}).get("score"))
            if not isinstance(lab, str) or not isinstance(sc, (int, float)) or isinstance(sc, bool) or lab in out:
                missing(f"{where}[{k}]", "label/score", "entry not used")
                continue
            out[lab] = sc
        return out
    hyp_scores = []
    for e, p in by_type.get("HYPOTHESES_SCORED", []):
        parts = [("hypotheses", p["hypotheses"])] if isinstance(p.get("hypotheses"), list) else []
        parts += [(k, [[a, s] for a, s in p[k].items()]) for k in ("before", "after") if isinstance(p.get(k), dict)]
        if not parts:
            missing(e["locator"], "payload.hypotheses", "score event with no score vector")
        for part, items in parts:
            hyp_scores.append({"basis": "event", "part": part, "seq": e["seq"], "event": ref(e), "event_type": e["type"], "execution": e["execution_id"], "actor": e["actor"],
                               "stage": p.get("stage"), "round": p.get("round"), "source": p.get("source"),
                               "scores": _vec(items, f"{e['locator']}.payload.{part}"), "src": {"locator": f"{e['locator']}.payload.{part}"}})
    out_ev = defaultdict(list)
    for e, _ in by_type.get("AGENT_OUTPUT_GENERATED", []):
        out_ev[e["execution_id"]].append(e)
    for x in raw_execs:
        xid = x["execution_id"]
        w = f"executions[execution_id={xid}]"
        sh = (x.get("input") or {}).get("scored_hypotheses")
        os_ = ((x.get("output") or {}).get("extras") or {}).get("scores")
        common = {"execution": xid, "actor": x["agent_id"], "stage": x.get("stage"), "round": x.get("round_id"), "source": None,
                  "execution_finding": {"label": x.get("finding_label"), "confidence": x.get("confidence"), "locator": w}}
        if isinstance(sh, list):
            st = started.get(xid)
            hyp_scores.append(dict(common, basis="execution_input", part="input.scored_hypotheses", seq=x.get("seq_start"), event=ref(st), event_type="AGENT_STARTED" if st else None,
                                   scores=_vec(sh, f"{w}.input.scored_hypotheses"), src={"locator": f"{w}.input.scored_hypotheses"}))
        if isinstance(os_, list):
            oe = out_ev.get(xid, [])
            if len(oe) != 1:
                missing(w, "AGENT_OUTPUT_GENERATED", f"{len(oe)} output events; output-score seq taken from seq_end")
            hyp_scores.append(dict(common, basis="execution_output", part="output.extras.scores", seq=oe[0]["seq"] if len(oe) == 1 else x.get("seq_end"),
                                   event=ref(oe[0]) if len(oe) == 1 else None, event_type="AGENT_OUTPUT_GENERATED" if len(oe) == 1 else None,
                                   scores=_vec(os_, f"{w}.output.extras.scores"), src={"locator": f"{w}.output.extras.scores"}))
    for h in hyp_scores:
        h["origin"] = "framework_computed"
    hyp_scores.sort(key=lambda r: (r["seq"] is None, r["seq"] or 0))  # stable: a pair event keeps before, after
    disagreements = [dict(d, src={"locator": f"disagreements[{i}]"}) for i, d in enumerate(raw.get("disagreements") or [])]
    rounds = [{"round": r.get("round_id"), "phase": r.get("phase"), "label": r.get("label"), "messages": [x.get("message_id") for x in r.get("messages") or []],
               "markers": r.get("markers"), "src": {"locator": f"timeline[{i}]"}} for i, r in enumerate(raw.get("timeline") or [])]
    fin = by_type.get("FINAL_SYNTHESIS_GENERATED", [])
    if len(fin) == 1:
        e, p = fin[0]
        summ = (raw.get("summary") or {}).get("final_decision") or {}
        final = {"label": p.get("final_label"), "diagnosis": p.get("final_diagnosis"), "confidence": p.get("confidence"), "review_decision": p.get("review_decision"),
                 "message_id": e["message_id"], "actor": e["actor"], "event": ref(e), "locator": f"{e['locator']}.payload",
                 "equals": {"trace.final_label": trace.get("final_label") == p.get("final_label"), "trace.final_diagnosis": trace.get("final_diagnosis") == p.get("final_diagnosis"),
                            "summary.final_decision.label": summ.get("label") == p.get("final_label")}}
    else:
        final = None
        missing("events", "FINAL_SYNTHESIS_GENERATED", f"{len(fin)} such events; final decision not represented")
    q = next((p.get("query") for e, p in by_type.get("TRACE_STARTED", [])), None)
    qe = next((e for e, _ in by_type.get("TRACE_STARTED", [])), None)

    counts = {"agents": len(agents), "agents_without_model_calls": sum(a["model_calls"] == 0 for a in agents), "executions": len(executions),
              "deterministic_executions": sum(x["mechanism"] == "deterministic" for x in executions), "model_calls": len(calls),
              "model_calls_by_mechanism": dict(Counter(c["mechanism"] for c in calls)), "model_input": dict(Counter(c["input"]["status"] for c in calls)),
              "model_output": dict(Counter(c["output"]["status"] for c in calls)), "messages": len(messages),
              "messages_by_text_mechanism": dict(Counter(m["text_mechanism"] for m in messages)), "messages_by_type": dict(Counter(m["type"] for m in messages)),
              "delivery_records": sum(len(m["deliveries"]) for m in messages),
              "deliveries_by_class": dict(Counter(d["class"] for m in messages for d in m["deliveries"])),
              "recorded_deliveries_by_extent": dict(Counter(d["extent"] for m in messages for d in m["deliveries"] if d["class"] == "recorded_delivery")),
              "evidence_records": len(evidence), "tool_calls": len(tools), "positions": len(positions), "joint_positions": len(joint), "hypothesis_score_records": len(hyp_scores),
              "disagreements": len(disagreements), "rounds": len(rounds), "events": len(events), "events_by_type": dict(Counter(e["type"] for e in events))}
    return {
        "format": STRUCTURE,
        "note": "Local research display data. Not agenttrace.semantic/0.3; holds no claims, propositions, states or semantic links.",
        "source": dict(source, export_format=raw.get("export_format"), raw_schema=raw.get("schema_version")),
        "run": {"trace_id": tid, "run_id": trace.get("run_id"), "status": trace.get("status"), "started_at": trace.get("started_at"),
                "completed_at": trace.get("completed_at"), "dataset_type": trace.get("dataset_type"), "llm_provider": trace.get("llm_provider"),
                "llm_model": trace.get("llm_model"), "council_llm_model": (trace.get("config") or {}).get("council_llm_model"), "config": trace.get("config"),
                "query": {"text": q, "chars": len(q) if isinstance(q, str) else None, "sha256": sha(q) if isinstance(q, str) else None,
                          "locator": f"{qe['locator']}.payload.query" if qe else None, "event": ref(qe)},
                "error": trace.get("error"), "src": {"locator": "trace"}},
        "agents": agents, "address_groups": addressees, "framework_actors": sorted({e["actor"] for e in events if e["actor"] in FRAMEWORK_ACTORS}),
        "executions": executions, "model_calls": calls, "messages": messages, "evidence": evidence, "tool_calls": tools,
        "positions": positions, "joint_positions": joint, "hypothesis_scores": hyp_scores, "disagreements": disagreements, "rounds": rounds, "final_decision": final,
        "events": events, "counts": counts, "ambiguities": amb,
        "order_caveat": "Order is the framework-assigned event seq (observation order only); it implies no causation.",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--archive", type=Path)
    ap.add_argument("--run")
    ap.add_argument("--input", type=Path)
    ap.add_argument("--list", action="store_true", help="list runs in the archive")
    args = ap.parse_args(argv)
    try:
        if args.list:
            print("\n".join(m.split("/")[0] for m in list_runs(args.archive)))
            return 0
        raw, src = load_run(args.archive, args.run, args.input)
        rec = adapt(raw, src)
    except AdapterError as e:
        print(f"STOPPED: {e}", file=sys.stderr)
        return 1
    print(json.dumps({"run": rec["run"]["trace_id"], "counts": rec["counts"], "ambiguities": len(rec["ambiguities"])}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
