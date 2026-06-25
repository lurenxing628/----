"""回归测试：GreedyScheduler.schedule 失败阻断语义一致性——batch_order 模式下无效 batch_id 和缺资源工序都计入
failed_ops（不被静默过滤）且失败即阻断同批后续工序，scheduled+failed==total；sgs 模式缺资源应抛 ValidationError(field=resource)
而非生成不可评分兜底 key。"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace

from core.algorithms.greedy.run_state import ScheduleRunState


@dataclass
class _StubCalendarService:
    """
    最小日历服务桩：满足 GreedyScheduler.schedule 所需接口。

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

    op_bad = SimpleNamespace(
        id=999,
        op_code="OP_BAD",
        batch_id="B_BAD",
        seq=1,
        source="internal",
        machine_id="M1",
        operator_id="O1",
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_id=None,
        op_type_name=None,
        supplier_id=None,
        ext_days=None,
        ext_group_id=None,
        ext_merge_mode=None,
        ext_group_total_days=None,
    )

    op1 = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B001",
        seq=1,
        source="internal",
        machine_id="",
        operator_id="",
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_id=None,
        op_type_name=None,
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
        op_type_id=None,
        op_type_name=None,
        supplier_id=None,
        ext_days=None,
        ext_group_id=None,
        ext_merge_mode=None,
        ext_group_total_days=None,
    )

    operations = [op_bad, op1, op2]
    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    return operations, batches, start_dt


def _run(dispatch_mode: str):

    from core.algorithms import GreedyScheduler

    operations, batches, start_dt = _build_case()
    sched = GreedyScheduler(calendar_service=_StubCalendarService())
    results, summary, _strategy, used_params = sched.schedule(
        operations=operations,
        batches=batches,
        start_dt=start_dt,
        dispatch_mode=dispatch_mode,
        dispatch_rule="slack",
    )
    return results, summary, used_params


def test_dispatch_blocking_consistency():
    # batch_order 仍走正式派工失败统计：失败即阻断该批次后续工序。
    results, summary, used_params = _run("batch_order")
    assert used_params.get("dispatch_mode") == "batch_order", f"dispatch_mode 解析异常：{used_params!r}"
    assert summary.total_ops == 3, f"total_ops 应为 3，实际 {summary.total_ops}"
    assert summary.scheduled_ops == 0, f"scheduled_ops 应为 0，实际 {summary.scheduled_ops}"
    assert summary.failed_ops == 3, f"failed_ops 应为 3，实际 {summary.failed_ops}"
    assert summary.scheduled_ops + summary.failed_ops == summary.total_ops, "summary 统计不一致"
    assert len(results) == 0, f"不应产出排程结果，实际 results={len(results)}"

    from core.infrastructure.errors import ValidationError

    # SGS 评分阶段必须能估算候选；缺资源不再生成不可评分兜底 key。
    try:
        _run("sgs")
    except ValidationError as exc:
        assert exc.field == "resource", f"SGS 缺资源应定位到 resource，实际={exc.field!r}"
    else:
        raise AssertionError("SGS 不应为缺资源内部工序生成不可评分兜底 key")


def test_dispatch_sgs_missing_batch_records_structured_failure_detail() -> None:
    from core.algorithms.greedy.dispatch.sgs import dispatch_sgs

    op_bad = SimpleNamespace(
        id=999,
        op_code="OP_BAD",
        batch_id="B_BAD",
        seq=1,
        source="internal",
        machine_id="M1",
        operator_id="O1",
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_id=None,
        op_type_name=None,
        supplier_id=None,
        ext_days=None,
        ext_group_id=None,
        ext_merge_mode=None,
        ext_group_total_days=None,
    )
    state = ScheduleRunState(base_time=datetime(2026, 1, 1, 8, 0, 0))

    scheduled_count, failed_count = dispatch_sgs(
        SimpleNamespace(calendar_service=_StubCalendarService()),
        sorted_ops=[op_bad],
        batches={},
        batch_order={},
        dispatch_rule="slack",
        base_time=state.base_time,
        end_dt_exclusive=None,
        machine_downtimes={},
        state=state,
        auto_assign_enabled=False,
        resource_pool=None,
        strict_mode=False,
    )

    assert scheduled_count == 0
    assert failed_count == 1
    assert [item["code"] for item in state.failure_details] == ["missing_batch"]
    assert state.failure_details[0]["op_code"] == "OP_BAD"


def test_graph_blocked_ops_already_counted_by_batch_skip_do_not_duplicate_failure_details() -> None:
    from core.algorithms.greedy.dispatch.sgs_graph import _record_graph_blocked_operations

    failed_op = SimpleNamespace(id=1, op_code="OP1", batch_id="B001", seq=1)
    blocked_op = SimpleNamespace(id=2, op_code="OP2", batch_id="B001", seq=2)
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
    """回归：missing_batch / dispatch 异常 / 图阻塞失败只写结构化 failure_details，不再往
    state.errors 塞原始中文串。旧行为会让原始串回落成 generic_scheduler_error（“请联系管理员”），
    与结构化具体文案并列形成双发并虚增 error_count。"""
    from core.algorithms.greedy.dispatch.sgs_graph import _record_graph_blocked_operations

    op = SimpleNamespace(id=1, op_code="OP1", batch_id="B001", seq=1)
    state = ScheduleRunState(base_time=datetime(2026, 1, 1, 8, 0, 0))
    state.record_missing_batch(op, "B001")
    state.record_dispatch_exception(op, "B001", dispatch_mode="sgs")
    assert state.errors == []
    assert [item["code"] for item in state.failure_details] == [
        "missing_batch",
        "dispatch_operation_exception",
    ]

    failed_op = SimpleNamespace(id=1, op_code="OP1", batch_id="B001", seq=1)
    blocked_op = SimpleNamespace(id=2, op_code="OP2", batch_id="B001", seq=2)
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
