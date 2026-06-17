"""回归测试：当日历服务 get_efficiency 返回大于 1（如 1.2）时，GreedyScheduler 应据此缩短实际工时——setup_hours=12 在效率 1.2 下应得 end_time = start + 10 小时，而非按原始工时排程。"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Optional


@dataclass
class _StubCalendarService:
    """
    最小日历服务桩：效率固定为 >1（验证工时应缩短）。
    """

    efficiency: float = 1.2

    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id: Optional[str] = None) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> float:
        return float(self.efficiency)

    def add_calendar_days(self, dt: datetime, days: float, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def test_efficiency_greater_than_one_shortens_hours() -> None:

    from core.algorithms import GreedyScheduler

    start = datetime(2026, 1, 1, 8, 0, 0)
    batch = SimpleNamespace(
        batch_id="B001",
        priority="normal",
        due_date=None,
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )
    batches = {"B001": batch}

    # setup=12h, eff=1.2 => 实际工时应为 10h
    op = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B001",
        seq=1,
        source="internal",
        machine_id="M1",
        operator_id="O1",
        setup_hours=12.0,
        unit_hours=0.0,
        op_type_id="OT01",
        op_type_name="车削",
        supplier_id=None,
        ext_days=None,
        ext_group_id=None,
        ext_merge_mode=None,
        ext_group_total_days=None,
    )

    sched = GreedyScheduler(calendar_service=_StubCalendarService(efficiency=1.2))
    results, summary, _strategy, _params = sched.schedule(operations=[op], batches=batches, start_dt=start, dispatch_mode="batch_order")
    assert summary.total_ops == 1 and summary.scheduled_ops == 1 and summary.failed_ops == 0, f"排产摘要异常：{summary!r}"
    assert len(results) == 1, f"结果数量异常：{len(results)}"

    r = results[0]
    expected_end = start + timedelta(hours=(12.0 / 1.2))
    assert r.start_time == start, f"start_time 异常：{r.start_time!r}"
    assert r.end_time is not None, "end_time 不能为空"
    assert abs((r.end_time - expected_end).total_seconds()) < 1e-6, f"效率>1 未生效：end={r.end_time!r} expected={expected_end!r}"
