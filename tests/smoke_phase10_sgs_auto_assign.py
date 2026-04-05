import os
import sys
import tempfile
import time
import traceback
from datetime import datetime


def find_repo_root():
    """
    约定：仓库根目录包含 app.py 与 schema.sql。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def write_report(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def _overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    # [a_start, a_end) overlaps [b_start, b_end)
    return not (a_end <= b_start or a_start >= b_end)


def main():
    t0 = time.time()
    lines = []
    lines.append("# Phase10（SGS/自动分配/OR-Tools/冻结窗口）冒烟测试报告")
    lines.append("")
    lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Python：{sys.version.splitlines()[0]}")

    repo_root = find_repo_root()
    lines.append(f"- 项目根目录：`{repo_root}`")

    tmpdir = tempfile.mkdtemp(prefix="aps_smoke_phase10_")
    test_db = os.path.join(tmpdir, "aps_phase10_test.db")
    lines.append(f"- 临时目录：`{tmpdir}`")
    lines.append(f"- 测试 DB：`{test_db}`")

    sys.path.insert(0, repo_root)
    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.logging import OperationLogger
    from core.services.scheduler import BatchService, ConfigService, ScheduleService

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)
    op_logger = OperationLogger(conn, logger=None)

    try:
        # 1) 基础数据：工种/设备/人员/人机关联
        lines.append("")
        lines.append("## 1. 基础数据准备")
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_A", "A工种", "internal"))
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_B", "B工种", "internal"))
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_EX", "外协", "external"))
        conn.execute(
            "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status) VALUES (?, ?, ?, ?, ?)",
            ("S001", "外协厂", "OT_EX", 2.0, "active"),
        )

        conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC_A1", "A-01", "OT_A", "active"))
        conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC_A2", "A-02", "OT_A", "active"))
        conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC_B1", "B-01", "OT_B", "active"))

        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "张三", "active"))
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP002", "李四", "active"))
        # 资质：OP001 可操作 A 两台；OP002 可操作 A2/B1
        conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)", ("OP001", "MC_A1", "high", "yes"))
        conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)", ("OP001", "MC_A2", "normal", "no"))
        conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)", ("OP002", "MC_A2", "high", "yes"))
        conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)", ("OP002", "MC_B1", "normal", "no"))

        # 2) 模板：两个内部工序 + merged 外协组（2 天）
        lines.append("")
        lines.append("## 2. 工艺模板准备（含 merged 外协组）")
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P10", "P10", "yes"))
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P10", 10, "OT_A", "A工种", "internal", None, None, None, 0.2, 0.5, "active"),
        )
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P10", 20, "OT_B", "B工种", "internal", None, None, None, 0.1, 0.4, "active"),
        )

        # merged 外协组（seq 35/40）
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P10", 35, "OT_EX", "外协-1", "external", "S001", None, "P10_G1", 0.0, 0.0, "active"),
        )
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P10", 40, "OT_EX", "外协-2", "external", "S001", None, "P10_G1", 0.0, 0.0, "active"),
        )
        conn.execute(
            "INSERT INTO ExternalGroups (group_id, part_no, start_seq, end_seq, merge_mode, total_days, supplier_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("P10_G1", "P10", 35, 40, "merged", 2.0, "S001"),
        )
        conn.commit()

        # 3) 创建批次：刻意不补全 machine/operator（用于验证 auto-assign）
        lines.append("")
        lines.append("## 3. 批次创建（内部工序缺省资源）")
        batch_svc = BatchService(conn, logger=None, op_logger=op_logger)
        b1 = batch_svc.create_batch_from_template(batch_id="B10_1", part_no="P10", quantity=10, due_date="2026-02-05", priority="urgent", ready_status="yes")
        b2 = batch_svc.create_batch_from_template(batch_id="B10_2", part_no="P10", quantity=8, due_date="2026-02-06", priority="normal", ready_status="yes")
        lines.append(f"- 已创建批次：{b1.batch_id}/{b2.batch_id}（内部工序未补全 machine/operator）")

        # 4) 停机：MC_A1 在 2026-02-01 09:00~12:00 停机
        conn.execute(
            """
            INSERT INTO MachineDowntimes (machine_id, scope_type, scope_value, start_time, end_time, reason_code, reason_detail, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("MC_A1", "machine", "MC_A1", "2026-02-01 09:00:00", "2026-02-01 12:00:00", "maint", "smoke", "active"),
        )
        conn.commit()

        sch_svc = ScheduleService(conn, logger=None, op_logger=op_logger)
        cfg_svc = ConfigService(conn, logger=None, op_logger=op_logger)

        start_dt = "2026-02-01 08:00:00"

        # 5) auto-assign 关闭：应出现失败（缺资源）
        lines.append("")
        lines.append("## 4. auto-assign 关闭：缺省资源应导致失败")
        cfg_svc.restore_default()
        cfg_svc.set_auto_assign_enabled("no")
        cfg_svc.set_dispatch("batch_order", "slack")
        r0 = sch_svc.run_schedule(batch_ids=["B10_1", "B10_2"], start_dt=start_dt, simulate=True, created_by="smoke10")
        lines.append(f"- result_status={r0['result_status']} failed_ops={r0['summary']['failed_ops']}")
        if int(r0["summary"]["failed_ops"]) <= 0:
            raise RuntimeError("auto-assign 关闭时，预期应出现 failed_ops>0（缺省资源）")

        # 6) auto-assign 开启：应成功排产（并回避停机）
        lines.append("")
        lines.append("## 5. auto-assign 开启：应成功排产且不与停机重叠")
        cfg_svc.set_auto_assign_enabled("yes")
        r1 = sch_svc.run_schedule(batch_ids=["B10_1", "B10_2"], start_dt=start_dt, simulate=True, created_by="smoke10")
        lines.append(f"- result_status={r1['result_status']} failed_ops={r1['summary']['failed_ops']} scheduled_ops={r1['summary']['scheduled_ops']}")
        if int(r1["summary"]["failed_ops"]) != 0:
            raise RuntimeError("auto-assign 开启后，预期 failed_ops=0")

        ver1 = int(r1["version"])
        rows = conn.execute("SELECT machine_id, operator_id, start_time, end_time FROM Schedule WHERE version=? AND machine_id IS NOT NULL", (ver1,)).fetchall()
        if not rows:
            raise RuntimeError("未找到内部工序 Schedule 记录（预期 machine_id 非空）")
        for r in rows:
            if not (r["machine_id"] and r["operator_id"]):
                raise RuntimeError("auto-assign 生成的内部排程缺少 machine/operator")

        # 停机重叠检查（仅检查 MC_A1 的排程不重叠）
        dt_st = _dt("2026-02-01 09:00:00")
        dt_et = _dt("2026-02-01 12:00:00")
        a1_rows = conn.execute(
            "SELECT start_time, end_time FROM Schedule WHERE version=? AND machine_id='MC_A1' ORDER BY start_time",
            (ver1,),
        ).fetchall()
        for rr in a1_rows:
            st = _dt(rr["start_time"])
            et = _dt(rr["end_time"])
            if _overlap(st, et, dt_st, dt_et):
                raise RuntimeError("检测到排程与停机区间重叠（downtime_avoid 失效）")
        lines.append("- downtime_avoid 校验通过（MC_A1 无重叠）")

        # 7) SGS：开启 sgs 派工（不要求更优，但要求可跑且无资源重叠）
        lines.append("")
        lines.append("## 6. SGS 派工：应可跑且无资源重叠")
        cfg_svc.set_dispatch("sgs", "slack")
        r2 = sch_svc.run_schedule(batch_ids=["B10_1", "B10_2"], start_dt=start_dt, simulate=True, created_by="smoke10")
        ver2 = int(r2["version"])
        lines.append(f"- SGS：version={ver2} failed_ops={r2['summary']['failed_ops']} scheduled_ops={r2['summary']['scheduled_ops']}")
        if int(r2["summary"]["failed_ops"]) != 0:
            raise RuntimeError("SGS 模式预期 failed_ops=0")

        def _check_no_overlap(field: str):
            rows0 = conn.execute(
                f"SELECT {field} AS rid, start_time, end_time FROM Schedule WHERE version=? AND {field} IS NOT NULL ORDER BY {field}, start_time, end_time",
                (ver2,),
            ).fetchall()
            cur = None
            last_end = None
            for r in rows0:
                rid = r["rid"]
                st = _dt(r["start_time"])
                et = _dt(r["end_time"])
                if cur != rid:
                    cur = rid
                    last_end = None
                if last_end and st < last_end:
                    raise RuntimeError(f"检测到资源重叠：{field}={rid} st={st} last_end={last_end}")
                last_end = et

        _check_no_overlap("machine_id")
        _check_no_overlap("operator_id")
        lines.append("- SGS 资源重叠校验通过（machine/operator）")

        # 8) merged 外协组：同组外协工序应同起止
        lines.append("")
        lines.append("## 7. merged 外协组：同组同起止")
        ext = conn.execute(
            """
            SELECT bo.seq, s.start_time, s.end_time
            FROM Schedule s
            JOIN BatchOperations bo ON bo.id=s.op_id
            WHERE s.version=? AND bo.batch_id='B10_1' AND bo.source='external'
            ORDER BY bo.seq
            """,
            (ver2,),
        ).fetchall()
        if len(ext) >= 2:
            st0 = ext[0]["start_time"]
            et0 = ext[0]["end_time"]
            for e in ext[1:]:
                if e["start_time"] != st0 or e["end_time"] != et0:
                    raise RuntimeError("merged 外协组起止不一致")
            lines.append(f"- 外协组起止一致：{st0} ~ {et0}")
        else:
            lines.append("- 外协工序数量不足，跳过校验")

        # 9) 冻结窗口：跑两次非模拟，第二次应产生 locked
        lines.append("")
        lines.append("## 8. 冻结窗口：第二次排产应出现 locked")
        cfg_svc.set_dispatch("batch_order", "slack")
        cfg_svc.set_freeze_window("no", 0)
        cfg_svc.set_algo_mode("greedy")
        r3 = sch_svc.run_schedule(batch_ids=["B10_1", "B10_2"], start_dt=start_dt, simulate=False, created_by="smoke10")
        cfg_svc.set_freeze_window("yes", 2)
        r4 = sch_svc.run_schedule(batch_ids=["B10_1", "B10_2"], start_dt=start_dt, simulate=False, created_by="smoke10")
        ver4 = int(r4["version"])
        locked = conn.execute("SELECT COUNT(1) AS c FROM Schedule WHERE version=? AND lock_status='locked'", (ver4,)).fetchone()["c"]
        lines.append(f"- freeze_window：v{r3['version']} -> v{ver4} locked_count={locked}")
        if int(locked) <= 0:
            raise RuntimeError("冻结窗口启用后，预期应出现 lock_status='locked'")

        # 10) OR-Tools 开关：开启后不应阻断主流程（无 ortools 也应继续）
        lines.append("")
        lines.append("## 9. OR-Tools 开关：可选项不应阻断排产")
        cfg_svc.set_algo_mode("improve")
        cfg_svc.set_time_budget_seconds(3)
        cfg_svc.set_ortools("yes", 2)
        r5 = sch_svc.run_schedule(batch_ids=["B10_1", "B10_2"], start_dt=start_dt, simulate=True, created_by="smoke10")
        lines.append(f"- ortools_enabled=yes：version={r5['version']} failed_ops={r5['summary']['failed_ops']}（无论环境是否安装 ortools，都应可继续）")

        lines.append("")
        lines.append("## 结论")
        lines.append("- PASS：SGS/自动分配/冻结窗口/外协合并周期/停机避让 基本链路可用。")
        lines.append(f"- 总耗时：{round(time.time() - t0, 3)}s")

    except Exception as e:
        lines.append("")
        lines.append("## 结论")
        lines.append(f"- FAIL：{e}")
        lines.append("")
        lines.append("### Traceback")
        lines.append("```")
        lines.append(traceback.format_exc())
        lines.append("```")
        lines.append(f"- 总耗时：{round(time.time() - t0, 3)}s")

    report_path = os.path.join(repo_root, "evidence", "Phase10", "smoke_phase10_report.md")
    write_report(report_path, lines)
    print(f"[smoke_phase10] report: {report_path}")


if __name__ == "__main__":
    main()

