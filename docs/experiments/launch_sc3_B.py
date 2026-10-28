"""Launcher for the scenario_3 condition-B run (pre-registration §14).

    # no model call: run the preflight, print the redacted plan, exit
    cd AssetOpsBench-agenttrace-spec
    .venv/bin/python ../AP/docs/experiments/launch_sc3_B.py

    # the one paid run, only after explicit approval and the run-day price check
    .venv/bin/python .../launch_sc3_B.py --execute --confirm-run-id aob-sc3-sonnet5-deep-spec-B-20261014

Run it with the worktree venv.  It builds a minimal environment and ``execve``s
``deep-agent``; the whole ``.env`` is never sourced.  The environment holds:
  * a fixed set of process basics (HOME, PATH, ...);
  * from the original ``.env``, only the server variables of ``SERVER_ENV``
    except the CouchDB ones, plus ``ANTHROPIC_API_KEY``;
  * the isolated CouchDB URL and its own credentials (from ``docker inspect``);
  * the research flags, the budget guard, and the per-run output paths.
Never prints a value.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import sc3_isolation as iso  # noqa: E402

sys.path.insert(0, str(iso.WORKTREE / "src"))

RUN_ID = "aob-sc3-sonnet5-deep-spec-B-20261014"
RUNS_DIR = HERE.parents[1] / "data/assetopsbench/runs"  # AP/data/assetopsbench/runs
MODEL_ID = "anthropic:claude-sonnet-5"  # unchanged production route
SCENARIO_ID = "scenario_3"
QUESTION_FILE = iso.COUCH_DIR / "scenarios_data/scenario_3/question.txt"
DEEP_AGENT = iso.WORKTREE / ".venv/bin/deep-agent"

MAX_MODEL_CALLS = 200
MAX_COST_USD = 10.0
# Sonnet 5, USD per million tokens.  [OBS 2026-10-14] official pricing page
# (platform.claude.com/docs/en/about-claude/pricing): input 2, 5m cache write 2.50,
# 1h cache write 4, output 10 (cache reads 0.20 are priced here as input; no
# long-context premium; inference_geo is not set, so no 1.1x).  --execute refuses
# unless PRICES_CHECKED_ON is the run date: on a later day, re-check and update it.
PRICES = {"input": 2.0, "cache_write_5m": 2.5, "cache_write_1h": 4.0, "output": 10.0}
PRICES_CHECKED_ON: str | None = "2026-10-14"

BASE_ENV_NAMES = ("HOME", "PATH", "USER", "LOGNAME", "SHELL", "TERM", "TMPDIR")
MODEL_KEY = "ANTHROPIC_API_KEY"
COUCH_NAMES = ("COUCHDB_URL", "COUCHDB_USERNAME", "COUCHDB_PASSWORD")


def output_paths() -> dict[str, Path]:
    return {
        "trajectory": RUNS_DIR / f"{RUN_ID}.json",
        "instrumented": RUNS_DIR / f"{RUN_ID}.instrumented.json",
        "otel": RUNS_DIR / f"otel-{RUN_ID}.jsonl",
    }


def guard_env() -> dict[str, str]:
    from agent.deep_agent import _budget_guard as bg

    return {
        bg.GUARD_ENV: "1",
        bg.MAX_CALLS_ENV: str(MAX_MODEL_CALLS),
        bg.MAX_COST_ENV: str(MAX_COST_USD),
        **{bg.PRICE_ENV[k]: str(v) for k, v in PRICES.items()},
    }


def build_env() -> dict[str, str]:
    """The run's complete environment.  Values are never printed."""
    from dotenv import dotenv_values

    from agent.deep_agent._specialists import SERVER_ENV

    vals = dotenv_values(iso.ORIGINAL_ENV)
    from_dotenv = ({n for names in SERVER_ENV.values() for n in names} - set(COUCH_NAMES)) | {MODEL_KEY}
    user, password = iso.isolated_credentials()

    env = {k: os.environ[k] for k in BASE_ENV_NAMES if k in os.environ}
    env |= {k: v for k, v in vals.items() if k in from_dotenv and v}
    env |= {"COUCHDB_URL": iso.ISOLATED_URL, "COUCHDB_USERNAME": user, "COUCHDB_PASSWORD": password}
    paths = output_paths()
    env |= {
        "AGENTTRACE_SPECIALISTS": "1",
        "AGENTTRACE_CAPTURE_SUBAGENTS": "1",
        "AGENT_TRAJECTORY_DIR": str(RUNS_DIR),
        "OTEL_TRACES_FILE": str(paths["otel"]),
    }
    env |= guard_env()
    return env


def argv() -> list[str]:
    question = QUESTION_FILE.read_text().rstrip("\n")
    return [str(DEEP_AGENT), "--model-id", MODEL_ID, "--run-id", RUN_ID,
            "--scenario-id", SCENARIO_ID, "--json", question]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--execute", action="store_true", help="start the paid run (needs approval)")
    p.add_argument("--confirm-run-id", default=None)
    args = p.parse_args()

    import preflight_sc3_B as pre

    report = pre.run_checks(mode="pre", env=build_env(), argv=argv())
    path = pre.write_record(report)
    print(f"preflight: {'PASS' if report['pass'] else 'FAIL'} -> {path}")
    for failure in report["failures"]:
        print(f"  FAIL {failure}")
    if not report["pass"]:
        return 1

    if not args.execute:
        print("dry run: no model call made. Environment names:", ", ".join(sorted(build_env())))
        return 0

    today = _dt.date.today().isoformat()
    if args.confirm_run_id != RUN_ID:
        print(f"refused: --confirm-run-id must be {RUN_ID}")
        return 1
    if PRICES_CHECKED_ON != today:
        print(f"refused: PRICES_CHECKED_ON is {PRICES_CHECKED_ON!r}, not today ({today})")
        return 1
    if any(p.exists() for p in output_paths().values()):
        print("refused: an output file for this run id already exists")
        return 1
    os.chdir(iso.WORKTREE)
    os.execve(str(DEEP_AGENT), argv(), build_env())
    return 1  # not reached


if __name__ == "__main__":
    sys.exit(main())
