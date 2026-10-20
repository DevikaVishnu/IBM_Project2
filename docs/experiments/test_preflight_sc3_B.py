"""Deterministic tests of the §14.8 post-run classification in preflight_sc3_B.

No model, Docker, network or real run output: every file is written under tmp_path,
the guard summaries come from the real BudgetGuard, and the isolation/DB queries
are replaced by fixtures.  Run with the worktree venv:

    cd AssetOpsBench-agenttrace-spec
    env -u OTEL_TRACES_FILE .venv/bin/python -m pytest \
        ../AP/docs/experiments/test_preflight_sc3_B.py -q -p no:cacheprovider
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import launch_sc3_B as launch  # noqa: E402
import preflight_sc3_B as pre  # noqa: E402
from agent.deep_agent._budget_guard import BudgetExceeded, BudgetGuard, Prices  # noqa: E402
from agent.deep_agent._subagent_capture import SCHEMA  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, LLMResult  # noqa: E402

RUN_ID = launch.RUN_ID


def guard_summary(*, stopped: bool = False, **limits) -> dict:
    """A real guard's summary after one settled call (and, if *stopped*, one refused)."""
    g = BudgetGuard(max_calls=limits.get("max_calls", launch.MAX_MODEL_CALLS),
                    max_cost_usd=limits.get("max_cost_usd", launch.MAX_COST_USD),
                    prices=Prices(**launch.PRICES))
    rid = uuid4()
    g.on_chat_model_start({}, [[]], run_id=rid, invocation_params={"max_tokens": 4096})
    msg = AIMessage("x", usage_metadata={"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100})
    g.on_llm_end(LLMResult(generations=[[ChatGeneration(message=msg)]]), run_id=rid)
    if stopped:  # a reservation far above $10: refused before any request
        with pytest.raises(BudgetExceeded):
            g.on_chat_model_start({}, [[]], run_id=uuid4(), invocation_params={"max_tokens": 2_000_000})
    return json.loads(json.dumps(g.summary()))


def write_outputs(tmp_path: Path, *, status: str = "ok", guard: dict | None | str = "default",
                  trajectory: bool | None = None, otel: bool = True, error: dict | None | str = "default",
                  **record) -> dict[str, Path]:
    paths = {"trajectory": tmp_path / f"{RUN_ID}.json",
             "instrumented": tmp_path / f"{RUN_ID}.instrumented.json",
             "otel": tmp_path / f"otel-{RUN_ID}.jsonl"}
    if guard == "default":
        guard = guard_summary()
    if error == "default":
        error = None if status == "ok" else {"type": "RuntimeError", "message": "m", "traceback": []}
    body = {"schema": SCHEMA, "status": status, "error": error, "run_id": RUN_ID,
            "agents": [], "delegations": [], "events": []}
    if guard is not None:
        body["budget_guard"] = guard
    body |= record
    paths["instrumented"].write_text(json.dumps(body))
    if trajectory is None:
        trajectory = status == "ok"
    if trajectory:
        paths["trajectory"].write_text(json.dumps({"run_id": RUN_ID, "trajectory": {}}))
    if otel:
        paths["otel"].write_text('{"resourceSpans": []}\n')
    return paths


def classify(paths: dict[str, Path]) -> dict:
    return pre.classify_outputs(paths, run_id=RUN_ID, max_calls=launch.MAX_MODEL_CALLS,
                                max_cost_usd=launch.MAX_COST_USD, prices=launch.PRICES)


# -- outcomes --------------------------------------------------------------------------


def test_completed_run_passes_strictly(tmp_path):
    out = classify(write_outputs(tmp_path))
    assert out["outcome"] == pre.COMPLETED
    assert all(out["checks"].values()), out["checks"]


def test_completed_run_without_native_trajectory_is_rejected(tmp_path):
    out = classify(write_outputs(tmp_path, trajectory=False))
    assert out["outcome"] == pre.EVIDENCE_INVALID
    assert not out["checks"]["native_trajectory"]


def test_completed_run_with_foreign_trajectory_is_rejected(tmp_path):
    paths = write_outputs(tmp_path)
    paths["trajectory"].write_text(json.dumps({"run_id": "other"}))
    assert classify(paths)["outcome"] == pre.EVIDENCE_INVALID


def test_ordinary_error_without_trajectory_is_accepted_as_error(tmp_path):
    out = classify(write_outputs(tmp_path, status="error"))
    assert out["outcome"] == pre.ERROR
    assert all(out["checks"].values()), out["checks"]
    assert out["evidence"]["native_trajectory_exists"] is False
    assert out["evidence"]["budget_stop_reason"] is None


def test_budget_stop_is_classified_separately(tmp_path):
    error = {"type": "BudgetExceeded", "message": "BUDGET-STOPPED: max_cost_usd", "traceback": []}
    out = classify(write_outputs(tmp_path, status="error", guard=guard_summary(stopped=True), error=error))
    assert out["outcome"] == pre.BUDGET_STOPPED
    assert all(out["checks"].values()), out["checks"]
    assert out["evidence"]["budget_stop_reason"] == "max_cost_usd"
    assert out["evidence"]["budget_calls_started"] == 1


def test_error_with_native_trajectory_contradicts_runner(tmp_path):
    out = classify(write_outputs(tmp_path, status="error", trajectory=True))
    assert out["outcome"] == pre.EVIDENCE_INVALID
    assert not out["checks"]["native_trajectory"]


# -- missing or unsupported evidence -------------------------------------------------------


def test_no_outputs_at_all_is_rejected(tmp_path):
    paths = write_outputs(tmp_path, status="error", otel=False)
    paths["instrumented"].unlink()
    out = classify(paths)
    assert out["outcome"] == pre.EVIDENCE_INVALID
    assert not out["checks"]["instrumented_record_valid"]


@pytest.mark.parametrize("status", ["ok", "error"])
def test_missing_otel_is_rejected(tmp_path, status):
    out = classify(write_outputs(tmp_path, status=status, otel=False))
    assert out["outcome"] == pre.EVIDENCE_INVALID
    assert not out["checks"]["otel_nonempty"]


def test_empty_otel_is_rejected(tmp_path):
    paths = write_outputs(tmp_path)
    paths["otel"].write_text("")
    assert not classify(paths)["checks"]["otel_nonempty"]


def test_corrupt_instrumented_record_is_rejected(tmp_path):
    paths = write_outputs(tmp_path, status="error")
    paths["instrumented"].write_text("{not json")
    out = classify(paths)
    assert out["outcome"] == pre.EVIDENCE_INVALID
    assert not out["checks"]["instrumented_record_valid"]


@pytest.mark.parametrize("override", [{"schema": "other/0.1"}, {"run_id": "other"}, {"status": "partial"}])
def test_instrumented_record_identity_is_checked(tmp_path, override):
    paths = write_outputs(tmp_path, status="error")
    paths["instrumented"].write_text(json.dumps(json.loads(paths["instrumented"].read_text()) | override))
    out = classify(paths)
    assert out["outcome"] == pre.EVIDENCE_INVALID
    assert not out["checks"]["instrumented_record_valid"]


def test_error_status_needs_error_info(tmp_path):
    out = classify(write_outputs(tmp_path, status="error", error=None))
    assert not out["checks"]["error_matches_status"]


def test_ok_status_with_error_info_is_rejected(tmp_path):
    out = classify(write_outputs(tmp_path, error={"type": "RuntimeError"}))
    assert not out["checks"]["error_matches_status"]


# -- budget_guard metadata -----------------------------------------------------------------


@pytest.mark.parametrize("status", ["ok", "error"])
def test_missing_budget_guard_is_rejected(tmp_path, status):
    out = classify(write_outputs(tmp_path, status=status, guard=None))
    assert out["outcome"] == pre.EVIDENCE_INVALID
    assert not out["checks"]["budget_guard_present"]


def test_budget_guard_with_other_limits_is_rejected(tmp_path):
    out = classify(write_outputs(tmp_path, guard=guard_summary(max_calls=50)))
    assert not out["checks"]["budget_guard_config"]


def test_budget_guard_with_other_prices_is_rejected(tmp_path):
    guard = guard_summary()
    guard["prices_usd_per_mtok"]["output"] = 15.0
    assert not classify(write_outputs(tmp_path, guard=guard))["checks"]["budget_guard_config"]


@pytest.mark.parametrize("edit", [
    {"stop_reason": None},       # stopped without a reason
    {"blocked": []},             # stopped without a refused call
    {"outcome": None},           # stopped but no outcome label
])
def test_inconsistent_stopped_guard_is_rejected(tmp_path, edit):
    guard = guard_summary(stopped=True) | edit
    out = classify(write_outputs(tmp_path, status="error", guard=guard))
    assert out["outcome"] == pre.EVIDENCE_INVALID
    assert not out["checks"]["budget_guard_consistent"]


def test_outcome_label_without_stop_is_rejected(tmp_path):
    guard = guard_summary() | {"outcome": "BUDGET-STOPPED"}
    assert not classify(write_outputs(tmp_path, status="error", guard=guard))["checks"]["budget_guard_consistent"]


def test_fired_guard_on_ok_record_is_rejected(tmp_path):
    out = classify(write_outputs(tmp_path, status="ok", guard=guard_summary(stopped=True)))
    assert out["outcome"] == pre.EVIDENCE_INVALID
    assert not out["checks"]["budget_guard_consistent"]


# -- isolated-DB change classes -----------------------------------------------------------


def _inv(**dbs) -> dict:
    return {name: {"doc_count": n, "doc_del_count": 0, "update_seq": n, "content_sha256": f"{name}{n}"}
            for name, n in dbs.items()}


BASE = _inv(asset=10, catalog=7, failure_code=10, failure_mode=3, feature_catalog=5,
            iot=10218, model_catalog=5, vibration=4097, workorder=7)


def test_no_change():
    assert pre.classify_db_changes(BASE, dict(BASE)) == {
        "expected_new": {}, "unexpected_new": [], "permitted_changed": [], "unexpected_changed": []}


def test_tsfm_created_dbs_are_expected():
    after = BASE | _inv(tsfm_runs=1, tsfm_plans=1, anomaly_result=2)
    c = pre.classify_db_changes(BASE, after)
    assert c["expected_new"] == {"anomaly_result": 2, "tsfm_plans": 1, "tsfm_runs": 1}
    assert not c["unexpected_new"]


def test_other_new_db_is_unexpected():
    assert pre.classify_db_changes(BASE, BASE | _inv(scratch=1))["unexpected_new"] == ["scratch"]


@pytest.mark.parametrize("db", sorted(pre.PERMITTED_WRITE_DBS))
def test_writes_by_kept_tools_are_permitted(db):
    after = BASE | _inv(**{db: BASE[db]["doc_count"] + 1})
    c = pre.classify_db_changes(BASE, after)
    assert c["permitted_changed"] == [db] and not c["unexpected_changed"]


@pytest.mark.parametrize("db", ["workorder", "iot", "asset", "catalog", "failure_code", "vibration"])
def test_writes_without_a_registered_tool_are_unexpected(db):
    after = BASE | {db: BASE[db] | {"content_sha256": "changed"}}
    assert pre.classify_db_changes(BASE, after)["unexpected_changed"] == [db]


def test_removed_db_is_unexpected():
    after = {k: v for k, v in BASE.items() if k != "failure_mode"}
    assert pre.classify_db_changes(BASE, after)["unexpected_changed"] == ["failure_mode"]


# -- run_checks(mode="post") wiring -------------------------------------------------------

WO = {"found": 1, "wonum": "1000045", "status": "WAPPR", "rev_prefix": "1-850525"}


def _post_report(monkeypatch, paths, *, isolated_after, shared_after=None, wo_after=WO):
    pre_record = {"isolated_inventory": BASE, "shared_inventory": BASE, "isolated_wo_1000045": WO}
    monkeypatch.setattr(launch, "output_paths", lambda: paths)
    monkeypatch.setattr(pre, "latest_record", lambda run_id, mode: {"path": "fixture", "record": pre_record})
    monkeypatch.setattr(pre.iso, "verify", lambda: {
        "isolation": {}, "files_sha256": dict(pre.PRE_REGISTERED_SHA256),
        "isolated_inventory": isolated_after, "shared_inventory": shared_after or BASE,
        "isolated_wo_1000045": wo_after, "shared_wo_1000045": WO, "problems": []})
    env = {"COUCHDB_URL": pre.iso.ISOLATED_URL, "COUCHDB_USERNAME": "u", "COUCHDB_PASSWORD": "p",
           launch.MODEL_KEY: "dummy", "AGENTTRACE_SPECIALISTS": "1",
           "AGENTTRACE_CAPTURE_SUBAGENTS": "1", **launch.guard_env()}
    return pre.run_checks(mode="post", env=env, argv=launch.argv())


POST_CHECKS = ["pre_record_found", "only_declared_new_dbs", "no_unexpected_db_change",
               "isolated_wo_unchanged", "shared_unchanged_since_pre", "instrumented_record_valid",
               "error_matches_status", "budget_guard_present", "budget_guard_config",
               "budget_guard_consistent", "native_trajectory", "otel_nonempty"]


def test_post_budget_stop_with_permitted_write(monkeypatch, tmp_path):
    paths = write_outputs(tmp_path, status="error", guard=guard_summary(stopped=True))
    after = BASE | _inv(failure_mode=4, tsfm_runs=1)
    r = _post_report(monkeypatch, paths, isolated_after=after)
    assert r["outcome"] == pre.BUDGET_STOPPED
    assert {k: r["checks"][k] for k in POST_CHECKS} == dict.fromkeys(POST_CHECKS, True)
    assert "outputs_exist" not in r["checks"]
    assert r["isolated_db_changes"]["permitted_changed"] == ["failure_mode"]
    assert r["shared_safety_failure"] is False


def test_post_shared_change_is_a_safety_failure(monkeypatch, tmp_path):
    shared_after = BASE | {"workorder": BASE["workorder"] | {"update_seq": 8}}
    r = _post_report(monkeypatch, write_outputs(tmp_path), isolated_after=BASE, shared_after=shared_after)
    assert r["shared_safety_failure"] is True
    assert not r["checks"]["shared_unchanged_since_pre"] and not r["pass"]


def test_post_unexpected_isolated_write_fails(monkeypatch, tmp_path):
    after = BASE | {"workorder": BASE["workorder"] | {"content_sha256": "changed"}}
    r = _post_report(monkeypatch, write_outputs(tmp_path), isolated_after=after,
                     wo_after=WO | {"status": "APPR", "rev_prefix": "2-abc"})
    assert r["isolated_db_changes"]["unexpected_changed"] == ["workorder"]
    assert not r["checks"]["no_unexpected_db_change"] and not r["checks"]["isolated_wo_unchanged"]
    assert not r["pass"]


def test_post_missing_outputs_fail(monkeypatch, tmp_path):
    paths = {k: tmp_path / n for k, n in
             {"trajectory": "t.json", "instrumented": "i.json", "otel": "o.jsonl"}.items()}
    r = _post_report(monkeypatch, paths, isolated_after=BASE)
    assert r["outcome"] == pre.EVIDENCE_INVALID and not r["pass"]
