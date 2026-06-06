"""回归测试：个人工作日历（OperatorCalendar）可覆盖全局 WorkCalendar——当全局把某天设为假期不可排产时内部工序应跳到次日；但若该人把该天个人覆盖为可工作日，则其内部工序应能排入该天。"""

from datetime import datetime
from types import SimpleNamespace


def test_operator_calendar_override_allows_work_on_global_holiday(db_path):
    """
    回归目标：
    - 个人工作日历（OperatorCalendar）可覆盖全局 WorkCalendar
    - 当全局把某天设为“假期不可排产”，但个人把该天设为“可工作”，则该人的内部工序应可排入该天
    """


    from core.algorithms.greedy.scheduler import GreedyScheduler
    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.scheduler import CalendarService


    conn = get_connection(db_path)

    try:
        # 必要基础数据：人员
        conn.execute("INSERT INTO Operators (operator_id, name, status, remark) VALUES (?, ?, ?, ?)", ("OP001", "张三", "active", ""))
        conn.commit()

        cal_svc = CalendarService(conn, logger=None, op_logger=None)

        # 全局：2026-01-26 设为假期不可排产
        cal_svc.upsert(
            date_value="2026-01-26",
            day_type="holiday",
            shift_hours=0,
            efficiency=1.0,
            allow_normal="no",
            allow_urgent="no",
            remark="全局假期",
        )

        # 构造最小批次与内部工序（纯内存对象，算法不会查 DB）
        batch = SimpleNamespace(
            batch_id="B001",
            priority="normal",
            due_date=None,
            ready_status="yes",
            ready_date=None,
            created_at=None,
            quantity=1,
        )
        op = SimpleNamespace(
            id=1,
            op_code="B001-10",
            batch_id="B001",
            seq=10,
            source="internal",
            machine_id="MC001",
            operator_id="OP001",
            setup_hours=0.0,
            unit_hours=1.0,
            op_type_name="车削",
            op_type_id="OT001",
        )

        start_dt = datetime(2026, 1, 26, 8, 0, 0)
        scheduler = GreedyScheduler(calendar_service=cal_svc, config_service=None, logger=None)

        # Case A：无个人覆盖 → 应跳到次日工作时间
        res1, summ1, _, _ = scheduler.schedule(operations=[op], batches={"B001": batch}, start_dt=start_dt)
        assert res1 and res1[0].start_time, "预期产生排程结果"
        assert res1[0].start_time.date().isoformat() == "2026-01-27", f"预期跳到 2026-01-27，实际 {res1[0].start_time}"

        # Case B：个人覆盖为工作日可排产 → 应可排入 2026-01-26
        cal_svc.upsert_operator_calendar(
            operator_id="OP001",
            date_value="2026-01-26",
            day_type="workday",
            shift_hours=8,
            efficiency=1.0,
            allow_normal="yes",
            allow_urgent="yes",
            remark="个人加班",
        )

        res2, summ2, _, _ = scheduler.schedule(operations=[op], batches={"B001": batch}, start_dt=start_dt)
        assert res2 and res2[0].start_time, "预期产生排程结果"
        assert res2[0].start_time.date().isoformat() == "2026-01-26", f"预期排入 2026-01-26，实际 {res2[0].start_time}"

    finally:
        try:
            conn.close()
        except Exception:
            pass


