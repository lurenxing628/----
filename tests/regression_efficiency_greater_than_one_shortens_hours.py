import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


@dataclass
class _StubCalendarService:
    """
    最小日历服务桩：效率固定为 >1（验证工时应缩短）。
    """

    efficiency: float = 1.2

    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id: str = None) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id: str = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, machine_id: str = None, operator_id: str = None) -> float:
        return float(self.efficiency)

    def add_calendar_days(self, dt: datetime, days: float, machine_id: str = None, operator_id: str = None) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

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

    print("OK")


if __name__ == "__main__":
    main()

