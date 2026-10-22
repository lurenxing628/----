from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from core.algorithm_runtime.calendar_timing_memo import register_calendar_timing_guard
from core.algorithm_runtime.checkpoint_calendar import register_checkpoint_calendar
from core.models import OperatorCalendar, WorkCalendar
from core.services.common.datetime_normalize import normalize_date
from core.services.common.excel_import_executor import execute_preview_rows_transactional
from core.services.common.excel_service import ImportMode
from core.services.common.normalize import to_str_or_blank

from .admin import CalendarAdmin
from .checkpoint_certificate import calendar_checkpoint_snapshot
from .engine import CalendarEngine, DayPolicy
from .native_timing import make_calendar_days_guard, make_native_method_guard, make_timing_memo_guard


class CalendarService:
    """
    工作日历服务（对外 façade）。

    说明：
    - 日历服务入口：`from core.services.scheduler.calendar.service import CalendarService`
    - 内部按职责拆分：管理侧（CRUD/标准化）与引擎侧（时间推进/效率）
    """

    def __init__(self, conn, logger=None, *, capture=None):
        self.conn = conn
        self.logger = logger
        self._admin = CalendarAdmin(conn, logger=logger)
        self._engine = CalendarEngine(conn, logger=logger, capture=capture)

    # -------------------------
    # CRUD（给页面/Excel用）
    # -------------------------
    def get(self, date_value: Any) -> WorkCalendar:
        d = normalize_date(date_value)
        row = self._admin.repo.get(d)
        return row if row else self._engine._default_for_date(d)

    def list_all(self) -> List[WorkCalendar]:
        return self._admin.list_all()

    def list_range(self, start_date: Any, end_date: Any) -> List[WorkCalendar]:
        return self._admin.list_range(start_date, end_date)

    def upsert(
        self,
        date_value: Any,
        day_type: Any = None,
        shift_hours: Any = None,
        shift_start: Any = None,
        shift_end: Any = None,
        efficiency: Any = None,
        allow_normal: Any = None,
        allow_urgent: Any = None,
        remark: Any = None,
        periods: Any = None,
    ) -> WorkCalendar:
        row = self._admin.upsert(
            date_value=date_value,
            day_type=day_type,
            shift_hours=shift_hours,
            shift_start=shift_start,
            shift_end=shift_end,
            efficiency=efficiency,
            allow_normal=allow_normal,
            allow_urgent=allow_urgent,
            remark=remark,
            periods=periods,
        )
        self._engine.clear_policy_cache()
        return row

    def upsert_no_tx(self, calendar_payload: Dict[str, Any]) -> WorkCalendar:
        row = self._admin.upsert_no_tx(calendar_payload)
        self._engine.clear_policy_cache()
        return row

    def delete(self, date_value: Any) -> None:
        self._admin.delete(date_value)
        self._engine.clear_policy_cache()

    def delete_all_no_tx(self) -> None:
        self._admin.delete_all_no_tx()
        self._engine.clear_policy_cache()

    # -------------------------
    # CRUD：人员专属日历（OperatorCalendar）
    # -------------------------
    def get_operator_calendar(self, operator_id: Any, date_value: Any) -> Optional[OperatorCalendar]:
        return self._admin.get_operator_calendar(operator_id, date_value)

    def list_operator_calendar(self, operator_id: Any) -> List[OperatorCalendar]:
        return self._admin.list_operator_calendar(operator_id)

    def list_operator_calendar_all(self) -> List[OperatorCalendar]:
        return self._admin.list_operator_calendar_all()

    def upsert_operator_calendar(
        self,
        operator_id: Any,
        date_value: Any,
        day_type: Any = None,
        shift_hours: Any = None,
        shift_start: Any = None,
        shift_end: Any = None,
        efficiency: Any = None,
        allow_normal: Any = None,
        allow_urgent: Any = None,
        remark: Any = None,
        periods: Any = None,
    ) -> OperatorCalendar:
        row = self._admin.upsert_operator_calendar(
            operator_id=operator_id,
            date_value=date_value,
            day_type=day_type,
            shift_hours=shift_hours,
            shift_start=shift_start,
            shift_end=shift_end,
            efficiency=efficiency,
            allow_normal=allow_normal,
            allow_urgent=allow_urgent,
            remark=remark,
            periods=periods,
        )
        self._engine.clear_policy_cache()
        return row

    def upsert_operator_calendar_no_tx(self, calendar_payload: Dict[str, Any]) -> OperatorCalendar:
        row = self._admin.upsert_operator_calendar_no_tx(calendar_payload)
        self._engine.clear_policy_cache()
        return row

    def delete_operator_calendar(self, operator_id: Any, date_value: Any) -> None:
        self._admin.delete_operator_calendar(operator_id, date_value)
        self._engine.clear_policy_cache()

    def delete_operator_calendar_all_no_tx(self) -> None:
        self._admin.delete_operator_calendar_all_no_tx()
        self._engine.clear_policy_cache()

    def import_operator_calendar_from_preview_rows(
        self,
        *,
        preview_rows: List[Any],
        mode: ImportMode,
        existing_ids: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """
        人员专属日历 Excel 导入编排入口（事务由本方法统一控制）。
        """
        rows = list(preview_rows or [])
        existing_row_ids = (
            set(existing_ids or set()) if existing_ids is not None else {f"{c.operator_id}|{c.date}" for c in self.list_operator_calendar_all()}
        )

        def _replace_existing_no_tx() -> None:
            self._admin.delete_operator_calendar_all_no_tx()

        def _row_id_getter(pr: Any) -> str:
            rid = to_str_or_blank(pr.data.get("__id"))
            if rid:
                return rid
            op_id = to_str_or_blank(pr.data.get("工号"))
            date_str = to_str_or_blank(pr.data.get("日期"))
            return f"{op_id}|{date_str}"

        def _apply_row_no_tx(pr: Any, _existed: bool) -> None:
            self._admin.upsert_operator_calendar_no_tx(
                {
                    "operator_id": to_str_or_blank(pr.data.get("工号")),
                    "date": to_str_or_blank(pr.data.get("日期")),
                    "day_type": pr.data.get("类型"),
                    "shift_start": pr.data.get("班次开始"),
                    "shift_end": pr.data.get("班次结束") or None,
                    "shift_hours": pr.data.get("可用工时"),
                    "efficiency": pr.data.get("效率"),
                    "allow_normal": pr.data.get("允许普通件"),
                    "allow_urgent": pr.data.get("允许急件"),
                    "remark": pr.data.get("说明"),
                }
            )

        with self._admin.normalization_operation(self._engine.default_periods):
            stats = execute_preview_rows_transactional(
                self.conn,
                mode=mode,
                preview_rows=rows,
                existing_row_ids=existing_row_ids,
                replace_existing_no_tx=_replace_existing_no_tx,
                row_id_getter=_row_id_getter,
                apply_row_no_tx=_apply_row_no_tx,
                max_error_sample=10,
            )
        result = stats.to_dict()
        result["total_rows"] = len(rows)
        self._engine.clear_policy_cache()
        return result

    def policy_for_datetime(self, dt: datetime, operator_id: Optional[str] = None) -> DayPolicy:
        return self._engine.policy_for_datetime(dt, operator_id=operator_id)

    def get_efficiency(self, dt: datetime, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> float:
        return self._engine.get_efficiency(dt, machine_id=machine_id, operator_id=operator_id)

    def adjust_to_working_time(
        self,
        dt: datetime,
        priority: Optional[str] = None,
        machine_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> datetime:
        return self._engine.adjust_to_working_time(dt, priority=priority, machine_id=machine_id, operator_id=operator_id)

    def add_working_hours(
        self,
        start: datetime,
        hours: float,
        priority: Optional[str] = None,
        machine_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> datetime:
        return self._engine.add_working_hours(start, hours, priority=priority, machine_id=machine_id, operator_id=operator_id)

    def add_effective_hours(
        self, start: datetime, hours: float, priority: Optional[str] = None,
        machine_id: Optional[str] = None, operator_id: Optional[str] = None,
    ) -> datetime:
        return self._engine.add_effective_hours(start, hours, priority=priority, machine_id=machine_id, operator_id=operator_id)

    def add_calendar_days(self, start: datetime, days: float, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> datetime:
        return self._engine.add_calendar_days(start, days, machine_id=machine_id, operator_id=operator_id)

    def working_hours_between(
        self,
        start: datetime,
        end: datetime,
        priority: Optional[str] = None,
        machine_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> float:
        return self._engine.working_hours_between(start, end, priority=priority, machine_id=machine_id, operator_id=operator_id)

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
            end = datetime.combine(end.date(), datetime.min.time())
            if (end - dt).days:
                return None
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
