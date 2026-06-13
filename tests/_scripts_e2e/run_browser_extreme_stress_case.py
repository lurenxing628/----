"""前台浏览器极限压测造数脚本。

这个脚本复用 run_synthetic_case.py 里的合成数据底座，再叠加更贴近前台复验的复杂因素：
- 多品种、多批次、多工序、混合自制/外协与合并外协组；
- 设备停机、人员日历、短班、加班、假期和效率波动；
- 交期挤压、短工序、长工序、瓶颈资源碰撞；
- 隐藏的失败边界批次，便于手工切换筛选后复验错误提示。

它只生成隔离临时库，不启动服务，也不污染仓库 db/。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import shutil
import sqlite3
import sys
import tempfile
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


def _find_repo_root() -> str:
    probe = os.path.dirname(os.path.abspath(__file__))
    while probe != os.path.dirname(probe):
        if os.path.exists(os.path.join(probe, "app.py")) and os.path.exists(os.path.join(probe, "schema.sql")):
            return probe
        probe = os.path.dirname(probe)
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


REPO_ROOT = _find_repo_root()
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _load_synthetic_helpers():
    path = os.path.join(REPO_ROOT, "tests", "_scripts_e2e", "run_synthetic_case.py")
    spec = importlib.util.spec_from_file_location("aps_synthetic_case_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 run_synthetic_case.py 里的造数函数")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SYN = _load_synthetic_helpers()


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _connect_file_db(db_path: str) -> sqlite3.Connection:
    _ensure_dir(os.path.dirname(db_path) or ".")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _copy_excel_templates(template_dir: str) -> None:
    src = os.path.join(REPO_ROOT, "templates_excel")
    if os.path.exists(template_dir):
        shutil.rmtree(template_dir)
    shutil.copytree(src, template_dir)


def _table_count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(1) AS c FROM {table}").fetchone()
    return int(row["c"] if row else 0)


def _seed_resource_teams(conn: sqlite3.Connection) -> None:
    teams = [
        ("TEAM-TURN", "压测车削班"),
        ("TEAM-MILL", "压测铣磨班"),
        ("TEAM-ASSY", "压测装配班"),
        ("TEAM-NIGHT", "压测夜班支援"),
    ]
    for team_id, name in teams:
        conn.execute(
            "INSERT OR IGNORE INTO ResourceTeams (team_id, name, status, remark) VALUES (?, ?, 'active', ?)",
            (team_id, name, "browser extreme stress"),
        )

    machines = [str(r["machine_id"]) for r in conn.execute("SELECT machine_id FROM Machines ORDER BY machine_id").fetchall()]
    operators = [str(r["operator_id"]) for r in conn.execute("SELECT operator_id FROM Operators ORDER BY operator_id").fetchall()]
    for idx, machine_id in enumerate(machines):
        conn.execute("UPDATE Machines SET team_id=? WHERE machine_id=?", (teams[idx % len(teams)][0], machine_id))
    for idx, operator_id in enumerate(operators):
        conn.execute("UPDATE Operators SET team_id=? WHERE operator_id=?", (teams[(idx + 1) % len(teams)][0], operator_id))
    conn.commit()


def _override_global_calendar(conn: sqlite3.Connection, *, start_dt: datetime, calendar_days: int) -> None:
    for offset in range(int(calendar_days)):
        d = start_dt.date() - timedelta(days=2) + timedelta(days=offset)
        if d.weekday() < 5 and offset % 13 == 0:
            conn.execute(
                """
                UPDATE WorkCalendar
                SET day_type='workday', shift_start='08:00', shift_end='12:00',
                    shift_hours=4, efficiency=0.72, allow_normal='yes', allow_urgent='yes',
                    remark='extreme-stress 短班'
                WHERE date=?
                """,
                (d.isoformat(),),
            )
        elif d.weekday() < 5 and offset % 17 == 0:
            conn.execute(
                """
                UPDATE WorkCalendar
                SET day_type='holiday', shift_start='00:00', shift_end='00:00',
                    shift_hours=0, efficiency=1.0, allow_normal='no', allow_urgent='no',
                    remark='extreme-stress 临时停工'
                WHERE date=?
                """,
                (d.isoformat(),),
            )
        elif d.weekday() == 5 and offset % 11 == 0:
            conn.execute(
                """
                UPDATE WorkCalendar
                SET day_type='overtime', shift_start='08:00', shift_end='17:00',
                    shift_hours=9, efficiency=0.88, allow_normal='no', allow_urgent='yes',
                    remark='extreme-stress 周末急件加班'
                WHERE date=?
                """,
                (d.isoformat(),),
            )
    conn.commit()


def _seed_operator_calendars(conn: sqlite3.Connection, *, start_dt: datetime, rnd: random.Random) -> None:
    operators = [str(r["operator_id"]) for r in conn.execute("SELECT operator_id FROM Operators ORDER BY operator_id").fetchall()]
    if not operators:
        return

    selected = operators[: max(4, min(len(operators), len(operators) // 2))]
    for idx, operator_id in enumerate(selected):
        leave_day = start_dt.date() + timedelta(days=2 + (idx % 9))
        conn.execute(
            """
            INSERT OR REPLACE INTO OperatorCalendar
            (operator_id, date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, 'leave', '00:00', '00:00', 0, 1.0, 'no', 'no', ?)
            """,
            (operator_id, leave_day.isoformat(), "extreme-stress 请假"),
        )

        short_day = start_dt.date() + timedelta(days=5 + (idx % 11))
        conn.execute(
            """
            INSERT OR REPLACE INTO OperatorCalendar
            (operator_id, date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, 'short_shift', '10:00', '15:00', 5, ?, 'yes', 'yes', ?)
            """,
            (operator_id, short_day.isoformat(), round(rnd.uniform(0.62, 0.82), 3), "extreme-stress 低效短班"),
        )

        overtime_day = start_dt.date() + timedelta(days=7 + (idx % 13))
        conn.execute(
            """
            INSERT OR REPLACE INTO OperatorCalendar
            (operator_id, date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, 'overtime', '08:00', '18:00', 10, ?, 'yes', 'yes', ?)
            """,
            (operator_id, overtime_day.isoformat(), round(rnd.uniform(0.9, 1.08), 3), "extreme-stress 支援加班"),
        )
    conn.commit()


def _machine_operator_for_op(master: Dict[str, Any], op_type_id: Any, fallback_index: int) -> Tuple[Optional[str], Optional[str]]:
    machines_by_op = master.get("machines_by_op") or {}
    operators_by_machine = master.get("operators_by_machine") or {}
    machines = list(machines_by_op.get(str(op_type_id or ""), []) or [])
    if not machines:
        for value in machines_by_op.values():
            machines.extend(list(value or []))
    if not machines:
        return None, None
    machine_id = machines[int(fallback_index) % len(machines)]
    operators = list(operators_by_machine.get(machine_id) or [])
    operator_id = operators[int(fallback_index) % len(operators)] if operators else None
    return machine_id, operator_id


def _intensify_batches(
    conn: sqlite3.Connection,
    *,
    batch_ids: List[str],
    start_dt: datetime,
    master: Dict[str, Any],
    rnd: random.Random,
) -> None:
    priority_cycle = ["critical", "urgent", "normal", "urgent", "normal"]
    for idx, batch_id in enumerate(batch_ids):
        qty = 8 + ((idx * 17) % 240)
        if idx % 23 == 0:
            qty = 1
        due = start_dt.date() + timedelta(days=4 + (idx % 18))
        ready = start_dt.date() + timedelta(days=idx % 5)
        priority = priority_cycle[idx % len(priority_cycle)]
        conn.execute(
            """
            UPDATE Batches
            SET quantity=?, due_date=?, priority=?, ready_status='yes', ready_date=?, remark=?
            WHERE batch_id=?
            """,
            (
                int(qty),
                due.isoformat(),
                priority,
                ready.isoformat(),
                "extreme-stress 主数据：交期挤压/资源碰撞/日历避让",
                batch_id,
            ),
        )

    placeholders = ",".join(["?"] * len(batch_ids))
    rows = conn.execute(
        f"""
        SELECT id, batch_id, seq, source, op_type_id
        FROM BatchOperations
        WHERE batch_id IN ({placeholders})
        ORDER BY batch_id, seq, id
        """,
        tuple(batch_ids),
    ).fetchall()
    for idx, row in enumerate(rows):
        source = str(row["source"] or "internal")
        if source == "external":
            ext_days = [0.5, 1.0, 1.75, 2.5, 4.0][idx % 5]
            conn.execute(
                "UPDATE BatchOperations SET ext_days=?, status='pending' WHERE id=?",
                (float(ext_days), int(row["id"])),
            )
            continue

        machine_id, operator_id = _machine_operator_for_op(master, row["op_type_id"], idx)
        if idx % 19 == 0:
            setup_hours = 0.0
            unit_hours = round(rnd.uniform(0.015, 0.04), 4)
        elif idx % 11 == 0:
            setup_hours = round(rnd.uniform(1.2, 2.4), 3)
            unit_hours = round(rnd.uniform(0.055, 0.12), 4)
        elif idx % 7 == 0:
            setup_hours = round(rnd.uniform(0.35, 0.9), 3)
            unit_hours = round(rnd.uniform(0.03, 0.065), 4)
        else:
            setup_hours = round(rnd.uniform(0.08, 0.55), 3)
            unit_hours = round(rnd.uniform(0.008, 0.045), 4)

        conn.execute(
            """
            UPDATE BatchOperations
            SET machine_id=?, operator_id=?, setup_hours=?, unit_hours=?, status='pending'
            WHERE id=?
            """,
            (machine_id, operator_id, float(setup_hours), float(unit_hours), int(row["id"])),
        )
    conn.commit()


def _seed_dense_downtime(conn: sqlite3.Connection, *, start_dt: datetime, rnd: random.Random) -> None:
    machine_ids = [str(r["machine_id"]) for r in conn.execute("SELECT machine_id FROM Machines ORDER BY machine_id").fetchall()]
    if not machine_ids:
        return
    picked = machine_ids[: max(4, min(len(machine_ids), len(machine_ids) // 2))]
    for idx, machine_id in enumerate(picked):
        for repeat in range(2 if idx % 3 else 3):
            start = start_dt + timedelta(days=1 + idx + repeat * 3, hours=[1, 2, 5][repeat % 3])
            end = start + timedelta(hours=[1.5, 2.0, 3.5][(idx + repeat) % 3])
            conn.execute(
                """
                INSERT INTO MachineDowntimes
                (machine_id, scope_type, scope_value, start_time, end_time, reason_code, reason_detail, status)
                VALUES (?, 'machine', ?, ?, ?, 'maintenance', ?, 'active')
                """,
                (
                    machine_id,
                    machine_id,
                    _fmt_dt(start),
                    _fmt_dt(end),
                    "extreme-stress 高密度停机/保养",
                ),
            )
    conn.commit()


def _seed_hidden_failure_edges(
    conn: sqlite3.Connection,
    *,
    part_no: str,
    start_dt: datetime,
    master: Dict[str, Any],
) -> List[str]:
    rows = conn.execute(
        """
        SELECT seq, op_type_id, op_type_name, source, supplier_id, ext_days
        FROM PartOperations
        WHERE part_no=? AND status='active'
        ORDER BY seq
        """,
        (part_no,),
    ).fetchall()
    if not rows:
        return []

    failure_ids: List[str] = []
    statuses = ["no", "partial"] * 6
    for idx, ready_status in enumerate(statuses, start=1):
        batch_id = f"PT-HIDDEN-{idx:03d}"
        failure_ids.append(batch_id)
        conn.execute(
            """
            INSERT INTO Batches
            (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, ready_date, status, remark, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                batch_id,
                part_no,
                "隐藏失败边界零件",
                10 + idx,
                (start_dt.date() + timedelta(days=3 + idx)).isoformat(),
                "urgent" if idx % 2 else "critical",
                ready_status,
                (start_dt.date() + timedelta(days=idx % 3)).isoformat(),
                "extreme-stress 隐藏失败边界：未齐套/部分齐套/缺资源",
                _fmt_dt(start_dt - timedelta(days=idx)),
            ),
        )
        for r in rows[:4]:
            source = str(r["source"] or "internal")
            machine_id = None
            operator_id = None
            supplier_id = r["supplier_id"]
            ext_days = r["ext_days"]
            if source != "external" and idx % 3 != 0:
                machine_id, operator_id = _machine_operator_for_op(master, r["op_type_id"], idx + int(r["seq"]))
            conn.execute(
                """
                INSERT INTO BatchOperations
                (op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source,
                 machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    f"{batch_id}-OP{int(r['seq']):02d}",
                    batch_id,
                    None,
                    int(r["seq"]),
                    r["op_type_id"],
                    r["op_type_name"],
                    source,
                    machine_id,
                    operator_id,
                    supplier_id,
                    0.2,
                    0.5,
                    ext_days if ext_days is not None else 1.0,
                ),
            )
    conn.commit()
    return failure_ids


def _configure_scheduler(conn: sqlite3.Connection, *, algo_mode: str, objective: str, time_budget: int) -> None:
    from core.services.scheduler.config.config_service import ConfigService

    cfg = ConfigService(conn)
    cfg.ensure_defaults()
    cfg.set_strategy("weighted")
    cfg.set_weights(0.35, 0.55, 0.10, require_sum_1=True)
    cfg.set_dispatch("sgs", "atc")
    cfg.set_auto_assign_enabled("no")
    cfg.set_algo_mode(algo_mode)
    cfg.set_objective(objective)
    cfg.set_time_budget_seconds(int(time_budget))
    cfg.set_enforce_ready_default("yes")
    cfg.set_freeze_window("no", 0)
    conn.commit()


def _build_dataset(
    conn: sqlite3.Connection,
    *,
    seed: int,
    parts: int,
    batches_min: int,
    batches_max: int,
    ops_per_part: int,
    calendar_days: int,
    algo_mode: str,
    objective: str,
    time_budget: int,
) -> Dict[str, Any]:
    rnd = random.Random(int(seed))
    tomorrow = date.today() + timedelta(days=1)
    start_dt = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 8, 0, 0)

    _SYN._load_schema(conn)
    _SYN._seed_calendar(conn, start_date=start_dt.date() - timedelta(days=2), days=int(calendar_days), rnd=rnd)
    _override_global_calendar(conn, start_dt=start_dt, calendar_days=int(calendar_days))
    master = _SYN._seed_master_data(conn, rnd=rnd)
    _seed_resource_teams(conn)
    _seed_operator_calendars(conn, start_dt=start_dt, rnd=rnd)
    part_nos = _SYN._seed_parts_routes(
        conn,
        parts=int(parts),
        ops_per_part=int(ops_per_part),
        rnd=rnd,
        master=master,
    )
    batch_ids = _SYN._seed_batches_and_ops(
        conn,
        part_nos=part_nos,
        batches_min=int(batches_min),
        batches_max=int(batches_max),
        ops_per_part=int(ops_per_part),
        start_dt=start_dt,
        rnd=rnd,
        master=master,
    )
    _intensify_batches(conn, batch_ids=batch_ids, start_dt=start_dt, master=master, rnd=rnd)
    _SYN._seed_machine_downtimes(conn, start_dt=start_dt, rnd=rnd, ratio=0.2)
    _seed_dense_downtime(conn, start_dt=start_dt, rnd=rnd)
    failure_ids = _seed_hidden_failure_edges(conn, part_no=part_nos[0], start_dt=start_dt, master=master) if part_nos else []
    _configure_scheduler(conn, algo_mode=algo_mode, objective=objective, time_budget=int(time_budget))

    from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION

    conn.execute(
        "UPDATE SchemaVersion SET version=?, updated_at=CURRENT_TIMESTAMP WHERE id=1",
        (int(CURRENT_SCHEMA_VERSION),),
    )
    conn.commit()

    return {
        "seed": int(seed),
        "start_dt": _fmt_dt(start_dt),
        "main_batch_ids": batch_ids,
        "hidden_failure_batch_ids": failure_ids,
        "scale": {
            "parts": int(parts),
            "main_batches": int(len(batch_ids)),
            "hidden_failure_batches": int(len(failure_ids)),
            "ops_per_part": int(ops_per_part),
            "calendar_days": int(calendar_days),
        },
    }


def _counts(conn: sqlite3.Connection) -> Dict[str, int]:
    tables = [
        "ResourceTeams",
        "OpTypes",
        "Suppliers",
        "Operators",
        "Machines",
        "OperatorMachine",
        "WorkCalendar",
        "OperatorCalendar",
        "MachineDowntimes",
        "Parts",
        "PartOperations",
        "ExternalGroups",
        "Batches",
        "BatchOperations",
        "ScheduleConfig",
    ]
    return {table: _table_count(conn, table) for table in tables}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", default=None, help="压测临时目录；不填则自动创建 /tmp 下目录")
    parser.add_argument("--force", action="store_true", help="允许覆盖 workdir 里的 aps.db 和 templates_excel")
    parser.add_argument("--seed", type=int, default=20260610)
    parser.add_argument("--parts", type=int, default=32)
    parser.add_argument("--batches-min", type=int, default=2)
    parser.add_argument("--batches-max", type=int, default=4)
    parser.add_argument("--ops-per-part", type=int, default=9)
    parser.add_argument("--calendar-days", type=int, default=150)
    parser.add_argument("--algo-mode", choices=["greedy", "improve"], default="greedy")
    parser.add_argument(
        "--objective",
        choices=["min_overdue", "min_tardiness", "min_weighted_tardiness", "min_changeover"],
        default="min_weighted_tardiness",
    )
    parser.add_argument("--time-budget", type=int, default=8)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=61662)
    args = parser.parse_args(argv)

    if args.workdir:
        workdir = os.path.abspath(args.workdir)
        _ensure_dir(workdir)
    else:
        workdir = tempfile.mkdtemp(prefix="aps-browser-extreme-stress.")

    db_path = os.path.join(workdir, "aps.db")
    log_dir = os.path.join(workdir, "logs")
    backup_dir = os.path.join(workdir, "backups")
    template_dir = os.path.join(workdir, "templates_excel")
    artifact_dir = os.path.join(workdir, "browser-artifacts")
    for path in (log_dir, backup_dir, artifact_dir):
        _ensure_dir(path)
    if os.path.exists(db_path):
        if not args.force:
            raise RuntimeError(f"目标临时库已存在，请加 --force 或换一个 --workdir：{db_path}")
        os.remove(db_path)
    _copy_excel_templates(template_dir)

    conn = _connect_file_db(db_path)
    try:
        dataset = _build_dataset(
            conn,
            seed=int(args.seed),
            parts=int(args.parts),
            batches_min=int(args.batches_min),
            batches_max=int(args.batches_max),
            ops_per_part=int(args.ops_per_part),
            calendar_days=int(args.calendar_days),
            algo_mode=str(args.algo_mode),
            objective=str(args.objective),
            time_budget=int(args.time_budget),
        )
        counts = _counts(conn)
    finally:
        conn.close()

    base_url = f"http://{str(args.host)}:{int(args.port)}"
    browser_url = base_url + "/scheduler/?status=pending&only_ready=yes&per_page=300"
    manifest = {
        "workdir": workdir,
        "db_path": db_path,
        "log_dir": log_dir,
        "backup_dir": backup_dir,
        "template_dir": template_dir,
        "artifact_dir": artifact_dir,
        "base_url": base_url,
        "browser_url": browser_url,
        "dataset": dataset,
        "counts": counts,
        "launch_env": {
            "APS_DB_PATH": db_path,
            "APS_LOG_DIR": log_dir,
            "APS_BACKUP_DIR": backup_dir,
            "APS_EXCEL_TEMPLATE_DIR": template_dir,
            "APS_HOST": str(args.host),
            "APS_PORT": str(int(args.port)),
            "SECRET_KEY": "aps-browser-extreme-stress-key",
        },
        "suggested_launch": (
            f"APS_DB_PATH={db_path!r} APS_LOG_DIR={log_dir!r} APS_BACKUP_DIR={backup_dir!r} "
            f"APS_EXCEL_TEMPLATE_DIR={template_dir!r} APS_HOST={str(args.host)!r} "
            f"APS_PORT={str(int(args.port))!r} SECRET_KEY={'aps-browser-extreme-stress-key'!r} python app.py"
        ),
    }

    manifest_path = os.path.join(artifact_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    print(json.dumps({**manifest, "manifest_path": manifest_path}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
