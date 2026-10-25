"""回归测试：GreedyScheduler 自动选机时，固定 operator_id 而 machine_id 缺省的工序，只能选中 op_type_id 匹配的设备（M_OK），不得选用同人可操作但工种不符的 M_BAD，且 operator_id 保持固定值。"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Optional

import pytest


@dataclass
class _StubCalendarService:
    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id: Optional[str] = None) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, operator_id: Optional[str] = None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


@dataclass
class _Cfg:
    auto_assign_enabled: str = "yes"


def test_auto_assign_fixed_operator_respects_op_type() -> None:

    from core.algorithms import GreedyScheduler

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

    # 固定 operator_id，machine_id 缺省：应自动选机，且必须匹配 op_type_id
    op = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B001",
        seq=1,
        source="internal",
        machine_id="",  # missing
        operator_id="O1",  # fixed
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_id="OT_OK",
        op_type_name="车削",
        supplier_id=None,
        ext_days=None,
        ext_group_id=None,
        ext_merge_mode=None,
        ext_group_total_days=None,
    )

    # machines_by_operator 含一个“错误工种”的设备 M_BAD，以及正确设备 M_OK
    resource_pool = {
        "machines_by_op_type": {"OT_OK": ["M_OK"]},
        "operators_by_machine": {"M_OK": ["O1"], "M_BAD": ["O1"]},
        "machines_by_operator": {"O1": ["M_BAD", "M_OK"]},
        "pair_rank": {},
    }

    sched = GreedyScheduler(calendar_service=_StubCalendarService(), config_service=_Cfg())
    results, summary, _strategy, used_params = sched.schedule(
        operations=[op],
        batches=batches,
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        resource_pool=resource_pool,
        dispatch_mode="batch_order",
        dispatch_rule="slack",
    )

    assert summary.success is True, f"排产应成功，summary={summary}"
    assert summary.failed_ops == 0, f"failed_ops 应为 0，summary={summary}"
    assert len(results) == 1, f"应只有 1 条结果，实际 {len(results)}"
    assert used_params.get("auto_assign_enabled") == "yes", f"used_params 留痕异常：{used_params}"

    r0 = results[0]
    assert r0.machine_id == "M_OK", f"自动选机应尊重 op_type_id，仅允许 M_OK，实际 {r0.machine_id!r}"
    assert r0.operator_id == "O1", f"operator_id 应保持为固定值 O1，实际 {r0.operator_id!r}"


@pytest.mark.parametrize("failure", ["hours_and_qualification", "machine_and_hours", "qualification"])
def test_auto_assign_keeps_machine_hours_qualification_failure_order(failure):
    from core.algorithm_runtime.algo_stats import make_algo_stats
    from core.algorithm_runtime.auto_assign_contract import (
        AUTO_ASSIGN_REASON_INVALID_INTERNAL_HOURS,
        AUTO_ASSIGN_REASON_MISSING_MACHINE_POOL,
    )
    from core.algorithms import GreedyScheduler
    from core.algorithms.greedy.auto_assign import auto_assign_internal_resources_attempt
    from core.algorithms.greedy.scheduler import prepare_native_schedule_inputs
    from core.errors import ValidationError

    op = SimpleNamespace(id=1, batch_id="B1", machine_id="", operator_id="", op_type_id="T1",
                         setup_hours=1.0 if failure == "qualification" else float("nan"), unit_hours=0.0)
    batch = SimpleNamespace(batch_id="B1", quantity=1)
    pool = {"machines_by_op_type": {"T1": [] if failure == "machine_and_hours" else ["M1"]},
            "operators_by_machine": {"M1": ["O1"]}, "machines_by_operator": {},
            "operator_skills": {}, "pair_rank": {}}
    scheduler = GreedyScheduler(calendar_service=_StubCalendarService(), config_service=_Cfg())
    preparation = prepare_native_schedule_inputs(None, scheduler=scheduler, operations=[op],
                                                 batches={"B1": batch}, resource_pool=pool)
    stats = make_algo_stats()
    kwargs = dict(calendar=scheduler.calendar, algo_stats=stats, op=op, batch=batch, batch_progress={},
                  machine_timeline={}, operator_timeline={}, base_time=datetime(2026, 1, 1, 8),
                  end_dt_exclusive=None, machine_downtimes=None, resource_pool=pool,
                  last_op_type_by_machine={}, machine_busy_hours={}, operator_busy_hours={},
                  resource_preparation=preparation)
    if failure == "qualification":
        with pytest.raises(ValidationError) as caught:
            auto_assign_internal_resources_attempt(**kwargs)
        assert caught.value.field == "operator_qualification"
        assert stats["fallback_counts"] == {}
    else:
        attempt = auto_assign_internal_resources_attempt(**kwargs)
        expected = (AUTO_ASSIGN_REASON_MISSING_MACHINE_POOL if failure == "machine_and_hours"
                    else AUTO_ASSIGN_REASON_INVALID_INTERNAL_HOURS)
        counter = ("auto_assign_missing_machine_pool_count" if failure == "machine_and_hours"
                   else "auto_assign_invalid_total_hours_count")
        assert attempt.reason == expected
        assert stats["fallback_counts"] == {counter: 1}
