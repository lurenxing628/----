from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


def _find_repo_root() -> Path:
    for base in (Path(__file__).resolve().parent, Path.cwd().resolve()):
        p = base
        while True:
            if (p / "app.py").is_file() and (p / "schema.sql").is_file():
                return p
            if p.parent == p:
                break
            p = p.parent
    raise RuntimeError("Unable to locate repo root (requires app.py and schema.sql).")


_REPO_ROOT = _find_repo_root()
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.infrastructure.safe_files import read_fixed_text, remove_fixed_file  # noqa: E402
from web.bootstrap.launcher_contract_result import (  # noqa: E402
    CONTRACT_STATUS_MISSING,
    CONTRACT_STATUS_VALID,
    read_runtime_contract_result,
)
from web.bootstrap.launcher_endpoint_result import (  # noqa: E402
    ENDPOINT_STATUS_MISSING,
    ENDPOINT_STATUS_VALID,
    read_runtime_endpoint_files_result,
)
from web.bootstrap.launcher_health import probe_runtime_health_result  # noqa: E402
from web.bootstrap.launcher_lock_result import LOCK_STATUS_MISSING, read_runtime_lock_result_from_path  # noqa: E402
from web.bootstrap.launcher_paths import resolve_runtime_state_paths, runtime_lock_path  # noqa: E402
from web.bootstrap.launcher_runtime_lock import is_runtime_lock_active, runtime_lock_mutation_guard  # noqa: E402
from web.bootstrap.sample_http import BASE, SampleClient, SampleProgress  # noqa: E402
from web.bootstrap.sample_injection import SampleInjector  # noqa: E402

_SYSTEM_METADATA_TABLES = frozenset({
    "sqlite_sequence", "SchemaVersion", "ScheduleConfig", "OperationLogs", "SystemJobState",
    "WorkbenchSourceRevisions", "WorkbenchPlanIdentityClock", "WorkbenchExecutionLedgerClock",
})
_TERMINAL_RUN_STATES = ("complete", "partial", "failed", "cancelled", "interrupted")
_STALE_STATE_KEYS = ("host_path", "port_path", "db_path", "contract_path", "error_path")


def _normalize_db_path(path: Union[str, Path]) -> str:
    raw = str(path).strip()
    if not raw:
        raise RuntimeError("DB path is empty.")
    return os.path.normcase(os.path.abspath(raw))


def _resolve_target_db_path(repo_root: Path, explicit_db_path: str) -> str:
    raw = explicit_db_path.strip() or (os.environ.get("APS_DB_PATH") or "").strip()
    return _normalize_db_path(raw) if raw else _normalize_db_path(repo_root / "db" / "aps.db")


def _clean_stale_runtime_state_files(paths: Dict[str, str]) -> None:
    lock_path = runtime_lock_path(paths["state_dir"])
    with runtime_lock_mutation_guard(lock_path):
        lock_res = read_runtime_lock_result_from_path(lock_path, state_dir=paths["state_dir"])
        if lock_res.status != LOCK_STATUS_MISSING and (
            not lock_res.ok or lock_res.payload is None or is_runtime_lock_active(lock_res.payload)
        ):
            raise RuntimeError(
                f"Detected active or ambiguous APS runtime lock ({lock_path}, status={lock_res.status}); refusing to remove runtime contract files or start a concurrent instance."
            )
        for key in _STALE_STATE_KEYS:
            remove_fixed_file(paths[key], missing_ok=True, allow_symlink=False)


