"""回归测试：run_schedule 的齐套约束开关——enforce_ready=True 时未齐套批次（ready_status!=yes）应被 ValidationError 拒绝排产；enforce_ready=False 时关闭齐套约束，未齐套批次应允许参与并产出排程结果。"""


def test_optional_ready_constraint(db_path):
    """
    回归目标：
    - enforce_ready=True：保持旧行为，未齐套（ready_status!=yes）应拒绝排产
    - enforce_ready=False：齐套约束关闭时，允许未齐套批次参与排产
    """


    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.errors import ValidationError
    from core.services.scheduler import BatchService, ScheduleService


    conn = get_connection(db_path)

    try:
        # 1) 最小可排数据：工种/设备/人员/人机关联
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_A", "A工种", "internal"))
        conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC_A1", "A-01", "OT_A", "active"))
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "操作员1", "active"))
        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            ("OP001", "MC_A1", "normal", "yes"),
        )

        # 2) 工艺模板：1 道内部工序
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P1", "P1", "yes"))
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P1", 10, "OT_A", "A工种", "internal", None, None, None, 0.0, 1.0, "active"),
        )
        conn.commit()

        # 3) 创建“未齐套”批次，并补全内部资源（避免因资源缺失导致排产失败）
        batch_svc = BatchService(conn, logger=None, op_logger=None)
        batch_svc.create_batch_from_template(
            batch_id="B_NOT_READY",
            part_no="P1",
            quantity=1,
            due_date="2026-02-10",
            priority="normal",
            ready_status="no",
        )
        sch_svc = ScheduleService(conn, logger=None, op_logger=None)

        ops = batch_svc.list_operations("B_NOT_READY")
        op_in = next(o for o in ops if (o.source or "").strip() == "internal")
        sch_svc.update_internal_operation(
            op_in.id,
            machine_id="MC_A1",
            operator_id="OP001",
            setup_hours=op_in.setup_hours,
            unit_hours=op_in.unit_hours,
        )

        # 4) enforce_ready=True：应拒绝
        rejected = False
        try:
            sch_svc.run_schedule(
                batch_ids=["B_NOT_READY"],
                start_dt="2026-02-01 08:00:00",
                simulate=True,
                created_by="regression",
                enforce_ready=True,
            )
        except ValidationError:
            rejected = True
        assert rejected, "enforce_ready=True 时应拒绝未齐套批次（ready_status!=yes）"

        # 5) enforce_ready=False：应允许
        r = sch_svc.run_schedule(
            batch_ids=["B_NOT_READY"],
            start_dt="2026-02-01 08:00:00",
            simulate=True,
            created_by="regression",
            enforce_ready=False,
        )
        assert int((r.get("summary") or {}).get("scheduled_ops") or 0) > 0, f"enforce_ready=False 时应产生排程结果，实际返回：{r}"

    finally:
        try:
            conn.close()
        except Exception:
            pass
