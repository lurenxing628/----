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
class _StubCalendarService:
    """
    最小日历服务桩：满足 GreedyScheduler.schedule 所需接口。

    说明：本用例只验证 batch_order_override 去重后的排序行为，
    不依赖真实工作日历逻辑。
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
    复现 bug：

    - batch_order_override 含重复 batch_id（例如 ["B1","B2","B1","B3"]）
    - 若不去重，最终 batch_order 字典会把 B1 的位置覆盖成“最后一次出现”的索引，
      从而导致 B2 的工序优先于 B1 被尝试排产（排序错误）。
    """

    batches = {
        "B1": SimpleNamespace(
            batch_id="B1",
            priority="normal",
            due_date="2026-01-10",
            ready_status="yes",
            ready_date=None,
            created_at=None,
            quantity=1,
        ),
        "B2": SimpleNamespace(
            batch_id="B2",
            priority="normal",
            due_date="2026-01-10",
            ready_status="yes",
            ready_date=None,
            created_at=None,
            quantity=1,
        ),
        "B3": SimpleNamespace(
            batch_id="B3",
            priority="normal",
            due_date="2026-01-10",
            ready_status="yes",
            ready_date=None,
            created_at=None,
            quantity=1,
        ),
    }

    # 每个批次 1 道外协工序，ext_days=0 触发错误并写入 summary.errors（顺序可用于断言排序）
    op_b1 = SimpleNamespace(
        id=101,
        op_code="OP_B1",
        batch_id="B1",
        seq=1,
        source="external",
        ext_days=0,  # <=0：不合法
        ext_group_id=None,
        ext_merge_mode=None,
        ext_group_total_days=None,
        machine_id=None,
        operator_id=None,
        setup_hours=None,
        unit_hours=None,
        op_type_id=None,
        op_type_name=None,
        supplier_id=None,
    )
    op_b2 = SimpleNamespace(
        id=102,
        op_code="OP_B2",
        batch_id="B2",
        seq=1,
        source="external",
        ext_days=0,
        ext_group_id=None,
        ext_merge_mode=None,
        ext_group_total_days=None,
        machine_id=None,
        operator_id=None,
        setup_hours=None,
        unit_hours=None,
        op_type_id=None,
        op_type_name=None,
        supplier_id=None,
    )
    op_b3 = SimpleNamespace(
        id=103,
        op_code="OP_B3",
        batch_id="B3",
        seq=1,
        source="external",
        ext_days=0,
        ext_group_id=None,
        ext_merge_mode=None,
        ext_group_total_days=None,
        machine_id=None,
        operator_id=None,
        setup_hours=None,
        unit_hours=None,
        op_type_id=None,
        op_type_name=None,
        supplier_id=None,
    )

    # 刻意打乱原始 operations 顺序，确保断言依赖于 batch_order 排序而非输入顺序
    operations = [op_b2, op_b1, op_b3]
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
        dispatch_mode="batch_order",
        batch_order_override=["B1", "B2", "B1", "B3"],
    )

    assert used_params.get("dispatch_mode") == "batch_order", f"dispatch_mode 解析异常：{used_params!r}"
    assert summary.total_ops == 3, f"total_ops 应为 3，实际 {summary.total_ops}"
    assert summary.scheduled_ops == 0, f"scheduled_ops 应为 0，实际 {summary.scheduled_ops}"
    assert summary.failed_ops == 3, f"failed_ops 应为 3，实际 {summary.failed_ops}"
    assert len(results) == 0, f"不应产出排程结果，实际 results={len(results)}"

    # 关键断言：去重后 B1 应保持在 override 的首位，因此第一个错误应来自 OP_B1
    assert summary.errors, "应产生错误信息（外协周期不合法）"
    assert "OP_B1" in (summary.errors[0] or ""), f"batch_order_override 去重失败：errors[0]={summary.errors[0]!r}"

    print("OK")


if __name__ == "__main__":
    main()

