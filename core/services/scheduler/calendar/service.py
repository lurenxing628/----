from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from core.algorithm_runtime.calendar_timing_memo import register_calendar_timing_guard
from core.algorithm_runtime.checkpoint_calendar import register_checkpoint_calendar

from .admin import CalendarAdmin
from .checkpoint_certificate import calendar_checkpoint_snapshot
from .day_policy import DayPolicy
from .engine import CalendarEngine
from .native_timing import make_calendar_days_guard, make_native_method_guard, make_timing_memo_guard


class CalendarService:
    """
    工作日历服务（对外 façade）。

    说明：
    - 日历服务入口：`from core.services.scheduler.calendar.service import CalendarService`
    - 内部按职责拆分：管理侧（CRUD/标准化）与引擎侧（时间推进/效率）
    """

    def __init__(self, conn, logger=None, *, capture=None, captured_global_rows=None):
        self.conn = conn
        self.logger = logger
        self._admin = CalendarAdmin(conn, logger=logger)
        self._engine = CalendarEngine(conn, logger=logger, capture=capture, captured_global_rows=captured_global_rows)

    def normalization_operation(self):
        """One calendar-row normalization operation; workday defaults come from this service's engine."""
        return self._admin.normalization_operation(self._engine.default_periods)

    def policy_for_datetime(self, dt: datetime, operator_id: Optional[str] = None) -> DayPolicy:
        return self._engine.policy_for_datetime(dt, operator_id=operator_id)

    def get_efficiency(self, dt: datetime, operator_id: Optional[str] = None) -> float:
        return self._engine.get_efficiency(dt, operator_id=operator_id)

    def adjust_to_working_time(
        self, dt: datetime, priority: Optional[str] = None, operator_id: Optional[str] = None,
    ) -> datetime:
        return self._engine.adjust_to_working_time(dt, priority=priority, operator_id=operator_id)

    def add_working_hours(
        self, start: datetime, hours: float, priority: Optional[str] = None, operator_id: Optional[str] = None,
    ) -> datetime:
        return self._engine.add_working_hours(start, hours, priority=priority, operator_id=operator_id)

    def add_effective_hours(
        self, start: datetime, hours: float, priority: Optional[str] = None, operator_id: Optional[str] = None,
    ) -> datetime:
        return self._engine.add_effective_hours(start, hours, priority=priority, operator_id=operator_id)

    def add_calendar_days(self, start: datetime, days: Optional[float]) -> datetime:
        return self._engine.add_calendar_days(start, days)

    def working_hours_between(
        self, start: datetime, end: datetime, priority: Optional[str] = None, operator_id: Optional[str] = None,
    ) -> float:
        return self._engine.working_hours_between(start, end, priority=priority, operator_id=operator_id)

    def certified_slot_window(self, dt: datetime, *, priority=None, operator_id=None):
        """Constant native policy span; adapted or instrumented timing stays legacy."""
        if not _NATIVE_METHODS_UNCHANGED(self):
            return None
        policy = self._engine.policy_for_datetime(dt, operator_id=operator_id)
        if policy.date_str != dt.date().isoformat() or not policy.is_priority_allowed(priority):
            return None
        window = next(((start, end) for start, end in policy.work_windows() if start <= dt < end), None)
        if window is None:
            return None
        start, end = window
        if end.date() != dt.date():
            end = datetime.combine(dt.date() + timedelta(days=1), datetime.min.time())
        return start, end

    def capacity_hours_between(self, start: datetime, end: datetime, *, priority=None, operator_id=None) -> float:
        return self._engine.capacity_hours_between(start, end, priority=priority, operator_id=operator_id)

    def certified_decode_checkpoint_snapshot(self):
        """Business calendar contents, unchanged by ordinary policy-cache population."""
        return calendar_checkpoint_snapshot(self)


_NATIVE_METHODS_UNCHANGED = make_native_method_guard(CalendarService)
register_calendar_timing_guard(CalendarService, make_timing_memo_guard(CalendarService),
                               calendar_days_guard=make_calendar_days_guard(CalendarService))
register_checkpoint_calendar(CalendarService, CalendarService.certified_decode_checkpoint_snapshot)