def _verify_live_repo_instance(repo_root: Path, target_db_path: str, timeout_s: float = 2.0) -> Optional[Dict[str, Any]]:
    normalized_target_db = _normalize_db_path(target_db_path)
    paths = resolve_runtime_state_paths(str(repo_root))
    ep = read_runtime_endpoint_files_result(paths["state_dir"])
    contract = read_runtime_contract_result(str(repo_root))
    if (
        ep.host_status == ENDPOINT_STATUS_MISSING and ep.port_status == ENDPOINT_STATUS_MISSING
        and contract.status == CONTRACT_STATUS_MISSING and not os.path.lexists(paths["db_path"])
    ):
        return None

    if (
        ep.host_status != ENDPOINT_STATUS_VALID or ep.port_status != ENDPOINT_STATUS_VALID
        or contract.status != CONTRACT_STATUS_VALID or contract.payload is None
    ):
        candidates: List[Tuple[str, int]] = []
        if ep.host_status == ENDPOINT_STATUS_VALID and ep.port_status == ENDPOINT_STATUS_VALID:
            candidates.append((ep.host, ep.port))
        if contract.payload is not None:
            pair = (contract.payload["host"], contract.payload["port"])
            if pair not in candidates:
                candidates.append(pair)
        if not any(probe_runtime_health_result(f"http://{h}:{p}", timeout_s=timeout_s).ok for h, p in candidates):
            return None
        ep = read_runtime_endpoint_files_result(paths["state_dir"])
        contract = read_runtime_contract_result(str(repo_root))
        if (
            ep.host_status != ENDPOINT_STATUS_VALID or ep.port_status != ENDPOINT_STATUS_VALID
            or contract.status != CONTRACT_STATUS_VALID or contract.payload is None
        ):
            raise RuntimeError(
                "Detected a healthy APS endpoint, but repo runtime contract/endpoint files are missing "
                "or corrupted; refusing to reuse an unverified instance."
            )

    contract_payload = contract.payload
    contract_host, contract_port = contract_payload["host"], contract_payload["port"]
    base_url = f"http://{ep.host}:{ep.port}"
    health = probe_runtime_health_result(base_url, timeout_s=timeout_s)
    if not health.ok or health.payload is None:
        if (contract_host, contract_port) != (ep.host, ep.port):
            if probe_runtime_health_result(f"http://{contract_host}:{contract_port}", timeout_s=timeout_s).ok:
                raise RuntimeError(
                    f"Runtime contract endpoint ({contract_host}:{contract_port}) disagrees with endpoint files "
                    f"({ep.host}:{ep.port}); refusing to reuse ambiguous live instance."
                )
        return None

    if contract_host != ep.host or contract_port != ep.port:
        raise RuntimeError(
            f"Runtime contract endpoint ({contract_host}:{contract_port}) does not match endpoint files "
            f"({ep.host}:{ep.port}); refusing to reuse instance."
        )

    health_payload = health.payload
    raw_pid = health_payload.get("pid")
    if (
        health_payload.get("instance_id") != contract_payload["instance_id"]
        or type(raw_pid) is not int or raw_pid != contract_payload["pid"]
    ):
        raise RuntimeError(
            "Live /system/health instance_id or pid does not match repo aps_runtime.json; "
            "refusing to reuse or overwrite foreign APS instance."
        )

    contract_db_raw = contract_payload.get("db_path")
    if not isinstance(contract_db_raw, str) or not contract_db_raw.strip() or _normalize_db_path(contract_db_raw) != normalized_target_db:
        raise RuntimeError(
            f"Repo aps_runtime.json db_path is {contract_db_raw!r}, which does not match target DB {normalized_target_db}; refusing to reuse the instance."
        )

    try:
        recorded_db = _normalize_db_path(read_fixed_text(paths["db_path"]))
    except (FileNotFoundError, OSError, UnicodeError) as exc:
        raise RuntimeError(f"Current repo runtime DB contract file is missing or unreadable ({paths['db_path']}): {exc}") from exc
    if recorded_db != normalized_target_db:
        raise RuntimeError(
            f"Current repo runtime DB file points to {recorded_db}, but target DB is {normalized_target_db}; refusing to reuse the instance."
        )

    live_db_raw = health_payload.get("db_path")
    if not isinstance(live_db_raw, str) or not live_db_raw.strip() or _normalize_db_path(live_db_raw) != normalized_target_db:
        raise RuntimeError(
            f"Live APS /system/health db_path is {live_db_raw!r}, which does not match target DB {normalized_target_db}; refusing to reuse the instance."
        )
    return {"host": ep.host, "port": ep.port, "base_url": base_url, "instance_id": contract_payload["instance_id"]}


