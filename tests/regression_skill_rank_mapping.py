import os
import sys
import tempfile


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main():
    """
    回归目标：
    - ScheduleService 的 resource_pool 构建中，技能等级应按 beginner/normal/expert 正确排序；
      否则会把 beginner/expert 都当成未知(9)，导致自动分配在同等条件下丢失技能差异。

    设计：
    - 1 台设备（OT_A）
    - 2 名人员均可操作该设备，且都设为主操（避免 primary 维度影响）
      - OP001: beginner（字典序更小）
      - OP002: expert（字典序更大，若技能映射失效会被错误地排在后面）
    - 1 个内部工序缺省 machine/operator，开启 auto-assign 后应选择 OP002（expert）
    """

    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.scheduler import BatchService, ConfigService, ScheduleService

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_skill_rank_")
    test_db = os.path.join(tmpdir, "aps_skill_rank_test.db")

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)

    try:
        # 1) 基础数据：工种/设备/人员/人机关联
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_A", "A工种", "internal"))
        conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC_A1", "A-01", "OT_A", "active"))
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "初级工", "active"))
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP002", "熟练工", "active"))

        # 两者都标记为主操，避免 primary 维度掩盖 skill 排序
        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            ("OP001", "MC_A1", "beginner", "yes"),
        )
        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            ("OP002", "MC_A1", "expert", "yes"),
        )

        # 2) 工艺模板：1 道内部工序（不指定 machine/operator，触发 auto-assign）
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P1", "P1", "yes"))
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P1", 10, "OT_A", "A工种", "internal", None, None, None, 1.0, 0.0, "active"),
        )
        conn.commit()

        # 3) 创建批次（内部工序缺省资源）
        batch_svc = BatchService(conn, logger=None, op_logger=None)
        batch_svc.create_batch_from_template(
            batch_id="B001",
            part_no="P1",
            quantity=1,
            due_date="2026-02-05",
            priority="normal",
            ready_status="yes",
        )

        # 4) 开启 auto-assign，并执行模拟排产
        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        cfg_svc.set_auto_assign_enabled("yes")
        cfg_svc.set_dispatch("batch_order", "slack")

        sch_svc = ScheduleService(conn, logger=None, op_logger=None)
        r = sch_svc.run_schedule(batch_ids=["B001"], start_dt="2026-02-01 08:00:00", simulate=True, created_by="regression")
        assert int(r["summary"]["failed_ops"]) == 0, f"预期 failed_ops=0，实际 {r['summary']}"

        ver = int(r["version"])
        rows = conn.execute(
            "SELECT machine_id, operator_id FROM Schedule WHERE version=? ORDER BY op_id",
            (ver,),
        ).fetchall()
        assert len(rows) == 1, f"预期 1 条 Schedule 记录，实际 {len(rows)}"
        assert (rows[0]["machine_id"] or "").strip() == "MC_A1"

        chosen = (rows[0]["operator_id"] or "").strip()
        assert chosen == "OP002", f"预期选择 expert( OP002 )，实际选择 {chosen!r}"

        print("OK")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

