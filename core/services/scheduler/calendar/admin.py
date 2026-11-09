from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from core.errors import ValidationError
from core.models.calendar import OperatorCalendar, WorkCalendar
from core.models.calendar_periods import (
    encode_periods,
    load_stored_periods,
    normalize_periods,
)
from core.models.enums import CalendarDayType, YesNo
from core.services.common.datetime_normalize import normalize_date
from core.services.common.normalization_matrix import (
    normalize_calendar_day_type_value,
    normalize_yes_no_narrow_value,
)
from core.services.common.normalize import normalize_text
from core.services.scheduler.config.config_field_spec import coerce_config_field
from core.shared.strict_parse import parse_optional_float
from data.repositories import CalendarRepository, OperatorCalendarRepository
from data.repositories.config_repo import ConfigRepository


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
    - 不承载排产引擎的“时间推进”逻辑（见 calendar_engine.py）
    """

    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        self.repo = CalendarRepository(conn, logger=logger)
        self.operator_calendar_repo = OperatorCalendarRepository(conn, logger=logger)

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
        try:
            normalized = normalize_calendar_day_type_value(
                value,
                default=CalendarDayType.WORKDAY.value,
            )
        except ValueError as exc:
            raise ValidationError("“类型”不正确，请选择：工作日 / 假期。", field="类型") from exc
        return normalized

    @staticmethod
    def _normalize_yesno(value: Any, field: str) -> str:
        try:
            return normalize_yes_no_narrow_value(value, default=YesNo.YES.value)
        except ValueError as e:
            raise ValidationError(
                f"“{field}”不正确，请选择：是 / 否。以前的 Excel 如果写过英文，系统会尽量按中文意思读取；新文件请直接填中文。",
                field=field,
            ) from e

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
        else:
            periods = normalize_periods(periods)
        return {
            "date": d,
            "day_type": dt,
            "efficiency": float(eff),
            "allow_normal": an,
            "allow_urgent": au,
            "remark": rmk,
            "periods_json": encode_periods(periods),
        }

    def _build_work_calendar(
        self,
        *,
        date_value: Any,
        day_type: Any = None,
        efficiency: Any = None,
        allow_normal: Any = None,
        allow_urgent: Any = None,
        remark: Any = None,
        periods: Any = None,
        context: CalendarNormalizationContext,
    ) -> WorkCalendar:
        fields = self._normalize_calendar_common_fields(
            date_value=date_value,
            day_type=day_type,
            efficiency=efficiency,
            allow_normal=allow_normal,
            allow_urgent=allow_urgent,
            remark=remark,
            periods=periods,
            context=context,
        )
        return WorkCalendar(**fields)

    @staticmethod
    def _payload_periods(payload):
        """Decode storage syntax; the common builder normalizes the periods once."""
        if "periods" in payload:
            return payload["periods"]
        raw = payload.get("periods_json")
        return None if raw is None else load_stored_periods(raw)

    def _build_work_calendar_from_payload(
        self,
        calendar_payload: Dict[str, Any],
        *,
        context: CalendarNormalizationContext,
    ) -> WorkCalendar:
        return self._build_work_calendar(
            date_value=calendar_payload.get("date"),
            day_type=calendar_payload.get("day_type"),
            efficiency=calendar_payload.get("efficiency"),
            allow_normal=calendar_payload.get("allow_normal"),
            allow_urgent=calendar_payload.get("allow_urgent"),
            remark=calendar_payload.get("remark"),
            periods=self._payload_periods(calendar_payload),
            context=context,
        )

    def _build_operator_calendar(
        self,
        *,
        operator_id: Any,
        date_value: Any,
        day_type: Any = None,
        efficiency: Any = None,
        allow_normal: Any = None,
        allow_urgent: Any = None,
        remark: Any = None,
        periods: Any = None,
        context: CalendarNormalizationContext,
    ) -> OperatorCalendar:
        op_id = self._require_operator_id(operator_id)
        fields = self._normalize_calendar_common_fields(
            date_value=date_value,
            day_type=day_type,
            efficiency=efficiency,
            allow_normal=allow_normal,
            allow_urgent=allow_urgent,
            remark=remark,
            periods=periods,
            context=context,
        )
        return OperatorCalendar(operator_id=op_id, **fields)

    def _build_operator_calendar_from_payload(
        self,
        calendar_payload: Dict[str, Any],
        *,
        context: CalendarNormalizationContext,
    ) -> OperatorCalendar:
        return self._build_operator_calendar(
            operator_id=calendar_payload.get("operator_id"),
            date_value=calendar_payload.get("date"),
            day_type=calendar_payload.get("day_type"),
            efficiency=calendar_payload.get("efficiency"),
            allow_normal=calendar_payload.get("allow_normal"),
            allow_urgent=calendar_payload.get("allow_urgent"),
            remark=calendar_payload.get("remark"),
            periods=self._payload_periods(calendar_payload),
            context=context,
        )
