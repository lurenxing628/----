"""回归测试（合并簇 seed_results_sanitize_contract）：守护 GreedyScheduler 注入 seed_results 时的清洗/净化契约——
去重（重复 op_id 仅出现 1 次）、坏时间剔除（end<=start 旧排产忽略 + 中文 warning 透出）、
半残资源种子（缺 operator_id / 缺 machine_id）仍按现有维度冻结、无效 op_id（=0）经 op_code 或 (batch_id,seq) 回填真实 id。

由四份原回归测试物理合并而来（方案 A，断言一条不动）：
- F1 regression_seed_results_dedup：重复 op_id 去重、时间回填。
- F2 regression_seed_results_drop_duplicate_op_id_and_bad_time：重复 op_id + 坏时间剔除 + warning 透出。
- F3 regression_seed_results_freeze_missing_resource：冻结种子缺一项资源维度仍冻结现有资源。
- F4 regression_seed_results_invalid_op_id_dedup：op_id<=0 经 op_code 或 (batch_id,seq) 匹配回填真实 id。

陷阱（规格 §10）：桩 _StubCalendarService 存在两种签名变体，禁统一为单桩——
F1/F2 路径不传 machine_id（4-arg 桩 _StubCalendarService4），F3/F4 路径含 machine_id（5-arg 桩 _StubCalendarService5）。
两个桩类、F3 的两 batch 工厂、各文件独有断言（warning×2 / all(op_id>0) / 跨 batch 冻结）一律全保留。
模块级 helper（_build_case / _run / _build_batches / _run_case）跨文件撞名，已加 _f1_/_f3_/_f4_ 场景前缀消除撞名。
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Optional


# ---------------------------------------------------------------------------
# 桩变体 1（4-arg，无 machine_id）：F1/F2 用。
# 反映 GreedyScheduler 在“去重 / 坏时间剔除”seed 路径下对 calendar_service 的调用方式。
# ---------------------------------------------------------------------------
@dataclass
class _StubCalendarService4:
    """
    最小日历服务桩（4-arg 变体）：满足 GreedyScheduler.schedule 所需接口。

    本变体方法签名仅含 priority/operator_id，无 machine_id 参数；add_calendar_days 为 2 参数。
    用于 F1（重复去重）/ F2（重复+坏时间）路径——禁与 5-arg 变体统一，避免掩盖本路径不传 machine_id 的契约。
    """

    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id: Optional[str] = None) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, operator_id: Optional[str] = None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


# ---------------------------------------------------------------------------
# 桩变体 2（5-arg，含 machine_id）：F3/F4 用。
# 反映 GreedyScheduler 在“半残资源冻结 / 无效 op_id 回填”seed 路径下对 calendar_service 的调用方式。
# ---------------------------------------------------------------------------
@dataclass
class _StubCalendarService5:
    """
    最小日历服务桩（5-arg 变体）：满足 GreedyScheduler.schedule 所需接口。

    本变体方法签名多了 machine_id 关键字参数，add_calendar_days 为 4 参数。
    用于 F3（半残资源冻结）/ F4（无效 op_id 回填）路径——禁与 4-arg 变体统一。
    """

    def adjust_to_working_time(
        self,
        dt: datetime,
        priority=None,
        machine_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(
        self,
        dt: datetime,
        hours: float,
        priority=None,
        machine_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


# ===========================================================================
# F1：重复 op_id 去重（seed 工序仅出现 1 次）+ 时间回填
# ===========================================================================
def _f1_build_case():
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
    operations = [op1, op2]

    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    seed_end = start_dt + timedelta(hours=1)
    return operations, batches, start_dt, seed_end


def _f1_run(dispatch_mode: str):

    from core.algorithms import GreedyScheduler, ScheduleResult

    operations, batches, start_dt, seed_end = _f1_build_case()

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
        )
    ]

    sched = GreedyScheduler(calendar_service=_StubCalendarService4())
    results, summary, _strategy, used_params = sched.schedule(
        operations=operations,
        batches=batches,
        start_dt=start_dt,
        seed_results=seed_results,
        dispatch_mode=dispatch_mode,
        dispatch_rule="slack",
    )
    return results, summary, used_params, seed_end


def test_seed_results_dedup():
    for mode in ("batch_order", "sgs"):
        results, summary, used_params, seed_end = _f1_run(mode)

        assert used_params.get("dispatch_mode") == mode, f"dispatch_mode 解析异常：{used_params!r}"

        op_ids = [int(r.op_id) for r in results]
        assert op_ids.count(1) == 1, f"seed 工序应只出现 1 次，实际 op_ids={op_ids}"
        assert set(op_ids) == {1, 2}, f"应仅包含 op_id=1/2，实际 op_ids={op_ids}"
        assert len(results) == 2, f"应仅产出 2 条结果（seed+新增），实际 len={len(results)} op_ids={op_ids}"

        assert summary.total_ops == 2, f"total_ops 应为 2（去重后=1+seed=1），实际 {summary.total_ops}"
        assert summary.scheduled_ops == 2, f"scheduled_ops 应为 2，实际 {summary.scheduled_ops}"
        assert summary.failed_ops == 0, f"failed_ops 应为 0，实际 {summary.failed_ops}"

        op2 = next((r for r in results if int(r.op_id) == 2), None)
        assert op2 is not None, "缺少 op_id=2 的排程结果"
        assert op2.start_time is not None, "op_id=2 start_time 为空"
        assert op2.start_time >= seed_end, f"op_id=2 应不早于 seed_end={seed_end}，实际 start_time={op2.start_time}"


# ===========================================================================
# F2：重复 op_id + 坏时间（end<=start）剔除 + warning 透出（中文逐字 pin）
# ===========================================================================
def test_seed_results_drop_duplicate_op_id_and_bad_time() -> None:

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

    # 1) 重复 seed：同 op_id=1 出现两条
    # 2) 坏时间 seed：op_id=2 且 end_time<=start_time，应被忽略
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
            end_time=seed_end,  # bad time
            source="internal",
            op_type_name=None,
        ),
    ]

    sched = GreedyScheduler(calendar_service=_StubCalendarService4())
    results, summary, _strategy, _used_params = sched.schedule(
        operations=operations,
        batches=batches,
        start_dt=start_dt,
        seed_results=seed_results,
        dispatch_mode="batch_order",
        dispatch_rule="slack",
    )

    op_ids = [int(r.op_id) for r in results]
    assert op_ids.count(1) == 1, f"重复 seed 应被去重，实际 op_ids={op_ids}"
    assert set(op_ids) == {1, 2}, f"应产出 op_id=1/2，实际 op_ids={op_ids}"
    assert len(results) == 2, f"应仅 2 条结果（seed+新增），实际 len={len(results)} op_ids={op_ids}"

    assert summary.total_ops == 2, f"total_ops 应为 2，实际 {summary.total_ops}"
    assert summary.scheduled_ops == 2, f"scheduled_ops 应为 2，实际 {summary.scheduled_ops}"
    assert summary.failed_ops == 0, f"failed_ops 应为 0，实际 {summary.failed_ops}"

    # warnings 应可观测（至少包含“重复工序编号”和“开始时间不早于结束时间”）
    warn_text = "\n".join([str(x) for x in (summary.warnings or [])])
    assert "重复工序编号" in warn_text, f"应提示重复旧排产记录，warnings={summary.warnings}"
    assert "开始时间不早于结束时间" in warn_text, f"应提示坏时间旧排产记录，warnings={summary.warnings}"

    # op2 应不早于 seed_end（确保 seed_end 推进了 batch_progress）
    op2_res = next((r for r in results if int(r.op_id) == 2), None)
    assert op2_res is not None and op2_res.start_time is not None
    assert op2_res.start_time >= seed_end, f"op2.start_time 应>=seed_end={seed_end}，实际 {op2_res.start_time}"


# ===========================================================================
# F3：冻结种子缺一项资源维度（缺 operator_id / 缺 machine_id）仍冻结现有资源
# 用两个 batch（B001 seed / B002 待排），与单 batch 场景不同——独立保留 _f3_build_batches。
# ===========================================================================
def _f3_build_batches():
    b1 = SimpleNamespace(
        batch_id="B001",
        priority="normal",
        due_date=None,
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )
    b2 = SimpleNamespace(
        batch_id="B002",
        priority="normal",
        due_date=None,
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )
    return {"B001": b1, "B002": b2}


def _f3_run_case(*, dispatch_mode: str, seed_machine_id, seed_operator_id, op_machine_id: str, op_operator_id: str):

    from core.algorithms import GreedyScheduler, ScheduleResult

    batches = _f3_build_batches()
    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    seed_end = start_dt + timedelta(hours=1)

    # B001：冻结种子（内部工序，但故意缺失一项资源）
    seed_results = [
        ScheduleResult(
            op_id=1,
            op_code="SEED_OP",
            batch_id="B001",
            seq=1,
            machine_id=seed_machine_id,
            operator_id=seed_operator_id,
            start_time=start_dt,
            end_time=seed_end,
            source="internal",
            op_type_name=None,
        )
    ]

    # B002：待排工序（占用与 seed 相同的资源维度，用于验证是否会被推迟）
    operations = [
        SimpleNamespace(
            id=2,
            op_code="OP2",
            batch_id="B002",
            seq=1,
            source="internal",
            machine_id=op_machine_id,
            operator_id=op_operator_id,
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
    ]

    sched = GreedyScheduler(calendar_service=_StubCalendarService5())
    results, summary, used_strategy, used_params = sched.schedule(
        operations=operations,
        batches=batches,
        start_dt=start_dt,
        seed_results=seed_results,
        dispatch_mode=dispatch_mode,
        dispatch_rule="slack",
    )
    return results, summary, used_strategy, used_params, seed_end


def test_seed_results_freeze_missing_resource():
    for mode in ("batch_order", "sgs"):
        # Case A：seed 缺 operator_id，但有 machine_id -> 应冻结设备资源
        results, summary, _strategy, used_params, seed_end = _f3_run_case(
            dispatch_mode=mode,
            seed_machine_id="M1",
            seed_operator_id=None,
            op_machine_id="M1",
            op_operator_id="O2",
        )
        assert used_params.get("dispatch_mode") == mode, f"dispatch_mode 解析异常：{used_params!r}"
        assert summary.failed_ops == 0, f"预期 failed_ops=0，实际 {summary.failed_ops}"
        op2 = next((r for r in results if int(r.op_id) == 2), None)
        assert op2 is not None, "缺少 op_id=2 的排程结果"
        assert op2.start_time is not None, "op_id=2 start_time 为空"
        assert (
            op2.start_time >= seed_end
        ), f"[{mode}] seed 缺 operator_id 时仍应冻结 machine=M1；期望 op2.start_time>={seed_end}，实际 {op2.start_time}"

        # Case B：seed 缺 machine_id，但有 operator_id -> 应冻结人员资源
        results, summary, _strategy, used_params, seed_end = _f3_run_case(
            dispatch_mode=mode,
            seed_machine_id=None,
            seed_operator_id="O1",
            op_machine_id="M2",
            op_operator_id="O1",
        )
        assert used_params.get("dispatch_mode") == mode, f"dispatch_mode 解析异常：{used_params!r}"
        assert summary.failed_ops == 0, f"预期 failed_ops=0，实际 {summary.failed_ops}"
        op2 = next((r for r in results if int(r.op_id) == 2), None)
        assert op2 is not None, "缺少 op_id=2 的排程结果"
        assert op2.start_time is not None, "op_id=2 start_time 为空"
        assert (
            op2.start_time >= seed_end
        ), f"[{mode}] seed 缺 machine_id 时仍应冻结 operator=O1；期望 op2.start_time>={seed_end}，实际 {op2.start_time}"


# ===========================================================================
# F4：op_id<=0（=0）经 op_code 或 (batch_id,seq) 匹配回填真实 id
# seed_end = start_dt + 2h（区分“复用 seed”与“重排 op1(1h)”，禁改 1h）。
# ===========================================================================
def _f4_build_case():
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

    # 两道内部工序（同批次串行）
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
    operations = [op1, op2]

    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    # seed 故意给更长的时间（2h），用于区分“复用 seed”与“重新排产 op1(1h)”
    seed_end = start_dt + timedelta(hours=2)
    return operations, batches, start_dt, seed_end


def _f4_run(dispatch_mode: str, *, seed_op_code: str, seed_seq: int):

    from core.algorithms import GreedyScheduler, ScheduleResult

    operations, batches, start_dt, seed_end = _f4_build_case()

    # 注意：op_id=0（无效），但可通过 op_code 或 (batch_id, seq) 匹配到真实工序 id=1
    seed_results = [
        ScheduleResult(
            op_id=0,
            op_code=seed_op_code,
            batch_id="B001",
            seq=int(seed_seq),
            machine_id="M1",
            operator_id="O1",
            start_time=start_dt,
            end_time=seed_end,
            source="internal",
            op_type_name=None,
        )
    ]

    sched = GreedyScheduler(calendar_service=_StubCalendarService5())
    results, summary, _strategy, used_params = sched.schedule(
        operations=operations,
        batches=batches,
        start_dt=start_dt,
        seed_results=seed_results,
        dispatch_mode=dispatch_mode,
        dispatch_rule="slack",
    )
    return results, summary, used_params, seed_end


def test_seed_results_invalid_op_id_dedup():
    # 两种派工模式都应满足：seed 回填 + 去重 + total_ops 正确
    for mode in ("batch_order", "sgs"):
        for tag, seed_op_code, seed_seq in (
            ("by_op_code", "OP1", 1),
            ("by_batch_seq", "", 1),
        ):
            results, summary, used_params, seed_end = _f4_run(mode, seed_op_code=seed_op_code, seed_seq=seed_seq)

            assert used_params.get("dispatch_mode") == mode, f"dispatch_mode 解析异常：{used_params!r}"

            op_ids = [int(r.op_id) for r in results]
            assert all(x > 0 for x in op_ids), f"[{mode}|{tag}] 不应产出 op_id<=0 的结果，实际 op_ids={op_ids}"
            assert set(op_ids) == {1, 2}, f"[{mode}|{tag}] 应仅包含 op_id=1/2，实际 op_ids={op_ids}"
            assert len(results) == 2, f"[{mode}|{tag}] 应仅产出 2 条结果（seed+新增），实际 len={len(results)} op_ids={op_ids}"

            assert summary.total_ops == 2, f"[{mode}|{tag}] total_ops 应为 2（去重后=1+seed=1），实际 {summary.total_ops}"
            assert summary.scheduled_ops == 2, f"[{mode}|{tag}] scheduled_ops 应为 2，实际 {summary.scheduled_ops}"
            assert summary.failed_ops == 0, f"[{mode}|{tag}] failed_ops 应为 0，实际 {summary.failed_ops}"

            # 验证 seed 时间被复用：op2 应不早于 seed_end（若 seed 被丢弃或重复排产口径错误，可能早于 seed_end）
            op2 = next((r for r in results if int(r.op_id) == 2), None)
            assert op2 is not None, f"[{mode}|{tag}] 缺少 op_id=2 的排程结果"
            assert op2.start_time is not None, f"[{mode}|{tag}] op_id=2 start_time 为空"
            assert (
                op2.start_time >= seed_end
            ), f"[{mode}|{tag}] op_id=2 应不早于 seed_end={seed_end}，实际 start_time={op2.start_time}"
