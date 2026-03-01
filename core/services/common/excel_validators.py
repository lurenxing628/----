from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, Optional

from core.infrastructure.errors import ValidationError
from core.models.enums import (
    BATCH_PRIORITY_VALUES,
    CALENDAR_DAY_TYPE_STORED_VALUES,
    READY_STATUS_VALUES,
    YESNO_VALUES,
    BatchPriority,
    CalendarDayType,
    ReadyStatus,
    YesNo,
)
from core.services.common.datetime_normalize import normalize_date, normalize_hhmm
from core.services.common.enum_normalizers import normalize_yesno_narrow
from data.repositories import OperatorRepository, PartRepository


def _normalize_batch_priority(value: Any) -> str:
    v = "" if value is None else str(value).strip()
    v_lower = v.lower()
    if v == "普通" or v_lower == BatchPriority.NORMAL.value:
        return BatchPriority.NORMAL.value
    if v in ("急", "急件") or v_lower == BatchPriority.URGENT.value:
        return BatchPriority.URGENT.value
    if v == "特急" or v_lower == BatchPriority.CRITICAL.value:
        return BatchPriority.CRITICAL.value
    return v or BatchPriority.NORMAL.value


def _normalize_ready_status(value: Any) -> str:
    v = "" if value is None else str(value).strip()
    v_lower = v.lower()
    if v in ("齐套", "是") or v_lower == ReadyStatus.YES.value:
        return ReadyStatus.YES.value
    if v == "部分齐套" or v_lower == ReadyStatus.PARTIAL.value:
        return ReadyStatus.PARTIAL.value
    if v in ("未齐套", "否") or v_lower == ReadyStatus.NO.value:
        return ReadyStatus.NO.value
    return v or ReadyStatus.YES.value


def _normalize_operator_calendar_day_type(value: Any) -> str:
    v = "" if value is None else str(value).strip()
    v_lower = v.lower()
    if v == "工作日" or v_lower == CalendarDayType.WORKDAY.value:
        return CalendarDayType.WORKDAY.value
    if v == "周末" or v_lower == CalendarDayType.WEEKEND.value:
        return CalendarDayType.HOLIDAY.value
    if v in ("节假日", "假期") or v_lower == CalendarDayType.HOLIDAY.value:
        return CalendarDayType.HOLIDAY.value
    return v or CalendarDayType.WORKDAY.value


def _normalize_yesno(value: Any) -> str:
    return normalize_yesno_narrow(value, default=YesNo.YES.value, unknown_policy="passthrough")


def _normalize_batch_date_cell(value: Any, field_label: str) -> Dict[str, Any]:
    if value is None:
        return {"value": None, "error": None}
    if isinstance(value, datetime):
        return {"value": value.date().isoformat(), "error": None}
    if isinstance(value, date):
        return {"value": value.isoformat(), "error": None}

    s = str(value).strip()
    if not s:
        return {"value": None, "error": None}
    if "T" in s or " " in s:
        return {
            "value": None,
            "error": f"“{field_label}”不合法：日期字段不允许包含时间（当前值：{s}）。请仅填写日期：YYYY-MM-DD 或 YYYY/MM/DD（例：2026-01-25）。",
        }

    m = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", s)
    if not m:
        return {"value": None, "error": f"“{field_label}”不合法：期望格式 YYYY-MM-DD 或 YYYY/MM/DD（当前值：{s}）。"}

    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        v = datetime(y, mo, d).date().isoformat()
    except Exception:
        return {"value": None, "error": f"“{field_label}”不合法：日期值不存在（当前值：{s}）。期望：YYYY-MM-DD 或 YYYY/MM/DD。"}
    return {"value": v, "error": None}


