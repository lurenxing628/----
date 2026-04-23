from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import webbrowser
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Optional


def _find_repo_root() -> Path:
    candidates = []
    try:
        candidates.append(Path(__file__).resolve())
    except Exception:
        pass
    try:
        candidates.append(Path.cwd().resolve())
    except Exception:
        pass

    for base in candidates:
        p = base if base.is_dir() else base.parent
        for _ in range(12):
            if (p / "app.py").exists() and (p / "schema.sql").exists():
                return p
            if p.parent == p:
                break
            p = p.parent
    raise RuntimeError("Unable to locate repo root (requires app.py and schema.sql).")


def _ensure_repo_on_path(repo_root: Path) -> None:
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)


def _runtime_probe(repo_root: Path):
    _ensure_repo_on_path(repo_root)
    from web.bootstrap import runtime_probe as runtime_probe_mod

    return runtime_probe_mod


def _normalize_db_path(path: Any) -> str:
    raw = str(path or "").strip()
    if not raw:
        raise RuntimeError("DB path is empty.")
    return os.path.normcase(os.path.abspath(raw))


def _resolve_target_db_path(repo_root: Path, explicit_db_path: str = "") -> str:
    raw = str(explicit_db_path or "").strip()
    if raw:
        return _normalize_db_path(raw)

    env_db_path = str(os.environ.get("APS_DB_PATH") or "").strip()
    if env_db_path:
        return _normalize_db_path(env_db_path)

    return _normalize_db_path(repo_root / "db" / "aps.db")


def _assert_repo_runtime_matches_endpoint(
    runtime_probe_mod,
    repo_root: Path,
    endpoint: Dict[str, Any],
    target_db_path: str,
) -> None:
    runtime = runtime_probe_mod.read_runtime_host_port(str(repo_root))
    if runtime is None:
        raise RuntimeError(
            "Detected a healthy APS endpoint, but current repo runtime host/port files are missing; "
            "cannot prove instance identity. Please restart APS from this repo and retry."
        )

    runtime_host, runtime_port = runtime
    runtime_base_url = str(runtime_probe_mod.build_base_url(runtime_host, runtime_port)).rstrip("/")
    endpoint_base_url = str(endpoint.get("base_url") or "").rstrip("/")
    if runtime_base_url != endpoint_base_url:
        raise RuntimeError(
            "Detected a healthy APS endpoint via preferred host/port, but current repo runtime files point to "
            f"{runtime_base_url} instead of {endpoint_base_url}; refusing to reuse an instance that cannot be "
            "proven to belong to this repo."
        )

    runtime_db_path = runtime_probe_mod.read_runtime_db_path(str(repo_root))
    if not runtime_db_path:
        raise RuntimeError(
            "Current repo runtime DB contract file is missing; cannot verify DB consistency. "
            "Please restart APS from this repo and retry."
        )

    normalized_target_db = _normalize_db_path(target_db_path)
    if runtime_db_path != normalized_target_db:
        raise RuntimeError(
            f"Current repo APS instance is using DB {runtime_db_path}, but runner target DB is "
            f"{normalized_target_db}; refusing to reuse the instance."
        )


