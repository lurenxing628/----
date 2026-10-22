"""日历与工序编辑拒绝非有限数值和非法状态，支持清空资源与工时。"""


def _expect_validation_error(fn, title: str) -> None:
    from core.errors import ValidationError

    ok = False
    try:
        fn()
    except ValidationError:
        ok = True
    assert ok, f"{title}：应抛出 ValidationError"


def test_scheduler_reject_nonfinite_and_invalid_status(db_path) -> None:

    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.batch.service import BatchService
    from core.services.scheduler.calendar.service import CalendarService
    from core.services.scheduler.schedule_service import ScheduleService

    conn = get_connection(db_path)

    try:
        # 基础数据：内部/外部工序各一条
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_IN", "内协工种", "internal"))
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_EX", "外协工种", "external"))
        conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC1", "设备1", "OT_IN", "active"))
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP1", "人员1", "active"))
        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            ("OP1", "MC1", "normal", "yes"),
        )
        conn.execute("INSERT INTO Suppliers (supplier_id, name, status) VALUES (?, ?, ?)", ("SUP1", "供应商1", "active"))
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P100", "测试零件", "yes"))
        conn.execute(
            """
            INSERT INTO PartOperations
            (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P100", 10, "OT_IN", "内协工种", "internal", None, None, None, 1.0, 0.5, "active"),
        )
        conn.execute(
            """
            INSERT INTO PartOperations
            (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P100", 20, "OT_EX", "外协工种", "external", "SUP1", 2.0, None, 0.0, 0.0, "active"),
        )
        conn.commit()

        batch_svc = BatchService(conn, logger=None)
        batch_svc.create_batch_from_template(
            batch_id="B100",
            part_no="P100",
            quantity=1,
            due_date="2026-02-15",
            priority="normal",
            ready_status="yes",
        )
        ops = batch_svc.list_operations("B100")
        op_in = next(o for o in ops if (o.source or "").strip() == "internal")
        op_ex = next(o for o in ops if (o.source or "").strip() == "external")

        cal_svc = CalendarService(conn, logger=None)
        sch_svc = ScheduleService(conn, logger=None)

        # 2) CalendarService：拒绝非有限效率
        _expect_validation_error(
            lambda: cal_svc.upsert(
                date_value="2026-02-01",
                day_type="workday",
                shift_hours=8,
                efficiency="inf",
                allow_normal="yes",
                allow_urgent="yes",
            ),
            "CalendarService.upsert(efficiency=inf)",
        )

        # 3) ScheduleService 工序编辑：拒绝非有限工时/周期
        _expect_validation_error(
            lambda: sch_svc.update_internal_operation(op_in.id, setup_hours="NaN", unit_hours=0.5),
            "update_internal_operation(setup_hours=NaN)",
        )
        _expect_validation_error(
            lambda: sch_svc.update_internal_operation(op_in.id, setup_hours=-0.1, unit_hours=0.5),
            "update_internal_operation(setup_hours=-0.1)",
        )
        _expect_validation_error(
            lambda: sch_svc.update_external_operation(op_ex.id, ext_days="inf"),
            "update_external_operation(ext_days=inf)",
        )
        op_in_blank = sch_svc.update_internal_operation(op_in.id, machine_id="", operator_id="", setup_hours="", unit_hours="")
        assert op_in_blank.machine_id is None, f"内部工序设备应允许清空：{op_in_blank.machine_id!r}"
        assert op_in_blank.operator_id is None, f"内部工序人员应允许清空：{op_in_blank.operator_id!r}"
        assert float(op_in_blank.setup_hours or 0.0) == 0.0, f"空换型工时应保存为 0：{op_in_blank.setup_hours!r}"
        assert float(op_in_blank.unit_hours or 0.0) == 0.0, f"空单件工时应保存为 0：{op_in_blank.unit_hours!r}"

        # 4) 工序状态白名单：非法值拒绝，合法值放行
        _expect_validation_error(
            lambda: sch_svc.update_internal_operation(op_in.id, status="archived"),
            "update_internal_operation(status=archived)",
        )
        _expect_validation_error(
            lambda: sch_svc.update_external_operation(op_ex.id, status="unknown"),
            "update_external_operation(status=unknown)",
        )

        op_in_after = sch_svc.update_internal_operation(op_in.id, status="scheduled")
        assert (op_in_after.status or "").strip().lower() == "scheduled", f"内部工序状态更新失败：{op_in_after.status!r}"
        op_ex_after = sch_svc.update_external_operation(op_ex.id, status="skipped")
        assert (op_ex_after.status or "").strip().lower() == "skipped", f"外部工序状态更新失败：{op_ex_after.status!r}"

    finally:
        try:
            conn.close()
        except Exception:
            pass
