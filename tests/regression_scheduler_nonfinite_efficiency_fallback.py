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
class _StubCalendar:
    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id: Optional[str] = None) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> float:
        # 回归场景：异常数据导致非有限效率
        return float("inf")

    def add_calendar_days(self, dt: datetime, days: float, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.algorithms import GreedyScheduler

    sched = GreedyScheduler(calendar_service=_StubCalendar())
    op = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B1",
        seq=1,
        source="internal",
        machine_id="M1",
        operator_id="O1",
        setup_hours=2.0,
        unit_hours=0.0,
        op_type_name="车削",
    )
    b = SimpleNamespace(
        batch_id="B1",
        priority="normal",
        due_date="2026-01-10",
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )

    results, summary, _strategy, _used_params = sched.schedule(
        operations=[op],
        batches={"B1": b},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
    )

    assert summary.scheduled_ops == 1 and summary.failed_ops == 0, f"排产应成功：summary={summary!r}"
    assert results, "应产生 1 条排程结果"
    r0 = results[0]
    assert r0.end_time and r0.start_time and r0.end_time > r0.start_time, f"非有限效率不应导致零时长：result={r0!r}"
    dur_h = (r0.end_time - r0.start_time).total_seconds() / 3600.0
    assert abs(dur_h - 2.0) < 1e-9, f"应按效率=1.0 回退：dur_h={dur_h!r}"

    print("OK")


if __name__ == "__main__":
    main()

