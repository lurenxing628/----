"""回归测试：生产解码入口的失败阻断语义一致性——batch_order 模式下无效 batch_id 和缺资源工序都计入
failed_ops（不被静默过滤）且失败即阻断同批后续工序，scheduled+failed==total；sgs 模式缺资源应抛 ValidationError(field=resource)
而非生成不可评分兜底 key。"""

from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

from core.algorithm_runtime.run_state import ScheduleRunState
from tests._support.algo_operations import make_algo_op, make_batch
from tests._support.schedule_decode import config_snapshot, production_decode


@dataclass
class _StubCalendarService:
    """
    最小日历服务桩：满足生产解码入口所需接口。

    说明：此回归用例只验证“失败阻断语义一致性”，不依赖真实工作日历逻辑。
    """

    def adjust_to_working_time(self, dt: datetime, priority=None) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def _build_case():
    """
    构造一个关键场景：
    - 1 个“无效 batch_id”的工序：必须被计入 failed_ops（不能被静默过滤）
    - 同一有效批次 2 道内部工序：
      - 第 1 道工序缺失 machine_id/operator_id -> _schedule_internal 返回 (None, blocked=False)
      - 第 2 道工序资源齐全，本可排；但一旦“失败即阻断批次”，应被阻断不再排
    """
    batches = {"B001": make_batch(batch_id="B001")}
    op_bad = make_algo_op(id=999, op_code="OP_BAD", batch_id="B_BAD", machine_id="M1", operator_id="O1",
                          setup_hours=1.0, unit_hours=0.0)
    op1 = make_algo_op(id=1, batch_id="B001", setup_hours=1.0, unit_hours=0.0)
    op2 = make_algo_op(id=2, batch_id="B001", seq=2, machine_id="M1", operator_id="O1", setup_hours=1.0, unit_hours=0.0)

    operations = [op_bad, op1, op2]
    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    return operations, batches, start_dt


def _run(dispatch_mode: str):

    from core.algorithms.greedy.scheduler import GreedyScheduler

    operations, batches, start_dt = _build_case()
    sched = GreedyScheduler(calendar_service=_StubCalendarService(), config_service=config_snapshot())
    decoded = production_decode(
        sched,
        operations=operations,
        batches=batches,
        start_dt=start_dt,
        dispatch_mode=dispatch_mode,
        dispatch_rule="slack",
    )
    return decoded.results, decoded.summary, decoded.used_params


def test_dispatch_blocking_consistency():
    # batch_order 仍走正式派工失败统计：失败即阻断该批次后续工序。
    results, summary, used_params = _run("batch_order")
    assert used_params.get("dispatch_mode") == "batch_order", f"dispatch_mode 解析异常：{used_params!r}"
    assert summary.total_ops == 3, f"total_ops 应为 3，实际 {summary.total_ops}"
    assert summary.scheduled_ops == 0, f"scheduled_ops 应为 0，实际 {summary.scheduled_ops}"
    assert summary.failed_ops == 3, f"failed_ops 应为 3，实际 {summary.failed_ops}"
    assert summary.scheduled_ops + summary.failed_ops == summary.total_ops, "summary 统计不一致"
    assert len(results) == 0, f"不应产出排程结果，实际 results={len(results)}"

    from core.errors import ValidationError

    # SGS 评分阶段必须能估算候选；缺资源不再生成不可评分兜底 key。
    try:
        _run("sgs")
    except ValidationError as exc:
        assert exc.field == "resource", f"SGS 缺资源应定位到 resource，实际={exc.field!r}"
    else:
        raise AssertionError("SGS 不应为缺资源内部工序生成不可评分兜底 key")


class _ExplodingCalendarService(_StubCalendarService):
    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id=None) -> datetime:
        raise RuntimeError("日历故障")


def test_batch_order_dispatch_exception_propagates_instead_of_recording_failure() -> None:
    """派工单步里的意外异常直接抛出，不再被吞成“工序排产异常”失败明细后继续排。"""
    from core.algorithms.greedy.scheduler import GreedyScheduler

    op = make_algo_op(id=1, batch_id="B001", machine_id="M1", operator_id="O1", setup_hours=1.0, unit_hours=0.0)
    scheduler = GreedyScheduler(calendar_service=_ExplodingCalendarService(), config_service=config_snapshot())
    with pytest.raises(RuntimeError, match="日历故障"):
        production_decode(scheduler, operations=[op], batches={"B001": make_batch(batch_id="B001")},
                          start_dt=datetime(2026, 1, 1, 8, 0, 0), dispatch_mode="batch_order", dispatch_rule="slack")


