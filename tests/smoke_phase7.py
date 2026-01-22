import os
import tempfile
import time
import traceback
from datetime import datetime


def find_repo_root():
    """
    约定：仓库根目录包含 app.py 与 schema.sql。
    兼容不同目录结构：优先 tests/ 上一级，其次扫描 D:\\Github 下子目录。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root

    base = r"D:\Github"
    try:
        if os.path.isdir(base):
            for d in os.listdir(base):
                p = os.path.join(base, d)
                if not os.path.isdir(p):
                    continue
                if os.path.exists(os.path.join(p, "app.py")) and os.path.exists(os.path.join(p, "schema.sql")):
                    return p
    except Exception:
        pass

    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def write_report(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def main():
    t0 = time.time()
    lines = []
    lines.append("# Phase7（排产算法 / M3）冒烟测试报告")
    lines.append("")
    lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Python：{os.sys.version.splitlines()[0]}")

    repo_root = find_repo_root()
    lines.append(f"- 项目根目录（自动识别）：`{repo_root}`")

    tmpdir = tempfile.mkdtemp(prefix="aps_smoke_phase7_")
    test_db = os.path.join(tmpdir, "aps_phase7_test.db")
    lines.append("")
    lines.append("## 0. 测试环境")
    lines.append(f"- 临时目录：`{tmpdir}`")
    lines.append(f"- 测试 DB：`{test_db}`")

    os.sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.errors import AppError
    from core.infrastructure.logging import OperationLogger
    from core.services.scheduler import BatchService, CalendarService, ConfigService, ScheduleService

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)
    op_logger = OperationLogger(conn, logger=None)

    try:
        # 1) 准备基础数据：工种/供应商/人员/设备/人机关联
        lines.append("")
        lines.append("## 1. 基础数据准备（工种/供应商/资源）")
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_IN", "数铣", "internal"))
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_EX", "标印", "external"))
        conn.execute(
            "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status) VALUES (?, ?, ?, ?, ?)",
            ("S001", "外协-标印厂", "OT_EX", 1.0, "active"),
        )
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "张三", "active"))
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC001", "CNC-01", "active"))
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC002", "CNC-02", "active"))
        conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP001", "MC001"))
        conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP001", "MC002"))

        # 2) 准备零件与模板工序
        # - P_CAL：内部 3 小时，用于验证日历跨天
        # - P_CON：内部工序，用于验证“同一人员冲突自动错开”
        # - P_EXT：内部 + merged 外部组（3 天），用于验证外部组合并周期
        lines.append("")
        lines.append("## 2. 工艺模板准备（含 merged 外部组）")
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_CAL", "日历验证件", "yes"))
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_CON", "人员冲突件", "yes"))
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_EXT", "外协合并周期件", "yes"))

        # P_CAL：seq=5 internal，unit_hours=1，qty=3 => 3h
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P_CAL", 5, "OT_IN", "数铣", "internal", None, None, None, 0.0, 1.0, "active"),
        )

        # P_CON：seq=5 internal，setup=0，unit=4，qty=1 => 4h
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P_CON", 5, "OT_IN", "数铣", "internal", None, None, None, 0.0, 4.0, "active"),
        )

        # P_EXT：seq=5 internal（1h） + 外部组 [35-40] merged total_days=3
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P_EXT", 5, "OT_IN", "数铣", "internal", None, None, None, 0.0, 1.0, "active"),
        )
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P_EXT", 35, "OT_EX", "标印", "external", "S001", None, "P_EXT_G1", 0.0, 0.0, "active"),
        )
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P_EXT", 40, "OT_EX", "总检", "external", "S001", None, "P_EXT_G1", 0.0, 0.0, "active"),
        )
        conn.execute(
            "INSERT INTO ExternalGroups (group_id, part_no, start_seq, end_seq, merge_mode, total_days, supplier_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("P_EXT_G1", "P_EXT", 35, 40, "merged", 3.0, "S001"),
        )
        conn.commit()

        # 3) 创建批次并生成批次工序
        lines.append("")
        lines.append("## 3. 批次创建（从模板复制生成工序）")
        batch_svc = BatchService(conn, logger=None, op_logger=op_logger)

        b_cal = batch_svc.create_batch_from_template(batch_id="B_CAL", part_no="P_CAL", quantity=3, due_date="2026-01-22", priority="normal", ready_status="yes")
        b1 = batch_svc.create_batch_from_template(batch_id="B001", part_no="P_CON", quantity=1, due_date="2026-02-05", priority="critical", ready_status="yes")
        b2 = batch_svc.create_batch_from_template(batch_id="B002", part_no="P_CON", quantity=1, due_date="2026-02-06", priority="normal", ready_status="yes")
        b_ext = batch_svc.create_batch_from_template(batch_id="B_EXT", part_no="P_EXT", quantity=1, due_date="2026-02-02", priority="urgent", ready_status="yes")
        lines.append(f"- 已创建批次：{b_cal.batch_id}/{b1.batch_id}/{b2.batch_id}/{b_ext.batch_id}")

        # 4) 补充内部工序资源（设备/人员），确保算法可跑
        lines.append("")
        lines.append("## 4. 工序补充（内部工序设备/人员/工时）")
        sch_svc = ScheduleService(conn, logger=None, op_logger=op_logger)

        def _set_internal(batch_id: str, machine_id: str):
            ops = batch_svc.list_operations(batch_id)
            op_in = next(o for o in ops if o.source == "internal")
            sch_svc.update_internal_operation(op_in.id, machine_id=machine_id, operator_id="OP001", setup_hours=op_in.setup_hours, unit_hours=op_in.unit_hours)
            return op_in.op_code

        _set_internal("B_CAL", "MC001")
        _set_internal("B001", "MC001")
        _set_internal("B002", "MC002")
        _set_internal("B_EXT", "MC001")
        lines.append("- 内部工序资源已补全（设备/人员均为 active 且符合 OperatorMachine）")

        # 5) 日历：配置短班次 + 停工，用于验证跨天
        lines.append("")
        lines.append("## 5. 工作日历约束：短班次 + 停工（用于验证跨天）")
        cal_svc = CalendarService(conn, logger=None, op_logger=op_logger)
        cal_svc.upsert("2026-01-21", day_type="workday", shift_hours=2, efficiency=1.0, allow_normal="yes", allow_urgent="yes", remark="短班次")
        cal_svc.upsert("2026-01-22", day_type="holiday", shift_hours=0, efficiency=1.0, allow_normal="no", allow_urgent="no", remark="停工")
        lines.append("- 已配置：2026-01-21 2h，2026-01-22 停工")

        # 6) 执行排产（四种策略切换验证 + 留痕）
        lines.append("")
        lines.append("## 6. 排产执行：策略切换 + 落库 + 留痕")
        cfg_svc = ConfigService(conn, logger=None, op_logger=op_logger)

        # 6.1 priority_first：先排 B_CAL（单批次）验证日历跨天
        cfg_svc.set_strategy("priority_first")
        r1 = sch_svc.run_schedule(batch_ids=["B_CAL"], start_dt="2026-01-21 08:00:00", created_by="smoke")
        lines.append(f"- priority_first（B_CAL）：version={r1['version']} result_status={r1['result_status']} scheduled_ops={r1['summary']['scheduled_ops']}")
        # 3h：2h(21号)+停工(22号)+1h(23号) => 2026-01-23 09:00
        end_dt = conn.execute(
            """
            SELECT end_time FROM Schedule s
            JOIN BatchOperations bo ON bo.id = s.op_id
            WHERE bo.batch_id='B_CAL' AND s.version=?
            ORDER BY s.id DESC LIMIT 1
            """,
            (r1["version"],),
        ).fetchone()["end_time"]
        lines.append(f"- 日历跨天校验：B_CAL end_time={end_dt}（期望 2026-01-23 09:00:00）")
        if str(end_dt) != "2026-01-23 09:00:00":
            raise RuntimeError("日历跨天计算不符合预期")

        # 6.2 due_date_first：对 B001/B002/B_EXT 进行排产（验证双资源冲突错开 + 外部组）
        cfg_svc.set_strategy("due_date_first")
        r2 = sch_svc.run_schedule(batch_ids=["B001", "B002", "B_EXT"], start_dt="2026-02-02 08:00:00", created_by="smoke")
        lines.append(f"- due_date_first：version={r2['version']} result_status={r2['result_status']} overdue={len(r2['overdue_batches'])}")

        # 人员冲突错开：同一人员 OP001 不能重叠
        row1 = conn.execute(
            """
            SELECT s.start_time, s.end_time
            FROM Schedule s
            JOIN BatchOperations bo ON bo.id=s.op_id
            WHERE bo.op_code='B001_05' AND s.version=?
            """,
            (r2["version"],),
        ).fetchone()
        row2 = conn.execute(
            """
            SELECT s.start_time, s.end_time
            FROM Schedule s
            JOIN BatchOperations bo ON bo.id=s.op_id
            WHERE bo.op_code='B002_05' AND s.version=?
            """,
            (r2["version"],),
        ).fetchone()
        if not row1 or not row2:
            raise RuntimeError("未找到 B001_05/B002_05 的排程记录")
        s1, e1 = _dt(row1["start_time"]), _dt(row1["end_time"])
        s2, e2 = _dt(row2["start_time"]), _dt(row2["end_time"])
        lines.append(f"- 人员冲突校验：B001_05 [{s1}~{e1}]  B002_05 [{s2}~{e2}]（期望不重叠）")
        if not (s2 >= e1 or s1 >= e2):
            raise RuntimeError("人员冲突未被错开（出现时间重叠）")

        # merged 外部组：B_EXT_35 与 B_EXT_40 起止应一致，且跨度 3 天
        ext_rows = conn.execute(
            """
            SELECT bo.op_code, s.start_time, s.end_time
            FROM Schedule s
            JOIN BatchOperations bo ON bo.id=s.op_id
            WHERE bo.batch_id='B_EXT' AND bo.source='external' AND s.version=?
            ORDER BY bo.seq
            """,
            (r2["version"],),
        ).fetchall()
        if len(ext_rows) < 2:
            raise RuntimeError("B_EXT 外部工序排程记录不足（期望至少 2 条）")
        st0, et0 = ext_rows[0]["start_time"], ext_rows[0]["end_time"]
        for rr in ext_rows:
            if rr["start_time"] != st0 or rr["end_time"] != et0:
                raise RuntimeError("merged 外部组起止不一致（组内应同起止）")
        span_days = (_dt(et0) - _dt(st0)).total_seconds() / 86400.0
        lines.append(f"- merged 外部组校验：start={st0} end={et0} span_days={span_days}（期望 3.0）")
        if abs(span_days - 3.0) > 1e-6:
            raise RuntimeError("merged 外部组合并周期不符合预期（应为 3 天）")

        # 超期预警：B_EXT due_date=2026-02-02，外部组结束在 02-05，应被标记超期
        if not any(x.get("batch_id") == "B_EXT" for x in r2["overdue_batches"]):
            raise RuntimeError("超期预警未包含 B_EXT（期望超期）")
        lines.append("- 超期预警校验：B_EXT 已出现在 overdue_batches")

        # 6.3 weighted：切换权重后再次跑（验证可切换 + 留痕 strategy_params）
        cfg_svc.set_strategy("weighted")
        cfg_svc.set_weights(0.4, 0.5, 0.1, require_sum_1=True)
        r3 = sch_svc.run_schedule(batch_ids=["B001", "B002"], start_dt="2026-02-02 08:00:00", created_by="smoke")
        lines.append(f"- weighted：version={r3['version']} strategy_params={r3['strategy_params']}")
        if not r3.get("strategy_params") or "priority_weight" not in r3["strategy_params"]:
            raise RuntimeError("weighted 未返回 strategy_params（留痕字段缺失）")

        # 6.4 fifo：再次切换策略跑一次（验证可切换）
        cfg_svc.set_strategy("fifo")
        r4 = sch_svc.run_schedule(batch_ids=["B001", "B002"], start_dt="2026-02-02 08:00:00", created_by="smoke")
        lines.append(f"- fifo：version={r4['version']}")

        # 7) 留痕核对：ScheduleHistory + OperationLogs
        lines.append("")
        lines.append("## 7. 留痕核对（ScheduleHistory / OperationLogs）")
        hist = conn.execute("SELECT id, version, strategy, result_status, result_summary FROM ScheduleHistory ORDER BY id DESC LIMIT 4").fetchall()
        lines.append(f"- ScheduleHistory 最近 4 条：{[(r['version'], r['strategy'], r['result_status']) for r in hist]}")
        strategies = [r["strategy"] for r in hist]
        for k in ("priority_first", "due_date_first", "weighted", "fifo"):
            if k not in strategies:
                raise RuntimeError(f"ScheduleHistory 缺少策略留痕：{k}")

        # result_summary JSON 必含 overdue_batches/strategy_params（至少对某些策略）
        import json as _json

        rs = _json.loads(hist[0]["result_summary"] or "{}")
        if "overdue_batches" not in rs or "strategy_params" not in rs:
            raise RuntimeError("ScheduleHistory.result_summary 缺少必要字段（overdue_batches/strategy_params）")
        lines.append("- ScheduleHistory.result_summary 字段校验：包含 overdue_batches/strategy_params")

        op_logs = conn.execute(
            """
            SELECT id, module, action, target_type, target_id, detail
            FROM OperationLogs
            WHERE module='scheduler' AND action='schedule'
            ORDER BY id DESC
            LIMIT 4
            """
        ).fetchall()
        lines.append(f"- OperationLogs(schedule) 最近 4 条：{[(r['id'], r['target_id']) for r in op_logs]}")
        if not op_logs:
            raise RuntimeError("OperationLogs 未写入 schedule 留痕")

        # 成功结论
        lines.append("")
        lines.append("## 结论")
        lines.append("- 通过：Phase7（排产算法 / M3）冒烟测试通过（策略切换/双资源冲突/日历/外部合并周期/落库/留痕）。")
        lines.append(f"- 总耗时：{int((time.time() - t0) * 1000)} ms")

    finally:
        try:
            conn.close()
        except Exception:
            pass

    report_path = os.path.join(repo_root, "evidence", "Phase7", "smoke_phase7_report.md")
    write_report(report_path, lines)
    print("OK")
    print(report_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        repo_root = None
        try:
            repo_root = find_repo_root()
        except Exception:
            pass

        lines = []
        lines.append("# Phase7（排产算法 / M3）冒烟测试报告（失败）")
        lines.append("")
        lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- 错误：{e}")
        lines.append("")
        lines.append("## Traceback")
        lines.append("```")
        lines.append(traceback.format_exc())
        lines.append("```")

        if repo_root:
            report_path = os.path.join(repo_root, "evidence", "Phase7", "smoke_phase7_report.md")
            write_report(report_path, lines)
            print("FAIL")
            print(report_path)
        raise

