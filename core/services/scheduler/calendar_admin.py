from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import OperatorCalendar, WorkCalendar
from core.models.enums import CALENDAR_DAY_TYPE_STORED_VALUES, CalendarDayType, YesNo
from core.services.common.datetime_normalize import normalize_date, normalize_hhmm
from core.services.common.normalization_matrix import (
    normalize_calendar_day_type_value,
    normalize_yes_no_narrow_value,
)
from core.services.common.normalize import normalize_text
from data.repositories import CalendarRepository, OperatorCalendarRepository

from .config.config_service import ConfigService
from .number_utils import parse_finite_float


class CalendarAdmin:
    """
    工作日历“管理侧”能力（CRUD/导入/标准化）。

    说明：
    - 仅负责 WorkCalendar / OperatorCalendar 的读写与输入标准化
    - 不承载排产引擎的“时间推进”逻辑（见 calendar_engine.py）
    """

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)
        self.repo = CalendarRepository(conn, logger=logger)
        self.operator_calendar_repo = OperatorCalendarRepository(conn, logger=logger)

    def _get_holiday_default_efficiency(self) -> float:
        """
        获取“假期默认效率”（>0）。
        - 来自 ScheduleConfig.holiday_default_efficiency
        - 写入链必须严格依赖合法配置，不允许在该层静默回退默认值
        """
        cfg_svc = ConfigService(self.conn, logger=self.logger, op_logger=self.op_logger)
        return float(cfg_svc.get_holiday_default_efficiency(strict_mode=True))

    # -------------------------
    # 规范化与校验
    # -------------------------

    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        return normalize_text(value)

    @staticmethod
    def _normalize_float(value: Any, field: str, allow_none: bool = True) -> Optional[float]:
        return parse_finite_float(value, field=field, allow_none=allow_none)

    @staticmethod
    def _normalize_hhmm(value: Any, field: str, allow_none: bool = True) -> Optional[str]:
        return normalize_hhmm(value, field=field, allow_none=allow_none)

    @staticmethod
    def _normalize_date(value: Any) -> str:
        return normalize_date(value)

    @staticmethod
    def _validate_day_type(value: Any) -> str:
        try:
            normalized = normalize_calendar_day_type_value(
                value,
                default=CalendarDayType.WORKDAY.value,
                unknown_policy="raise",
            )
        except ValueError as exc:
            raise ValidationError("“类型”不正确，请选择：工作日 / 假期。", field="类型") from exc
        if normalized not in CALENDAR_DAY_TYPE_STORED_VALUES:
            raise ValidationError("“类型”不正确，请选择：工作日 / 假期。", field="类型")
        return normalized

    @staticmethod
    def _normalize_yesno(value: Any, field: str) -> str:
        try:
            return normalize_yes_no_narrow_value(value, default=YesNo.YES.value, unknown_policy="raise")
        except Exception as e:
            raise ValidationError(
                f"“{field}”不正确，请选择：是 / 否。以前的 Excel 如果写过英文，系统会尽量按中文意思读取；新文件请直接填中文。",
                field=field,
            ) from e

    def _normalize_shift_window(
        self,
        *,
        shift_hours: float,
        shift_start: Any,
        shift_end: Any,
    ) -> Tuple[str, Optional[str], float]:
        ss = self._normalize_hhmm(shift_start, field="班次开始", allow_none=True) or "08:00"
        se = self._normalize_hhmm(shift_end, field="班次结束", allow_none=True)
        sh = float(shift_hours)
        if se:
            st_t = datetime.strptime(ss, "%H:%M")
            et_t = datetime.strptime(se, "%H:%M")
            if et_t <= st_t:
                et_t = et_t + timedelta(days=1)
            sh = (et_t - st_t).total_seconds() / 3600.0
        else:
            try:
                if sh > 0 and sh <= 24:
                    st_t = datetime.strptime(ss, "%H:%M")
                    et_t = st_t + timedelta(hours=sh)
                    se = et_t.time().strftime("%H:%M")
            except Exception:
                se = None
        return ss, se, float(sh)

    def _build_work_calendar(
        self,
        *,
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
        d = self._normalize_date(date_value)
        dt = self._validate_day_type(day_type)

        sh = self._normalize_float(shift_hours, field="可用工时", allow_none=True)
        eff = self._normalize_float(efficiency, field="效率", allow_none=True)
        if sh is None:
            sh = 8.0 if dt == CalendarDayType.WORKDAY.value else 0.0
        if sh < 0:
            raise ValidationError("“可用工时”不能为负数", field="可用工时")
        if eff is None:
            eff = 1.0 if dt == CalendarDayType.WORKDAY.value else self._get_holiday_default_efficiency()
        if eff <= 0:
            raise ValidationError("“效率”必须大于 0", field="效率")

        an = self._normalize_yesno(allow_normal, field="允许普通件")
        au = self._normalize_yesno(allow_urgent, field="允许急件")
        rmk = self._normalize_text(remark)
        ss, se, sh_value = self._normalize_shift_window(
            shift_hours=float(sh),
            shift_start=shift_start,
            shift_end=shift_end,
        )
        return WorkCalendar(
            date=d,
            day_type=dt,
            shift_start=ss,
            shift_end=se,
            shift_hours=sh_value,
            efficiency=float(eff),
            allow_normal=an,
            allow_urgent=au,
            remark=rmk,
        )

    def _build_work_calendar_from_payload(self, calendar_payload: Any) -> WorkCalendar:
        if isinstance(calendar_payload, WorkCalendar):
            return self._build_work_calendar(
                date_value=calendar_payload.date,
                day_type=calendar_payload.day_type,
                shift_hours=calendar_payload.shift_hours,
                shift_start=calendar_payload.shift_start,
                shift_end=calendar_payload.shift_end,
                efficiency=calendar_payload.efficiency,
                allow_normal=calendar_payload.allow_normal,
                allow_urgent=calendar_payload.allow_urgent,
                remark=calendar_payload.remark,
            )
        payload = dict(calendar_payload or {})
        return self._build_work_calendar(
            date_value=payload.get("date"),
            day_type=payload.get("day_type"),
            shift_hours=payload.get("shift_hours"),
            shift_start=payload.get("shift_start"),
            shift_end=payload.get("shift_end"),
            efficiency=payload.get("efficiency"),
            allow_normal=payload.get("allow_normal"),
            allow_urgent=payload.get("allow_urgent"),
            remark=payload.get("remark"),
        )

    def _build_operator_calendar(
        self,
        *,
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
        op_id = self._normalize_text(operator_id)
        if not op_id:
            raise ValidationError("“工号”不能为空", field="工号")
        d = self._normalize_date(date_value)
        dt = self._validate_day_type(day_type)

        sh = self._normalize_float(shift_hours, field="可用工时", allow_none=True)
        eff = self._normalize_float(efficiency, field="效率", allow_none=True)
        if sh is None:
            sh = 8.0 if dt == CalendarDayType.WORKDAY.value else 0.0
        if sh < 0:
            raise ValidationError("“可用工时”不能为负数", field="可用工时")
        if eff is None:
            eff = 1.0 if dt == CalendarDayType.WORKDAY.value else self._get_holiday_default_efficiency()
        if eff <= 0:
            raise ValidationError("“效率”必须大于 0", field="效率")

        an = self._normalize_yesno(allow_normal, field="允许普通件")
        au = self._normalize_yesno(allow_urgent, field="允许急件")
        rmk = self._normalize_text(remark)
        ss, se, sh_value = self._normalize_shift_window(
            shift_hours=float(sh),
            shift_start=shift_start,
            shift_end=shift_end,
        )
        return OperatorCalendar(
            operator_id=op_id,
            date=d,
            day_type=dt,
            shift_start=ss,
            shift_end=se,
            shift_hours=sh_value,
            efficiency=float(eff),
            allow_normal=an,
            allow_urgent=au,
            remark=rmk,
        )

    def _build_operator_calendar_from_payload(self, calendar_payload: Any) -> OperatorCalendar:
        if isinstance(calendar_payload, OperatorCalendar):
            return self._build_operator_calendar(
                operator_id=calendar_payload.operator_id,
                date_value=calendar_payload.date,
                day_type=calendar_payload.day_type,
                shift_hours=calendar_payload.shift_hours,
                shift_start=calendar_payload.shift_start,
                shift_end=calendar_payload.shift_end,
                efficiency=calendar_payload.efficiency,
                allow_normal=calendar_payload.allow_normal,
                allow_urgent=calendar_payload.allow_urgent,
                remark=calendar_payload.remark,
            )
        payload = dict(calendar_payload or {})
        return self._build_operator_calendar(
            operator_id=payload.get("operator_id"),
            date_value=payload.get("date"),
            day_type=payload.get("day_type"),
            shift_hours=payload.get("shift_hours"),
            shift_start=payload.get("shift_start"),
            shift_end=payload.get("shift_end"),
            efficiency=payload.get("efficiency"),
            allow_normal=payload.get("allow_normal"),
            allow_urgent=payload.get("allow_urgent"),
            remark=payload.get("remark"),
        )

    # -------------------------
    # WorkCalendar：CRUD（给页面/Excel用）
    # -------------------------
    def list_all(self) -> List[WorkCalendar]:
        return self.repo.list_all()

    def list_range(self, start_date: Any, end_date: Any) -> List[WorkCalendar]:
        s = self._normalize_date(start_date)
        e = self._normalize_date(end_date)
        return self.repo.list_range(s, e)

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
        cal = self._build_work_calendar(
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
        with self.tx_manager.transaction():
            self.repo.upsert(cal.to_dict())
        return cal

    def upsert_no_tx(self, calendar_payload: Dict[str, Any]) -> WorkCalendar:
        """
        upsert 工作日历（不控制事务）。

        说明：
        - 供 Excel 批量导入在“外部已开启事务”时使用，避免嵌套 commit 导致无法整体回滚。
        """
        c = self._build_work_calendar_from_payload(calendar_payload)
        self.repo.upsert(c.to_dict())
        return c

    def delete(self, date_value: Any) -> None:
        d = self._normalize_date(date_value)
        with self.tx_manager.transaction():
            self.repo.delete(d)

    def delete_all_no_tx(self) -> None:
        self.repo.delete_all()

    # -------------------------
    # OperatorCalendar：CRUD（人员专属日历）
    # -------------------------
    def get_operator_calendar(self, operator_id: Any, date_value: Any) -> Optional[OperatorCalendar]:
        op_id = self._normalize_text(operator_id)
        if not op_id:
            raise ValidationError("“工号”不能为空", field="工号")
        d = self._normalize_date(date_value)
        return self.operator_calendar_repo.get(op_id, d)

    def list_operator_calendar(self, operator_id: Any) -> List[OperatorCalendar]:
        op_id = self._normalize_text(operator_id)
        if not op_id:
            raise ValidationError("“工号”不能为空", field="工号")
        return self.operator_calendar_repo.list_by_operator(op_id)

    def list_operator_calendar_all(self) -> List[OperatorCalendar]:
        return self.operator_calendar_repo.list_all()

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
        cal = self._build_operator_calendar(
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
        with self.tx_manager.transaction():
            self.operator_calendar_repo.upsert(cal.to_dict())
        return cal

    def upsert_operator_calendar_no_tx(self, calendar_payload: Dict[str, Any]) -> OperatorCalendar:
        c = self._build_operator_calendar_from_payload(calendar_payload)
        self.operator_calendar_repo.upsert(c.to_dict())
        return c

    def delete_operator_calendar(self, operator_id: Any, date_value: Any) -> None:
        op_id = self._normalize_text(operator_id)
        if not op_id:
            raise ValidationError("“工号”不能为空", field="工号")
        d = self._normalize_date(date_value)
        with self.tx_manager.transaction():
            self.operator_calendar_repo.delete(op_id, d)

    def delete_operator_calendar_all_no_tx(self) -> None:
        self.operator_calendar_repo.delete_all()
