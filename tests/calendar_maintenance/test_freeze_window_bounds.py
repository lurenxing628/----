"""回归测试：开启冻结窗口重排时，只冻结 start_time 落在 [start_dt, start_dt+freeze_days) 区间内的工序——窗口起点之前的 B_OUT 不锁定、窗口内的 B_IN 被锁定，且 completed 的 B_TERM 不经 freeze seed 回流新版本。"""

from datetime import datetime, timedelta


def _dt(s: str) -> datetime:
    return datetime.strptime(str(s), "%Y-%m-%d %H:%M:%S")


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def test_freeze_window_bounds(db_path):
    """
    回归目标：
    冻结窗口（freeze window）读取上一版本排程时，应只冻结窗口区间内的工序：
    - start_time >= start_dt
    - start_time <  start_dt + freeze_days

    复现设计（必然触发旧 bug）：
    - 先生成上一版本排程（version=1）
      - B_OUT 的工序 start_time 在窗口起点之前
      - B_IN  的工序 start_time 手工调整到窗口内
      - B_TERM 的工序也手工调整到窗口内，再把工序状态改成 completed
    - 再将 start_dt 向后移动并开启冻结窗口（version=2）
      - 预期：只冻结 B_IN，不冻结 B_OUT，且 completed 的 B_TERM 不能经 seed 回流新版本
    """


    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.batch.service import BatchService
    from core.services.scheduler import ConfigService, ScheduleService


    conn = get_connection(db_path)

    try:
        # 1) 基础数据：工种/设备/人员/人机关联
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_A", "A工种", "internal"))
        conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC_A1", "A-01", "OT_A", "active"))
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "操作员1", "active"))
        conn.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            ("OP001", "MC_A1", "normal", "yes"),
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

        # 3) 三个批次（均 1 道内部工序）
        batch_svc = BatchService(conn, logger=None, op_logger=None)
        batch_svc.create_batch_from_template(
            batch_id="B_OUT",
            part_no="P1",
            quantity=1,
            due_date="2026-02-10",
            priority="normal",
            ready_status="yes",
        )
        batch_svc.create_batch_from_template(
            batch_id="B_IN",
            part_no="P1",
            quantity=1,
            due_date="2026-02-10",
            priority="normal",
            ready_status="yes",
        )
        batch_svc.create_batch_from_template(
            batch_id="B_TERM",
            part_no="P1",
            quantity=1,
            due_date="2026-02-10",
            priority="normal",
            ready_status="yes",
        )

        # 4) 生成上一版本排程（version=1）
        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        cfg_svc.restore_default()
        cfg_svc.set_auto_assign_enabled("yes")
        cfg_svc.set_dispatch("batch_order", "slack")
        cfg_svc.set_algo_mode("greedy")
        cfg_svc.set_freeze_window("no", 0)

        sch_svc = ScheduleService(conn, logger=None, op_logger=None)
        r1 = sch_svc.run_schedule(
            batch_ids=["B_OUT", "B_IN", "B_TERM"],
            start_dt="2026-02-01 08:00:00",
            simulate=False,
            created_by="regression",
        )
        ver1 = int(r1["version"])

        # 5) 手工调整上一版本中 B_IN 的 start/end 到窗口内（用于验证“窗口内仍可冻结”）
        # 窗口起点：2026-02-03 08:00:00；freeze_days=2 => freeze_end=2026-02-05 08:00:00
        start_dt = datetime(2026, 2, 3, 8, 0, 0)
        freeze_days = 2
        freeze_end = start_dt + timedelta(days=freeze_days)

        rows_v1 = conn.execute(
            """
            SELECT s.id AS sid, bo.batch_id AS batch_id, s.start_time, s.end_time
            FROM Schedule s
            JOIN BatchOperations bo ON bo.id = s.op_id
            WHERE s.version=?
            ORDER BY bo.batch_id
            """,
            (ver1,),
        ).fetchall()
        assert len(rows_v1) == 3, f"预期 version=1 有 3 条 Schedule 记录，实际 {len(rows_v1)}"

        in_sid = None
        term_sid = None
        for rr in rows_v1:
            if (rr["batch_id"] or "").strip() == "B_IN":
                in_sid = int(rr["sid"])
            if (rr["batch_id"] or "").strip() == "B_TERM":
                term_sid = int(rr["sid"])
        assert in_sid is not None, "未找到 B_IN 的 Schedule 记录（version=1）"
        assert term_sid is not None, "未找到 B_TERM 的 Schedule 记录（version=1）"

        in_st = datetime(2026, 2, 3, 10, 0, 0)
        in_et = in_st + timedelta(hours=1)
        term_st = datetime(2026, 2, 3, 12, 0, 0)
        term_et = term_st + timedelta(hours=1)
        assert start_dt <= in_st < freeze_end, "测试数据构造错误：B_IN.start_time 必须在冻结窗口内"
        assert start_dt <= term_st < freeze_end, "测试数据构造错误：B_TERM.start_time 必须在冻结窗口内"
        conn.execute("UPDATE Schedule SET start_time=?, end_time=? WHERE id=?", (_fmt(in_st), _fmt(in_et), int(in_sid)))
        conn.execute("UPDATE Schedule SET start_time=?, end_time=? WHERE id=?", (_fmt(term_st), _fmt(term_et), int(term_sid)))
        conn.execute("UPDATE BatchOperations SET status='completed' WHERE batch_id='B_TERM'")
        conn.commit()

        # 6) 启用冻结窗口并将 start_dt 向后移动（version=2）
        cfg_svc.set_freeze_window("yes", freeze_days)
        r2 = sch_svc.run_schedule(
            batch_ids=["B_OUT", "B_IN", "B_TERM"],
            start_dt=_fmt(start_dt),
            simulate=False,
            created_by="regression",
        )
        ver2 = int(r2["version"])

        locked = conn.execute(
            """
            SELECT bo.batch_id AS batch_id, s.start_time, s.end_time
            FROM Schedule s
            JOIN BatchOperations bo ON bo.id = s.op_id
            WHERE s.version=? AND s.lock_status='locked'
            ORDER BY bo.batch_id
            """,
            (ver2,),
        ).fetchall()

        # 关键断言：只应冻结窗口内的 B_IN；B_OUT（窗口起点之前）不应被锁定
        assert len(locked) == 1, f"预期仅 1 条 locked 记录（只冻结 B_IN），实际 {len(locked)} 条：{[dict(x) for x in locked]}"
        assert (locked[0]["batch_id"] or "").strip() == "B_IN", f"预期冻结 B_IN，实际冻结 {(locked[0]['batch_id'] or '').strip()!r}"

        st_locked = _dt(locked[0]["start_time"])
        assert st_locked >= start_dt, f"冻结窗口下界错误：locked.start_time={st_locked} < start_dt={start_dt}"
        assert st_locked < freeze_end, f"冻结窗口上界错误：locked.start_time={st_locked} >= freeze_end={freeze_end}"

        version2_rows = conn.execute(
            """
            SELECT bo.batch_id AS batch_id, s.lock_status AS lock_status
            FROM Schedule s
            JOIN BatchOperations bo ON bo.id = s.op_id
            WHERE s.version=?
            ORDER BY bo.batch_id, s.id
            """,
            (ver2,),
        ).fetchall()
        version2_batch_ids = [(rr["batch_id"] or "").strip() for rr in version2_rows]
        assert "B_TERM" not in version2_batch_ids, f"completed 工序不应经 freeze seed 回流新版本：{version2_batch_ids}"

    finally:
        try:
            conn.close()
        except Exception:
            pass


