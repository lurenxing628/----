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
    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id: Optional[str] = None) -> datetime:
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, operator_id: Optional[str] = None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


class _StubConfigService:
    def __init__(self, values):
        self._values = dict(values or {})

    def get(self, key: str, default=None):
        return self._values.get(key, default)


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

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

    sched = GreedyScheduler(
        calendar_service=_StubCalendarService(),
        config_service=_StubConfigService({"auto_assign_enabled": "yes"}),
    )
    _results, summary, _strategy, _used_params = sched.schedule(
        operations=[op],
        batches=batches,
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        dispatch_mode="batch_order",
        dispatch_rule="slack",
        resource_pool={},
    )

    stats = getattr(sched, "_last_algo_stats", {}) or {}
    fallback_counts = (stats.get("fallback_counts") or {}) if isinstance(stats, dict) else {}

    assert summary.failed_ops == 1, f"行为回归异常：{summary.failed_ops}"
    assert int(fallback_counts.get("internal_auto_assign_attempt_count") or 0) == 1, f"auto-assign attempt 计数异常：{fallback_counts!r}"
    assert int(fallback_counts.get("internal_auto_assign_failed_count") or 0) == 1, f"auto-assign failed 计数异常：{fallback_counts!r}"
    assert int(fallback_counts.get("auto_assign_missing_op_type_id_count") or 0) == 1, (
        f"auto_assign 根因计数异常：{fallback_counts!r}"
    )

    print("OK")


if __name__ == "__main__":
    main()
