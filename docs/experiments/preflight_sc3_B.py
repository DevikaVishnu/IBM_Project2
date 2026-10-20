"""No-LLM pre- and post-run checks for the scenario_3 condition-B run (§14).

    cd AssetOpsBench-agenttrace-spec
    .venv/bin/python ../AP/docs/experiments/preflight_sc3_B.py          # pre
    .venv/bin/python ../AP/docs/experiments/preflight_sc3_B.py --post   # post

Writes ``runs/preflight/<run id>.<mode>.<UTC time>.json`` (configuration,
versions, hashes, inventories, environment *names*; never a value) and exits
non-zero if any check fails.  The pre mode also starts the real MCP servers with
the run's connection environment, lists their tools and calls two read tools
(WO ``get_workorder``, IoT ``sites``) against the isolated CouchDB.  No model is
constructed or called.  The post mode classifies the outcome and the isolated-DB
changes as in pre-registration §14.8.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import hashlib
import importlib.metadata
import json
import platform
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import sc3_isolation as iso  # noqa: E402

sys.path.insert(0, str(iso.WORKTREE / "src"))

AP = HERE.parents[1]  # this file is AP/docs/experiments/preflight_sc3_B.py
SCHEMA_FILE = AP / "docs/agenttrace.semantic.0.3.md"
SCHEMA_SHA256 = "2273d210090d19c17f75e98bb06875e0c55ef10b9c26528ea2471cee25c01c06"
TRACES_JSONL = AP / "data/assetopsbench/runs/traces.jsonl"
TRACES_JSONL_SIZE = 101_154
WORKTREE_BRANCH = "research/agenttrace-specialists"
WORKTREE_BASE = "6ec35fb"
QUESTION_SHA256 = "ab0147071bed7eedfa76659f1f4ee807c006b84e2b5e58d43c77aeb062e70e98"
PRE_REGISTERED_SHA256 = {  # §4
    "chiller_6.json": "8073af23ea71fc401aee97fd40b47678a80ad0549eb4153b1eb0ab8dc9b246e2",
    "groundtruth.txt": "ff1d124863f3cad7c73617723b1780bef3f5128e4c992de48f04d9d7dde667f8",
}
# Per-agent configured tools [OBS 2026-10-14 readiness review]: server + utilities.
EXPECTED_PARTITIONS = {"coordinator": 79, "iot": 18, "tsfm": 47, "fmsr": 9, "wo": 15}
WO_WRITE_TOOLS = {"create_workorder", "approve_workorder", "assign_workorder",
                  "close_workorder", "cancel_workorder"}
RUN_CREATED_DBS = re.compile(r"^(tsfm_runs|tsfm_plans|.+_result)$")  # §13.3, declared
# §14.8: existing isolated DBs that kept production write tools may change (§13.3).
# Every other isolated DB has no registered write tool.
PERMITTED_WRITE_DBS = {
    "model_catalog": "TSFM register_*/update_*/deprecate_*/new_model_version",
    "feature_catalog": "TSFM *_feature tools",
    "failure_mode": "FMSR add_failure_modes",
}
# §14.8 outcome labels from the output files.
COMPLETED, ERROR, BUDGET_STOPPED, EVIDENCE_INVALID = (
    "COMPLETED", "ERROR", "BUDGET-STOPPED", "EVIDENCE-INVALID")
FORBIDDEN_ENV = re.compile(r"WATSONX|LITELLM|TOKENROUTER|OPENAI|AOB_READONLY|^OTEL_(?!TRACES_FILE$)")
SOURCE_FILES = ["runner.py", "_specialists.py", "_subagent_capture.py", "_file_observer.py",
                "_budget_guard.py", "cli.py"]
VERSION_PACKAGES = ["deepagents", "langgraph", "langchain", "langchain-core", "langchain-anthropic",
                    "anthropic", "langchain-mcp-adapters", "mcp", "opentelemetry-sdk",
                    "opentelemetry-exporter-otlp-proto-common", "protobuf"]


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(iso.WORKTREE), *args], capture_output=True,
                          text=True, check=True).stdout.strip()


def _versions() -> dict:
    out = {"python": platform.python_version()}
    for pkg in VERSION_PACKAGES:
        try:
            out[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            out[pkg] = None
    return out


def _connections(env: dict) -> dict:
    from agent.deep_agent._specialists import with_forwarded_env, with_readonly_wo
    from agent.deep_agent.runner import _build_mcp_connections
    from agent.runner import DEFAULT_SERVER_PATHS

    return with_readonly_wo(with_forwarded_env(_build_mcp_connections(DEFAULT_SERVER_PATHS), environ=env))


async def _probe_servers(connections: dict) -> dict:
    """Real MCP servers, run's connection env, read tools only; no model."""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    from agent.deep_agent._specialists import SHARED_SERVERS, SPECIALIST_SERVERS, load_tools_by_server

    client = MultiServerMCPClient(connections)
    by_server = await load_tools_by_server(client, list(connections))
    names = {s: [t.name for t in tools] for s, tools in by_server.items()}
    shared = sum(len(names[s]) for s in SHARED_SERVERS)
    partitions = {"coordinator": sum(len(v) for v in names.values())}
    partitions |= {s: len(names[s]) + shared for s in SPECIALIST_SERVERS}

    def tool(server, name):
        return next(t for t in by_server[server] if t.name == name)

    wo = await tool("wo", "get_workorder").ainvoke({"wonum": "1000045", "site_id": "MAIN"})
    sites = await tool("iot", "sites").ainvoke({})
    wo_text, sites_text = json.dumps(wo, default=str), json.dumps(sites, default=str)
    return {
        "tools_per_server": {s: len(v) for s, v in names.items()},
        "partitions": partitions,
        "wo_write_tools_offered": sorted(WO_WRITE_TOOLS & set(names["wo"])),
        "wo_get_workorder_1000045": {"WAPPR": "WAPPR" in wo_text, "CHILLER6": "CHILLER6" in wo_text},
        "iot_sites": {"MAIN": "MAIN" in sites_text, "NORTH": "NORTH" in sites_text},
    }


