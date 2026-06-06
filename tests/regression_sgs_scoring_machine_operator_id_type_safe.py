"""守护 SGS 评分阶段对 machine_id/operator_id 为 int 的类型安全：历史 BUG 会对 int 调 .strip() 抛异常并 continue 导致候选静默跳过、退化为 candidates[0]；本回归用 batch_order_override 把更晚交期排在首位，断言 GreedyScheduler 仍按 dispatch key(交期)优先排出更紧急的 OP_EARLY，两道工序全部成功排产。"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Optional


@dataclass
class _StubCalendar:
    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id: Optional[str] = None) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def _build_case():
    """
    复现历史 BUG（评分阶段类型不安全导致候选静默跳过 -> 退化为 candidates[0]）：

    - 两个批次各 1 道内部工序
    - machine_id/operator_id 故意给 int（历史代码会对 int 调用 .strip() 抛异常并 continue）
    - 通过 batch_order_override 强制 candidates[0] 是“交期更晚”的批次
    - 期望：SGS 仍应基于 dispatch key（交期）选择更紧急者，而不是无条件回退到 candidates[0]
    """
    batch_late = SimpleNamespace(
        batch_id="B_LATE",
        priority="normal",
        due_date="2026-01-10",
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )
    batch_early = SimpleNamespace(
        batch_id="B_EARLY",
        priority="normal",
        due_date="2026-01-02",
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )
    batches = {"B_LATE": batch_late, "B_EARLY": batch_early}

    op_late = SimpleNamespace(
        id=1,
        op_code="OP_LATE",
        batch_id="B_LATE",
        seq=1,
        source="internal",
        machine_id=123,  # int（历史代码会在评分阶段 .strip() 崩溃）
        operator_id=456,  # int
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
    op_early = SimpleNamespace(
        id=2,
        op_code="OP_EARLY",
        batch_id="B_EARLY",
        seq=1,
        source="internal",
        machine_id=789,  # int
        operator_id=101,  # int
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

    operations = [op_late, op_early]
    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    return operations, batches, start_dt


def test_sgs_scoring_machine_operator_id_type_safe() -> None:

    from core.algorithms import GreedyScheduler

    operations, batches, start_dt = _build_case()

    sched = GreedyScheduler(calendar_service=_StubCalendar())
    results, summary, _strategy, used_params = sched.schedule(
        operations=operations,
        batches=batches,
        start_dt=start_dt,
        dispatch_mode="sgs",
        dispatch_rule="slack",
        batch_order_override=["B_LATE", "B_EARLY"],  # candidates[0] 将是 B_LATE（更晚交期）
    )

    assert used_params.get("dispatch_mode") == "sgs", f"dispatch_mode 解析异常：{used_params!r}"
    assert summary.total_ops == 2, f"total_ops 应为 2，实际 {summary.total_ops}"
    assert summary.scheduled_ops == 2, f"scheduled_ops 应为 2，实际 {summary.scheduled_ops}"
    assert summary.failed_ops == 0, f"failed_ops 应为 0，实际 {summary.failed_ops}"
    assert len(results) == 2, f"应产出 2 条排程结果，实际 results={len(results)}"

    # 关键断言：第一个被排产的应是更早交期的 OP_EARLY。
    assert [result.op_code for result in results] == ["OP_EARLY", "OP_LATE"], results


