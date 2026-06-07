"""回归测试：run_schedule 未显式传 enforce_ready 时须回退到配置 enforce_ready_default——默认为 yes 时拒绝未齐套批次（抛 ValidationError），默认为 no 时允许排产（scheduled_ops>0）。"""


def test_scheduler_enforce_ready_default_from_config(db_path) -> None:

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.errors import ValidationError
    from core.services.scheduler import BatchService, ConfigService, ScheduleService

    conn = get_connection(db_path)

    try:
        # 最小可排数据
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_A", "A工种", "internal"))
        conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC_A1", "A-01", "OT_A", "active"))
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "操作员1", "active"))
        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            ("OP001", "MC_A1", "normal", "yes"),
        )
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P1", "P1", "yes"))
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P1", 10, "OT_A", "A工种", "internal", None, None, None, 0.0, 1.0, "active"),
        )
        conn.commit()

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

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)

        # Case 1: 配置默认 yes，且调用不显式传 enforce_ready -> 应拒绝
        cfg_svc.set_enforce_ready_default("yes")
        rejected = False
        try:
            sch_svc.run_schedule(
                batch_ids=["B_NOT_READY"],
                start_dt="2026-02-01 08:00:00",
                simulate=True,
                created_by="regression",
            )
        except ValidationError:
            rejected = True
        assert rejected, "enforce_ready_default=yes 且未显式传 enforce_ready 时，应拒绝未齐套批次"

        # Case 2: 配置默认 no，且调用不显式传 enforce_ready -> 应允许
        cfg_svc.set_enforce_ready_default("no")
        ret = sch_svc.run_schedule(
            batch_ids=["B_NOT_READY"],
            start_dt="2026-02-01 08:00:00",
            simulate=True,
            created_by="regression",
        )
        assert int((ret.get("summary") or {}).get("scheduled_ops") or 0) > 0, f"配置默认 no 时应允许排产，返回：{ret}"

    finally:
        try:
            conn.close()
        except Exception:
            pass