def _read_json(path: Path) -> object:
    """Parsed JSON, or None when the file is missing or not valid JSON."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def classify_outputs(paths: dict[str, Path], *, run_id: str, max_calls: int,
                     max_cost_usd: float, prices: dict) -> dict:
    """§14.8 outcome of the run from its output files; no network.

    The instrumented record is the evidence.  It must be valid and carry a
    consistent ``budget_guard`` object in every case.  A missing native trajectory
    is accepted only when that record says ``status: error`` (the runner writes the
    trajectory only on success).  The outcome is BUDGET-STOPPED when the guard
    fired, ERROR for any other error, COMPLETED otherwise, and EVIDENCE-INVALID
    whenever a check fails.
    """
    from agent.deep_agent._budget_guard import GUARD_ENV, OUTCOME
    from agent.deep_agent._subagent_capture import SCHEMA

    checks: dict[str, bool] = {}
    record = _read_json(paths["instrumented"])
    rec = record if isinstance(record, dict) else {}
    status = rec.get("status")
    checks["instrumented_record_valid"] = (
        isinstance(record, dict) and rec.get("schema") == SCHEMA
        and rec.get("run_id") == run_id and status in ("ok", "error"))
    err = rec.get("error")
    checks["error_matches_status"] = (
        (status == "ok" and err is None)
        or (status == "error" and isinstance(err, dict) and bool(err.get("type"))))

    guard = rec.get("budget_guard")
    g = guard if isinstance(guard, dict) else {}
    stopped = g.get("stopped") is True
    checks["budget_guard_present"] = isinstance(guard, dict) and g.get("source") == GUARD_ENV
    checks["budget_guard_config"] = (
        g.get("limits") == {"max_model_calls": max_calls, "max_cost_usd": max_cost_usd}
        and g.get("prices_usd_per_mtok") == prices)
    checks["budget_guard_consistent"] = (
        g.get("outcome") == (OUTCOME if stopped else None)
        and (g.get("stop_reason") is not None) == stopped
        and isinstance(g.get("blocked"), list) and bool(g.get("blocked")) == stopped
        and (not stopped or status == "error"))  # a fired guard always raises out of the run

    trajectory_exists = paths["trajectory"].exists()
    if status == "ok":
        traj = _read_json(paths["trajectory"])
        checks["native_trajectory"] = isinstance(traj, dict) and traj.get("run_id") == run_id
    else:  # absent on error; one present would contradict the record
        checks["native_trajectory"] = status == "error" and not trajectory_exists
    otel = paths["otel"]
    checks["otel_nonempty"] = otel.exists() and otel.stat().st_size > 0

    if not all(checks.values()):
        outcome = EVIDENCE_INVALID
    elif stopped:
        outcome = BUDGET_STOPPED
    elif status == "error":
        outcome = ERROR
    else:
        outcome = COMPLETED
    return {
        "outcome": outcome,
        "checks": checks,
        "evidence": {
            "instrumented_status": status,
            "error_type": err.get("type") if isinstance(err, dict) else None,
            "budget_stop_reason": g.get("stop_reason"),
            "budget_calls_started": g.get("calls_started"),
            "budget_total_usd_estimate": g.get("total_usd_estimate"),
            "budget_calls_over_reservation": g.get("calls_over_reservation"),
            "native_trajectory_exists": trajectory_exists,
            "otel_bytes": otel.stat().st_size if otel.exists() else None,
        },
    }


def classify_db_changes(before: dict, after: dict) -> dict:
    """§14.8 classes of isolated-DB change between two inventories."""
    new = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(d for d in before if d in after and before[d] != after[d])
    return {
        "expected_new": {d: after[d]["doc_count"] for d in new if RUN_CREATED_DBS.match(d)},
        "unexpected_new": [d for d in new if not RUN_CREATED_DBS.match(d)],
        "permitted_changed": [d for d in changed if d in PERMITTED_WRITE_DBS],
        "unexpected_changed": [d for d in changed if d not in PERMITTED_WRITE_DBS] + removed,
    }


def run_checks(*, mode: str, env: dict, argv: list[str], probe_servers: bool = True) -> dict:
    import launch_sc3_B as launch
    from agent.deep_agent._budget_guard import BudgetGuard

    checks: dict[str, bool] = {}
    report: dict = {"mode": mode, "run_id": launch.RUN_ID, "checked_at": _dt.datetime.now(_dt.UTC).isoformat()}

    def check(name: str, ok: bool) -> None:
        checks[name] = bool(ok)

    # Worktree and code under test.
    report["worktree"] = {
        "path": str(iso.WORKTREE),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "head": _git("rev-parse", "HEAD"),
        "status_short": _git("status", "--short").splitlines(),
        "source_sha256": {f: iso.sha256_file(iso.WORKTREE / "src/agent/deep_agent" / f) for f in SOURCE_FILES},
        "uv_lock_sha256": iso.sha256_file(iso.WORKTREE / "uv.lock"),
    }
    check("worktree_branch", report["worktree"]["branch"] == WORKTREE_BRANCH)
    check("worktree_base", report["worktree"]["head"].startswith(WORKTREE_BASE))
    check("worktree_has_no_dotenv", not (iso.WORKTREE / ".env").exists())
    report["versions"] = _versions()
    report["schema_sha256"] = iso.sha256_file(SCHEMA_FILE)
    check("schema_0_3_unchanged", report["schema_sha256"] == SCHEMA_SHA256)

    # Configuration (names and non-secret values only).
    paths = launch.output_paths()
    report["config"] = {
        "model_id": launch.MODEL_ID, "scenario_id": launch.SCENARIO_ID,
        "argv_without_question": argv[:-1],
        "question_sha256": hashlib.sha256(argv[-1].encode()).hexdigest(),
        "outputs": {k: str(v) for k, v in paths.items()},
        "flags": {k: env.get(k) for k in ("AGENTTRACE_SPECIALISTS", "AGENTTRACE_CAPTURE_SUBAGENTS")},
        "couchdb_url": env.get("COUCHDB_URL"),
        "prices_checked_on": launch.PRICES_CHECKED_ON,
        "env_names": sorted(env),
    }
    check("question_verbatim", report["config"]["question_sha256"] == QUESTION_SHA256
          and (iso.COUCH_DIR / "scenarios_data/scenario_3/question.txt").read_text().rstrip("\n") == argv[-1])
    check("env_couchdb_is_isolated", env.get("COUCHDB_URL") == iso.ISOLATED_URL)
    check("env_has_model_key", bool(env.get(launch.MODEL_KEY)))
    check("env_has_no_forbidden_names", not [k for k in env if FORBIDDEN_ENV.search(k)])
    check("env_flags_on", report["config"]["flags"] == {"AGENTTRACE_SPECIALISTS": "1",
                                                        "AGENTTRACE_CAPTURE_SUBAGENTS": "1"})

    guard = BudgetGuard.from_env(env)
    report["budget_guard"] = {k: v for k, v in guard.summary().items()
                              if k in ("source", "limits", "prices_usd_per_mtok", "basis")}
    check("guard_limits", (guard.max_calls, guard.max_cost_usd) == (200, 10.0))

    # Connections exactly as the runner builds them with this environment.
    conns = _connections(env)
    user = env.get("COUCHDB_USERNAME")
    report["connections"] = {n: sorted((c.get("env") or {})) for n, c in conns.items()}
    check("every_server_uses_isolated_couchdb", all(
        (c.get("env") or {}).get("COUCHDB_URL") == iso.ISOLATED_URL
        and (c.get("env") or {}).get("COUCHDB_USERNAME") == user for c in conns.values()))
    check("no_model_key_on_servers", all(launch.MODEL_KEY not in (c.get("env") or {}) for c in conns.values()))
    check("wo_readonly", (conns["wo"].get("env") or {}).get("AOB_READONLY") == "1")

    # Data and evidence files.
    db = iso.verify()
    report["isolation"] = db["isolation"]
    report["files_sha256"] = db["files_sha256"]
    report["isolated_inventory"] = db["isolated_inventory"]
    report["shared_inventory"] = db["shared_inventory"]
    report["isolated_wo_1000045"] = db["isolated_wo_1000045"]
    report["shared_wo_1000045"] = db["shared_wo_1000045"]
    report["tsfm_workdir"] = sorted(p.name for p in Path("/tmp/tsfm_work").glob("*")) \
        if Path("/tmp/tsfm_work").exists() else None
    check("source_hashes_as_preregistered", all(
        db["files_sha256"][k] == v for k, v in PRE_REGISTERED_SHA256.items()))
    check("shared_wo_unchanged", db["shared_wo_1000045"] == {"found": 1, "wonum": "1000045",
                                                           "status": "WAPPR", "rev_prefix": "1-850525"})
    report["traces_jsonl_size"] = TRACES_JSONL.stat().st_size
    check("traces_jsonl_unchanged", report["traces_jsonl_size"] == TRACES_JSONL_SIZE)

    if mode == "pre":
        report["db_problems"] = db["problems"]
        check("isolated_matches_shared_and_baseline", not db["problems"])
        check("no_run_created_dbs_yet", not [d for d in db["isolated_inventory"] if RUN_CREATED_DBS.match(d)])
        check("tsfm_workdir_absent", report["tsfm_workdir"] is None)
        check("no_outputs_for_run_id", not any(p.exists() for p in paths.values()))
        if probe_servers:
            probe = asyncio.run(_probe_servers(conns))
            report["server_probe"] = probe
            check("partitions_as_preregistered", probe["partitions"] == EXPECTED_PARTITIONS)
            check("no_wo_write_tools", probe["wo_write_tools_offered"] == [])
            check("wo_read_from_isolated", all(probe["wo_get_workorder_1000045"].values()))
            check("iot_read_from_isolated", all(probe["iot_sites"].values()))
    else:
        pre = latest_record(launch.RUN_ID, "pre")
        report["compared_with"] = pre["path"] if pre else None
        check("pre_record_found", pre is not None)
        if pre is not None:
            changes = classify_db_changes(pre["record"]["isolated_inventory"], db["isolated_inventory"])
            report["isolated_db_changes"] = changes  # permitted_changed: attribute each to a tool call
            check("only_declared_new_dbs", not changes["unexpected_new"])
            check("no_unexpected_db_change", not changes["unexpected_changed"])
            check("isolated_wo_unchanged", db["isolated_wo_1000045"] == pre["record"]["isolated_wo_1000045"])
            shared_ok = db["shared_inventory"] == pre["record"]["shared_inventory"]
            report["shared_safety_failure"] = not shared_ok
            check("shared_unchanged_since_pre", shared_ok)
        outputs = classify_outputs(paths, run_id=launch.RUN_ID, max_calls=launch.MAX_MODEL_CALLS,
                                   max_cost_usd=launch.MAX_COST_USD, prices=launch.PRICES)
        report["outcome"] = outputs["outcome"]
        report["outcome_evidence"] = outputs["evidence"]
        for name, ok in outputs["checks"].items():
            check(name, ok)

    report["checks"] = checks
    report["failures"] = [k for k, ok in checks.items() if not ok]
    report["pass"] = not report["failures"]
    return report


def _record_dir() -> Path:
    import launch_sc3_B as launch

    return launch.RUNS_DIR / "preflight"


def write_record(report: dict) -> Path:
    stamp = report["checked_at"].replace(":", "").replace("-", "").split(".")[0]
    out = _record_dir() / f"{report['run_id']}.{report['mode']}.{stamp}Z.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise FileExistsError(out)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return out


def latest_record(run_id: str, mode: str) -> dict | None:
    files = sorted(_record_dir().glob(f"{run_id}.{mode}.*Z.json"))
    for path in reversed(files):
        record = json.loads(path.read_text())
        if record.get("pass"):
            return {"path": str(path), "record": record}
    return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--post", action="store_true")
    p.add_argument("--no-server-probe", action="store_true")
    args = p.parse_args()
    import launch_sc3_B as launch

    try:
        report = run_checks(mode="post" if args.post else "pre", env=launch.build_env(),
                            argv=launch.argv(), probe_servers=not args.no_server_probe)
    except iso.IsolationError as exc:
        print(f"ISOLATION CHECK FAILED: {exc}", file=sys.stderr)
        return 1
    path = write_record(report)
    for name, ok in report["checks"].items():
        print(f"{'ok  ' if ok else 'FAIL'} {name}")
    if "outcome" in report:
        print(f"outcome: {report['outcome']}")
    print(f"{'PASS' if report['pass'] else 'FAIL'} -> {path}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
