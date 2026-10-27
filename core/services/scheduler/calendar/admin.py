from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.errors import ValidationError
from core.models.calendar import OperatorCalendar, WorkCalendar
from core.models.calendar_periods import (
    encode_periods,
    load_stored_periods,
    normalize_periods,
    period_summary,
)
from core.models.enums import CalendarDayType, YesNo
from core.services.common.datetime_normalize import normalize_date, normalize_hhmm
from core.services.common.normalization_matrix import (
    normalize_calendar_day_type_value,
    normalize_yes_no_narrow_value,
)
from core.services.common.normalize import normalize_text
from core.services.scheduler.config.config_field_spec import coerce_config_field
from core.shared.strict_parse import parse_optional_float
from data.repositories import CalendarRepository, OperatorCalendarRepository
from data.repositories.config_repo import ConfigRepository

from .defaults import read_default_periods

#: 没有单独设置开工时刻时采用的默认值。工作台据此判断某天的班次结束是推出来的还是真实班表。
DEFAULT_SHIFT_START = "08:00"


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
        self._normalization_defaults: Optional[Dict[str, Any]] = None

    @contextmanager
    def normalization_operation(self, default_periods):
        """Keep only the defaults actually consumed by this one domain operation."""
        if self._normalization_defaults is not None:
            yield
            return
        self._normalization_defaults = {"period_reader": default_periods}
        try:
            yield
        finally:
            self._normalization_defaults = None

    def _holiday_efficiency(self) -> float:
        values = self._normalization_defaults
        if values is None:
            return self._get_holiday_default_efficiency()
        if "efficiency" not in values:
            values["efficiency"] = self._get_holiday_default_efficiency()
        return values["efficiency"]

    def _workday_periods(self):
        values = self._normalization_defaults
        if values is None:
            return read_default_periods(self.conn)
        if "periods" not in values:
            values["periods"] = values["period_reader"]()
        return values["periods"]

    def _get_holiday_default_efficiency(self) -> float:
        """
        获取“假期工作效率”（>0）。
        - 来自 ScheduleConfig.holiday_default_efficiency
        - 写入链必须严格依赖合法配置，不允许在该层静默回退默认值
        """
        key = "holiday_default_efficiency"
        raw_value = ConfigRepository(self.conn, logger=self.logger).get_value(key)
        return coerce_config_field(key, raw_value, missing=(raw_value is None))

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

    def _normalize_shift_window(
        self,
        *,
        shift_hours: Any,
        shift_start: Any,
        shift_end: Any,
        periods: Optional[List[Dict[str, Any]]],
        default_hours: float,
    ) -> Tuple[str, Optional[str], float]:
        # Explicit periods own the window; legacy single-shift fields are superseded.
        if periods:
            return period_summary(periods)
        ss = normalize_hhmm(shift_start, field="班次开始") or DEFAULT_SHIFT_START
        if periods is not None:
            return ss, None, 0.0
        se = normalize_hhmm(shift_end, field="班次结束")
        if se:
            st_t = datetime.strptime(ss, "%H:%M")
            et_t = datetime.strptime(se, "%H:%M")
            if et_t <= st_t:
                et_t = et_t + timedelta(days=1)
            sh = (et_t - st_t).total_seconds() / 3600.0
        else:
            sh = parse_optional_float(shift_hours, field="可用工时")
            sh = default_hours if sh is None else sh
            if sh < 0:
                raise ValidationError("“可用工时”不能为负数", field="可用工时")
            if 0 < sh <= 24:
                minutes = sh * 60
                whole_minutes = round(minutes)
                if whole_minutes == 0 or abs(minutes - whole_minutes) > 1e-7:
                    raise ValidationError("填的工时换成班次的分钟数后存不稳，请核对工时。", field="可用工时")
                sh = whole_minutes / 60.0
                st_t = datetime.strptime(ss, "%H:%M")
                se = (st_t + timedelta(minutes=whole_minutes)).time().strftime("%H:%M")
        return ss, se, float(sh)

    def _normalize_calendar_common_fields(
        self,
        *,
        date_value: Any,
        day_type: Any,
        shift_hours: Any,
        shift_start: Any,
        shift_end: Any,
        efficiency: Any,
        allow_normal: Any,
        allow_urgent: Any,
        remark: Any,
        periods: Any,
    ) -> Dict[str, Any]:
        d = normalize_date(date_value)
        dt = self._validate_day_type(day_type)
        eff = parse_optional_float(efficiency, field="效率")
        if eff is None:
            eff = 1.0 if dt == CalendarDayType.WORKDAY.value else self._holiday_efficiency()
        if eff <= 0:
            raise ValidationError("“效率”必须大于 0", field="效率")
        an = self._normalize_yesno(allow_normal, field="允许普通件")
        au = self._normalize_yesno(allow_urgent, field="允许急件")
        rmk = normalize_text(remark)
        if periods is None and all(value is None for value in (shift_start, shift_end, shift_hours)) and dt == CalendarDayType.WORKDAY.value:
            periods = self._workday_periods()
        else:
            periods = normalize_periods(periods)
        ss, se, sh_value = self._normalize_shift_window(
            shift_hours=shift_hours,
            shift_start=shift_start,
            shift_end=shift_end,
            periods=periods,
            default_hours=8.0 if dt == CalendarDayType.WORKDAY.value else 0.0,
        )
        return {
            "date": d,
            "day_type": dt,
            "shift_start": ss,
            "shift_end": se,
            "shift_hours": sh_value,
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
        shift_hours: Any = None,
        shift_start: Any = None,
        shift_end: Any = None,
        efficiency: Any = None,
        allow_normal: Any = None,
        allow_urgent: Any = None,
        remark: Any = None,
        periods: Any = None,
        requested_shift_hours: Optional[float] = None,
    ) -> WorkCalendar:
        fields = self._normalize_calendar_common_fields(
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
        d, sh_value = fields["date"], fields["shift_hours"]
        if requested_shift_hours is not None and (
                sh_value == 0 and requested_shift_hours > 0 or abs(sh_value - requested_shift_hours) > 1e-9):
            raise ValidationError(
                f"{d} 按原班次起止算出 {sh_value:g} 小时，和你填的 {requested_shift_hours:g} 小时对不上，"
                "所以没有保存；请先核对原班次。", field="可用工时")
        return WorkCalendar(**fields)

    @staticmethod
    def _payload_periods(payload):
        """Decode storage syntax; the common builder normalizes the periods once."""
        if "periods" in payload:
            return payload["periods"]
        raw = payload.get("periods_json")
        return None if raw is None else load_stored_periods(raw)

    def _build_work_calendar_from_payload(self, calendar_payload: Dict[str, Any], *, requested_shift_hours=None) -> WorkCalendar:
        return self._build_work_calendar(
            date_value=calendar_payload.get("date"),
            day_type=calendar_payload.get("day_type"),
            shift_hours=calendar_payload.get("shift_hours"),
            shift_start=calendar_payload.get("shift_start"),
            shift_end=calendar_payload.get("shift_end"),
            efficiency=calendar_payload.get("efficiency"),
            allow_normal=calendar_payload.get("allow_normal"),
            allow_urgent=calendar_payload.get("allow_urgent"),
            remark=calendar_payload.get("remark"),
            periods=self._payload_periods(calendar_payload),
            requested_shift_hours=requested_shift_hours,
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
        periods: Any = None,
    ) -> OperatorCalendar:
        op_id = self._require_operator_id(operator_id)
        fields = self._normalize_calendar_common_fields(
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
        return OperatorCalendar(operator_id=op_id, **fields)

    def _build_operator_calendar_from_payload(self, calendar_payload: Dict[str, Any]) -> OperatorCalendar:
        return self._build_operator_calendar(
            operator_id=calendar_payload.get("operator_id"),
            date_value=calendar_payload.get("date"),
            day_type=calendar_payload.get("day_type"),
            shift_hours=calendar_payload.get("shift_hours"),
            shift_start=calendar_payload.get("shift_start"),
            shift_end=calendar_payload.get("shift_end"),
            efficiency=calendar_payload.get("efficiency"),
            allow_normal=calendar_payload.get("allow_normal"),
            allow_urgent=calendar_payload.get("allow_urgent"),
            remark=calendar_payload.get("remark"),
            periods=self._payload_periods(calendar_payload),
        )
