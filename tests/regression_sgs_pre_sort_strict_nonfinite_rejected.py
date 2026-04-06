from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import pytest

from core.algorithms.dispatch_rules import DispatchRule
from core.algorithms.greedy.dispatch.sgs import dispatch_sgs
from core.infrastructure.errors import ValidationError


@dataclass
class _StubCalendar:
    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id: Optional[str] = None) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


class _StubLogger:
    def exception(self, *args, **kwargs) -> None:
        return None


class _StubScheduler:
    def __init__(self):
        self.calendar = _StubCalendar()
        self.logger = _StubLogger()

    def _schedule_external(self, *args, **kwargs):
        raise NotImplementedError

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
        raise AssertionError("strict_mode 非法工时应在评分前被拒绝，不应进入 _schedule_internal")


def test_sgs_pre_sort_strict_nonfinite_setup_hours_rejected() -> None:
    sched = _StubScheduler()
    batch = SimpleNamespace(batch_id="B_BAD", priority="normal", due_date=date(2026, 1, 2), quantity=1)
    op = SimpleNamespace(
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

    with pytest.raises(ValidationError) as exc_info:
        dispatch_sgs(
            sched,
            sorted_ops=[op],
            batches={"B_BAD": batch},
            batch_order={"B_BAD": 0},
            dispatch_rule=DispatchRule.CR,
            base_time=datetime(2026, 1, 1, 8, 0, 0),
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
            results=[],
            errors=[],
            blocked_batches=set(),
            scheduled_count=0,
            failed_count=0,
            strict_mode=True,
        )

    assert exc_info.value.field == "setup_hours", f"SGS strict_mode 未拒绝非有限 setup_hours：{exc_info.value.field!r}"
