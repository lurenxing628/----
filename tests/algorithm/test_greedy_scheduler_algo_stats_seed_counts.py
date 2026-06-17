"""回归测试：GreedyScheduler 处理 seed_results 时，在 _last_algo_stats.fallback_counts 里如实记录被丢弃/过滤的种子计数——重复种子(seed_duplicate_dropped_count)、坏时间种子(seed_bad_time_dropped_count)、重叠过滤(seed_overlap_filtered_count)各为 1。"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Optional


@dataclass
class _StubCalendarService:
    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id: Optional[str] = None) -> datetime:
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, operator_id: Optional[str] = None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def test_greedy_scheduler_algo_stats_seed_counts() -> None:

    from core.algorithms import GreedyScheduler, ScheduleResult

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

    op1 = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B001",
        seq=1,
        source="internal",
        machine_id="M1",
        operator_id="O1",
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
    op2 = SimpleNamespace(
        id=2,
        op_code="OP2",
        batch_id="B001",
        seq=2,
        source="internal",
        machine_id="M1",
        operator_id="O1",
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
    operations = [op1, op2]

    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    seed_end = start_dt + timedelta(hours=1)
    seed_results = [
        ScheduleResult(
            op_id=1,
            op_code="OP1",
            batch_id="B001",
            seq=1,
            machine_id="M1",
            operator_id="O1",
            start_time=start_dt,
            end_time=seed_end,
            source="internal",
            op_type_name=None,
        ),
        ScheduleResult(
            op_id=1,
            op_code="OP1",
            batch_id="B001",
            seq=1,
            machine_id="M1",
            operator_id="O1",
            start_time=start_dt,
            end_time=seed_end,
            source="internal",
            op_type_name=None,
        ),
        ScheduleResult(
            op_id=2,
            op_code="OP2",
            batch_id="B001",
            seq=2,
            machine_id="M1",
            operator_id="O1",
            start_time=seed_end,
            end_time=seed_end,
            source="internal",
            op_type_name=None,
        ),
    ]

    sched = GreedyScheduler(calendar_service=_StubCalendarService())
    _results, summary, _strategy, _used_params = sched.schedule(
        operations=operations,
        batches=batches,
        start_dt=start_dt,
        seed_results=seed_results,
        dispatch_mode="batch_order",
        dispatch_rule="slack",
    )

    stats = getattr(sched, "_last_algo_stats", {}) or {}
    fallback_counts = (stats.get("fallback_counts") or {}) if isinstance(stats, dict) else {}

    assert summary.failed_ops == 0, f"行为回归异常：{summary.failed_ops}"
    assert int(fallback_counts.get("seed_duplicate_dropped_count") or 0) == 1, f"重复 seed 计数异常：{fallback_counts!r}"
    assert int(fallback_counts.get("seed_bad_time_dropped_count") or 0) == 1, f"坏时间 seed 计数异常：{fallback_counts!r}"
    assert int(fallback_counts.get("seed_overlap_filtered_count") or 0) == 1, f"overlap 过滤计数异常：{fallback_counts!r}"
