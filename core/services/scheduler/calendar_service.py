from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from core.services.common.excel_import_executor import execute_preview_rows_transactional
from core.services.common.excel_service import ImportMode
from core.models import OperatorCalendar, WorkCalendar

from .calendar_admin import CalendarAdmin
from .calendar_engine import CalendarEngine, DayPolicy


class CalendarService:
    """
    工作日历服务（对外 façade）。

    说明：
    - 对外 API 保持稳定（路由层/算法层继续 `from core.services.scheduler import CalendarService`）
    - 内部按职责拆分：管理侧（CRUD/标准化）与引擎侧（时间推进/效率）
    """

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self._admin = CalendarAdmin(conn, logger=logger, op_logger=op_logger)
        self._engine = CalendarEngine(conn, logger=logger, op_logger=op_logger)

    # -------------------------
    # Backward compatibility
    # -------------------------
    @staticmethod
    def _normalize_date(value: Any) -> str:
        """
        兼容历史调用：路由层/旧脚本曾直接调用 CalendarService._normalize_date(...)。

        当前实现已拆分为 CalendarAdmin（管理侧）与 CalendarEngine（引擎侧），
        这里保留一个轻量代理，避免出现 AttributeError 导致页面 500。
        """
        return CalendarAdmin._normalize_date(value)

    @staticmethod
    def _normalize_hhmm(value: Any, field: str, allow_none: bool = True) -> Optional[str]:
        """
        兼容历史调用：路由层曾直接调用 CalendarService._normalize_hhmm(...)。
        """
        return CalendarAdmin._normalize_hhmm(value, field=field, allow_none=allow_none)

    # -------------------------
    # CRUD（给页面/Excel用）
    # -------------------------
    def get(self, date_value: Any) -> WorkCalendar:
        d = self._admin._normalize_date(date_value)
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
    ) -> WorkCalendar:
        return self._admin.upsert(
            date_value=date_value,
            day_type=day_type,
            shift_hours=shift_hours,
            shift_start=shift_start,
            shift_end=shift_end,
            efficiency=efficiency,
            allow_normal=allow_normal,
            allow_urgent=allow_urgent,
            remark=remark,
        )

    def upsert_no_tx(self, calendar_payload: Dict[str, Any]) -> WorkCalendar:
        return self._admin.upsert_no_tx(calendar_payload)

    def delete(self, date_value: Any) -> None:
        self._admin.delete(date_value)

    def delete_all_no_tx(self) -> None:
        self._admin.delete_all_no_tx()

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
    ) -> OperatorCalendar:
        return self._admin.upsert_operator_calendar(
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
        )

    def upsert_operator_calendar_no_tx(self, calendar_payload: Dict[str, Any]) -> OperatorCalendar:
        return self._admin.upsert_operator_calendar_no_tx(calendar_payload)

    def delete_operator_calendar(self, operator_id: Any, date_value: Any) -> None:
        self._admin.delete_operator_calendar(operator_id, date_value)

    def delete_operator_calendar_all_no_tx(self) -> None:
        self._admin.delete_operator_calendar_all_no_tx()

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
            self.delete_operator_calendar_all_no_tx()

        def _row_id_getter(pr: Any) -> str:
            rid = str(pr.data.get("__id") or "").strip()
            if rid:
                return rid
            op_id = str(pr.data.get("工号") or "").strip()
            date_str = str(pr.data.get("日期") or "").strip()
            return f"{op_id}|{date_str}"

        def _apply_row_no_tx(pr: Any, _existed: bool) -> None:
            self.upsert_operator_calendar_no_tx(
                {
                    "operator_id": str(pr.data.get("工号") or "").strip(),
                    "date": str(pr.data.get("日期") or "").strip(),
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

    def add_calendar_days(self, start: datetime, days: float, machine_id: Optional[str] = None, operator_id: Optional[str] = None) -> datetime:
        return self._engine.add_calendar_days(start, days, machine_id=machine_id, operator_id=operator_id)

