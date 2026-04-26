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
    from core.infrastructure.errors import ValidationError

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

    try:
        sched.schedule(
            operations=[op],
            batches={"B1": b},
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
        )
    except ValidationError as exc:
        assert exc.field == "efficiency", f"非有限效率应定位到 efficiency，实际={exc.field!r}"
    else:
        raise AssertionError("非有限效率不应回退到 1.0 后继续排产")

    print("OK")


if __name__ == "__main__":
    main()