def _existing_server(repo_root: Path, db_path: str) -> Dict[str, Any]:
    instance = _verify_live_repo_instance(repo_root, db_path)
    if instance is not None:
        return {**instance, "started_now": False}
    paths = resolve_runtime_state_paths(str(repo_root))
    if any(os.path.lexists(paths[key]) for key in ("host_path", "port_path", "db_path", "contract_path")):
        raise RuntimeError("Repo runtime contract/endpoint files are missing, corrupted, or stale. Restart APS explicitly before viewing.")
    raise RuntimeError("No healthy APS instance belongs to this repo. Start the service explicitly before viewing.")


def _resolve_project_python(repo_root: Path) -> Path:
    python_path = repo_root / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    if not python_path.is_file():
        raise RuntimeError(f"Project virtualenv interpreter not found: {python_path}")
    return python_path


def _start_server_if_needed(repo_root: Path, host: str, port: int, wait_seconds: int, db_path: str) -> Dict[str, Any]:
    normalized_db_path = _normalize_db_path(db_path)
    existing = _verify_live_repo_instance(repo_root, normalized_db_path)
    if existing is not None:
        return {**existing, "started_now": False}

    _clean_stale_runtime_state_files(resolve_runtime_state_paths(str(repo_root)))
    project_python = _resolve_project_python(repo_root)
    env: Dict[str, str] = {
        **os.environ, "APS_ENV": "development", "FLASK_ENV": "development", "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8", "APS_HOST": host, "APS_PORT": str(port), "APS_DB_PATH": normalized_db_path,
    }
    proc = subprocess.Popen([str(project_python), "app.py"], cwd=str(repo_root), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + max(1, wait_seconds)
    while True:
        verified = _verify_live_repo_instance(repo_root, normalized_db_path)
        if verified is not None:
            return {**verified, "started_now": True}
        rc = proc.poll()
        if rc is not None:
            raise RuntimeError(f"APS server exited prematurely with code {rc} before becoming healthy.")
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Timed out after {wait_seconds}s waiting for verified APS instance for DB {normalized_db_path}.")
        time.sleep(0.5)


def _assert_isolated_empty_demo_db(db_path: Path, *, before_server_start: bool) -> None:
    if before_server_start and not db_path.exists():
        return
    if not db_path.exists():
        raise RuntimeError(f"Expected initialized database at {db_path}, but file does not exist.")
    with closing(sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        for (table_name,) in rows:
            if table_name in _SYSTEM_METADATA_TABLES:
                continue
            quoted = '"' + table_name.replace('"', '""') + '"'
            if conn.execute(f"SELECT 1 FROM {quoted} LIMIT 1").fetchone() is not None:
                raise RuntimeError(
                    f"Refusing rerun on non-empty database {db_path}: table {table_name!r} already contains data. Specify a fresh isolated --db-path."
                )


def _build_route_demo_blueprint() -> Dict[str, Any]:
    p = "ROUTEDEMO_"
    part_a, part_b = f"{p}PA", f"{p}PB"
    base_day = date.today() + timedelta(days=1)
    day_periods = [{"start": "08:00", "end": "12:00", "day_offset": 0}, {"start": "13:00", "end": "17:00", "day_offset": 0}]
    short_periods = [{"start": "08:00", "end": "10:00", "day_offset": 0}]
    in_skills = [f"{p}OT_IN_1", f"{p}OT_IN_2"]

    def work_day(offset: int, periods: List[Dict[str, Any]], note: Optional[str]) -> Dict[str, Any]:
        return {"date": (base_day + timedelta(days=offset)).isoformat(), "fields": {"type": "work", "eff": 100, "allowNormal": "yes", "allowUrgent": "yes", "periods": periods, "note": note}}

    def in_op(seq: int, code: str, unit_h: float) -> Dict[str, Any]:
        return {"seq": seq, "op_type_code": f"{p}{code}", "source": "internal", "supplier_code": None, "setup_hours": 0.5, "unit_hours": unit_h, "external_days": None}

    def ex_op(seq: int, code: str) -> Dict[str, Any]:
        return {"seq": seq, "op_type_code": f"{p}{code}", "source": "external", "supplier_code": f"{p}S001", "setup_hours": None, "unit_hours": None, "external_days": None}

    def batch_row(code: str, part: str, qty: int, due_off: int, prio: str, remark: str) -> Dict[str, Any]:
        return {"business_code": f"{p}{code}", "part_code": part, "fields": {"quantity": qty, "due_date": (base_day + timedelta(days=due_off)).isoformat(), "priority": prio, "ready_status": "yes", "ready_date": base_day.isoformat(), "remark": remark}, "materials": []}

    calendar_days: List[Dict[str, Any]] = [
        work_day(0, day_periods, "demo"),
        work_day(1, short_periods, "short"),
        {"date": (base_day + timedelta(days=2)).isoformat(), "fields": {"type": "rest", "eff": 100, "allowNormal": "no", "allowUrgent": "no", "periods": [], "note": "stop"}},
        *[work_day(offset, day_periods, None) for offset in range(3, 12)],
    ]
    return {
        "resources": {
            "op_types": [
                {"business_code": f"{p}OT_IN_1", "label": "MILL", "fields": {"category": "internal", "remark": None}, "relationships": {}},
                {"business_code": f"{p}OT_IN_2", "label": "FIT", "fields": {"category": "internal", "remark": None}, "relationships": {}},
                {"business_code": f"{p}OT_EX_1", "label": "PRINT", "fields": {"category": "external", "default_merge_mode": "merged", "remark": None}, "relationships": {}},
                {"business_code": f"{p}OT_EX_2", "label": "QAEXT", "fields": {"category": "external", "default_merge_mode": "merged", "remark": None}, "relationships": {}},
            ],
            "machine_groups": [], "shift_profiles": [], "materials": [],
            "machines": [
                {"business_code": f"{p}{mc}", "label": label, "fields": {"status": "active", "category": cat, "remark": None}, "relationships": {"op_type_codes": [f"{p}{ot}"]}}
                for mc, label, cat, ot in (("MC001", "MILL-01", "MILL", "OT_IN_1"), ("MC002", "MILL-02", "MILL", "OT_IN_1"), ("MC003", "FIT-01", "FIT", "OT_IN_2"))
            ],
            "operators": [
                {"business_code": f"{p}{op}", "label": name, "fields": {"status": "active", "remark": None}, "relationships": {"skill_codes": in_skills}}
                for op, name in (("OP001", "Alice"), ("OP002", "Bob"), ("OP003", "Carol"))
            ],
            "suppliers": [{"business_code": f"{p}S001", "label": "Vendor-Ext", "fields": {"status": "active", "default_days": 1.5, "remark": None}, "relationships": {"op_type_codes": [f"{p}OT_EX_1", f"{p}OT_EX_2"]}}],
        },
        "operator_machine_permissions": [
            {"operator_code": f"{p}OP001", "machine_codes": [f"{p}MC001", f"{p}MC002"]},
            {"operator_code": f"{p}OP002", "machine_codes": [f"{p}MC002", f"{p}MC003"]},
            {"operator_code": f"{p}OP003", "machine_codes": [f"{p}MC001", f"{p}MC003"]},
        ],
        "calendar_days": calendar_days, "operator_calendar_days": [], "machine_downtimes": [],
        "parts": [
            {"business_code": part_a, "label": "Demo Part A", "remark": None, "operations": [in_op(5, "OT_IN_1", 0.5), in_op(10, "OT_IN_2", 0.4), in_op(20, "OT_IN_1", 0.5), ex_op(35, "OT_EX_1"), ex_op(40, "OT_EX_2")], "groups": [{"sequences": [35, 40], "supplier_code": f"{p}S001", "total_days": 3.0}]},
            {"business_code": part_b, "label": "Demo Part B", "remark": None, "operations": [in_op(5, "OT_IN_2", 0.4), in_op(10, "OT_IN_1", 0.5)], "groups": []},
        ],
        "batches": [
            batch_row("B001", part_a, 4, 8, "critical", "Demo A critical"),
            batch_row("B002", part_a, 2, 10, "urgent", "Demo A urgent"),
            batch_row("B003", part_a, 1, 15, "normal", "Demo A normal"),
            batch_row("B101", part_b, 6, 8, "urgent", "Demo B urgent"),
            batch_row("B102", part_b, 3, 12, "normal", "Demo B normal"),
        ],
        "schedule_window": {"start_date": base_day.isoformat(), "end_date": (base_day + timedelta(days=20)).isoformat(), "ready_check": True, "missing_resource_policy": "auto_assign", "completed_policy": "preserve_actuals"},
    }


def _seed_and_schedule(base_url: str, wait_seconds: int) -> Dict[str, Any]:
    client = SampleClient(base_url, request_prefix="route-demo-")
    seed = SampleInjector(client, SampleProgress(None, client), _build_route_demo_blueprint()).inject()
    preflight_req = {**seed["schedule_window"], "batch_refs": sorted(seed["refs"]["batch"].values()), "hold_window": None}
    preflight = client.post(BASE + "/scheduling/preflight", preflight_req)["data"]
    if preflight["blockers"]:
        raise RuntimeError(f"Route demo preflight reported blockers: {preflight['blockers']}")
    preview = client.post(BASE + "/scheduling/runs/preview", {"input_ref": preflight["input_ref"]})["data"]
    if preview["write_context"]["capabilities"]["scheduling.run"] is not True:
        raise RuntimeError(f"Route demo run preview denied: {preview['write_context']['blocked_reasons']}")
    accepted = client.post(
        BASE + "/scheduling/runs",
        {"input_ref": preflight["input_ref"], "write_token": preview["write_context"]["write_token"], "request_key": "route-demo-" + uuid.uuid4().hex},
        status=202,
    )
    run_ref = str(accepted["run_ref"])
    deadline = time.monotonic() + max(wait_seconds, 120)
    while True:
        run = client.get(BASE + "/scheduling/runs/" + run_ref)
        if run["state"] in _TERMINAL_RUN_STATES:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Timed out waiting for scheduling run {run_ref} to finish.")
        time.sleep(0.5)
    if run["state"] not in ("complete", "partial"):
        raise RuntimeError(f"Scheduling run {run_ref} did not complete: {run}")
    catalog = client.get(BASE + "/scheduling/runs/" + run_ref + "/candidates?size=50")
    complete = [row for row in catalog["candidates"] if row["status"] == "completed" and row["completeness"] == "complete"]
    if not complete:
        raise RuntimeError(f"Scheduling run {run_ref} produced no complete candidate: {catalog}")
    candidate_ref = str(complete[0]["candidate_ref"])
    adopt_preview = client.post(BASE + "/scheduling/candidates/" + candidate_ref + "/adopt-preview", {})["data"]
    if adopt_preview["validation"]["can_adopt"] is not True or adopt_preview["scope_complete"] is not True:
        raise RuntimeError(f"Candidate {candidate_ref} failed adopt-preview: {adopt_preview['validation']}")
    receipt = client.command(BASE + "/scheduling/candidates/" + candidate_ref + "/adopt", adopt_preview["write_context"], {"confirm": True, "reason": "ROUTEDEMO 隔离库样例重跑", "declared_operator": "route_demo"})
    official_plan = receipt["data"]["official_plan"]
    return {"version": int(official_plan["version"]), "plan_ref": str(official_plan["plan_ref"])}


def _read_json(url: str) -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError) as exc:
        raise RuntimeError(f"Failed to read workbench plan API: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("ok") is not True or not isinstance(payload.get("data"), dict):
        raise RuntimeError("Workbench plan API returned an invalid response.")
    return payload["data"]


def _read_existing_plan(base_url: str, expected_version: Optional[int] = None) -> Dict[str, Any]:
    catalog = _read_json(base_url + "/api/workbench/v1/plans?collection=history&size=1")
    official = [item for item in catalog.get("plans", []) if isinstance(item, dict) and item.get("kind") == "official"]
    if len(official) != 1:
        raise RuntimeError("No unique latest official plan is available; no sample data was created by this read.")
    plan = official[0]
    version = plan.get("version")
    if type(version) is not int or version <= 0 or (expected_version is not None and version != expected_version):
        raise RuntimeError("Latest service plan version does not match the requested version; refusing substitution.")
    plan_ref, caps = plan.get("plan_ref"), plan.get("capabilities")
    if not isinstance(plan_ref, str) or not plan_ref or not isinstance(caps, dict) or caps.get("view") is not True:
        raise RuntimeError("Latest official plan cannot be viewed; its identity or details are unavailable.")
    workspace = _read_json(base_url + "/api/workbench/v1/plans/" + urllib.parse.quote(plan_ref, safe="") + "/workspace")
    selected = workspace.get("plan")
    if not isinstance(selected, dict) or selected.get("plan_ref") != plan_ref or selected.get("version") != version or selected.get("kind") != "official":
        raise RuntimeError("Workbench returned a different plan identity; refusing substitution.")
    tasks, task_count, tasks_complete = workspace.get("tasks"), workspace.get("task_count"), workspace.get("tasks_complete")
    if (
        not isinstance(tasks, list) or type(task_count) is not int or task_count <= 0 or type(tasks_complete) is not bool
        or (len(tasks) != task_count if tasks_complete else not (0 < len(tasks) < task_count))
    ):
        raise RuntimeError("工作台甘特接口返回的任务列表与计划任务总数不一致。")
    navigation = {"version": 1, "view": "gantt", "context": {"plan_ref": plan_ref}}
    url = base_url + "/workbench?" + urllib.parse.urlencode({"view": "gantt", "nav": json.dumps(navigation, separators=(",", ":"))})
    return {"version": version, "plan_ref": plan_ref, "task_count": task_count, "url": url}


def _open_url(url: str) -> None:
    try:
        if webbrowser.open(url, new=2):
            return
    except (OSError, webbrowser.Error):
        pass
    if os.name == "nt":
        try:
            os.startfile(url)  # type: ignore[attr-defined]
        except OSError:
            pass


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="启动、查看现有结果或在全新/空业务表隔离数据库重跑 APS 样例。")
    p.add_argument("command", nargs="?", choices=("rerun", "start-only", "view-only"), default="start-only")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--db-path", default="")
    p.add_argument("--wait-seconds", type=int, default=60)
    p.add_argument("--no-open", action="store_true")
    args = p.parse_args(argv)

    if args.command == "rerun" and not args.db_path.strip():
        p.error("rerun requires an explicit --db-path for an isolated empty sample database; defaults and APS_DB_PATH are not sufficient.")

    repo_root = _find_repo_root()
    target_db_path = _resolve_target_db_path(repo_root, args.db_path)
    if args.command == "rerun":
        _assert_isolated_empty_demo_db(Path(target_db_path), before_server_start=True)

    endpoint = (
        _existing_server(repo_root, target_db_path) if args.command == "view-only"
        else _start_server_if_needed(repo_root, args.host, args.port, args.wait_seconds, target_db_path)
    )
    endpoint_host, endpoint_port = endpoint["host"], endpoint["port"]
    endpoint_base_url, started_now = endpoint["base_url"].rstrip("/"), endpoint["started_now"]

    if args.command == "start-only":
        url = endpoint_base_url + "/"
        if not args.no_open:
            _open_url(url)
        print(json.dumps({"ok": True, "mode": "start-only", "repo_root": repo_root.as_posix(), "server_started_now": started_now, "host": endpoint_host, "port": endpoint_port, "url": url}, ensure_ascii=True))
        return 0

    if args.command == "view-only":
        existing = _read_existing_plan(endpoint_base_url)
        if not args.no_open:
            _open_url(existing["url"])
        print(json.dumps({**existing, "ok": True, "mode": "view-only", "repo_root": repo_root.as_posix(), "server_started_now": False, "host": endpoint_host, "port": endpoint_port}, ensure_ascii=True))
        return 0

    _assert_isolated_empty_demo_db(Path(target_db_path), before_server_start=False)
    seeded = _seed_and_schedule(endpoint_base_url, wait_seconds=args.wait_seconds)
    verified = _read_existing_plan(endpoint_base_url, expected_version=seeded["version"])
    if verified["plan_ref"] != seeded["plan_ref"]:
        raise RuntimeError("Latest service official plan_ref does not match adopted plan_ref; refusing substitution.")
    if not args.no_open:
        _open_url(verified["url"])
    print(json.dumps({"ok": True, "mode": "rerun", "repo_root": repo_root.as_posix(), "server_started_now": started_now, "host": endpoint_host, "port": endpoint_port, **verified}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
