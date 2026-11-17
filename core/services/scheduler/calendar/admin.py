from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from core.errors import ValidationError
from core.models.calendar import OperatorCalendar, WorkCalendar
from core.models.calendar_periods import (
    decode_periods,
    encode_periods,
    normalize_periods,
)
from core.models.enums import CALENDAR_DAY_TYPE_STORED_VALUES, YESNO_VALUES, CalendarDayType, YesNo
from core.services.common.datetime_normalize import normalize_date
from core.services.common.normalize import normalize_text
from core.services.scheduler.config.config_field_spec import coerce_config_field
from core.shared.strict_parse import parse_optional_float
from data.repositories.calendar_defaults_repo import CalendarDefaultsRepository
from data.repositories.calendar_repo import CalendarRepository
from data.repositories.config_repo import ConfigRepository
from data.repositories.operator_calendar_repo import OperatorCalendarRepository

from .defaults import default_periods_from_row


class CalendarNormalizationContext:
    def __init__(self, conn, logger=None, *, period_reader: Callable[[], List[Dict[str, Any]]]):
        self._conn = conn
        self._logger = logger
        self._period_reader = period_reader
        self._efficiency: Optional[float] = None

    def holiday_efficiency(self) -> float:
        if self._efficiency is None:
            key = "holiday_default_efficiency"
            raw_value = ConfigRepository(self._conn, logger=self._logger).get_value(key)
            self._efficiency = float(coerce_config_field(key, raw_value, missing=(raw_value is None)))
        return self._efficiency

    def workday_periods(self) -> List[Dict[str, Any]]:
        return self._period_reader()


class CalendarAdmin:
    """
    工作日历“管理侧”能力（CRUD/导入/标准化）。

    说明：
    - 仅负责 WorkCalendar / OperatorCalendar 的读写与输入标准化
    - 类型与许可只收存储代号（workday/holiday、yes/no）；界面和文件的叫法由各自入口先翻成代号
    - 不承载排产引擎的“时间推进”逻辑（见 calendar_engine.py）
    """

    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        self.repo = CalendarRepository(conn, logger=logger)
        self.operator_calendar_repo = OperatorCalendarRepository(conn, logger=logger)

    def normalization_context(self) -> CalendarNormalizationContext:
        """One calendar-row normalization context; workday defaults are read at most once per context."""
        periods: Optional[List[Dict[str, Any]]] = None

        def read_once() -> List[Dict[str, Any]]:
            nonlocal periods
            if periods is None:
                periods = default_periods_from_row(CalendarDefaultsRepository(self.conn).get())
            return periods

        return CalendarNormalizationContext(self.conn, logger=self.logger, period_reader=read_once)

    # -------------------------
    # 规范化与校验
    # -------------------------

    @staticmethod
    def _require_operator_id(operator_id: Any) -> str:
        op_id = (operator_id if operator_id.strip() else None) if type(operator_id) is str else normalize_text(operator_id)
        if not op_id:
            raise ValidationError("人员编号不能为空", field="operator_id")
        return op_id

    @staticmethod
    def _validate_day_type(value: Any) -> str:
        """省略按工作日；给了就只能是存储的两种类型，周末按假期存。"""
        if value is None:
            return CalendarDayType.WORKDAY.value
        if value not in CALENDAR_DAY_TYPE_STORED_VALUES:
            raise ValidationError("“类型”不正确，请选择：工作日 / 假期。", field="类型")
        return value

    @staticmethod
    def _normalize_yesno(value: Any, field: str) -> str:
        """省略按允许；给了就只能是 yes / no。"""
        if value is None:
            return YesNo.YES.value
        if value not in YESNO_VALUES:
            raise ValidationError(f"“{field}”不正确，请选择：是 / 否。", field=field)
        return value

    def _normalize_calendar_common_fields(
        self,
        *,
        date_value: Any,
        day_type: Any,
        efficiency: Any,
        allow_normal: Any,
        allow_urgent: Any,
        remark: Any,
        periods: Any,
        context: CalendarNormalizationContext,
    ) -> Dict[str, Any]:
        """工作时段是唯一的时间事实：未给时段的工作日取默认时段，假期为空数组；起止与工时一律由它现算。"""
        d = normalize_date(date_value)
        dt = self._validate_day_type(day_type)
        eff = parse_optional_float(efficiency, field="效率")
        if eff is None:
            eff = 1.0 if dt == CalendarDayType.WORKDAY.value else context.holiday_efficiency()
        if eff <= 0:
            raise ValidationError("“效率”必须大于 0", field="效率")
        an = self._normalize_yesno(allow_normal, field="允许普通件")
        au = self._normalize_yesno(allow_urgent, field="允许急件")
        rmk = normalize_text(remark)
        if periods is None:
            periods = context.workday_periods() if dt == CalendarDayType.WORKDAY.value else []
        return {
            "date": d,
            "day_type": dt,
            "efficiency": float(eff),
            "allow_normal": an,
            "allow_urgent": au,
            "remark": rmk,
            "periods_json": encode_periods(periods),
        }

    @staticmethod
    def _payload_periods(payload):
        """提交的时段按外部输入准入；只带已存时段文本的按存储读取。两条入口各规范化一次，都没给返回 None。"""
        if "periods" in payload:
            return normalize_periods(payload["periods"])
        raw = payload.get("periods_json")
        return None if raw is None else decode_periods(raw)

    def build_work_calendar_from_payload(
        self,
        calendar_payload: Dict[str, Any],
        *,
        context: CalendarNormalizationContext,
    ) -> WorkCalendar:
        fields = self._normalize_calendar_common_fields(
            date_value=calendar_payload.get("date"),
            day_type=calendar_payload.get("day_type"),
            efficiency=calendar_payload.get("efficiency"),
            allow_normal=calendar_payload.get("allow_normal"),
            allow_urgent=calendar_payload.get("allow_urgent"),
            remark=calendar_payload.get("remark"),
            periods=self._payload_periods(calendar_payload),
            context=context,
        )
        return WorkCalendar(**fields)

    def build_operator_calendar_from_payload(
        self,
        calendar_payload: Dict[str, Any],
        *,
        context: CalendarNormalizationContext,
    ) -> OperatorCalendar:
        periods = self._payload_periods(calendar_payload)
        op_id = self._require_operator_id(calendar_payload.get("operator_id"))
        fields = self._normalize_calendar_common_fields(
            date_value=calendar_payload.get("date"),
            day_type=calendar_payload.get("day_type"),
            efficiency=calendar_payload.get("efficiency"),
            allow_normal=calendar_payload.get("allow_normal"),
            allow_urgent=calendar_payload.get("allow_urgent"),
            remark=calendar_payload.get("remark"),
            periods=periods,
            context=context,
        )
        return OperatorCalendar(operator_id=op_id, **fields)