def test_piece_batches_hold_only_the_covered_piece_and_common_work():
    """分件批次里，时段盖住 A 件的工序时，前道只算 A 件和共同工序；B 件排在后面的工序不算，整批不会因此被跳过。
    不分件的批次和原来一样：工序号不超过时段里最大号的全部工序。"""
    from types import SimpleNamespace as Op

    from core.services.scheduler.run.freeze_window_prefixes import prefix_op_ids_for_anchors, window_anchors_by_batch

    ops = [Op(id=1, batch_id="B1", seq=10, piece_id=None), Op(id=2, batch_id="B1", seq=20, piece_id="A"),
           Op(id=3, batch_id="B1", seq=30, piece_id="A"), Op(id=4, batch_id="B1", seq=20, piece_id="B"),
           Op(id=5, batch_id="B1", seq=30, piece_id="B"), Op(id=6, batch_id="B1", seq=40, piece_id=None)]
    anchors = window_anchors_by_batch({3: {}}, {op.id: op for op in ops})
    assert anchors == {"B1": {"A": 30}}
    assert prefix_op_ids_for_anchors(ops, "B1", anchors["B1"]) == [1, 2, 3]
    assert prefix_op_ids_for_anchors(ops, "B1", {None: 40}) == [1, 2, 3, 4, 5, 6]
    plain = [Op(id=index, batch_id="B2", seq=index * 10, piece_id=None) for index in (1, 2, 3)]
    assert prefix_op_ids_for_anchors(plain, "B2", {None: 20}) == [1, 2]
