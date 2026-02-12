import os
import sys
import tempfile


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _expect_validation_error(fn, title: str) -> None:
    from core.infrastructure.errors import ValidationError

    ok = False
    try:
        fn()
    except ValidationError:
        ok = True
    assert ok, f"{title}：应抛出 ValidationError"


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.scheduler import BatchService, CalendarService, ConfigService, ScheduleService

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_scheduler_validation_")
    test_db = os.path.join(tmpdir, "aps_scheduler_validation.db")
    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)

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

        batch_svc = BatchService(conn, logger=None, op_logger=None)
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

        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cal_svc = CalendarService(conn, logger=None, op_logger=None)
        sch_svc = ScheduleService(conn, logger=None, op_logger=None)

        # 1) ConfigService：拒绝非有限数值
        _expect_validation_error(
            lambda: cfg_svc.set_holiday_default_efficiency("NaN"),
            "set_holiday_default_efficiency(NaN)",
        )
        _expect_validation_error(
            lambda: cfg_svc.set_weights("inf", 0.2, 0.8, require_sum_1=False),
            "set_weights(inf)",
        )

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
            lambda: sch_svc.update_external_operation(op_ex.id, ext_days="inf"),
            "update_external_operation(ext_days=inf)",
        )

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

        print("OK")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
