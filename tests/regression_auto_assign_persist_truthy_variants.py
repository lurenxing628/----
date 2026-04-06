from __future__ import annotations

import os
import sys
import tempfile


def find_repo_root() -> str:
    """
    约定：仓库根目录包含 app.py 与 schema.sql。
    """
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
    from core.services.scheduler import BatchService, ConfigService, ScheduleService
    from core.services.scheduler.config_service import ConfigService as _ConfigService

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_auto_assign_persist_")
    test_db = os.path.join(tmpdir, "aps_reg_auto_assign_persist.db")
    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)
    try:
        # 1) 资源与模板：一个内部工种 + 设备/人员/资质 + 仅包含 1 道内部工序的零件模板
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_A", "A工种", "internal"))
        conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC_A1", "A-01", "OT_A", "active"))
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "张三", "active"))
        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            ("OP001", "MC_A1", "high", "yes"),
        )
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P1", "P1", "yes"))
        conn.execute(
            """
            INSERT INTO PartOperations
            (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P1", 10, "OT_A", "A工种", "internal", None, None, None, 0.2, 0.1, "active"),
        )
        conn.commit()

        # 2) 创建批次：刻意不补全 machine/operator（用于验证 auto_assign_persist 回写）
        batch_svc = BatchService(conn, logger=None, op_logger=None)
        batch_svc.create_batch_from_template(batch_id="B001", part_no="P1", quantity=10, priority="normal", ready_status="yes")

        op_row = conn.execute(
            "SELECT id, machine_id, operator_id FROM BatchOperations WHERE batch_id='B001' AND source='internal' ORDER BY id LIMIT 1"
        ).fetchone()
        if not op_row:
            raise RuntimeError("未生成内部工序（BatchOperations）")
        op_id = int(op_row["id"])
        if (op_row["machine_id"] is not None and str(op_row["machine_id"]).strip()) or (
            op_row["operator_id"] is not None and str(op_row["operator_id"]).strip()
        ):
            raise RuntimeError(f"用例前置不满足：期望内部工序缺省资源，但实际 machine={op_row['machine_id']!r} operator={op_row['operator_id']!r}")

        # 3) 开启 auto-assign（算法可分配缺省资源）
        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        cfg_svc.set_auto_assign_enabled("yes")

        # 4) 注入 cfg.auto_assign_persist='1'（truthy 变体），验证不会被当成 False
        orig_get_snapshot = _ConfigService.get_snapshot

        def _patched_get_snapshot(self, *args, **kwargs):
            snap = orig_get_snapshot(self, *args, **kwargs)
            setattr(snap, "auto_assign_persist", "1")
            return snap

        _ConfigService.get_snapshot = _patched_get_snapshot
        try:
            sch_svc = ScheduleService(conn, logger=None, op_logger=None)
            sch_svc.run_schedule(batch_ids=["B001"], start_dt="2026-02-01 08:00:00", simulate=False, created_by="reg")
        finally:
            _ConfigService.get_snapshot = orig_get_snapshot

        # 5) 断言：缺省资源被回写（machine/operator 均非空）
        after = conn.execute("SELECT machine_id, operator_id FROM BatchOperations WHERE id=?", (op_id,)).fetchone()
        mc = "" if after is None or after["machine_id"] is None else str(after["machine_id"]).strip()
        oid = "" if after is None or after["operator_id"] is None else str(after["operator_id"]).strip()
        if not mc or not oid:
            raise RuntimeError(f"auto_assign_persist='1' 未触发回写：machine_id={mc!r} operator_id={oid!r}")

        print("OK")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

