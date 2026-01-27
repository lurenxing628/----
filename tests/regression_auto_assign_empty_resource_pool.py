import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace


def find_repo_root() -> str:
    """
    约定：仓库根目录包含 app.py 与 schema.sql。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


@dataclass
class _StubCalendarService:
    """
    最小日历服务桩：满足 GreedyScheduler.schedule 所需接口。
    """

    def adjust_to_working_time(self, dt: datetime, priority=None) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


class _StubConfigService:
    def __init__(self, values):
        self._values = dict(values or {})

    def get(self, key: str, default=None):
        return self._values.get(key, default)


def main():
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.algorithms import GreedyScheduler

    # 构造一个内部工序：刻意缺省 machine_id/operator_id
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

    op = SimpleNamespace(
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
    operations = [op]

    sched = GreedyScheduler(
        calendar_service=_StubCalendarService(),
        config_service=_StubConfigService({"auto_assign_enabled": "yes"}),
    )

    results, summary, _strategy, used_params = sched.schedule(
        operations=operations,
        batches=batches,
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        dispatch_mode="batch_order",
        dispatch_rule="slack",
        resource_pool={},  # 关键：显式提供空 dict，不应被当成“未提供”
    )

    assert used_params.get("auto_assign_enabled") == "yes", f"auto_assign_enabled 解析异常：{used_params!r}"
    assert summary.total_ops == 1, f"total_ops 应为 1，实际 {summary.total_ops}"
    assert summary.scheduled_ops == 0, f"scheduled_ops 应为 0，实际 {summary.scheduled_ops}"
    assert summary.failed_ops == 1, f"failed_ops 应为 1，实际 {summary.failed_ops}"
    assert len(results) == 0, f"不应产出排程结果，实际 results={len(results)}"

    # 修复目标：resource_pool={} 时仍进入 auto-assign 分支，给出“自动分配失败”而不是“无法排产（必填）”
    assert any("自动分配失败" in (e or "") for e in (summary.errors or [])), f"错误信息不符合预期：{summary.errors!r}"

    print("OK")


if __name__ == "__main__":
    main()

