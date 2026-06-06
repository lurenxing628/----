"""回归测试：ScheduleService 构建 resource_pool 时技能等级须按 beginner/normal/expert 正确映射排名——开启 auto-assign 后，对同一设备上两名都设为主操的人员（OP001=beginner、OP002=expert），自动分配必须选中技能更高的 OP002，而非因技能映射失效把两者并列成未知。"""


def test_skill_rank_mapping(db_path):
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


    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.scheduler import BatchService, ConfigService, ScheduleService


    conn = get_connection(db_path)

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
        r = sch_svc.run_schedule(batch_ids=["B001"], start_dt="2026-02-01 08:00:00", simulate=False, created_by="regression")
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

    finally:
        try:
            conn.close()
        except Exception:
            pass


