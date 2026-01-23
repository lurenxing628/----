import json
import os
import tempfile
from datetime import date


def find_repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _write_html(repo_root: str, rel_path: str, title: str, meta: dict, tasks: list):
    out_path = os.path.join(repo_root, rel_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # 该 HTML 设计为“直接双击打开（file://）”即可看到图。
    # 相对路径：evidence/FullE2E/ -> ../../static/...
    meta_json = json.dumps(meta, ensure_ascii=False, indent=2, default=str)
    tasks_json = json.dumps(tasks, ensure_ascii=False, default=str)

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title}</title>
  <link rel="stylesheet" href="../../static/css/frappe-gantt.css"/>
  <style>
    body {{ font-family: -apple-system, Segoe UI, Arial, "Microsoft YaHei", sans-serif; margin: 16px; }}
    .meta {{ color: #666; margin: 8px 0 16px; white-space: pre-wrap; }}
    .wrap {{ border: 1px solid #e5e5e5; border-radius: 8px; padding: 12px; }}
    #gantt {{ overflow-x: auto; }}
    .hint {{ color: #999; font-size: 12px; margin-top: 8px; }}
  </style>
</head>
<body>
  <h2>{title}</h2>
  <div class="meta"><b>meta</b>\n{meta_json}</div>
  <div class="wrap">
    <div id="gantt"></div>
  </div>
  <div class="hint">提示：这是“复杂案例”生成的 tasks，样式来自仓库内置 Frappe Gantt 0.6.1 资源。</div>

  <script src="../../static/js/frappe-gantt.min.js"></script>
  <script>
    const tasks = {tasks_json};
    const gantt = new Gantt("#gantt", tasks, {{
      view_mode: "Day",
      language: "zh",
      popup_trigger: "click"
    }});
  </script>
</body>
</html>
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def main():
    repo_root = find_repo_root()
    tmpdir = tempfile.mkdtemp(prefix="aps_gantt_complex_")
    test_db = os.path.join(tmpdir, "aps_complex.db")
    test_logs = os.path.join(tmpdir, "logs")
    test_backups = os.path.join(tmpdir, "backups")
    test_templates = os.path.join(tmpdir, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = test_db
    os.environ["APS_LOG_DIR"] = test_logs
    os.environ["APS_BACKUP_DIR"] = test_backups
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = test_templates

    os.sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.logging import OperationLogger
    from core.services.process import ExternalGroupService
    from core.services.scheduler import BatchService, CalendarService, ScheduleService
    from core.services.scheduler.gantt_service import GanttService

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)
    op_logger = OperationLogger(conn, logger=None)

    # -------------------------
    # 1) 基础数据：工种/供应商/人员/设备/人机
    # -------------------------
    # 工种
    conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_IN_1", "数铣", "internal"))
    conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_IN_2", "钳", "internal"))
    conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_EX_1", "标印", "external"))
    conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_EX_2", "总检", "external"))

    # 供应商（外协）
    conn.execute(
        "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status) VALUES (?, ?, ?, ?, ?)",
        ("S001", "外协-标印厂", "OT_EX_1", 1.5, "active"),
    )
    conn.execute(
        "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status) VALUES (?, ?, ?, ?, ?)",
        ("S002", "外协-总检厂", "OT_EX_2", 1.0, "active"),
    )

    # 设备
    conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC001", "CNC-01", "OT_IN_1", "active"))
    conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC002", "CNC-02", "OT_IN_1", "active"))
    conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC003", "钳工台", "OT_IN_2", "active"))

    # 人员
    conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "张三", "active"))
    conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP002", "李四", "active"))
    conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP003", "王五", "active"))

    # 人机关联（制造冲突与错开）
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP001", "MC001"))
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP001", "MC002"))
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP002", "MC002"))
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP002", "MC003"))
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP003", "MC001"))
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP003", "MC003"))

    # -------------------------
    # 2) 工艺模板（Parts + PartOperations + ExternalGroups）
    # -------------------------
    # P_A：内部 3 道 + 外协连续组 [35-40]
    conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_A", "复杂件A", "yes"))
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_A", 5, "OT_IN_1", "数铣", "internal", None, None, None, 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_A", 10, "OT_IN_2", "钳", "internal", None, None, None, 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_A", 20, "OT_IN_1", "数铣", "internal", None, None, None, 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_A", 35, "OT_EX_1", "标印", "external", "S001", None, "P_A_G1", 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_A", 40, "OT_EX_2", "总检", "external", "S002", None, "P_A_G1", 0.0, 0.0, "active"),
    )
    conn.execute(
        "INSERT INTO ExternalGroups (group_id, part_no, start_seq, end_seq, merge_mode, total_days, supplier_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("P_A_G1", "P_A", 35, 40, "separate", None, "S001"),
    )

    # P_B：纯内部两道
    conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_B", "复杂件B", "yes"))
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_B", 5, "OT_IN_2", "钳", "internal", None, None, None, 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_B", 10, "OT_IN_1", "数铣", "internal", None, None, None, 0.0, 0.0, "active"),
    )

    conn.commit()

    # 将 P_A 的外协连续组改为 merged（整组 3.0 天）
    eg_svc = ExternalGroupService(conn, op_logger=op_logger)
    eg_svc.set_merge_mode(group_id="P_A_G1", merge_mode="merged", total_days=3.0)
    conn.commit()

    # -------------------------
    # 3) 日历（制造跨天/停工效果）
    # -------------------------
    cal = CalendarService(conn, logger=None, op_logger=op_logger)
    # 固定从 2026-01-26（周一）开始，周二短班，周三停工
    cal.upsert("2026-01-26", day_type="workday", shift_hours=8, efficiency=1.0, allow_normal="yes", allow_urgent="yes", remark="正常")
    cal.upsert("2026-01-27", day_type="workday", shift_hours=2, efficiency=1.0, allow_normal="yes", allow_urgent="yes", remark="短班次")
    cal.upsert("2026-01-28", day_type="holiday", shift_hours=0, efficiency=1.0, allow_normal="no", allow_urgent="no", remark="停工")
    conn.commit()

    # -------------------------
    # 4) 创建批次（多批次，制造资源冲突）
    # -------------------------
    batch_svc = BatchService(conn, logger=None, op_logger=op_logger)
    batches = [
        # P_A：含外协 merged 组（会拉长完工）
        ("B001", "P_A", 4, "2026-01-27", "critical", "yes", "复杂A-特急"),
        ("B002", "P_A", 2, "2026-01-29", "urgent", "yes", "复杂A-急件"),
        ("B003", "P_A", 1, "2026-02-05", "normal", "yes", "复杂A-普通"),
        # P_B：纯内部，用于和 P_A 抢资源
        ("B101", "P_B", 6, "2026-01-27", "urgent", "yes", "复杂B-急件"),
        ("B102", "P_B", 3, "2026-01-30", "normal", "yes", "复杂B-普通"),
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

    # -------------------------
    # 5) 补齐批次工序：分配设备/人员 + 工时（确保甘特可见且足够复杂）
    # -------------------------
    sch_svc = ScheduleService(conn, logger=None, op_logger=op_logger)

    def assign_internal(op, batch_id: str):
        # 基于工种名决定资源池
        name = (op.op_type_name or "").strip()
        seq = int(op.seq or 0)
        # 数铣 -> MC001/MC002；钳 -> MC003
        if name == "数铣":
            machine = "MC001" if (seq % 2 == 1) else "MC002"
            operator = "OP001" if machine in ("MC001", "MC002") else "OP003"
            # 制造冲突：让部分数铣统一用 OP001
            if batch_id in ("B001", "B002", "B101"):
                operator = "OP001"
        else:
            machine = "MC003"
            operator = "OP002" if batch_id in ("B101", "B102") else "OP003"

        # 工时策略（让时间跨天）
        # setup 固定 0.5h，unit 根据工序类型与序号给不同强度
        setup = 0.5
        if name == "数铣":
            unit = 1.2 if batch_id in ("B001", "B101") else 0.8
        else:
            unit = 0.6 if batch_id in ("B101", "B102") else 0.4

        sch_svc.update_internal_operation(op.id, machine_id=machine, operator_id=operator, setup_hours=setup, unit_hours=unit)

    def assign_external(op):
        # merged 外协组：不传 ext_days（会被服务层设置为 None）
        # 但 supplier_id 可以设置/回显
        sup = op.supplier_id or ("S001" if int(op.seq or 0) == 35 else "S002")
        sch_svc.update_external_operation(op.id, supplier_id=sup, ext_days=None)

    for bid, *_ in batches:
        ops = batch_svc.list_operations(bid)
        for op in ops:
            if (op.source or "").strip() == "internal":
                assign_internal(op, batch_id=bid)
            else:
                assign_external(op)

    # -------------------------
    # 6) 执行排产（固定起点，便于展示）
    # -------------------------
    result = sch_svc.run_schedule(batch_ids=[x[0] for x in batches], start_dt="2026-01-26 08:00:00", created_by="complex_demo")
    version = int(result.get("version") or 1)

    # 以排程起点所在周作为 week_start（保证甘特命中）
    min_start = conn.execute("SELECT MIN(start_time) AS st FROM Schedule WHERE version=?", (version,)).fetchone()["st"]
    week_start = str(min_start)[:10] if min_start else "2026-01-26"

    gantt_svc = GanttService(conn, logger=None, op_logger=op_logger)
    data_machine = gantt_svc.get_gantt_tasks(view="machine", week_start=week_start, offset_weeks=0, version=version)
    data_operator = gantt_svc.get_gantt_tasks(view="operator", week_start=week_start, offset_weeks=0, version=version)

    tasks_machine = data_machine.get("tasks") or []
    tasks_operator = data_operator.get("tasks") or []
    if not tasks_machine:
        raise RuntimeError("复杂案例 machine tasks 为空（不符合预期）")
    if not tasks_operator:
        raise RuntimeError("复杂案例 operator tasks 为空（不符合预期）")

    out_dir = os.path.join(repo_root, "evidence", "FullE2E")
    os.makedirs(out_dir, exist_ok=True)

    tasks_machine_path = os.path.join(out_dir, "gantt_tasks_complex_machine.json")
    with open(tasks_machine_path, "w", encoding="utf-8") as f:
        json.dump(
            {"meta": {"version": version, "week_start": week_start, "view": "machine"}, "tasks": tasks_machine},
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    tasks_operator_path = os.path.join(out_dir, "gantt_tasks_complex_operator.json")
    with open(tasks_operator_path, "w", encoding="utf-8") as f:
        json.dump(
            {"meta": {"version": version, "week_start": week_start, "view": "operator"}, "tasks": tasks_operator},
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    meta = {
        "tmpdir": tmpdir,
        "db": test_db,
        "version": version,
        "week_start": week_start,
        "batch_ids": [x[0] for x in batches],
        "tasks_machine": len(tasks_machine),
        "tasks_operator": len(tasks_operator),
        "note": "包含资源冲突、人机约束、外协 merged 周期、日历短班/停工、不同优先级/交期（含超期标记）",
    }

    html_machine = _write_html(repo_root, "evidence/FullE2E/gantt_preview_complex_machine.html", "甘特图预览（复杂案例 / 设备视图）", meta, tasks_machine)
    html_operator = _write_html(repo_root, "evidence/FullE2E/gantt_preview_complex_operator.html", "甘特图预览（复杂案例 / 人员视图）", meta, tasks_operator)

    print("OK")
    print(f"machine_html={html_machine}")
    print(f"operator_html={html_operator}")
    print(f"machine_tasks={tasks_machine_path}")
    print(f"operator_tasks={tasks_operator_path}")


if __name__ == "__main__":
    main()

