"""Tests for the Belief Explorer bundle pipeline.

    WT=../AssetOpsBench-agenttrace-spec
    env -u OTEL_TRACES_FILE PYTHONPATH=$WT/src $WT/.venv/bin/python -m pytest scripts/explorer/test_explorer_bundles.py -q -p no:cacheprovider

Tests that need the local bundles, raw traces or the worktree are skipped when those are absent.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
AP_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from validate_bundle import validate  # noqa: E402

DATA = AP_ROOT / "src/explorer/data"
TRACES = ["aob-621", "aob-sc3-B", "gomoku"]
EXPECTED = {"aob-621": {"entities": 21, "events": 61, "evidence": 127, "delivers": 1454},
            "aob-sc3-B": {"entities": 24, "events": 159, "evidence": 268, "delivers": 4713}}


def load(tid):
    p = DATA / f"{tid}.bundle.json"
    if not p.exists():
        pytest.skip("local bundles not built (see docs/DATA.md)")
    return json.loads(p.read_text(encoding="utf-8"))


def worktree():
    try:
        from agent.deep_agent import _semantic_adapter  # noqa: F401
    except ImportError:
        pytest.skip("worktree src not on PYTHONPATH")
    import build_bundle
    return build_bundle


# --- built bundles -----------------------------------------------------------------------------


@pytest.mark.parametrize("tid", TRACES)
def test_bundle_validates(tid):
    assert validate(load(tid)) == []


def test_manifest_sha_matches():
    man = DATA / "index.json"
    if not man.exists():
        pytest.skip("no manifest")
    m = json.loads(man.read_text(encoding="utf-8"))
    assert [b["trace_id"] for b in m["bundles"]] == TRACES
    for b in m["bundles"]:
        assert hashlib.sha256((DATA / b["file"]).read_bytes()).hexdigest() == b["sha256"]


@pytest.mark.parametrize("tid", ["aob-621", "aob-sc3-B"])
def test_adapter_counts_recorded(tid):
    b = load(tid)
    assert b["checks"]["adapter_counts"] == EXPECTED[tid]
    assert b["checks"]["verifier_errors"] == 0


def test_621_chain():
    b = load("aob-621")
    assert b["trace"]["kind"] == "single-agent" and len(b["matrix"]["rows"]) == 1 and b["matrix"]["note"]
    by = {c["id"]: c for c in b["claims"]}
    june = by["clm:621:june10-sequence"]
    assert june["o3"]["comparison"] == "AGREES" and june["o3"]["fixture_expected"] == "AGREES"
    assert june["links"][0]["evidence"] == "evi:tool_result:123" and june["links"][0]["delivery"]["value"] == "DELIVERED"
    assert by["clm:621:mean-stddev"]["o3"]["status"] == "rule-dependent"
    assert by["clm:621:sensor-fault"]["state"]["value"] == "UNCERTAIN" and not by["clm:621:sensor-fault"]["links"]
    for cid in ("clm:621:readings", "clm:621:tonnage-range", "clm:621:pct-loaded-peak", "clm:621:no-prior-wo"):
        assert by[cid]["o3"]["comparison"] == "AGREES"
    assert [n["label"] for n in b["non_claims"]] == ["Yes, I'd open a work order"]
    assert all(c["event"] == "ev:llm:157" and c["step"] == 158 for c in b["claims"])


def test_sc3_facts():
    b = load("aob-sc3-B")
    by = {c["id"]: c for c in b["claims"]}
    s = by["clm:sc3:page-sum"]
    assert s["speaker"] == "$unresolved" and s["o3"]["status"] == "not computable" and s["o3"]["hand_comparison"] == "DIFFERS"
    # UNKNOWN or UNRESOLVED delivery is never presented as DELIVERED.
    assert all(l["delivery"]["value"] == "UNRESOLVED" for c in b["claims"] for l in c["links"])
    flags = {f["id"]: f for f in b["flags"]}
    assert "40 helper calls" in flags["flag:sc3:error-158"]["computed"][0]["text"]
    assert "51 helper calls (steps 96–378)" in flags["flag:sc3:description-dropped"]["computed"][0]["text"]
    assert any(e["from"] == "ev:llm:92" and e["to"] == "ev:llm:96" for e in b["matrix"]["edges"])
    assert any(r["id"] == "$unresolved" for r in b["matrix"]["rows"])
    tool = next(f for f in b["facts"] if f["id"] == "fact:tool-results")
    assert tool["origin"] == "computed" and tool["data"]["total"] == 82 and tool["data"]["reached_next_call"] == 75
    assert tool["data"]["reached_as_substitute"] == 6 and tool["data"]["no_later_call"] == [414] and tool["data"]["lost"] == []
    assert "No tool result was lost within an agent; 6 reached the model only as substitutes." in tool["text"]
    assert not any("83 tool" in f["text"] or "all 83" in f["text"] for f in b["facts"])
    handoff = next(f for f in b["facts"] if f["id"] == "fact:handoff")
    assert '"placeholder"' in handoff["handoff"]["observed"][0]["text"]


def test_gomoku_skeleton():
    b = load("gomoku")
    assert b["matrix"]["origin"] == "hand-reconstructed" and b["matrix"]["source_contract"] is None
    # 13 usage records in the log; 12 of them open with a logged [Start Chat] input (the 12 calls of §14.2); 7 are §14's own events.
    counts = b["skeleton"]["counts"]
    assert counts["llm_calls"] == 13 and counts["start_chat_calls"] == 12 and counts["unlogged_input_calls"] == 1 and counts["reconstructed_llm_calls"] == 7
    nd = b["skeleton"]["delivery"]["not_delivered"][0]
    assert nd["item"] == "gk:gui-config" and nd["value"] == "NOT_DELIVERED" and "COMPLETE" in nd["coverage"]
    r3 = b["claims"][0]
    assert r3["state"]["value"] == "FALSE" and r3["o3"]["comparison"] == "UNKNOWN"
    assert {p["id"] for p in b["propositions"]} >= {"prop:gk:G1", "prop:gk:G4"}


def test_gomoku_full_history():
    b = load("gomoku")
    mx = b["matrix"]
    rows = {r["id"]: r for r in mx["rows"]}
    assert set(rows) == {"role:ceo", "role:cpo", "role:cto", "role:programmer", "role:reviewer", "role:counselor", "role:test-gate"}
    per_row = {rid: sum(1 for c in mx["columns"] if c["row"] == rid) for rid in rows}
    assert per_row == {"role:ceo": 2, "role:cpo": 2, "role:cto": 1, "role:programmer": 5, "role:reviewer": 3, "role:counselor": 0, "role:test-gate": 1}
    assert not any(c["row"] in ("$not_reconstructed", "$unresolved") for c in mx["columns"])
    # Roles without annotated claims say so; only the Code Reviewer holds the annotated claim.
    assert all(("claims not annotated" in r["sub"]) == (rid not in ("role:reviewer", "role:test-gate")) for rid, r in rows.items())
    # The call with no logged input has delivery UNKNOWN, not zero.
    unlogged = next(c for c in mx["columns"] if c["id"] == "gk:call:110")
    assert unlogged["delivers"] is None and unlogged["first"] is None and "input not logged" in unlogged["phase"]
    # §14's handoffs are kept; every handoff joins two different rows and reaches a role the item had not reached before.
    edges = {(e["from"], e["to"]) for e in mx["edges"]}
    assert {("gk:coding", "gk:r1"), ("gk:r1", "gk:m1"), ("gk:m1", "gk:r2"), ("gk:r2", "gk:m2"), ("gk:m2", "gk:r3"), ("gk:r3", "gk:m3")} <= edges
    assert {("gk:m3", "gk:call:2677"), ("gk:m3", "gk:call:2901"), ("gk:call:2505", "gk:call:2677"), ("gk:call:184", "gk:coding")} <= edges
    col = {c["id"]: c for c in mx["columns"]}
    assert all(col[f]["row"] != col[t]["row"] for f, t in edges)
    assert not any(t == "gk:call:110" or f == "gk:call:67" and t == "gk:call:110" for f, t in edges)
    # The test gate stays a check, not an LLM call; framework, config and test records are skeleton events only.
    kinds = {e["id"]: e["kind"] for e in b["skeleton"]["events"]}
    assert kinds["gk:test"] == "check" and kinds["gk:test:2467"] == "test_output" and kinds["gk:cfg:23"] == "config"
    assert not ({c["id"] for c in mx["columns"]} & {i for i, k in kinds.items() if k in ("framework_event", "config", "test_output")})
    assert next(f for f in b["facts"] if f["id"] == "fact:calls")["discrepancy"] is True


# --- validator: missing layers and violations --------------------------------------------------


def minimal():
    return {"contract": "agenttrace-explorer-bundle/0.1", "trace": {"id": "x", "label": "x", "kind": "single-agent"},
            "honesty": {"annotations": "Not annotated", "skeleton": "", "rules": []}, "provenance": {},
            "layers": {k: False for k in ("skeleton", "matrix", "claims", "evidence", "delivery", "o3", "flags")},
            "skeleton": None, "matrix": None, "evidence": {}, "propositions": [], "claims": [], "non_claims": [], "flags": [], "facts": []}


def test_missing_layers_are_valid():
    assert validate(minimal()) == []


@pytest.mark.parametrize("tid", TRACES)
def test_stripped_layers_still_valid(tid):
    b = copy.deepcopy(load(tid))
    b["claims"], b["propositions"], b["non_claims"], b["flags"] = [], [], [], []
    b.pop("walkthrough", None)
    b["matrix"]["overlays"] = []
    b["layers"].update(claims=False, flags=False, o3=False)
    assert validate(b) == []
    b["matrix"] = None
    b["layers"]["matrix"] = False
    assert validate(b) == []


def test_validator_rejects_violations():
    b = load("aob-621")
    bad = copy.deepcopy(b)
    bad["matrix"]["claims"] = []
    assert any("claim-free" in p for p in validate(bad))
    bad = copy.deepcopy(b)
    del bad["claims"][0]["origin"]
    assert any("origin" in p for p in validate(bad))
    bad = copy.deepcopy(b)
    bad["claims"][0]["links"][0]["delivery"]["value"] = "NOT_DELIVERED"
    assert any("NOT_DELIVERED" in p for p in validate(bad))
    bad = copy.deepcopy(b)
    bad["matrix"]["overlays"][0]["ref"] = "clm:nope"
    assert any("ref" in p for p in validate(bad))
    bad = copy.deepcopy(b)
    bad["claims"][0]["proposition"] = "prop:nope"
    assert any("proposition" in p for p in validate(bad))
    bad = copy.deepcopy(b)
    bad["provenance"]["raw_trace"] = "/Users/someone/x.json"
    assert any("home" in p for p in validate(bad))


# --- builder (needs the worktree and local traces) ----------------------------------------------


def test_rebuild_is_byte_identical():
    bb = worktree()
    from agent.deep_agent import _semantic_compare as compare
    from build_matrix import canonical
    assert canonical(bb.build_gomoku(compare)) == (DATA / "gomoku.bundle.json").read_text(encoding="utf-8")


def test_builder_stops_on_count_mismatch(monkeypatch):
    bb = worktree()
    from agent.deep_agent import _semantic_adapter as adapter, _semantic_compare as compare, _semantic_locator as locator
    from agent.deep_agent._semantic_verify import verify
    cfg = copy.deepcopy(bb.AOB["aob-621"])
    cfg["expected"]["delivers"] += 1
    if not (AP_ROOT / cfg["raw"]).exists():
        pytest.skip("raw trace absent")
    with pytest.raises(bb.Mismatch, match="adapter counts"):
        bb.build_aob("aob-621", cfg, AP_ROOT.parent / "AssetOpsBench-agenttrace-spec", (adapter, verify, locator, compare))


def test_builder_stops_on_annotation_mismatch(tmp_path, monkeypatch):
    bb = worktree()
    from agent.deep_agent import _semantic_adapter as adapter, _semantic_compare as compare, _semantic_locator as locator
    from agent.deep_agent._semantic_verify import verify
    src = AP_ROOT / "src/explorer/annotations/aob-621.json"
    if not src.exists() or not (AP_ROOT / bb.AOB["aob-621"]["raw"]).exists():
        pytest.skip("annotation or raw trace absent")
    ann = json.loads(src.read_text(encoding="utf-8"))
    ann["claims"][0]["links"][0]["contains"] = ["\"count\": 2877"]
    (tmp_path / "aob-621.json").write_text(json.dumps(ann), encoding="utf-8")
    monkeypatch.setattr(bb, "ANN_DIR", tmp_path)
    with pytest.raises(bb.Mismatch, match="2877"):
        bb.build_aob("aob-621", bb.AOB["aob-621"], AP_ROOT.parent / "AssetOpsBench-agenttrace-spec", (adapter, verify, locator, compare))


# --- "How it's built" walkthrough ---------------------------------------------------------------


def test_walkthrough_matches_bundle():
    b = load("aob-621")
    w = b["walkthrough"]
    claim = next(c for c in b["claims"] if c["id"] == w["claim"])
    ev = b["evidence"][w["evidence"]]
    sk = {e["id"]: e for e in b["skeleton"]["events"]}
    # Stage 1: records run from the tool call to the first receiving model call.
    assert w["raw"]["steps"] == [sk[w["tool_event"]]["steps"][0], sk[w["first_receiver"]]["steps"][0]]
    assert [r["seq"] for r in w["raw"]["records"]] == list(range(w["raw"]["steps"][0], w["raw"]["steps"][1] + 1))
    end = next(r for r in w["raw"]["records"] if r["type"] == "tool_end")
    assert end["output_size"] == ev["size"] and ev["sha256"].startswith(end["output_sha256_prefix"])
    assert not any(k in r for r in w["raw"]["records"] for k in ("output", "input_batches", "message", "args"))  # metadata only
    # Stage 2: delivers links are the claim's evidence, byte-identical, and include the claiming call.
    events = [d["event"] for d in w["adapter"]["delivers"]]
    assert w["first_receiver"] == events[0] and claim["event"] in events and all(d["byte_identical"] for d in w["adapter"]["delivers"])
    assert w["adapter"]["verifier_errors"] == b["checks"]["verifier_errors"] == 0
    # Stage 3: the hand-annotated link is the evidence item followed here.
    assert w["evidence"] in [l["evidence"] for l in claim["links"]]
    # Stage 4: O2 at the claiming call equals the claim chain's delivery; O3 is the claim's own result.
    o2 = {o["event"]: o["value"] for o in w["comparator"]["o2"]}
    assert o2[claim["event"]] == next(l for l in claim["links"] if l["evidence"] == w["evidence"])["delivery"]["value"] == "DELIVERED"
    assert claim["o3"]["comparison"] == "AGREES" and claim["o3"]["direct"] == "TRUE" and claim["o3"]["delivered_direct"] == "TRUE"
    # Stage 6: the claim has a marker in the matrix at its call.
    assert any(o["ref"] == claim["id"] and o["column"] == claim["event"] for o in b["matrix"]["overlays"])
    assert "Gomoku skeleton is hand-reconstructed" in w["note"]
    for tid in ("aob-sc3-B", "gomoku"):
        assert "walkthrough" not in load(tid)


def test_walkthrough_component_has_no_trace_values():
    """The component must read every trace value from the bundle."""
    b = load("aob-621")
    w = b["walkthrough"]
    ev = b["evidence"][w["evidence"]]
    claim = next(c for c in b["claims"] if c["id"] == w["claim"])
    src = (AP_ROOT / "src/explorer/WalkthroughPanel.jsx").read_text(encoding="utf-8")
    values = {str(ev["size"]), f"{ev['size']:,}", ev["sha256"][:8], w["evidence"], w["claim"], w["tool_event"], w["first_receiver"], claim["event"],
              str(b["skeleton"]["counts"]["delivers"]), f"{b['skeleton']['counts']['delivers']:,}", str(b["skeleton"]["counts"]["events"]),
              str(b["skeleton"]["counts"]["evidence"]), str(claim["step"]), str(w["raw"]["records"][0]["args.offset"]), "June 10", "AGREES"}
    values |= {str(r["seq"]) for r in w["raw"]["records"]} | {str(d["message_index"]) for d in w["adapter"]["delivers"]}
    found = sorted(x for x in values if re_word(x).search(src))
    assert not found, f"hard-coded trace values in WalkthroughPanel.jsx: {found}"


def re_word(x):
    import re
    return re.compile(rf"(?<![\w.]){re.escape(x)}(?![\w])")