def test_dispatch_sgs_missing_batch_records_structured_failure_detail() -> None:
    from core.algorithms.greedy.scheduler import GreedyScheduler

    op_bad = make_algo_op(id=999, op_code="OP_BAD", batch_id="B_BAD", machine_id="M1", operator_id="O1",
                          setup_hours=1.0, unit_hours=0.0)
    scheduler = GreedyScheduler(calendar_service=_StubCalendarService(), config_service=config_snapshot())
    summary = production_decode(scheduler, operations=[op_bad], batches={}, start_dt=datetime(2026, 1, 1, 8, 0, 0),
                                dispatch_mode="sgs", dispatch_rule="slack").summary

    assert summary.scheduled_ops == 0
    assert summary.failed_ops == 1
    assert [item["code"] for item in summary.failure_details] == ["missing_batch"]
    assert summary.failure_details[0]["op_code"] == "OP_BAD"


def test_graph_blocked_ops_already_counted_by_batch_skip_do_not_duplicate_failure_details() -> None:
    from core.algorithms.greedy.dispatch.sgs_graph_failure import _record_graph_blocked_operations

    failed_op = make_algo_op(id=1, batch_id="B001")
    blocked_op = make_algo_op(id=2, batch_id="B001", seq=2)
    graph_state = {
        "op_by_id": {
            1: ("B001", failed_op),
            2: ("B001", blocked_op),
        }
    }
    state = ScheduleRunState(base_time=datetime(2026, 1, 1, 8, 0, 0))

    extra_failed = _record_graph_blocked_operations(
        state,
        graph_state=graph_state,
        failed_op_id=1,
        newly_blocked_op_ids=[2],
        already_counted_op_ids={1, 2},
    )

    assert extra_failed == 0
    # 已被同批跳过路径计数的工序，图阻塞路径既不重复计数也不写明细；
    # 且不再往 state.errors 塞原始串（旧行为会回落成 generic “请联系管理员”双发）。
    assert state.errors == []
    assert state.failure_details == []


def test_dispatch_failures_record_structured_details_without_raw_error_duplication() -> None:
    """回归：missing_batch / 图阻塞失败只写结构化 failure_details，不再往
    state.errors 塞原始中文串。旧行为会让原始串回落成 generic_scheduler_error（“请联系管理员”），
    与结构化具体文案并列形成双发并虚增 error_count。"""
    from core.algorithms.greedy.dispatch.sgs_graph_failure import _record_graph_blocked_operations

    op = make_algo_op(id=1, batch_id="B001")
    state = ScheduleRunState(base_time=datetime(2026, 1, 1, 8, 0, 0))
    state.record_missing_batch(op, "B001")
    assert state.errors == []
    assert [item["code"] for item in state.failure_details] == ["missing_batch"]

    failed_op = make_algo_op(id=1, batch_id="B001")
    blocked_op = make_algo_op(id=2, batch_id="B001", seq=2)
    graph_state = {"op_by_id": {1: ("B001", failed_op), 2: ("B001", blocked_op)}}
    graph_state_run = ScheduleRunState(base_time=datetime(2026, 1, 1, 8, 0, 0))
    extra_failed = _record_graph_blocked_operations(
        graph_state_run,
        graph_state=graph_state,
        failed_op_id=1,
        newly_blocked_op_ids=[2],
        already_counted_op_ids={1},
    )
    assert extra_failed == 1
    assert graph_state_run.errors == []
    assert [item["code"] for item in graph_state_run.failure_details] == ["graph_blocked_after_failure"]


