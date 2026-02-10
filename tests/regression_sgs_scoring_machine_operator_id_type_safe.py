import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


@dataclass
class _StubCalendar:
    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id: str = None) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id: str = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, machine_id: str = None, operator_id: str = None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float, machine_id: str = None, operator_id: str = None) -> datetime:
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

    # 让排产阶段必定失败：setup_hours 非法（触发 _schedule_internal 的“工时不合法”错误）
    op_late = SimpleNamespace(
        id=1,
        op_code="OP_LATE",
        batch_id="B_LATE",
        seq=1,
        source="internal",
        machine_id=123,  # int（历史代码会在评分阶段 .strip() 崩溃）
        operator_id=456,  # int
        setup_hours="bad",
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
        setup_hours="bad",
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


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

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
    assert summary.scheduled_ops == 0, f"scheduled_ops 应为 0，实际 {summary.scheduled_ops}"
    assert summary.failed_ops == 2, f"failed_ops 应为 2，实际 {summary.failed_ops}"
    assert len(results) == 0, f"不应产出排程结果，实际 results={len(results)}"

    # 关键断言：第一个被尝试排产（从而产生 errors[0]）的应是更早交期的 OP_EARLY
    assert summary.errors, "应产生错误信息（工时不合法）"
    assert "OP_EARLY" in (summary.errors[0] or ""), f"SGS 评分选择错误：errors[0]={summary.errors[0]!r}"

    print("OK")


if __name__ == "__main__":
    main()

