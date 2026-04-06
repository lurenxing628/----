import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Optional


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


@dataclass
class _StubCalendarService:
    """满足 GreedyScheduler.schedule 最小接口的日历桩。"""

    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id: Optional[str] = None) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, operator_id: Optional[str] = None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.algorithms import GreedyScheduler
    from core.algorithms.sort_strategies import SortStrategy

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

    # 防御场景：start_dt 误传字符串；machine_id/operator_id 不是 str（避免 .strip() 崩溃）
    op = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B001",
        seq=1,
        source="internal",
        machine_id=101,  # int
        operator_id=202,  # int
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_id="OT01",
        op_type_name="车削",
        supplier_id=None,
        ext_days=None,
        ext_group_id=None,
        ext_merge_mode=None,
        ext_group_total_days=None,
    )

    sched = GreedyScheduler(calendar_service=_StubCalendarService())
    results, summary, _strategy, used_params = sched.schedule(
        operations=[op],
        batches=batches,
        strategy=SortStrategy.WEIGHTED,
        strategy_params={"priority_weight": None, "due_weight": "abc"},  # 防御：非法权重不应崩溃
        start_dt="2026-01-01 08:00",  # 防御：字符串 start_dt
        dispatch_mode="batch_order",
        dispatch_rule="slack",
    )

    assert summary.success is True, f"排产应成功，summary={summary}"
    assert summary.total_ops == 1, f"total_ops 应为 1，实际 {summary.total_ops}"
    assert summary.scheduled_ops == 1, f"scheduled_ops 应为 1，实际 {summary.scheduled_ops}"
    assert summary.failed_ops == 0, f"failed_ops 应为 0，实际 {summary.failed_ops}"
    assert len(results) == 1, f"应仅产出 1 条结果，实际 len={len(results)}"

    r0 = results[0]
    assert str(r0.machine_id) == "101", f"machine_id 应被安全转为字符串，实际 {r0.machine_id!r}"
    assert str(r0.operator_id) == "202", f"operator_id 应被安全转为字符串，实际 {r0.operator_id!r}"

    # 非法权重应回退默认，不应是 NaN/抛异常
    priority_weight = used_params.get("priority_weight")
    due_weight = used_params.get("due_weight")
    assert priority_weight is not None, f"priority_weight 不应缺失：{used_params}"
    assert due_weight is not None, f"due_weight 不应缺失：{used_params}"
    assert abs(float(priority_weight) - 0.4) < 1e-9, f"priority_weight 回退异常：{used_params}"
    assert abs(float(due_weight) - 0.5) < 1e-9, f"due_weight 回退异常：{used_params}"

    print("OK")


if __name__ == "__main__":
    main()

