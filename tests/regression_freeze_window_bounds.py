import os
import sys
import tempfile
from datetime import datetime, timedelta


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _dt(s: str) -> datetime:
    return datetime.strptime(str(s), "%Y-%m-%d %H:%M:%S")


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def main():
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

    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.scheduler import BatchService, ConfigService, ScheduleService

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_freeze_window_")
    test_db = os.path.join(tmpdir, "aps_freeze_window_bounds.db")

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)

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
            simulate=True,
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
            simulate=True,
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

        print("OK")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

