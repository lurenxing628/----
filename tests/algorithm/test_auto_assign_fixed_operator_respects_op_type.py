"""回归测试：GreedyScheduler 自动选机时，固定 operator_id 而 machine_id 缺省的工序，只能选中 op_type_id 匹配的设备（M_OK），不得选用同人可操作但工种不符的 M_BAD，且 operator_id 保持固定值。"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Optional


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
