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
    assert b["skeleton"]["counts"]["llm_calls"] == 12 and b["skeleton"]["counts"]["reconstructed_llm_calls"] == 7
    nd = b["skeleton"]["delivery"]["not_delivered"][0]
    assert nd["item"] == "gk:gui-config" and nd["value"] == "NOT_DELIVERED" and "COMPLETE" in nd["coverage"]
    r3 = b["claims"][0]
    assert r3["state"]["value"] == "FALSE" and r3["o3"]["comparison"] == "UNKNOWN"
    assert {p["id"] for p in b["propositions"]} >= {"prop:gk:G1", "prop:gk:G4"}


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
