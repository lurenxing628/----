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
    """
    最小日历服务桩：满足 GreedyScheduler.schedule 所需接口。

    说明：本用例只验证 SGS 评分兜底行为，不依赖真实工作日历逻辑。
    """

    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id: Optional[str] = None) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, operator_id: Optional[str] = None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def _build_case():
    """
    构造一个关键场景（复现历史 bug）：

    - 两个批次各 1 道外协工序，且 ext_days=0（评分阶段不可估算，历史代码会 continue）
    - 通过 batch_order_override 强制 candidates[0] 是“交期更晚”的批次
    - 期望：即便所有候选都不可估算，SGS 仍应基于 dispatch key（交期）选择更紧急者，
      而不是无条件回退到 candidates[0]。
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
        source="external",
        machine_id=None,
        operator_id=None,
        setup_hours=None,
        unit_hours=None,
        op_type_id=None,
        op_type_name=None,
        supplier_id=None,
        ext_days=0,  # <=0：不可估算
        ext_group_id=None,
        ext_merge_mode=None,
        ext_group_total_days=None,
    )
    op_early = SimpleNamespace(
        id=2,
        op_code="OP_EARLY",
        batch_id="B_EARLY",
        seq=1,
        source="external",
        machine_id=None,
        operator_id=None,
        setup_hours=None,
        unit_hours=None,
        op_type_id=None,
        op_type_name=None,
        supplier_id=None,
        ext_days=0,  # <=0：不可估算
        ext_group_id=None,
        ext_merge_mode=None,
        ext_group_total_days=None,
    )

    # 注意：这里的 operations 顺序不重要；SGS 的 candidates 顺序由 batch_order_override 控制
    operations = [op_late, op_early]
    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    return operations, batches, start_dt


def main():
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.algorithms import GreedyScheduler

    operations, batches, start_dt = _build_case()

    sched = GreedyScheduler(calendar_service=_StubCalendarService())
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
    assert summary.scheduled_ops == 0, f"scheduled_ops 应为 0，实际 {summary.scheduled_ops}"
    assert summary.failed_ops == 2, f"failed_ops 应为 2，实际 {summary.failed_ops}"
    assert len(results) == 0, f"不应产出排程结果，实际 results={len(results)}"

    # 关键断言：第一个被尝试排产（从而产生 errors[0]）的应是更早交期的 OP_EARLY
    assert summary.errors, "应产生错误信息（外协周期不合法）"
    assert "OP_EARLY" in (summary.errors[0] or ""), f"SGS 评分兜底选择错误：errors[0]={summary.errors[0]!r}"

    algo_stats = getattr(sched, "_last_algo_stats", {}) or {}
    fallback_counts = algo_stats.get("fallback_counts", {}) or {}
    probe_keys = [
        "auto_assign_missing_op_type_id_count",
        "auto_assign_missing_machine_pool_count",
        "auto_assign_no_machine_candidate_count",
        "auto_assign_invalid_total_hours_count",
        "auto_assign_no_operator_candidate_count",
        "auto_assign_no_feasible_pair_count",
    ]
    for key in probe_keys:
        assert fallback_counts.get(key, 0) == 0, (
            f"评分探测污染了 fallback_counts[{key!r}]={fallback_counts.get(key, 0)}，"
            "probe_only=True 时不应记数"
        )

    _test_probe_only_internal_ops(GreedyScheduler)
    print("OK")


def _test_probe_only_internal_ops(GreedyScheduler):
    """验证 SGS 评分阶段的自动分配探测不污染 fallback_counts。

    构造内部工序（source=internal），缺 machine_id/operator_id/op_type_id，
    开启 auto_assign + resource_pool 非空。
    评分阶段应走 probe_only=True → _count 为空操作 → 不累加计数。
    正式排产阶段不传 probe_only → 应正常记数。
    """

    class _StubConfigService:
        def __init__(self, values):
            self._values = dict(values or {})

        def get(self, key, default=None):
            return self._values.get(key, default)

    batch = SimpleNamespace(
        batch_id="B_INT", priority="normal", due_date="2026-01-10",
        ready_status="yes", ready_date=None, created_at=None, quantity=1,
    )
    op = SimpleNamespace(
        id=10, op_code="OP_INT", batch_id="B_INT", seq=1,
        source="internal",
        machine_id="", operator_id="",
        setup_hours=1.0, unit_hours=0.5,
        op_type_id=None, op_type_name=None, supplier_id=None,
        ext_days=None, ext_group_id=None, ext_merge_mode=None, ext_group_total_days=None,
    )

    sched = GreedyScheduler(
        calendar_service=_StubCalendarService(),
        config_service=_StubConfigService({"auto_assign_enabled": "yes"}),
    )
    results, summary, _strategy, used_params = sched.schedule(
        operations=[op],
        batches={"B_INT": batch},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        dispatch_mode="sgs",
        dispatch_rule="slack",
        resource_pool={},  # 非 None → 触发自动分配
    )

    algo_stats = getattr(sched, "_last_algo_stats", {}) or {}
    fallback_counts = algo_stats.get("fallback_counts", {}) or {}

    # 核心断言：1 道工序 → 正式排产阶段记 1 次 auto_assign_missing_op_type_id_count。
    # 若 probe_only=True 泄漏，评分阶段也会记 1 次 → 总计 2。
    # 因此精确断言为 1 即可锁住 probe_only 的正确性。
    assert fallback_counts.get("auto_assign_missing_op_type_id_count", 0) == 1, (
        f"auto_assign_missing_op_type_id_count 应为 1（仅正式排产阶段），"
        f"实际={fallback_counts.get('auto_assign_missing_op_type_id_count', 0)}；"
        "若为 2 说明评分探测泄漏了计数（probe_only 未生效）"
    )

    assert int(fallback_counts.get("internal_auto_assign_attempt_count", 0)) == 1, (
        f"正式排产阶段应恰好尝试 1 次自动分配：{fallback_counts!r}"
    )
    assert int(fallback_counts.get("internal_auto_assign_failed_count", 0)) == 1, (
        f"正式排产阶段自动分配应恰好失败 1 次（缺 op_type_id）：{fallback_counts!r}"
    )


if __name__ == "__main__":
    main()