def get_batch_row_validate_and_normalize(
    conn,
    *,
    parts_cache: dict | None = None,
    inplace: bool = True,
) -> Callable[[dict], str | None]:
    parts = parts_cache if isinstance(parts_cache, dict) else {p.part_no: p for p in PartRepository(conn).list()}

    def _validate_and_normalize(row: dict) -> str | None:
        target = row if inplace else dict(row)

        if not target.get("批次号") or str(target.get("批次号")).strip() == "":
            return "“批次号”不能为空"
        if not target.get("图号") or str(target.get("图号")).strip() == "":
            return "“图号”不能为空"
        pn = str(target.get("图号")).strip()
        if pn not in parts:
            return f"图号“{pn}”不存在，请先在工艺管理中维护零件。"

        qty = target.get("数量")
        if qty is None or str(qty).strip() == "":
            return "“数量”不能为空"
        try:
            q = int(qty)
            if q <= 0:
                return "“数量”必须大于 0"
            target["数量"] = q
        except Exception:
            return "“数量”必须是整数"

        target["优先级"] = _normalize_batch_priority(target.get("优先级"))
        if target["优先级"] not in BATCH_PRIORITY_VALUES:
            return "“优先级”不合法（允许：normal/urgent/critical；或中文：普通/急件/特急）"

        target["齐套"] = _normalize_ready_status(target.get("齐套"))
        if target["齐套"] not in READY_STATUS_VALUES:
            return "“齐套”不合法（允许：yes/no/partial；或中文：齐套/未齐套/部分齐套）"

        ready_res = _normalize_batch_date_cell(target.get("齐套日期"), field_label="齐套日期")
        if ready_res.get("error"):
            return str(ready_res.get("error"))
        target["齐套日期"] = ready_res.get("value")

        due_res = _normalize_batch_date_cell(target.get("交期"), field_label="交期")
        if due_res.get("error"):
            return str(due_res.get("error"))
        target["交期"] = due_res.get("value")
        return None

    return _validate_and_normalize


def get_operator_calendar_row_validate_and_normalize(
    conn,
    *,
    holiday_default_efficiency: float,
    op_repo=None,
    inplace: bool = True,
) -> Callable[[dict], str | None]:
    repo = op_repo if op_repo is not None else OperatorRepository(conn)
    hde = float(holiday_default_efficiency) if float(holiday_default_efficiency) > 0 else 0.8

    def _validate_and_normalize(row: dict) -> str | None:
        target = row if inplace else dict(row)

        op_id = str(target.get("工号") or "").strip()
        if not op_id:
            return "“工号”不能为空"
        if not repo.exists(op_id):
            return f"人员“{op_id}”不存在，请先在人员管理中新增该人员。"

        if not target.get("日期") or str(target.get("日期")).strip() == "":
            return "“日期”不能为空"
        try:
            target["日期"] = normalize_date(target.get("日期"))
        except ValidationError as e:
            return e.message
        except Exception:
            return "“日期”格式不合法（期望：YYYY-MM-DD）"

        target["类型"] = _normalize_operator_calendar_day_type(target.get("类型"))
        if target["类型"] not in CALENDAR_DAY_TYPE_STORED_VALUES:
            return "“类型”不合法（允许：workday/holiday；或中文：工作日/假期/节假日/周末）"

        try:
            ss = normalize_hhmm(target.get("班次开始"), field="班次开始", allow_none=True)
        except ValidationError as e:
            return e.message
        except Exception:
            return "“班次开始”格式不合法（期望：HH:MM）"
        target["班次开始"] = ss or "08:00"

        try:
            se = normalize_hhmm(target.get("班次结束"), field="班次结束", allow_none=True)
        except ValidationError as e:
            return e.message
        except Exception:
            return "“班次结束”格式不合法（期望：HH:MM）"
        target["班次结束"] = se or ""

        sh = target.get("可用工时")
        if sh is None or str(sh).strip() == "":
            target["可用工时"] = 8 if target["类型"] == CalendarDayType.WORKDAY.value else 0
        else:
            try:
                v = float(sh)
                if v < 0:
                    return "“可用工时”不能为负数"
                target["可用工时"] = v
            except Exception:
                return "“可用工时”必须是数字"

        if target.get("班次结束"):
            try:
                st_t = datetime.strptime(str(target["班次开始"]), "%H:%M")
                et_t = datetime.strptime(str(target["班次结束"]), "%H:%M")
                if et_t <= st_t:
                    et_t = et_t + timedelta(days=1)
                target["可用工时"] = (et_t - st_t).total_seconds() / 3600.0
            except Exception:
                return "“班次开始/结束”格式不合法（期望：HH:MM）"

        eff = target.get("效率")
        if eff is None or str(eff).strip() == "":
            target["效率"] = 1.0 if target["类型"] == CalendarDayType.WORKDAY.value else hde
        else:
            try:
                v = float(eff)
                if v <= 0:
                    return "“效率”必须大于 0"
                target["效率"] = v
            except Exception:
                return "“效率”必须是数字"

        target["允许普通件"] = _normalize_yesno(target.get("允许普通件"))
        if target["允许普通件"] not in YESNO_VALUES:
            return "“允许普通件”不合法（允许：yes/no；或中文：是/否）"
        target["允许急件"] = _normalize_yesno(target.get("允许急件"))
        if target["允许急件"] not in YESNO_VALUES:
            return "“允许急件”不合法（允许：yes/no；或中文：是/否）"

        target["__id"] = f"{op_id}|{target.get('日期')}"
        return None

    return _validate_and_normalize

