"""Isolated, disposable CouchDB for the scenario_3 condition-B run.

Research tooling for `prereg-aob-sc3-sonnet5-deep-spec-B-20261014.md` (§14).
Not part of AssetOpsBench.  Never prints a credential value.

    python sc3_isolation.py create    # new container + new volume; refuses if either exists
    python sc3_isolation.py load      # isolation checks, then init_data.py for scenario 3
    python sc3_isolation.py verify    # isolation checks + inventory/digest vs the shared DB

Isolation model:
  * the isolated container publishes only 127.0.0.1:5985, has one named volume
    and no bind mounts, so it cannot see the shared volume or the repo;
  * it has its own random admin password, read back from ``docker inspect`` and
    never written to disk, so a request that reached the shared server with
    these credentials would be rejected (401);
  * every write-capable step first runs :func:`assert_isolated`, which proves the
    URL reaches the isolated container (server uuid via ``docker exec``) and
    rejects the shared address, port, container, volume and uuid.
Run it with the worktree venv (``python-dotenv`` is used for the shared, read-only
comparison only).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# The AP repo, the original AssetOpsBench clone and its specialist worktree are
# siblings in one projects directory (this file is AP/docs/experiments/...).
PROJECTS = Path(__file__).resolve().parents[3]
WORKTREE = PROJECTS / "AssetOpsBench-agenttrace-spec"
ORIGINAL_REPO = PROJECTS / "AssetOpsBench"
ORIGINAL_ENV = ORIGINAL_REPO / ".env"

ISOLATED_CONTAINER = "agenttrace-sc3-couchdb"
ISOLATED_VOLUME = "agenttrace-sc3-couchdb-data"
ISOLATED_PORT = 5985
ISOLATED_URL = f"http://127.0.0.1:{ISOLATED_PORT}"
ISOLATED_USER = "agenttrace"
PURPOSE_LABEL = ("agenttrace.purpose", "sc3-isolated")

SHARED_CONTAINER = "couchdb-couchdb-1"
SHARED_VOLUME = "couchdb_couchdb-data"
SHARED_PORT = 5984
SHARED_URL = f"http://localhost:{SHARED_PORT}"

SCENARIO = "3"
COUCH_DIR = WORKTREE / "src/couchdb"
HASHED_FILES = {
    "chiller_6.json": COUCH_DIR / "scenarios_data/shared/iot/chiller_6.json",
    "groundtruth.txt": COUCH_DIR / "scenarios_data/scenario_3/groundtruth.txt",
    "question.txt": COUCH_DIR / "scenarios_data/scenario_3/question.txt",
    "scenario_3/manifest.json": COUCH_DIR / "scenarios_data/scenario_3/manifest.json",
    "default/manifest.json": COUCH_DIR / "scenarios_data/default/manifest.json",
    "workorders.csv": COUCH_DIR / "scenarios_data/shared/work_order/workorders.csv",
}
# Pre-registration §4 baseline [OBS 2026-10-14].
EXPECTED_DOC_COUNTS = {
    "asset": 10, "catalog": 7, "failure_code": 10, "failure_mode": 3,
    "feature_catalog": 5, "iot": 10218, "model_catalog": 5,
    "vibration": 4097, "workorder": 7,
}
EXPECTED_WO = {"wonum": "1000045", "status": "WAPPR", "rev_prefix": "1-850525"}
# collections.json gives these no primary_key, so CouchDB assigns random _ids at load:
# a reload can match only on bodies without _id/_rev [OBS 2026-10-14].
GENERATED_ID_DBS = {"catalog"}


class IsolationError(RuntimeError):
    pass


# -- helpers -------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _docker(*args: str, env: dict | None = None) -> str:
    out = subprocess.run(["docker", *args], capture_output=True, text=True, env=env)
    if out.returncode != 0:
        raise IsolationError(f"docker {args[0]} failed: {out.stderr.strip()[:200]}")
    return out.stdout


def _inspect(kind: str, name: str) -> dict | None:
    out = subprocess.run(["docker", kind, "inspect", name], capture_output=True, text=True)
    if out.returncode != 0:
        return None
    return json.loads(out.stdout)[0]


def _http(method: str, url: str, auth: tuple[str, str] | None = None, body: dict | None = None):
    req = urllib.request.Request(url, method=method)
    if auth is not None:
        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=60) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as exc:
        return exc.code, None


def isolated_credentials() -> tuple[str, str]:
    """Admin credentials of the isolated container, from ``docker inspect``."""
    info = _inspect("container", ISOLATED_CONTAINER)
    if info is None:
        raise IsolationError(f"container {ISOLATED_CONTAINER} not found")
    env = dict(e.split("=", 1) for e in info["Config"]["Env"] if "=" in e)
    user, password = env.get("COUCHDB_USER"), env.get("COUCHDB_PASSWORD")
    if not user or not password:
        raise IsolationError("isolated container has no COUCHDB_USER/COUCHDB_PASSWORD")
    return user, password


def shared_credentials() -> tuple[str, str]:
    """Shared-server credentials from the original .env (read-only comparison only)."""
    from dotenv import dotenv_values

    vals = dotenv_values(ORIGINAL_ENV)
    return vals.get("COUCHDB_USERNAME") or "", vals.get("COUCHDB_PASSWORD") or ""


# -- isolation checks ------------------------------------------------------------


def assert_isolated(url: str = ISOLATED_URL) -> dict:
    """Raise :class:`IsolationError` unless *url* provably reaches only the isolated
    container.  Returns non-secret facts for the record."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.port == SHARED_PORT or parsed.port != ISOLATED_PORT:
        raise IsolationError(f"rejected port {parsed.port} (shared is {SHARED_PORT})")
    if parsed.hostname != "127.0.0.1" or url.rstrip("/") != ISOLATED_URL:
        raise IsolationError(f"rejected URL {url!r}; only {ISOLATED_URL} is allowed")

    iso = _inspect("container", ISOLATED_CONTAINER)
    shared = _inspect("container", SHARED_CONTAINER)
    if iso is None:
        raise IsolationError(f"isolated container {ISOLATED_CONTAINER} not found")
    if shared is None:
        raise IsolationError(f"shared container {SHARED_CONTAINER} not found (cannot compare)")
    if iso["Id"] == shared["Id"]:
        raise IsolationError("isolated and shared container ids are equal")
    if not iso["State"]["Running"]:
        raise IsolationError("isolated container is not running")
    if (iso["Config"]["Labels"] or {}).get(PURPOSE_LABEL[0]) != PURPOSE_LABEL[1]:
        raise IsolationError("isolated container lacks the purpose label")

    mounts = iso["Mounts"]
    if [(m["Type"], m.get("Name"), m["Destination"]) for m in mounts] != [
        ("volume", ISOLATED_VOLUME, "/opt/couchdb/data")
    ]:
        raise IsolationError(f"unexpected isolated mounts: {[m.get('Name') or m['Source'] for m in mounts]}")
    shared_vols = {m.get("Name") for m in shared["Mounts"] if m["Type"] == "volume"}
    if SHARED_VOLUME not in shared_vols or ISOLATED_VOLUME in shared_vols:
        raise IsolationError("volume layout of the shared container is not as expected")

    ports = iso["NetworkSettings"]["Ports"] or {}
    if ports != {"5984/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(ISOLATED_PORT)}]}:
        raise IsolationError(f"unexpected isolated port bindings: {ports}")

    # The URL reaches this container: same server uuid from inside it.
    inside = json.loads(_docker("exec", ISOLATED_CONTAINER, "curl", "-s", "http://127.0.0.1:5984/"))
    status, outside = _http("GET", ISOLATED_URL + "/")
    if status != 200 or outside.get("uuid") != inside.get("uuid"):
        raise IsolationError("isolated URL does not reach the isolated container")
    s_status, shared_root = _http("GET", SHARED_URL + "/")
    if s_status != 200 or shared_root.get("uuid") == outside.get("uuid"):
        raise IsolationError("isolated and shared servers have the same uuid (or shared unreachable)")

    user, password = isolated_credentials()
    s_user, s_password = shared_credentials()
    if password == s_password:
        raise IsolationError("isolated password equals the shared password")
    if _http("GET", SHARED_URL + "/_all_dbs", auth=(user, password))[0] != 401:
        raise IsolationError("isolated credentials are accepted by the shared server")

    return {
        "isolated_url": ISOLATED_URL,
        "isolated_container_id": iso["Id"][:12],
        "isolated_image": iso["Image"],
        "isolated_volume": ISOLATED_VOLUME,
        "isolated_server_uuid": outside["uuid"],
        "couchdb_version": outside.get("version"),
        "shared_container_id": shared["Id"][:12],
        "shared_image": shared["Image"],
        "shared_server_uuid": shared_root["uuid"],
        "isolated_creds_rejected_by_shared": True,
    }


# -- inventory -----------------------------------------------------------------


def inventory(url: str, auth: tuple[str, str], *, digests: bool = True) -> dict:
    """Per user DB: doc_count, doc_del_count, update_seq number and (optionally)
    a digest of every document without ``_rev`` plus a digest of the revs.
    GET requests only."""
    status, dbs = _http("GET", url + "/_all_dbs", auth=auth)
    if status != 200:
        raise IsolationError(f"_all_dbs returned {status}")
    out = {}
    for db in dbs:
        if db.startswith("_"):
            continue
        _, info = _http("GET", f"{url}/{db}", auth=auth)
        entry = {
            "doc_count": info["doc_count"],
            "doc_del_count": info["doc_del_count"],
            "update_seq": int(str(info["update_seq"]).split("-", 1)[0]),
        }
        if digests:
            _, rows = _http("GET", f"{url}/{db}/_all_docs?include_docs=true", auth=auth)
            docs = sorted((r["doc"] for r in rows["rows"]), key=lambda d: d["_id"])
            bodies = [{k: v for k, v in d.items() if k != "_rev"} for d in docs]
            revs = [[d["_id"], d["_rev"]] for d in docs]
            entry["content_sha256"] = hashlib.sha256(
                json.dumps(bodies, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            entry["revs_sha256"] = hashlib.sha256(json.dumps(revs).encode()).hexdigest()
            no_ids = sorted(  # design docs keep their (deterministic) _id
                json.dumps(
                    b if b["_id"].startswith("_design/") else {k: v for k, v in b.items() if k != "_id"},
                    sort_keys=True, separators=(",", ":"),
                )
                for b in bodies
            )
            entry["bodies_without_ids_sha256"] = hashlib.sha256("\n".join(no_ids).encode()).hexdigest()
        out[db] = entry
    return out


def workorder_status(url: str, auth: tuple[str, str]) -> dict:
    status, res = _http(
        "POST", f"{url}/workorder/_find", auth=auth,
        body={"selector": {"wonum": EXPECTED_WO["wonum"]}, "fields": ["wonum", "status", "_rev"]},
    )
    docs = (res or {}).get("docs") or []
    if status != 200 or len(docs) != 1:
        return {"found": len(docs), "http": status}
    d = docs[0]
    return {"found": 1, "wonum": d.get("wonum"), "status": d.get("status"), "rev_prefix": d["_rev"][:8]}


def compare(isolated: dict, shared: dict) -> list[str]:
    """Differences that matter for fidelity (empty list = equivalent)."""
    problems = []
    if set(isolated) != set(shared):
        problems.append(f"DB sets differ: only isolated {sorted(set(isolated) - set(shared))}, "
                        f"only shared {sorted(set(shared) - set(isolated))}")
    for db in sorted(set(isolated) & set(shared)):
        keys = ("doc_count", "doc_del_count", "bodies_without_ids_sha256")
        if db not in GENERATED_ID_DBS:
            keys += ("content_sha256", "revs_sha256")
        for key in keys:
            if isolated[db].get(key) != shared[db].get(key):
                problems.append(f"{db}.{key}: isolated {isolated[db].get(key)} != shared {shared[db].get(key)}")
    for db, n in EXPECTED_DOC_COUNTS.items():
        if isolated.get(db, {}).get("doc_count") != n:
            problems.append(f"{db}.doc_count != pre-registered {n}")
    return problems


# -- commands --------------------------------------------------------------------


def cmd_create() -> None:
    if _inspect("container", ISOLATED_CONTAINER) is not None:
        raise IsolationError(f"container {ISOLATED_CONTAINER} already exists; refusing")
    if _inspect("volume", ISOLATED_VOLUME) is not None:
        raise IsolationError(f"volume {ISOLATED_VOLUME} already exists; refusing")
    shared = _inspect("container", SHARED_CONTAINER)
    if shared is None:
        raise IsolationError("shared container not found; cannot pin the same image")
    image = shared["Image"]  # same image id as the shared server
    env = {"PATH": os.environ["PATH"], "HOME": os.environ["HOME"],
           "COUCHDB_USER": ISOLATED_USER, "COUCHDB_PASSWORD": secrets.token_urlsafe(24)}
    # -e NAME (no value) makes the docker CLI read the value from its own env: not in argv.
    _docker(
        "run", "-d", "--name", ISOLATED_CONTAINER,
        "--label", "=".join(PURPOSE_LABEL),
        "-p", f"127.0.0.1:{ISOLATED_PORT}:5984",
        "-v", f"{ISOLATED_VOLUME}:/opt/couchdb/data",
        "-e", "COUCHDB_USER", "-e", "COUCHDB_PASSWORD",
        image,
        env=env,
    )
    print(f"created {ISOLATED_CONTAINER} (image {image[:19]}) on {ISOLATED_URL}")


def _wait_ready(tries: int = 30) -> None:
    import time

    for _ in range(tries):
        try:
            if _http("GET", ISOLATED_URL + "/_up")[0] == 200:
                return
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(1)
    raise IsolationError("isolated CouchDB did not become ready")


def cmd_load() -> None:
    _wait_ready()
    facts = assert_isolated(ISOLATED_URL)
    auth = isolated_credentials()
    # Single-node system DBs (CouchDB setup step); only on the isolated URL.
    for sysdb in ("_users", "_replicator"):
        code = _http("PUT", f"{ISOLATED_URL}/{sysdb}", auth=auth)[0]
        if code not in (201, 202, 412):
            raise IsolationError(f"creating {sysdb} returned {code}")
    if inventory(ISOLATED_URL, auth, digests=False):
        raise IsolationError("isolated server already has user DBs; refusing to load")

    # The loader reads COUCHDB_URL at import; bind it for this one process only and
    # assert inside that process, before any request, that it is the isolated URL.
    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "import loader, init_data\n"
        "assert loader.COUCHDB_URL == %r, loader.COUCHDB_URL\n"
        "assert loader._db_url('x').startswith(%r + '/')\n"
        "for k, (db, n) in init_data.init_data(%r).items(): print(k, db, n)\n"
    ) % (str(COUCH_DIR), ISOLATED_URL, ISOLATED_URL, SCENARIO)
    env = {"PATH": os.environ["PATH"], "HOME": os.environ["HOME"],
           "COUCHDB_URL": ISOLATED_URL, "COUCHDB_USERNAME": auth[0], "COUCHDB_PASSWORD": auth[1]}
    res = subprocess.run([str(WORKTREE / ".venv/bin/python"), "-c", code],
                         cwd=str(COUCH_DIR), env=env, capture_output=True, text=True)
    print(res.stdout.strip())
    if res.returncode != 0:
        raise IsolationError(f"load failed: {res.stderr.strip()[-400:]}")
    print(json.dumps({"isolation": facts}, indent=2))


def verify() -> dict:
    facts = assert_isolated(ISOLATED_URL)
    auth = isolated_credentials()
    report = {
        "isolation": facts,
        "files_sha256": {k: sha256_file(p) for k, p in HASHED_FILES.items()},
        "isolated_inventory": inventory(ISOLATED_URL, auth),
        "isolated_wo_1000045": workorder_status(ISOLATED_URL, auth),
        "tsfm_workdir_exists": Path("/tmp/tsfm_work").exists(),
    }
    wo = report["isolated_wo_1000045"]
    problems = []
    if (wo.get("status"), wo.get("rev_prefix")) != (EXPECTED_WO["status"], EXPECTED_WO["rev_prefix"]):
        problems.append(f"isolated WO 1000045 is {wo}")
    s_auth = shared_credentials()
    report["shared_inventory"] = inventory(SHARED_URL, s_auth)
    report["shared_wo_1000045"] = workorder_status(SHARED_URL, s_auth)
    problems += compare(report["isolated_inventory"], report["shared_inventory"])
    report["problems"] = problems
    return report


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "verify"
    try:
        if cmd == "create":
            cmd_create()
        elif cmd == "load":
            cmd_load()
        elif cmd == "verify":
            report = verify()
            print(json.dumps(report, indent=2))
            return 1 if report["problems"] else 0
        else:
            print(__doc__)
            return 2
    except IsolationError as exc:
        print(f"ISOLATION CHECK FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
