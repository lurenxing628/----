import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple


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


class _StubLogger:
    def exception(self, *args, **kwargs) -> None:
        return None


class _StubScheduler:
    def __init__(self):
        self.calendar = _StubCalendar()
        self.logger = _StubLogger()
        self.calls: List[str] = []

    def _schedule_external(self, *args, **kwargs):
        raise NotImplementedError("本回归不覆盖外协工序")

    def _schedule_internal(
        self,
        op: Any,
        batch: Any,
        batch_progress: Dict[str, datetime],
        machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
        base_time: datetime,
        errors: List[str],
        end_dt_exclusive: Optional[datetime],
        machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]] = None,
        *,
        auto_assign_enabled: bool = False,
        resource_pool: Optional[Dict[str, Any]] = None,
        last_op_type_by_machine: Optional[Dict[str, str]] = None,
        machine_busy_hours: Optional[Dict[str, float]] = None,
        operator_busy_hours: Optional[Dict[str, float]] = None,
    ):
        from core.algorithms.types import ScheduleResult

        op_code = str(getattr(op, "op_code", "") or "")
        self.calls.append(op_code)

        bid = str(getattr(op, "batch_id", "") or "")
        start = batch_progress.get(bid, base_time)
        end = start + timedelta(hours=1)
        return (
            ScheduleResult(
                op_id=int(getattr(op, "id", 0) or 0),
                op_code=op_code,
                batch_id=bid,
                seq=int(getattr(op, "seq", 0) or 0),
                machine_id=str(getattr(op, "machine_id", "") or ""),
                operator_id=str(getattr(op, "operator_id", "") or ""),
                start_time=start,
                end_time=end,
                source="internal",
                op_type_name=None,
            ),
            False,
        )


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.algorithms.dispatch_rules import DispatchRule
    from core.algorithms.greedy.dispatch.sgs import dispatch_sgs

    base_time = datetime(2026, 1, 1, 8, 0, 0)

    # BAD：交期更早，但工时为 inf（不可估算），应在评分阶段被惩罚
    batch_bad = SimpleNamespace(batch_id="B_BAD", priority="normal", due_date=date(2026, 1, 1), quantity=1)
    op_bad = SimpleNamespace(
        id=1,
        op_code="BAD_INF",
        batch_id="B_BAD",
        seq=1,
        source="internal",
        machine_id="M1",
        operator_id="O1",
        setup_hours=float("inf"),
        unit_hours=0.0,
        op_type_name="A",
    )

    # OK：交期更晚，但工时可估算
    batch_ok = SimpleNamespace(batch_id="B_OK", priority="normal", due_date=date(2026, 1, 10), quantity=1)
    op_ok = SimpleNamespace(
        id=2,
        op_code="OK_FINITE",
        batch_id="B_OK",
        seq=1,
        source="internal",
        machine_id="M1",
        operator_id="O1",
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_name="A",
    )

    sched = _StubScheduler()
    results: List[Any] = []
    errors: List[str] = []

    dispatch_sgs(
        sched,
        sorted_ops=[op_bad, op_ok],
        batches={"B_BAD": batch_bad, "B_OK": batch_ok},
        batch_order={"B_BAD": 0, "B_OK": 1},
        dispatch_rule=DispatchRule.CR,
        base_time=base_time,
        end_dt_exclusive=None,
        machine_downtimes=None,
        batch_progress={},
        external_group_cache={},
        machine_timeline={},
        operator_timeline={},
        machine_busy_hours={},
        operator_busy_hours={},
        last_op_type_by_machine={},
        last_end_by_machine={},
        auto_assign_enabled=False,
        resource_pool=None,
        results=results,
        errors=errors,
        blocked_batches=set(),
        scheduled_count=0,
        failed_count=0,
    )

    assert sched.calls, "未触发 _schedule_internal 调用"
    assert sched.calls[0] == "OK_FINITE", f"不可估算工时候选未被惩罚：calls={sched.calls!r}"
    assert results and getattr(results[0], "op_code", None) == "OK_FINITE", f"首个成功排程应为 OK_FINITE：results={results!r}"

    print("OK")


if __name__ == "__main__":
    main()