def _start_server_if_needed(repo_root: Path, host: str, port: int, wait_seconds: int, db_path: str) -> Dict[str, Any]:
    runtime_probe_mod = _runtime_probe(repo_root)
    normalized_db_path = _normalize_db_path(db_path)
    # Reuse is only allowed when the current repo runtime contract already resolves a healthy endpoint.
    endpoint = runtime_probe_mod.resolve_healthy_endpoint(
        str(repo_root),
        timeout=2.0,
    )
    if endpoint is not None:
        _assert_repo_runtime_matches_endpoint(
            runtime_probe_mod=runtime_probe_mod,
            repo_root=repo_root,
            endpoint=endpoint,
            target_db_path=normalized_db_path,
        )
        reused = dict(endpoint)
        reused["started_now"] = False
        return reused

    runtime_probe_mod.delete_stale_runtime_files(str(repo_root))
    env: Dict[str, str] = dict(os.environ)
    env["APS_HOST"] = str(host)
    env["APS_PORT"] = str(int(port))
    env["APS_DB_PATH"] = normalized_db_path

    if os.name == "nt":
        subprocess.Popen(
            ["cmd", "/c", "start.bat"],
            cwd=str(repo_root),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        # Fallback for non-Windows environments.
        subprocess.Popen(
            [sys.executable, "app.py"],
            cwd=str(repo_root),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    started = dict(
        runtime_probe_mod.wait_for_healthy_runtime_endpoint(
            str(repo_root),
            timeout_s=wait_seconds,
            interval_s=0.5,
        )
    )
    _assert_repo_runtime_matches_endpoint(
        runtime_probe_mod=runtime_probe_mod,
        repo_root=repo_root,
        endpoint=started,
        target_db_path=normalized_db_path,
    )
    started["started_now"] = True
    return started


def _seed_and_schedule(repo_root: Path, db_path: Path, view: str) -> Dict[str, Any]:
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = str(db_path)
    _ensure_repo_on_path(repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.logging import OperationLogger
    from core.services.process import ExternalGroupService
    from core.services.scheduler import BatchService, CalendarService, GanttService, ScheduleService

    ensure_schema(str(db_path), logger=None, schema_path=str(repo_root / "schema.sql"))
    conn = get_connection(str(db_path))
    op_logger = OperationLogger(conn, logger=None)

    prefix = "ROUTEDEMO_"
    part_a = f"{prefix}PA"
    part_b = f"{prefix}PB"

    try:
        # Cleanup previous demo rows for idempotent rerun.
        conn.execute(
            "DELETE FROM Schedule WHERE op_id IN (SELECT id FROM BatchOperations WHERE batch_id LIKE ?)",
            (f"{prefix}%",),
        )
        conn.execute("DELETE FROM BatchOperations WHERE batch_id LIKE ?", (f"{prefix}%",))
        conn.execute("DELETE FROM Batches WHERE batch_id LIKE ?", (f"{prefix}%",))
        conn.execute("DELETE FROM ExternalGroups WHERE part_no LIKE ?", (f"{prefix}%",))
        conn.execute("DELETE FROM PartOperations WHERE part_no LIKE ?", (f"{prefix}%",))
        conn.execute("DELETE FROM Parts WHERE part_no LIKE ?", (f"{prefix}%",))
        conn.execute(
            "DELETE FROM OperatorMachine WHERE operator_id LIKE ? OR machine_id LIKE ?",
            (f"{prefix}%", f"{prefix}%"),
        )
        conn.execute("DELETE FROM Operators WHERE operator_id LIKE ?", (f"{prefix}%",))
        conn.execute("DELETE FROM Machines WHERE machine_id LIKE ?", (f"{prefix}%",))
        conn.execute("DELETE FROM Suppliers WHERE supplier_id LIKE ?", (f"{prefix}%",))
        conn.execute("DELETE FROM OpTypes WHERE op_type_id LIKE ?", (f"{prefix}%",))
        conn.commit()

        # 1) Master data
        conn.execute(
            "INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)",
            (f"{prefix}OT_IN_1", "MILL", "internal"),
        )
        conn.execute(
            "INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)",
            (f"{prefix}OT_IN_2", "FIT", "internal"),
        )
        conn.execute(
            "INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)",
            (f"{prefix}OT_EX_1", "PRINT", "external"),
        )
        conn.execute(
            "INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)",
            (f"{prefix}OT_EX_2", "QAEXT", "external"),
        )

        conn.execute(
            "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status) VALUES (?, ?, ?, ?, ?)",
            (f"{prefix}S001", "Vendor-Print", f"{prefix}OT_EX_1", 1.5, "active"),
        )
        conn.execute(
            "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status) VALUES (?, ?, ?, ?, ?)",
            (f"{prefix}S002", "Vendor-QA", f"{prefix}OT_EX_2", 1.0, "active"),
        )

        conn.execute(
            "INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)",
            (f"{prefix}MC001", "MILL-01", f"{prefix}OT_IN_1", "active"),
        )
        conn.execute(
            "INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)",
            (f"{prefix}MC002", "MILL-02", f"{prefix}OT_IN_1", "active"),
        )
        conn.execute(
            "INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)",
            (f"{prefix}MC003", "FIT-01", f"{prefix}OT_IN_2", "active"),
        )

        conn.execute(
            "INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)",
            (f"{prefix}OP001", "Alice", "active"),
        )
        conn.execute(
            "INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)",
            (f"{prefix}OP002", "Bob", "active"),
        )
        conn.execute(
            "INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)",
            (f"{prefix}OP003", "Carol", "active"),
        )

        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)",
            (f"{prefix}OP001", f"{prefix}MC001"),
        )
        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)",
            (f"{prefix}OP001", f"{prefix}MC002"),
        )
        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)",
            (f"{prefix}OP002", f"{prefix}MC002"),
        )
        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)",
            (f"{prefix}OP002", f"{prefix}MC003"),
        )
        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)",
            (f"{prefix}OP003", f"{prefix}MC001"),
        )
        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)",
            (f"{prefix}OP003", f"{prefix}MC003"),
        )

        # 2) Process templates
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", (part_a, "Demo Part A", "yes"))
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (part_a, 5, f"{prefix}OT_IN_1", "MILL", "internal", None, None, None, 0.0, 0.0, "active"),
        )
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (part_a, 10, f"{prefix}OT_IN_2", "FIT", "internal", None, None, None, 0.0, 0.0, "active"),
        )
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (part_a, 20, f"{prefix}OT_IN_1", "MILL", "internal", None, None, None, 0.0, 0.0, "active"),
        )
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (part_a, 35, f"{prefix}OT_EX_1", "PRINT", "external", f"{prefix}S001", None, f"{part_a}_G1", 0.0, 0.0, "active"),
        )
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (part_a, 40, f"{prefix}OT_EX_2", "QAEXT", "external", f"{prefix}S002", None, f"{part_a}_G1", 0.0, 0.0, "active"),
        )
        conn.execute(
            "INSERT INTO ExternalGroups (group_id, part_no, start_seq, end_seq, merge_mode, total_days, supplier_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"{part_a}_G1", part_a, 35, 40, "separate", None, f"{prefix}S001"),
        )

        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", (part_b, "Demo Part B", "yes"))
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (part_b, 5, f"{prefix}OT_IN_2", "FIT", "internal", None, None, None, 0.0, 0.0, "active"),
        )
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (part_b, 10, f"{prefix}OT_IN_1", "MILL", "internal", None, None, None, 0.0, 0.0, "active"),
        )
        conn.commit()

        eg_svc = ExternalGroupService(conn, op_logger=op_logger)
        eg_svc.set_merge_mode(group_id=f"{part_a}_G1", merge_mode="merged", total_days=3.0)
        conn.commit()

        # 3) Calendar
        base_day = date.today() + timedelta(days=1)
        cal_svc = CalendarService(conn, logger=None, op_logger=op_logger)
        cal_svc.upsert(
            base_day.isoformat(),
            day_type="workday",
            shift_hours=8,
            efficiency=1.0,
            allow_normal="yes",
            allow_urgent="yes",
            remark="demo",
        )
        cal_svc.upsert(
            (base_day + timedelta(days=1)).isoformat(),
            day_type="workday",
            shift_hours=2,
            efficiency=1.0,
            allow_normal="yes",
            allow_urgent="yes",
            remark="short",
        )
        cal_svc.upsert(
            (base_day + timedelta(days=2)).isoformat(),
            day_type="holiday",
            shift_hours=0,
            efficiency=1.0,
            allow_normal="no",
            allow_urgent="no",
            remark="stop",
        )
        conn.commit()

        # 4) Batches
        batch_svc = BatchService(conn, logger=None, op_logger=op_logger)
        batches = [
            (f"{prefix}B001", part_a, 4, (base_day + timedelta(days=1)).isoformat(), "critical", "yes", "Demo A critical"),
            (f"{prefix}B002", part_a, 2, (base_day + timedelta(days=3)).isoformat(), "urgent", "yes", "Demo A urgent"),
            (f"{prefix}B003", part_a, 1, (base_day + timedelta(days=10)).isoformat(), "normal", "yes", "Demo A normal"),
            (f"{prefix}B101", part_b, 6, (base_day + timedelta(days=1)).isoformat(), "urgent", "yes", "Demo B urgent"),
            (f"{prefix}B102", part_b, 3, (base_day + timedelta(days=4)).isoformat(), "normal", "yes", "Demo B normal"),
        ]
        for bid, pn, qty, due, prio, ready, remark in batches:
            batch_svc.create_batch_from_template(
                batch_id=bid,
                part_no=pn,
                quantity=qty,
                due_date=due,
                priority=prio,
                ready_status=ready,
                remark=remark,
                rebuild_ops=True,
            )

        # 5) Assign resources and operation durations
        sch_svc = ScheduleService(conn, logger=None, op_logger=op_logger)

        def assign_internal(op, batch_id: str) -> None:
            name = (op.op_type_name or "").strip()
            seq = int(op.seq or 0)
            if name == "MILL":
                machine = f"{prefix}MC001" if (seq % 2 == 1) else f"{prefix}MC002"
                if batch_id in (f"{prefix}B001", f"{prefix}B002", f"{prefix}B101"):
                    operator = f"{prefix}OP001"
                elif machine == f"{prefix}MC001":
                    operator = f"{prefix}OP003"
                else:
                    operator = f"{prefix}OP002"
            else:
                machine = f"{prefix}MC003"
                operator = f"{prefix}OP002" if batch_id in (f"{prefix}B101", f"{prefix}B102") else f"{prefix}OP003"
            setup = 0.5
            if name == "MILL":
                unit = 1.2 if batch_id in (f"{prefix}B001", f"{prefix}B101") else 0.8
            else:
                unit = 0.6 if batch_id in (f"{prefix}B101", f"{prefix}B102") else 0.4
            sch_svc.update_internal_operation(
                op.id,
                machine_id=machine,
                operator_id=operator,
                setup_hours=setup,
                unit_hours=unit,
            )

        def assign_external(op) -> None:
            seq = int(op.seq or 0)
            sup = op.supplier_id or (f"{prefix}S001" if seq == 35 else f"{prefix}S002")
            sch_svc.update_external_operation(op.id, supplier_id=sup, ext_days=None)

        for bid, *_ in batches:
            for op in batch_svc.list_operations(bid):
                if (op.source or "").strip() == "internal":
                    assign_internal(op, batch_id=bid)
                else:
                    assign_external(op)

        # 6) Run schedule and resolve route URL
        start_dt = f"{base_day.isoformat()} 08:00:00"
        run_ret = sch_svc.run_schedule(
            batch_ids=[x[0] for x in batches],
            start_dt=start_dt,
            created_by="route_demo",
        )
        version = int(run_ret.get("version") or 1)
        min_start = conn.execute(
            "SELECT MIN(start_time) AS st FROM Schedule WHERE version=?",
            (version,),
        ).fetchone()["st"]
        week_start = str(min_start)[:10] if min_start else base_day.isoformat()

        gantt_svc = GanttService(conn, logger=None, op_logger=op_logger)
        data = gantt_svc.get_gantt_tasks(
            view=view,
            week_start=week_start,
            offset_weeks=0,
            version=version,
        )
        task_count = len(data.get("tasks") or [])
        if task_count <= 0:
            raise RuntimeError("No tasks returned from GanttService.")

        return {
            "version": version,
            "week_start": week_start,
            "task_count": task_count,
        }
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _verify_route(host: str, port: int, view: str, week_start: str, version: int) -> int:
    u = (
        f"http://{host}:{int(port)}/scheduler/gantt/data"
        f"?view={view}&week_start={week_start}&version={int(version)}"
    )
    try:
        with urllib.request.urlopen(u, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to fetch gantt data route: {e}") from e

    if not bool(payload.get("success")):
        raise RuntimeError(f"Gantt data route returned success=false: {payload}")
    data = payload.get("data") or {}
    return int(data.get("task_count") or 0)


def _open_url(url: str) -> None:
    try:
        opened = webbrowser.open(url, new=2)
        if opened:
            return
    except Exception:
        pass
    if os.name == "nt":
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            return
        except Exception:
            pass


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Start APS and optionally rerun complex scheduling route demo.")
    p.add_argument(
        "command",
        nargs="?",
        choices=("rerun", "start-only"),
        default="rerun",
        help="rerun: 启动并重跑排产（默认）；start-only: 仅启动项目，不执行排产",
    )
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--view", choices=("machine", "operator"), default="machine")
    p.add_argument("--db-path", default="", help="Target DB path. Priority: --db-path > APS_DB_PATH > repo_root/db/aps.db")
    p.add_argument("--wait-seconds", type=int, default=60)
    p.add_argument("--no-open", action="store_true", help="Do not auto-open browser page.")
    args = p.parse_args(argv)

    repo_root = _find_repo_root()
    target_db_path = _resolve_target_db_path(repo_root, str(args.db_path))

    endpoint = _start_server_if_needed(
        repo_root=repo_root,
        host=str(args.host),
        port=int(args.port),
        wait_seconds=int(args.wait_seconds),
        db_path=target_db_path,
    )
    endpoint_host = str(endpoint["host"])
    endpoint_port = int(endpoint["port"])
    endpoint_base_url = str(endpoint["base_url"]).rstrip("/")
    started_now = bool(endpoint.get("started_now"))

    if str(args.command) == "start-only":
        url = endpoint_base_url + "/"
        if not bool(args.no_open):
            _open_url(url)
        result = {
            "ok": True,
            "mode": "start-only",
            "repo_root": repo_root.as_posix(),
            "server_started_now": started_now,
            "host": endpoint_host,
            "port": endpoint_port,
            "url": url,
        }
        print(json.dumps(result, ensure_ascii=True))
        return 0

    seeded = _seed_and_schedule(
        repo_root=repo_root,
        db_path=Path(target_db_path),
        view=str(args.view),
    )

    route_task_count = _verify_route(
        host=endpoint_host,
        port=endpoint_port,
        view=str(args.view),
        week_start=str(seeded["week_start"]),
        version=int(seeded["version"]),
    )

    url = (
        f"{endpoint_base_url}/scheduler/gantt"
        f"?view={args.view}&week_start={seeded['week_start']}&version={seeded['version']}"
    )
    if not bool(args.no_open):
        _open_url(url)

    result = {
        "ok": True,
        "mode": "rerun",
        "repo_root": repo_root.as_posix(),
        "server_started_now": started_now,
        "host": endpoint_host,
        "port": endpoint_port,
        "view": str(args.view),
        "version": int(seeded["version"]),
        "week_start": str(seeded["week_start"]),
        "task_count": int(seeded["task_count"]),
        "route_task_count": int(route_task_count),
        "url": url,
    }
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
