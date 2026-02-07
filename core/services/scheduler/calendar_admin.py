from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from core.infrastructure.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import OperatorCalendar, WorkCalendar
from core.models.enums import CalendarDayType, YesNo
from core.services.scheduler.config_service import ConfigService
from data.repositories import CalendarRepository, OperatorCalendarRepository


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
        - 任意异常都回退到 ConfigService.DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY
        """
        try:
            cfg_svc = ConfigService(self.conn, logger=self.logger, op_logger=self.op_logger)
            raw = cfg_svc.get("holiday_default_efficiency", default=ConfigService.DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY)
            v = float(raw) if raw is not None else float(ConfigService.DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY)
            if v <= 0:
                return float(ConfigService.DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY)
            return float(v)
        except Exception:
            return float(ConfigService.DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY)

    # -------------------------
    # 规范化与校验
    # -------------------------
    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            v = value.strip()
            return v if v != "" else None
        v = str(value).strip()
        return v if v != "" else None

    @staticmethod
    def _normalize_float(value: Any, field: str, allow_none: bool = True) -> Optional[float]:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None if allow_none else 0.0
        try:
            return float(value)
        except Exception:
            raise ValidationError(f"“{field}”必须是数字", field=field)

    @staticmethod
    def _normalize_hhmm(value: Any, field: str, allow_none: bool = True) -> Optional[str]:
        """
        时间标准化为 HH:MM（支持 HH:MM / HH:MM:SS）。
        """
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None if allow_none else "08:00"
        s = str(value).strip().replace("：", ":")
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                t = datetime.strptime(s, fmt).time()
                return t.strftime("%H:%M")
            except Exception:
                continue
        raise ValidationError(f"“{field}”格式不合法（期望：HH:MM）", field=field)

    @staticmethod
    def _normalize_date(value: Any) -> str:
        """
        日期标准化为 YYYY-MM-DD。
        - 支持 date/datetime
        - 支持字符串：YYYY-MM-DD / YYYY/MM/DD
        """
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if value is None:
            raise ValidationError("“日期”不能为空", field="日期")
        v = str(value).strip()
        if not v:
            raise ValidationError("“日期”不能为空", field="日期")
        v = v.replace("/", "-")
        try:
            return datetime.strptime(v, "%Y-%m-%d").date().isoformat()
        except Exception:
            raise ValidationError("“日期”格式不合法（期望：YYYY-MM-DD）", field="日期")

    @staticmethod
    def _validate_day_type(value: Any) -> str:
        v = CalendarAdmin._normalize_text(value) or CalendarDayType.WORKDAY.value
        # 兼容：weekend 统一视为 holiday（存储只保留 workday/holiday）
        if v == CalendarDayType.WEEKEND.value:
            return CalendarDayType.HOLIDAY.value
        if v not in (CalendarDayType.WORKDAY.value, CalendarDayType.HOLIDAY.value):
            raise ValidationError("“类型”不合法（允许：workday / holiday）", field="类型")
        return v

    @staticmethod
    def _normalize_yesno(value: Any, field: str) -> str:
        v = CalendarAdmin._normalize_text(value) or YesNo.YES.value
        if v in ("是", "y", "Y", "yes", "YES"):
            return YesNo.YES.value
        if v in ("否", "n", "N", "no", "NO"):
            return YesNo.NO.value
        if v not in (YesNo.YES.value, YesNo.NO.value):
            raise ValidationError(f"“{field}”不合法（允许：yes / no）", field=field)
        return v

    # -------------------------
    # WorkCalendar：CRUD（给页面/Excel用）
    # -------------------------
    def get_row(self, date_value: Any) -> Optional[WorkCalendar]:
        d = self._normalize_date(date_value)
        return self.repo.get(d)

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

        ss = self._normalize_hhmm(shift_start, field="班次开始", allow_none=True) or "08:00"
        se = self._normalize_hhmm(shift_end, field="班次结束", allow_none=True)
        # 若给了起止时间，则用其推导可用工时（允许跨午夜：shift_end <= shift_start 表示次日结束）
        if se:
            st_t = datetime.strptime(ss, "%H:%M")
            et_t = datetime.strptime(se, "%H:%M")
            if et_t <= st_t:
                et_t = et_t + timedelta(days=1)
            sh = (et_t - st_t).total_seconds() / 3600.0
        else:
            # 没填结束时间：根据 shift_hours 推导一个用于展示的 shift_end（支持跨午夜；仅对 0~24h 推导）
            try:
                sh0 = float(sh or 0.0)
                if sh0 > 0 and sh0 <= 24:
                    st_t = datetime.strptime(ss, "%H:%M")
                    et_t = st_t + timedelta(hours=sh0)
                    se = et_t.time().strftime("%H:%M")
            except Exception:
                se = None

        cal = WorkCalendar(
            date=d,
            day_type=dt,
            shift_start=ss,
            shift_end=se,
            shift_hours=float(sh),
            efficiency=float(eff),
            allow_normal=an,
            allow_urgent=au,
            remark=rmk,
        )
        with self.tx_manager.transaction():
            self.upsert_no_tx(cal.to_dict())
        return cal

    def upsert_no_tx(self, calendar_payload: Dict[str, Any]) -> WorkCalendar:
        """
        upsert 工作日历（不控制事务）。

        说明：
        - 供 Excel 批量导入在“外部已开启事务”时使用，避免嵌套 commit 导致无法整体回滚。
        """
        c = calendar_payload if isinstance(calendar_payload, WorkCalendar) else WorkCalendar.from_row(calendar_payload)
        self.repo.upsert(c.to_dict())
        return c

    def delete(self, date_value: Any) -> None:
        d = self._normalize_date(date_value)
        with self.tx_manager.transaction():
            self.repo.delete(d)

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

        ss = self._normalize_hhmm(shift_start, field="班次开始", allow_none=True) or "08:00"
        se = self._normalize_hhmm(shift_end, field="班次结束", allow_none=True)
        if se:
            st_t = datetime.strptime(ss, "%H:%M")
            et_t = datetime.strptime(se, "%H:%M")
            if et_t <= st_t:
                et_t = et_t + timedelta(days=1)
            sh = (et_t - st_t).total_seconds() / 3600.0
        else:
            try:
                sh0 = float(sh or 0.0)
                if sh0 > 0 and sh0 <= 24:
                    st_t = datetime.strptime(ss, "%H:%M")
                    et_t = st_t + timedelta(hours=sh0)
                    se = et_t.time().strftime("%H:%M")
            except Exception:
                se = None

        cal = OperatorCalendar(
            operator_id=op_id,
            date=d,
            day_type=dt,
            shift_start=ss,
            shift_end=se,
            shift_hours=float(sh),
            efficiency=float(eff),
            allow_normal=an,
            allow_urgent=au,
            remark=rmk,
        )
        with self.tx_manager.transaction():
            self.upsert_operator_calendar_no_tx(cal.to_dict())
        return cal

    def upsert_operator_calendar_no_tx(self, calendar_payload: Dict[str, Any]) -> OperatorCalendar:
        c = (
            calendar_payload
            if isinstance(calendar_payload, OperatorCalendar)
            else OperatorCalendar.from_row(calendar_payload)
        )
        self.operator_calendar_repo.upsert(c.to_dict())
        return c

    def delete_operator_calendar(self, operator_id: Any, date_value: Any) -> None:
        op_id = self._normalize_text(operator_id)
        if not op_id:
            raise ValidationError("“工号”不能为空", field="工号")
        d = self._normalize_date(date_value)
        with self.tx_manager.transaction():
            self.operator_calendar_repo.delete(op_id, d)

