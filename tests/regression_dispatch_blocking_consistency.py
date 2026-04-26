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
        dispatch_mode=dispatch_mode,
        dispatch_rule="slack",
    )
    return results, summary, used_params


def main():
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

    print("OK")


if __name__ == "__main__":
    main()
