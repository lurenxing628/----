"""回归测试：GreedyScheduler.schedule 在 batch_order 派工模式下，当 bid 赋值首行（读 batch_id）即抛异常时，except 分支不应因 bid 未定义触发 UnboundLocalError；该工序应计入 failed_ops，并以结构化 failure_details（code=dispatch_operation_exception，含 OP_ERR 标识）记录，公开文案由摘要层渲染，不泄露原始异常或 UnboundLocalError。"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace


@dataclass
class _StubCalendarService:
    """
    最小日历服务桩：满足 GreedyScheduler.schedule 所需接口。

    本回归用例仅验证：batch_order 模式下 bid 赋值失败时，不应在 except 中因 bid 未定义而崩溃。
    """

    def adjust_to_working_time(self, dt: datetime, priority=None, **_kwargs) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, **_kwargs) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, **_kwargs) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


class _FlakyBatchIdOp:
    """
    构造一个“batch_id 第二次读取抛异常”的工序对象：
    - 第 1 次读取用于 schedule() 内部排序 key 计算（应成功）
    - 第 2 次读取发生在 batch_order 分支 try 的首行 bid 赋值（应抛异常）

    修复前会在 except 中触发 UnboundLocalError（bid 未定义）；修复后应正常吞掉异常并计入 failed_ops。
    """

    def __init__(self, batch_id: str):
        self._batch_id = str(batch_id)
        self._read_cnt = 0

        # schedule() 里会使用到的字段
        self.id = 1
        self.op_code = "OP_ERR"
        self.seq = 1
        self.source = "internal"
        self.machine_id = "M1"
        self.operator_id = "O1"
        self.setup_hours = 1.0
        self.unit_hours = 0.0
        self.op_type_id = None
        self.op_type_name = None
        self.supplier_id = None
        self.ext_days = None
        self.ext_group_id = None
        self.ext_merge_mode = None
        self.ext_group_total_days = None

    @property
    def batch_id(self) -> str:
        self._read_cnt += 1
        if self._read_cnt >= 2:
            raise RuntimeError("boom")
        return self._batch_id


class _FlakyOpCodeOp:
    def __init__(self, batch_id: str):
        self.id = 2
        self.batch_id = batch_id
        self.seq = 1
        self.source = "internal"
        self.machine_id = "M1"
        self.operator_id = "O1"
        self.setup_hours = 1.0
        self.unit_hours = 0.0
        self.op_type_id = None
        self.op_type_name = None
        self.supplier_id = None
        self.ext_days = None
        self.ext_group_id = None
        self.ext_merge_mode = None
        self.ext_group_total_days = None

    @property
    def op_code(self) -> str:
        raise RuntimeError("bad op_code property")


def _build_quiet_logger() -> logging.Logger:
    # 本回归会故意触发排产异常；为避免控制台输出 traceback，使用静默 logger
    lg = logging.getLogger("aps.regression_batch_order_bid_unboundlocal")
    lg.handlers = []
    lg.addHandler(logging.NullHandler())
    lg.propagate = False
    lg.setLevel(logging.CRITICAL)
    return lg


def test_batch_order_bid_unboundlocal():

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
    operations = [_FlakyBatchIdOp(batch_id="B001")]
    start_dt = datetime(2026, 1, 1, 8, 0, 0)

    sched = GreedyScheduler(calendar_service=_StubCalendarService(), logger=_build_quiet_logger())
    results, summary, _strategy, used_params = sched.schedule(
        operations=operations,
        batches=batches,
        start_dt=start_dt,
        dispatch_mode="batch_order",
        dispatch_rule="slack",
    )

    assert used_params.get("dispatch_mode") == "batch_order", f"dispatch_mode 解析异常：{used_params!r}"
    assert summary.total_ops == 1, f"total_ops 应为 1，实际 {summary.total_ops}"
    assert summary.scheduled_ops == 0, f"scheduled_ops 应为 0，实际 {summary.scheduled_ops}"
    assert summary.failed_ops == 1, f"failed_ops 应为 1，实际 {summary.failed_ops}"
    assert len(results) == 0, f"不应产出排程结果，实际 results={len(results)}"

    # 失败统一记进结构化 failure_details，不再往 summary.errors 塞原始串（公开文案由摘要层渲染）。
    assert summary.errors == [], f"不应再往 summary.errors 塞原始串：{summary.errors!r}"
    assert summary.failure_details, "应记录异常到 failure_details"
    exception_details = [d for d in summary.failure_details if d.get("code") == "dispatch_operation_exception"]
    assert exception_details, f"failure_details 未包含派工异常：{summary.failure_details!r}"
    assert exception_details[0].get("op_code") == "OP_ERR", f"应保留工序标识：{exception_details!r}"
    detail_text = repr(summary.failure_details)
    assert "boom" not in detail_text, f"failure_details 不应暴露原异常：{detail_text}"
    assert "UnboundLocalError" not in detail_text, f"不应出现 UnboundLocalError：{detail_text}"


def test_sgs_dispatch_exception_bad_op_code_property_does_not_mask_failure():
    from core.algorithms.dispatch_rules import DispatchRule
    from core.algorithms.greedy.dispatch.sgs import dispatch_sgs
    from core.algorithms.greedy.run_context import ScheduleRunContext
    from core.algorithms.greedy.run_state import ScheduleRunState

    def _raise_internal(**_kwargs):
        raise RuntimeError("primary dispatch failed")

    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    state = ScheduleRunState(base_time=start_dt)
    context = ScheduleRunContext(
        calendar=_StubCalendarService(),
        logger=_build_quiet_logger(),
        algo_stats={},
        internal_callback=_raise_internal,
    )
    batch = SimpleNamespace(
        batch_id="B001",
        priority="normal",
        due_date=None,
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )

    scheduled_count, failed_count = dispatch_sgs(
        context,
        sorted_ops=[_FlakyOpCodeOp(batch_id="B001")],
        batches={"B001": batch},
        batch_order={"B001": 0},
        dispatch_rule=DispatchRule.SLACK,
        base_time=start_dt,
        end_dt_exclusive=None,
        machine_downtimes={},
        state=state,
        auto_assign_enabled=False,
        resource_pool=None,
    )

    assert scheduled_count == 0
    assert failed_count == 1
    assert state.failure_details
    assert state.failure_details[0]["code"] == "dispatch_operation_exception"
    # state.errors 不再承载原始串；失败已由结构化 failure_details 记录，且不泄漏原始异常文案。
    assert state.errors == []
    assert "bad op_code property" not in repr(state.failure_details)
