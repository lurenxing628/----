from __future__ import annotations

"""
合成案例基线脚本（不依赖 Excel）。

目的：
- 生成一套“合理但可复现”的 APS 合成数据（批次/工序/资源/日历/停机/外协组）
- 直接调用现有 `ScheduleService.run_schedule()` 跑排产（simulate=True）
- 输出核心指标：overdue/tardiness/changeover/makespan + 机器/人员利用率与负荷均衡
- 可选导出甘特图 JSON（machine/operator 视图），便于肉眼对比

运行示例：
  python tests/run_synthetic_case.py --mode both --objective min_tardiness --time-budget 20 --export-gantt-dir evidence/Synthetic
"""

import argparse
import json
import os
import random
import sqlite3
import statistics
import sys
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip().replace("/", "-").replace("T", " ").replace("：", ":")
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _connect_in_memory() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _load_schema(conn: sqlite3.Connection) -> None:
    schema_path = os.path.join(REPO_ROOT, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _seed_calendar(conn: sqlite3.Connection, start_date: date, days: int, rnd: random.Random) -> None:
    """
    生成工作日历：
    - 周一~周五：8 小时班次（08:00-16:00），效率 0.85~1.0
    - 周末：不可排产（shift_hours=0）
    """
    for i in range(int(days)):
        d = start_date + timedelta(days=i)
        is_weekend = d.weekday() >= 5
        if is_weekend:
            day_type = "weekend"
            shift_hours = 0.0
            eff = 1.0
        else:
            day_type = "workday"
            shift_hours = 8.0
            eff = float(round(rnd.uniform(0.85, 1.0), 3))
        conn.execute(
            """
            INSERT INTO WorkCalendar (date, day_type, shift_start, shift_end, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d.isoformat(),
                day_type,
                "08:00",
                "16:00",
                float(shift_hours),
                float(eff),
                "yes",
                "yes",
                "synthetic",
            ),
        )
    conn.commit()


def _seed_master_data(conn: sqlite3.Connection, rnd: random.Random) -> Dict[str, Any]:
    """
    生成 OpTypes / Machines / Operators / OperatorMachine / Suppliers。
    返回：dict，包含 internal_op_types, machines_by_op, operators_by_machine 等索引。
    """
    internal_types: List[Tuple[str, str]] = [
        ("OT01", "车削"),
        ("OT02", "铣削"),
        ("OT03", "磨削"),
        ("OT04", "热处理"),
        ("OT05", "装配"),
        ("OT06", "检验"),
    ]
    ext_type = ("OT_EXT", "外协")

    for op_type_id, name in internal_types + [ext_type]:
        conn.execute(
            "INSERT INTO OpTypes (op_type_id, name, category, default_hours, remark) VALUES (?, ?, ?, ?, ?)",
            (op_type_id, name, "internal" if op_type_id != "OT_EXT" else "external", None, "synthetic"),
        )

    # suppliers（外协可引用）
    suppliers = [("SUP01", "外协A"), ("SUP02", "外协B"), ("SUP03", "外协C")]
    for sid, sname in suppliers:
        conn.execute(
            "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status, remark) VALUES (?, ?, ?, ?, ?, ?)",
            (sid, sname, "OT_EXT", 3.0, "active", "synthetic"),
        )

    # machines：每个内部工种 3 台
    machines_by_op: Dict[str, List[str]] = {}
    all_machines: List[str] = []
    for op_type_id, name in internal_types:
        for j in range(1, 4):
            mid = f"M-{op_type_id}-{j}"
            conn.execute(
                "INSERT INTO Machines (machine_id, name, op_type_id, category, status, remark) VALUES (?, ?, ?, ?, ?, ?)",
                (mid, f"{name}{j}", op_type_id, name, "active", "synthetic"),
            )
            machines_by_op.setdefault(op_type_id, []).append(mid)
            all_machines.append(mid)

    # operators：按机器规模生成（保证可覆盖）
    operator_count = max(18, int(len(all_machines) * 1.2))
    operators = [f"O{idx:03d}" for idx in range(1, operator_count + 1)]
    for oid in operators:
        conn.execute(
            "INSERT INTO Operators (operator_id, name, status, remark) VALUES (?, ?, ?, ?)",
            (oid, f"操作员{oid}", "active", "synthetic"),
        )

    # operator-machine 关联：保证每台机器至少 2 人可用
    operators_by_machine: Dict[str, List[str]] = {mid: [] for mid in all_machines}
    for mid in all_machines:
        cand = rnd.sample(operators, k=min(3, len(operators)))
        for x in cand:
            if x not in operators_by_machine[mid]:
                operators_by_machine[mid].append(x)

    # 让每个操作员再额外覆盖一些机器（提升耦合度）
    for oid in operators:
        extra = rnd.sample(all_machines, k=min(3, len(all_machines)))
        for mid in extra:
            if oid not in operators_by_machine[mid]:
                operators_by_machine[mid].append(oid)

    for mid, oids in operators_by_machine.items():
        for oid in oids:
            skill_level = "high" if rnd.random() < 0.15 else "normal"
            is_primary = "yes" if rnd.random() < 0.08 else "no"
            conn.execute(
                "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
                (oid, mid, skill_level, is_primary),
            )

    conn.commit()
    return {
        "internal_op_types": list(internal_types),
        "ext_type": ext_type,
        "suppliers": list(suppliers),
        "machines_by_op": machines_by_op,
        "operators_by_machine": operators_by_machine,
    }


def _seed_parts_routes(
    conn: sqlite3.Connection,
    *,
    parts: int,
    ops_per_part: int,
    rnd: random.Random,
    master: Dict[str, Any],
) -> List[str]:
    """
    生成 Parts / PartOperations / ExternalGroups。
    - 每个零件：ops_per_part 道工序
    - 每个零件：随机 0~1 个“合并外协组（merged）”，长度固定 2 道（连续 seq）
    """
    internal_types: List[Tuple[str, str]] = master["internal_op_types"]
    suppliers: List[Tuple[str, str]] = master["suppliers"]

    part_nos: List[str] = []
    for i in range(1, int(parts) + 1):
        part_no = f"P{i:03d}"
        part_nos.append(part_no)
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
            (part_no, f"品种{part_no}", None, "yes", "synthetic"),
        )

        # 外协组（可选）：随机选 2 个连续 seq
        use_group = rnd.random() < 0.35
        group_id = None
        ext_start = None
        ext_end = None
        if use_group and ops_per_part >= 4:
            ext_start = rnd.randint(2, ops_per_part - 2)
            ext_end = ext_start + 1
            group_id = f"EXTG-{part_no}"
            sid, _ = rnd.choice(suppliers)
            total_days = float(round(rnd.uniform(2.0, 5.0), 2))
            conn.execute(
                """
                INSERT INTO ExternalGroups (group_id, part_no, start_seq, end_seq, merge_mode, total_days, supplier_id, remark)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (group_id, part_no, int(ext_start), int(ext_end), "merged", total_days, sid, "synthetic"),
            )

        for seq in range(1, int(ops_per_part) + 1):
            if group_id and ext_start and ext_end and ext_start <= seq <= ext_end:
                # 外协（合并周期）
                sid, _ = rnd.choice(suppliers)
                conn.execute(
                    """
                    INSERT INTO PartOperations
                    (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (part_no, int(seq), "OT_EXT", "外协", "external", sid, None, group_id, 0.0, 0.0, "active"),
                )
            else:
                # 内部工序
                op_type_id, op_type_name = rnd.choice(internal_types)
                setup = float(round(rnd.uniform(0.1, 0.8), 3))
                unit = float(round(rnd.uniform(0.005, 0.03), 4))
                conn.execute(
                    """
                    INSERT INTO PartOperations
                    (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (part_no, int(seq), op_type_id, op_type_name, "internal", None, None, None, setup, unit, "active"),
                )

    conn.commit()
    return part_nos


def _seed_batches_and_ops(
    conn: sqlite3.Connection,
    *,
    part_nos: List[str],
    batches_min: int,
    batches_max: int,
    ops_per_part: int,
    start_dt: datetime,
    rnd: random.Random,
    master: Dict[str, Any],
) -> List[str]:
    """
    生成 Batches / BatchOperations（把内部工序的人机补全）。
    返回：batch_id 列表。
    """
    machines_by_op: Dict[str, List[str]] = master["machines_by_op"]
    operators_by_machine: Dict[str, List[str]] = master["operators_by_machine"]
    suppliers: List[Tuple[str, str]] = master["suppliers"]

    batch_ids: List[str] = []
    batch_seq = 0
    for part_no in part_nos:
        bcnt = rnd.randint(int(batches_min), int(batches_max))
        for _ in range(bcnt):
            batch_seq += 1
            bid = f"B{batch_seq:05d}"
            batch_ids.append(bid)

            qty = rnd.randint(20, 200)
            pr = rnd.random()
            if pr < 0.1:
                priority = "critical"
            elif pr < 0.3:
                priority = "urgent"
            else:
                priority = "normal"

            # due_date：未来 10~45 天
            due = (start_dt.date() + timedelta(days=rnd.randint(10, 45))).isoformat()
            ready = (start_dt.date() + timedelta(days=rnd.randint(0, 4))).isoformat()

            created_at = _fmt_dt(start_dt - timedelta(days=rnd.randint(1, 20), hours=rnd.randint(0, 8)))

            conn.execute(
                """
                INSERT INTO Batches
                (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, ready_date, status, remark, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (bid, part_no, f"品种{part_no}", int(qty), due, priority, "yes", ready, "pending", "synthetic", created_at),
            )

            # 按模板生成批次工序（保持 seq=1..ops_per_part）
            rows = conn.execute(
                """
                SELECT seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id
                FROM PartOperations
                WHERE part_no = ? AND status = 'active'
                ORDER BY seq
                """,
                (part_no,),
            ).fetchall()

            for r in rows[: int(ops_per_part)]:
                seq = int(r["seq"])
                op_code = f"{bid}-OP{seq:02d}"
                source = str(r["source"] or "internal")
                op_type_id = r["op_type_id"]
                op_type_name = str(r["op_type_name"] or "")

                if source == "external":
                    sid = r["supplier_id"]
                    if not sid:
                        sid, _ = rnd.choice(suppliers)
                    # separate 外协给一个随机周期；merged 由 ExternalGroups.total_days 控制，因此这里允许为空
                    ext_days = r["ext_days"]
                    if ext_days is None and (r["ext_group_id"] is None or str(r["ext_group_id"]).strip() == ""):
                        ext_days = float(round(rnd.uniform(1.0, 4.0), 2))
                    conn.execute(
                        """
                        INSERT INTO BatchOperations
                        (op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source,
                         machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            op_code,
                            bid,
                            None,
                            int(seq),
                            op_type_id,
                            op_type_name,
                            "external",
                            None,
                            None,
                            sid,
                            0.0,
                            0.0,
                            ext_days,
                            "pending",
                        ),
                    )
                else:
                    # 内部工序：补全 machine/operator
                    mids = machines_by_op.get(str(op_type_id) if op_type_id else "", [])
                    if not mids:
                        # 兜底：随机挑一台机器（保证外键存在）
                        mids = [m for v in machines_by_op.values() for m in v]
                    mid = rnd.choice(mids)
                    oids = operators_by_machine.get(mid) or []
                    oid = rnd.choice(oids) if oids else None

                    setup = float(round(rnd.uniform(0.1, 1.2), 3))
                    unit = float(round(rnd.uniform(0.005, 0.04), 4))
                    conn.execute(
                        """
                        INSERT INTO BatchOperations
                        (op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source,
                         machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            op_code,
                            bid,
                            None,
                            int(seq),
                            op_type_id,
                            op_type_name,
                            "internal",
                            mid,
                            oid,
                            None,
                            setup,
                            unit,
                            None,
                            "pending",
                        ),
                    )

    conn.commit()
    return batch_ids


def _seed_machine_downtimes(
    conn: sqlite3.Connection,
    *,
    start_dt: datetime,
    rnd: random.Random,
    ratio: float = 0.12,
) -> None:
    """
    在部分设备上随机插入停机区间（用于验证 downtime_avoid 约束）。
    """
    machine_ids = [str(r["machine_id"]) for r in conn.execute("SELECT machine_id FROM Machines WHERE status='active'").fetchall()]
    if not machine_ids:
        return
    pick = rnd.sample(machine_ids, k=max(1, int(len(machine_ids) * float(ratio))))
    for mid in pick:
        for _ in range(rnd.randint(1, 2)):
            day = rnd.randint(1, 15)
            st = start_dt + timedelta(days=day, hours=rnd.choice([9, 10, 13]))
            et = st + timedelta(hours=rnd.choice([2, 3, 4]))
            conn.execute(
                """
                INSERT INTO MachineDowntimes
                (machine_id, scope_type, scope_value, start_time, end_time, reason_code, reason_detail, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (mid, "machine", mid, _fmt_dt(st), _fmt_dt(et), "maint", "synthetic", "active"),
            )
    conn.commit()


def _calc_utilization_from_schedule(conn: sqlite3.Connection, version: int) -> Dict[str, Any]:
    rows = conn.execute(
        """
        SELECT machine_id, operator_id, start_time, end_time
        FROM Schedule
        WHERE version = ?
        """,
        (int(version),),
    ).fetchall()

    # 利用率口径：默认按“内部工序”窗口计算（避免外协周期把窗口拉长导致 utilization 被动变低）
    # 若内部工序为空，则退化为全量窗口。
    min_st_int: Optional[datetime] = None
    max_et_int: Optional[datetime] = None
    min_st_all: Optional[datetime] = None
    max_et_all: Optional[datetime] = None
    machine_busy: Dict[str, float] = {}
    operator_busy: Dict[str, float] = {}
    for r in rows:
        st = _parse_dt(r["start_time"])
        et = _parse_dt(r["end_time"])
        if not st or not et or et <= st:
            continue
        if min_st_all is None or st < min_st_all:
            min_st_all = st
        if max_et_all is None or et > max_et_all:
            max_et_all = et

        mid = str(r["machine_id"] or "").strip()
        if mid:
            machine_busy[mid] = machine_busy.get(mid, 0.0) + (et - st).total_seconds() / 3600.0
            if min_st_int is None or st < min_st_int:
                min_st_int = st
            if max_et_int is None or et > max_et_int:
                max_et_int = et
        oid = str(r["operator_id"] or "").strip()
        if oid:
            operator_busy[oid] = operator_busy.get(oid, 0.0) + (et - st).total_seconds() / 3600.0
            if min_st_int is None or st < min_st_int:
                min_st_int = st
            if max_et_int is None or et > max_et_int:
                max_et_int = et

    def _hours(a: Optional[datetime], b: Optional[datetime]) -> float:
        if a and b and b > a:
            return (b - a).total_seconds() / 3600.0
        return 0.0

    horizon_hours_internal = _hours(min_st_int, max_et_int)
    horizon_hours_total = _hours(min_st_all, max_et_all)
    horizon_hours = horizon_hours_internal if horizon_hours_internal > 0 else horizon_hours_total

    def _cv(values: List[float]) -> float:
        if not values:
            return 0.0
        m = statistics.fmean(values)
        if m <= 0:
            return 0.0
        if len(values) < 2:
            return 0.0
        return float(statistics.pstdev(values) / m)

    machine_hours = list(machine_busy.values())
    operator_hours = list(operator_busy.values())

    machine_util_avg = float(statistics.fmean([h / horizon_hours for h in machine_hours])) if horizon_hours > 0 and machine_hours else 0.0
    operator_util_avg = float(statistics.fmean([h / horizon_hours for h in operator_hours])) if horizon_hours > 0 and operator_hours else 0.0

    return {
        "horizon_hours_internal": float(round(horizon_hours_internal, 4)),
        "horizon_hours_total": float(round(horizon_hours_total, 4)),
        "horizon_hours_used": float(round(horizon_hours, 4)),
        "machine": {
            "count_used": int(len(machine_busy)),
            "busy_hours_total": float(round(sum(machine_hours), 4)),
            "util_avg": float(round(machine_util_avg, 6)),
            "load_cv": float(round(_cv(machine_hours), 6)),
            "load_max_hours": float(round(max(machine_hours), 4)) if machine_hours else 0.0,
            "load_min_hours": float(round(min(machine_hours), 4)) if machine_hours else 0.0,
        },
        "operator": {
            "count_used": int(len(operator_busy)),
            "busy_hours_total": float(round(sum(operator_hours), 4)),
            "util_avg": float(round(operator_util_avg, 6)),
            "load_cv": float(round(_cv(operator_hours), 6)),
            "load_max_hours": float(round(max(operator_hours), 4)) if operator_hours else 0.0,
            "load_min_hours": float(round(min(operator_hours), 4)) if operator_hours else 0.0,
        },
    }


def _export_gantt(conn: sqlite3.Connection, version: int, start_dt: datetime, days: int, out_dir: str) -> None:
    from core.services.scheduler.gantt_service import GanttService

    os.makedirs(out_dir, exist_ok=True)
    sd = start_dt.date().isoformat()
    ed = (start_dt.date() + timedelta(days=int(days))).isoformat()
    gs = GanttService(conn)
    machine = gs.get_gantt_tasks(view="machine", start_date=sd, end_date=ed, version=int(version))
    operator = gs.get_gantt_tasks(view="operator", start_date=sd, end_date=ed, version=int(version))
    with open(os.path.join(out_dir, f"gantt_tasks_machine_v{version}.json"), "w", encoding="utf-8") as f:
        json.dump(machine, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, f"gantt_tasks_operator_v{version}.json"), "w", encoding="utf-8") as f:
        json.dump(operator, f, ensure_ascii=False, indent=2)


def _run_one(
    conn: sqlite3.Connection,
    *,
    batch_ids: List[str],
    start_dt: datetime,
    algo_mode: str,
    objective: str,
    time_budget: int,
    export_gantt_dir: Optional[str],
    gantt_days: int,
) -> Dict[str, Any]:
    from core.services.scheduler.config_service import ConfigService
    from core.services.scheduler.schedule_service import ScheduleService
    from data.repositories import ScheduleHistoryRepository

    cfg = ConfigService(conn)
    cfg.ensure_defaults()
    cfg.set_strategy("weighted")
    cfg.set_weights(0.4, 0.5, 0.1, require_sum_1=True)
    cfg.set_algo_mode(algo_mode)
    cfg.set_objective(objective)
    cfg.set_time_budget_seconds(int(time_budget))
    cfg.set_freeze_window("no", 0)

    svc = ScheduleService(conn)
    ret = svc.run_schedule(batch_ids=batch_ids, start_dt=start_dt, simulate=True, created_by="synthetic")
    version = int(ret.get("version") or 1)

    hist = ScheduleHistoryRepository(conn).get_by_version(version)
    summary_obj = {}
    if hist and hist.result_summary:
        try:
            summary_obj = json.loads(hist.result_summary or "{}")
        except Exception:
            summary_obj = {}

    algo = (summary_obj.get("algo") or {}) if isinstance(summary_obj, dict) else {}
    util = _calc_utilization_from_schedule(conn, version)
    out = {
        "version": version,
        "mode": algo_mode,
        "objective": objective,
        "time_budget_seconds": int(time_budget),
        "counts": summary_obj.get("counts"),
        "algo_metrics": (algo.get("metrics") if isinstance(algo, dict) else None),
        "best_score": (algo.get("best_score") if isinstance(algo, dict) else None),
        "utilization": util,
    }

    if export_gantt_dir:
        _export_gantt(conn, version, start_dt=start_dt, days=gantt_days, out_dir=export_gantt_dir)
        out["export_gantt_dir"] = export_gantt_dir
        out["export_gantt_days"] = int(gantt_days)

    return out


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=7, help="随机种子（保证可复现）")
    p.add_argument("--parts", type=int, default=50, help="品种数")
    p.add_argument("--batches-min", type=int, default=3, help="每品种最少批次数")
    p.add_argument("--batches-max", type=int, default=10, help="每品种最多批次数")
    p.add_argument("--ops-per-part", type=int, default=10, help="每品种模板工序数（每批次同样数量）")
    p.add_argument("--calendar-days", type=int, default=120, help="生成多少天工作日历")

    p.add_argument("--mode", choices=["greedy", "improve", "both"], default="both", help="运行 greedy / improve 或两者对比")
    p.add_argument(
        "--objective",
        choices=["min_overdue", "min_tardiness", "min_weighted_tardiness", "min_changeover"],
        default="min_tardiness",
        help="目标函数（lexicographic）",
    )
    p.add_argument("--time-budget", type=int, default=20, help="improve 模式时间预算（秒）")

    p.add_argument("--export-gantt-dir", default=None, help="可选：导出甘特 tasks 的目录（machine/operator 两份 JSON）")
    p.add_argument("--gantt-days", type=int, default=90, help="导出甘特图覆盖天数（从 start_dt 起算）")

    args = p.parse_args(argv)
    rnd = random.Random(int(args.seed))

    # 默认从“明天 08:00”开始（与系统默认一致）
    tomorrow = date.today() + timedelta(days=1)
    start_dt = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 8, 0, 0)

    conn = _connect_in_memory()
    _load_schema(conn)

    _seed_calendar(conn, start_date=start_dt.date() - timedelta(days=2), days=int(args.calendar_days), rnd=rnd)
    master = _seed_master_data(conn, rnd=rnd)
    part_nos = _seed_parts_routes(
        conn,
        parts=int(args.parts),
        ops_per_part=int(args.ops_per_part),
        rnd=rnd,
        master=master,
    )
    batch_ids = _seed_batches_and_ops(
        conn,
        part_nos=part_nos,
        batches_min=int(args.batches_min),
        batches_max=int(args.batches_max),
        ops_per_part=int(args.ops_per_part),
        start_dt=start_dt,
        rnd=rnd,
        master=master,
    )
    _seed_machine_downtimes(conn, start_dt=start_dt, rnd=rnd)

    # 运行排产（模拟）
    results: List[Dict[str, Any]] = []
    if args.mode in ("greedy", "both"):
        results.append(
            _run_one(
                conn,
                batch_ids=batch_ids,
                start_dt=start_dt,
                algo_mode="greedy",
                objective=str(args.objective),
                time_budget=int(args.time_budget),
                export_gantt_dir=args.export_gantt_dir,
                gantt_days=int(args.gantt_days),
            )
        )
    if args.mode in ("improve", "both"):
        results.append(
            _run_one(
                conn,
                batch_ids=batch_ids,
                start_dt=start_dt,
                algo_mode="improve",
                objective=str(args.objective),
                time_budget=int(args.time_budget),
                export_gantt_dir=args.export_gantt_dir,
                gantt_days=int(args.gantt_days),
            )
        )

    out = {
        "seed": int(args.seed),
        "start_dt": _fmt_dt(start_dt),
        "scale": {
            "parts": int(args.parts),
            "batches": int(len(batch_ids)),
            "ops_per_batch": int(args.ops_per_part),
            "calendar_days": int(args.calendar_days),
        },
        "runs": results,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

