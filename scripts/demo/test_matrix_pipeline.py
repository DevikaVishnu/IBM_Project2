"""Deterministic tests for the trace-to-matrix pipeline (build_matrix.py + validate_matrix.py).

Run from the AP root with the AssetOpsBench worktree interpreter:

    env -u OTEL_TRACES_FILE PYTHONPATH=../AssetOpsBench-agenttrace-spec/src \
        ../AssetOpsBench-agenttrace-spec/.venv/bin/python -m pytest scripts/demo/test_matrix_pipeline.py -q -p no:cacheprovider

Real traces are read-only and re-hashed after the tests.  SYNTHETIC records are derived in memory from
real ones (renamed copies, removed or altered records); they test pipeline behaviour only and are never
written to the demo data or shown as agent behaviour.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
AP = HERE.parents[1]
sys.path.insert(0, str(HERE))
import build_matrix as bm  # noqa: E402
from validate_matrix import validate  # noqa: E402

from agent.deep_agent import _semantic_adapter as adapter, _semantic_locator as locator  # noqa: E402
from agent.deep_agent._semantic_verify import verify  # noqa: E402

RUNS = AP / "data/assetopsbench/runs"
WT_FIX = Path(adapter.__file__).resolve().parent / "tests/fixtures"
TRACES = {
    "sc3": "aob-sc3-sonnet5-deep-spec-B-20261014.instrumented.json",
    "621": "aob-621-sonnet5-deep-fileobs-20261013.instrumented.json",
    "620f": "aob-620-sonnet5-deep-fileobs-20261013.instrumented.json",
    "607": "aob-607-sonnet5-deep-20261005.instrumented.json",
}
FIXTURES = {
    "sc3": WT_FIX / "agenttrace_semantic_0_3/aob-sc3-B.semantic.json",
    "621": WT_FIX / "agenttrace_semantic_0_3/aob-621.semantic.json",
    "620f": WT_FIX / "agenttrace_compare_0_1/aob-620-compare.trace.json",
}
pytestmark = pytest.mark.skipif(not all((RUNS / t).exists() for t in TRACES.values()), reason="local raw traces not present")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest.fixture(scope="module")
def raw():
    out, before = {}, {}
    for k, name in TRACES.items():
        data = (RUNS / name).read_bytes()
        before[k] = _sha(data)
        out[k] = (json.loads(data), data)
    yield out
    for k, name in TRACES.items():
        assert _sha((RUNS / name).read_bytes()) == before[k], f"raw trace {name} changed during the tests"


def _build(rec, data, run_id="t", fixture=None, **kw):
    return bm.build(rec, data, run_id, "trace.json", adapter=kw.get("adapter", adapter), verify=kw.get("verify", verify), locator=locator,
                    fixture=fixture, fixture_display="fixture.json" if fixture else None,
                    fixture_bytes=json.dumps(fixture).encode() if fixture else None)


def _ok(rec, data, run_id="t", fixture=None):
    m = _build(rec, data, run_id, fixture)
    body = bm.canonical(m)
    problems = validate(body, rec, data, fixture=fixture)
    assert problems == [], problems
    return m, body


def _bytes(rec) -> bytes:
    return json.dumps(rec).encode()


# --- real traces --------------------------------------------------------------------------------

@pytest.mark.parametrize("key", ["sc3", "621", "620f", "607"])
def test_real_trace_builds_and_validates(key, raw):
    rec, data = raw[key]
    fx = json.loads(FIXTURES[key].read_bytes()) if key in FIXTURES else None
    m, _ = _ok(rec, data, f"run-{key}", fx)
    assert [r["agent_id"] for r in m["rows"]] == [a["agent_id"] for a in rec["agents"]]
    assert m["semantic"] == {"claims_extracted": False, "claims": 0, "propositions": 0, "states": 0}
    if fx is not None:
        want = [l for l in fx.get("semantic", fx)["links"] if l["relation"] == "delivers"]
        assert len(m["fixture_links"]) == len(want)


def test_sc3_shape(raw):
    m, _ = _ok(*raw["sc3"], "sc3", json.loads(FIXTURES["sc3"].read_bytes()))
    assert m["counts"]["per_row"] == {"agent:root": 14, "agent:sub-1": 56, "$unresolved": 1}
    unresolved = [c for c in m["columns"] if c["row"] == "$unresolved"]
    assert [c["id"] for c in unresolved] == ["ev:llm:383"]
    assert unresolved[0]["origin"]["candidates"] == ["agent:sub-1", "framework:deepagents", "$absent"]
    assert unresolved[0]["delivers"] == [] and unresolved[0]["first_delivered_here"] == []
    issuing = [c for c in m["columns"] if c["issued_delegations"]]
    receiving = [c for c in m["columns"] if any(t in c["delegation_input"] for t, _ in c["first_delivered_here"])]
    assert [c["id"] for c in issuing] == ["ev:llm:92"] and [c["id"] for c in receiving] == ["ev:llm:96"]
    assert m["run"]["status"] == "error" and "traceback" not in json.dumps(m["run"]["error"])


def test_no_telemetry_run_has_no_deliveries_and_unresolved_calls(raw):
    m, _ = _ok(*raw["607"], "607")
    assert m["telemetry"]["delivery"] == "absent"
    assert all(c["delivers"] == [] for c in m["columns"]) and m["counts"]["delivers"] == 0
    assert all(c["row"] == "$unresolved" for c in m["columns"])  # no rendered input: origin not established


@pytest.mark.parametrize("key", ["sc3", "607"])
def test_byte_identical_rebuild(key, raw):
    rec, data = raw[key]
    fx = json.loads(FIXTURES[key].read_bytes()) if key in FIXTURES else None
    assert bm.canonical(_build(rec, data, "x", fx)) == bm.canonical(_build(copy.deepcopy(rec), data, "x", fx))


def test_manifest_is_deterministic(tmp_path, raw):
    rec, data = raw["607"]
    m, body = _ok(rec, data, "a")
    for order in (["a", "b"], ["b", "a"]):
        d = tmp_path / "-".join(order)
        d.mkdir()
        for rid in order:
            bm.update_manifest(d, rid, f"{rid}.matrix.json", body, m)
        assert (d / "index.json").read_text() == (tmp_path / "a-b" / "index.json").read_text()


# --- SYNTHETIC records derived from real ones ------------------------------------------------------

def _rename(rec: dict, agent_map: dict, offset: int, tag: str) -> dict:
    """Rename agent, tool-call and LangChain ids and shift seqs (same approach as the adapter tests'
    _rename), so a copy can sit beside the original as a separate agent."""
    rec = copy.deepcopy(rec)
    calls: dict = {}
    old_ids = {e["tool_call_id"] for e in rec["events"] if e.get("tool_call_id")}

    def call(x):
        return None if x is None else calls.setdefault(x, f"{tag}call{len(calls)}")

    def text(x):
        if not isinstance(x, str):
            return x
        for old in sorted(old_ids, key=len, reverse=True):
            x = x.replace(old, call(old))
        return x

    for e in rec["events"]:
        e["seq"] += offset
        if e.get("agent_id") is not None:
            e["agent_id"] = agent_map[e["agent_id"]]
        for k in ("path", "result_path"):
            if k in e:
                e[k] = text(e[k])
        if e.get("type") == "tool_result_committed" and "content" in e:
            e["content"] = text(e["content"])
            e["sha256"] = hashlib.sha256(e["content"].encode()).hexdigest()
        for k in ("tool_call_id", "delegation_id"):
            if k in e:
                e[k] = call(e[k])
        for k in ("lc_run_id", "lc_parent_run_id"):
            if e.get(k):
                e[k] = f"{tag}-{e[k]}"
        for tc in (e.get("message") or {}).get("tool_calls") or []:
            tc["id"] = call(tc["id"])
        for batch in e.get("input_batches") or []:
            for msg in batch:
                if msg.get("role") == "tool" and isinstance(msg.get("content"), str) and msg["content"].startswith("Tool result too large"):
                    msg["content"] = text(msg["content"])
                if "tool_call_id" in msg:
                    msg["tool_call_id"] = call(msg["tool_call_id"])
                for tc in msg.get("tool_calls") or []:
                    tc["id"] = call(tc["id"])
    return rec


def _three_agents(rec: dict) -> dict:
    """SYNTHETIC: the single-agent 620-fileobs run plus two renamed copies as subagents of root."""
    out = copy.deepcopy(rec)
    for i, name in enumerate(["helper-a", "helper-b"], start=1):
        cp = _rename(rec, {"root": name}, 1000 * i, f"s{i}")
        out["agents"].append({"agent_id": name, "name": f"synthetic-{name}", "kind": "subagent", "parent_agent_id": "root",
                              "delegation_id": None, "status": "ok"})
        out["events"] += cp["events"]
    out["events"].sort(key=lambda e: e["seq"])
    return out


def test_synthetic_additional_agents(raw):
    rec = _three_agents(raw["620f"][0])
    m, _ = _ok(rec, _bytes(rec), "synthetic-3")
    assert [r["id"] for r in m["rows"]] == ["agent:root", "agent:helper-a", "agent:helper-b"]
    assert m["counts"]["per_row"]["agent:helper-a"] == m["counts"]["per_row"]["agent:root"] == 7


def test_synthetic_no_model_calls(raw):
    rec = copy.deepcopy(raw["607"][0])
    rec["events"] = [e for e in rec["events"] if e["type"] in ("agent_start", "agent_end")]
    m, _ = _ok(rec, _bytes(rec), "synthetic-empty")
    assert m["columns"] == [] and m["counts"]["model_calls"] == 0 and m["rows"][0]["agent_id"] == "root"


def _break_first_tool_message(rec: dict, after_seq: int = 0) -> int:
    target = next(e for e in rec["events"] if e["type"] == "llm_start" and e["seq"] > after_seq and e.get("input_batches")
                  and any(msg.get("role") == "tool" for msg in e["input_batches"][0]))
    next(msg for msg in target["input_batches"][0] if msg.get("role") == "tool")["tool_call_id"] = "malformed-id"
    return target["seq"]


def test_synthetic_malformed_reference_with_offered_tools_skips_only_that_join(raw):
    """sc3 calls carry offered_tools: origin holds, the broken tool message is surfaced as an unjoined skip."""
    rec = copy.deepcopy(raw["sc3"][0])
    full, _ = _ok(*raw["sc3"], "sc3")
    seq = _break_first_tool_message(rec, after_seq=100)
    m, _ = _ok(rec, _bytes(rec), "synthetic-malformed-sc3")
    assert m["counts"]["delivers"] == full["counts"]["delivers"] - 1
    assert any(s["kind"] == "rendered_tool_message_unjoined" and seq in s["seq"] for s in m["skipped"])
    assert m["counts"]["per_row"] == full["counts"]["per_row"]


def test_synthetic_malformed_reference_without_offered_tools_fails_closed(raw):
    """620-fileobs has no offered_tools: the broken message breaks the agent-loop continuity check, so that call
    and every later call of the agent lose their origin (unresolved) and source no deliveries."""
    rec = copy.deepcopy(raw["620f"][0])
    seq = _break_first_tool_message(rec)
    m, _ = _ok(rec, _bytes(rec), "synthetic-malformed-620f")
    later = [c for c in m["columns"] if c["start_seq"] >= seq]
    assert later and all(c["row"] == "$unresolved" and c["origin_rule"] == "agent_loop_signature_failed" and c["delivers"] == [] for c in later)
    assert all(c["row"] == "agent:root" for c in m["columns"] if c["start_seq"] < seq)


def test_synthetic_unknown_origin_stays_unresolved(raw):
    rec = copy.deepcopy(raw["620f"][0])
    start = next(e for e in rec["events"] if e["type"] == "llm_start" and e["seq"] > 1)
    for e in rec["events"]:
        if e.get("lc_run_id") == start["lc_run_id"] and e["type"] in ("llm_start", "llm_end"):
            e["agent_id"] = "ghost"
    m, _ = _ok(rec, _bytes(rec), "synthetic-ghost")
    col = next(c for c in m["columns"] if c["start_seq"] == start["seq"])
    assert col["row"] == "$unresolved" and "agent:ghost" not in [r["id"] for r in m["rows"]]
    assert col["origin_rule"] == "agent_id_unattributed"


# --- rejection and validator independence ---------------------------------------------------------

def test_invalid_adapter_output_is_rejected(raw):
    rec, data = raw["620f"]

    class Tampering:
        @staticmethod
        def adapt(*a, **k):
            doc = adapter.adapt(*a, **k)
            doc["semantic"]["claims"].append({"id": "clm:x"})
            return doc
    with pytest.raises(bm.Rejected) as exc:
        _build(rec, data, adapter=Tampering)
    assert exc.value.code == 2 and exc.value.errors


def test_unknown_raw_schema_is_rejected(raw):
    rec = copy.deepcopy(raw["607"][0])
    rec["schema"] = "something-else/9"
    with pytest.raises(bm.Rejected) as exc:
        _build(rec, _bytes(rec))
    assert exc.value.code == 2


def test_fixture_for_another_trace_is_rejected(raw):
    with pytest.raises(bm.Rejected) as exc:
        _build(*raw["621"], fixture=json.loads(FIXTURES["sc3"].read_bytes()))
    assert exc.value.code == 3


def test_bad_run_id_is_rejected(raw):
    with pytest.raises(bm.Rejected):
        _build(*raw["607"], run_id="../escape")


def _tamper(m: dict) -> list:
    def drop_col(x): x["columns"].pop()
    def move_row(x): next(c for c in x["columns"] if c["row"] != "$unresolved")["row"] = "agent:nobody"
    def add_deliver(x): next(c for c in x["columns"] if c["delivers"])["delivers"].append("evi:fake")
    def resolve_unresolved(x):
        c = next(c for c in x["columns"] if c["row"] == "$unresolved"); c["row"] = "agent:sub-1"
    def bad_excerpt(x):
        k = next(iter(x["evidence"])); x["evidence"][k]["excerpt"] = "edited"
    def bad_locator(x):
        k = next(iter(x["evidence"])); x["evidence"][k]["raw_ref"]["locator"] = "events[seq=999999].output"
    def add_claim(x): x["claims"] = [{"id": "clm:x"}]
    def claims_flag(x): x["semantic"]["claims_extracted"] = True
    def add_row(x): x["rows"].append({"id": "agent:iot"})
    def counts(x): x["counts"]["model_calls"] += 1
    def first_here(x): next(c for c in x["columns"] if c["first_delivered_here"])["first_delivered_here"].pop()
    def home(x): x["run"]["model"] = "/Users/someone/x"
    return [drop_col, move_row, add_deliver, resolve_unresolved, bad_excerpt, bad_locator, add_claim, claims_flag, add_row, counts, first_here, home]


@pytest.mark.parametrize("i", range(12))
def test_validator_rejects_tampered_matrix(i, raw):
    rec, data = raw["sc3"]
    fx = json.loads(FIXTURES["sc3"].read_bytes())
    m, _ = _ok(rec, data, "sc3", fx)
    t = copy.deepcopy(m)
    _tamper(t)[i](t)
    assert validate(bm.canonical(t), rec, data, fixture=fx), _tamper(m)[i].__name__


def test_validator_rejects_non_canonical_bytes(raw):
    rec, data = raw["607"]
    m, body = _ok(rec, data, "607")
    assert validate(json.dumps(m, indent=1), rec, data)


def test_validator_shares_no_code_with_builder():
    src = (HERE / "validate_matrix.py").read_text()
    assert "build_matrix" not in src.replace("build_matrix.py", "")