def test_graph_blocked_public_error_keeps_operation_codes_through_size_guard_projections() -> None:
    """回归：图阻塞的公开错误带上 failed_op_code；体积裁剪逐级投影（含对自身输出再投影、最小摘要）
    后 op_code / op_id / failed_op_code 仍在，文案不坍塌成 “工序 -”“前序工序 -”。"""
    from core.algorithms.greedy.dispatch.sgs_graph_failure import _record_graph_blocked_operations
    from core.models.scheduler_public_errors import build_public_error_records
    from core.services.scheduler.summary.summary_size_guard_fields import (
        minimal_summary_for_size_guard,
        size_guard_public_error_detail,
    )

    failed_op = make_algo_op(id=1, batch_id="B001")
    blocked_op = make_algo_op(id=2, batch_id="B001", seq=2)
    state = ScheduleRunState(base_time=datetime(2026, 1, 1, 8, 0, 0))
    _record_graph_blocked_operations(
        state,
        graph_state={"op_by_id": {1: ("B001", failed_op), 2: ("B001", blocked_op)}},
        failed_op_id=1,
        newly_blocked_op_ids=[2],
        already_counted_op_ids={1},
    )

    (record,) = build_public_error_records([], structured_details=state.failure_details)
    assert record["message"] == "工序 OP2：依赖的前序工序 OP1 排产失败，本次跳过。"
    assert (record["op_code"], record["op_id"], record["failed_op_code"]) == ("OP2", 2, "OP1")

    tier_once = size_guard_public_error_detail(record)
    tier_twice = size_guard_public_error_detail(tier_once)
    assert tier_once == record
    assert tier_twice == record
    minimal = minimal_summary_for_size_guard(
        {
            "summary_schema_version": "1.2",
            "is_simulation": False,
            "completion_status": "partial",
            "readiness": {"gate_enabled": False},
            "version": 1,
            "strategy": "priority_first",
            "counts": {"batch_count": 1, "op_count": 2, "scheduled_ops": 0, "failed_ops": 2, "unscheduled_batch_count": 1},
            "time_cost_ms": 1,
            "public_error_details": [tier_twice],
        },
        original_size=1,
        diagnostics_truncated=False,
    )
    assert minimal["public_error_details"] == [record]



def test_graph_skipped_operation_blocks_its_cross_batch_successors_once() -> None:
    """回归：批内失败后被同批跳过的工序同样不会完成，它的跨批后继要随之图阻塞。

    B1 的 OP1 超窗失败，同批 OP2 被跳过；OP2 的前驱 OP10（B0）随后也超窗失败。
    旧实现只阻塞失败工序自己的图后继，OP2 留在图里，等 OP10 失败传播时再被记一次
    graph_blocked_after_failure，失败数超过总工序数。"""
    from core.algorithms.greedy.scheduler import GreedyScheduler
    from tests._support.busy_block_case import BASE, native_calendar

    batches = {bid: make_batch(batch_id=bid) for bid in ("B0", "B1", "B2")}

    def op(op_id, batch_id, seq, hours):
        return make_algo_op(id=op_id, batch_id=batch_id, seq=seq, machine_id="M1", operator_id="O1",
                            setup_hours=0.0, unit_hours=hours, op_type_name="TYPE1")

    context = {
        "enabled": True, "schedulable_op_ids": [10, 1, 2, 3], "fixed_op_ids": [], "score_enabled": True,
        "predecessor_op_ids_by_op_id": {10: [], 1: [], 2: [10], 3: [2]},
        "successor_op_ids_by_op_id": {10: [2], 1: [], 2: [3], 3: []},
        "sort_key_by_op_id": {10: (0, 0, 10), 1: (1, 0, 1), 2: (1, 1, 2), 3: (2, 0, 3)},
        # Both 80-hour operations overrun the window; OP1's smaller graph key makes it fail first.
        "graph_priority_key_by_op_id": {10: (2.0, 10.0), 1: (0.0, 1.0), 2: (5.0, 2.0), 3: (1.0, 3.0)},
    }
    with native_calendar() as calendar:
        scheduler = GreedyScheduler(calendar_service=calendar, config_service=config_snapshot(auto_assign_enabled="no"))
        decoded = production_decode(
            scheduler,
            operations=[op(10, "B0", 0, 80.0), op(1, "B1", 0, 80.0), op(2, "B1", 1, 1.0), op(3, "B2", 0, 1.0)],
            batches=batches, start_dt=BASE, end_date=(BASE + timedelta(days=2)).date(),
            dispatch_mode="sgs", dispatch_rule="atc", graph_ready_context=context,
        )
    results, summary = decoded.results, decoded.summary

    assert results == []
    assert (summary.scheduled_ops, summary.failed_ops, summary.total_ops) == (0, 4, 4)
    assert sorted((item["code"], item["op_id"]) for item in summary.failure_details) == [
        ("dispatch_operation_failed", 1),
        ("dispatch_operation_failed", 10),
        ("graph_blocked_after_failure", 3),
        ("skipped_after_batch_failure", 2),
    ]
