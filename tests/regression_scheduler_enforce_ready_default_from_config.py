import os
import sys
import tempfile


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.errors import ValidationError
    from core.services.scheduler import BatchService, ConfigService, ScheduleService

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_ready_default_")
    test_db = os.path.join(tmpdir, "aps_ready_default.db")
    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)

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

        print("OK")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
