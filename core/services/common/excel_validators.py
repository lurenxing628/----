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
from core.services.common.normalization_matrix import (
    normalize_batch_priority_value,
    normalize_calendar_day_type_value,
    normalize_ready_status_value,
    normalize_yes_no_narrow_value,
)
from core.services.common.normalize import is_blank_value, to_str_or_blank
from core.services.common.number_utils import parse_finite_float, parse_finite_int
from data.repositories import OperatorRepository, PartRepository


def _normalize_batch_priority(value: Any) -> str:
    return normalize_batch_priority_value(
        value,
        default=BatchPriority.NORMAL.value,
        unknown_policy="passthrough",
    )


def _normalize_ready_status(value: Any) -> str:
    return normalize_ready_status_value(
        value,
        default=ReadyStatus.YES.value,
        unknown_policy="passthrough",
    )


def _normalize_operator_calendar_day_type(value: Any) -> str:
    return normalize_calendar_day_type_value(
        value,
        default=CalendarDayType.WORKDAY.value,
        unknown_policy="passthrough",
    )


def _normalize_yesno(value: Any) -> str:
    return normalize_yes_no_narrow_value(value, default=YesNo.YES.value, unknown_policy="passthrough")


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
    conn=None,
    *,
    parts_cache: dict | None = None,
    inplace: bool = True,
) -> Callable[[dict], str | None]:
    """
    构建“批次信息”Excel 导入行校验器。

    兼容约定：
    - 允许沿用旧调用方式：首参位置继续传 conn。
    - 当 parts_cache 已是 dict 时，conn 可省略。
    - 若两者都不可用，则显式抛出 ValueError，避免把装配错误伪装成空数据。
    """
    if isinstance(parts_cache, dict):
        parts = parts_cache
    else:
        if conn is None:
            raise ValueError("get_batch_row_validate_and_normalize 缺少 conn 或 parts_cache")
        parts = {p.part_no: p for p in PartRepository(conn).list()}

    def _validate_and_normalize(row: dict) -> str | None:
        target = row if inplace else dict(row)

        if is_blank_value(target.get("批次号")):
            return "“批次号”不能为空"
        if is_blank_value(target.get("图号")):
            return "“图号”不能为空"
        pn = to_str_or_blank(target.get("图号"))
        if pn not in parts:
            return f"图号“{pn}”不存在，请先在工艺管理中维护零件。"

        qty = target.get("数量")
        if qty is None or str(qty).strip() == "":
            return "“数量”不能为空"
        try:
            q = parse_finite_int(qty, field="数量", allow_none=False)
            if q is None or q <= 0:
                return "“数量”必须大于 0"
            target["数量"] = q
        except ValidationError as e:
            return e.message

        target["优先级"] = _normalize_batch_priority(target.get("优先级"))
        if target["优先级"] not in BATCH_PRIORITY_VALUES:
            return "“优先级”不合法，可填写：普通 / 急件 / 特急；也兼容英文标准值 normal/urgent/critical。"

        target["齐套"] = _normalize_ready_status(target.get("齐套"))
        if target["齐套"] not in READY_STATUS_VALUES:
            return "“齐套”不合法，可填写：齐套 / 未齐套 / 部分齐套 / 是 / 否；也兼容英文标准值 yes/no/partial。"

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
    hde = parse_finite_float(holiday_default_efficiency, field="假期默认效率", allow_none=False)
    if hde <= 0:
        raise ValidationError("假期默认效率必须大于 0。", field="假期默认效率")

    def _validate_and_normalize(row: dict) -> str | None:
        target = row if inplace else dict(row)

        op_id = to_str_or_blank(target.get("工号"))
        if not op_id:
            return "“工号”不能为空"
        if not repo.exists(op_id):
            return f"人员“{op_id}”不存在，请先在人员管理中新增该人员。"

        if is_blank_value(target.get("日期")):
            return "“日期”不能为空"
        try:
            target["日期"] = normalize_date(target.get("日期"))
        except ValidationError as e:
            return e.message
        except Exception:
            return "“日期”格式不合法（期望：YYYY-MM-DD）"

        target["类型"] = _normalize_operator_calendar_day_type(target.get("类型"))
        if target["类型"] not in CALENDAR_DAY_TYPE_STORED_VALUES:
            return "“类型”不合法，可填写：工作日 / 假期 / 周末 / 节假日；也兼容英文标准值 workday/holiday。"

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
        if sh is None or (isinstance(sh, str) and sh.strip() == ""):
            target["可用工时"] = 8 if target["类型"] == CalendarDayType.WORKDAY.value else 0
        else:
            try:
                parsed_shift_hours = parse_finite_float(sh, field="可用工时", allow_none=False)
                if parsed_shift_hours < 0:
                    return "“可用工时”不能为负数"
                target["可用工时"] = parsed_shift_hours
            except ValidationError as e:
                return e.message

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
        if eff is None or (isinstance(eff, str) and eff.strip() == ""):
            target["效率"] = 1.0 if target["类型"] == CalendarDayType.WORKDAY.value else hde
        else:
            try:
                parsed_efficiency = parse_finite_float(eff, field="效率", allow_none=False)
                if parsed_efficiency <= 0:
                    return "“效率”必须大于 0"
                target["效率"] = parsed_efficiency
            except ValidationError as e:
                return e.message

        target["允许普通件"] = _normalize_yesno(target.get("允许普通件"))
        if target["允许普通件"] not in YESNO_VALUES:
            return "“允许普通件”不合法，可填写：是 / 否；也兼容英文标准值 yes/no/true/false/1/0。"
        target["允许急件"] = _normalize_yesno(target.get("允许急件"))
        if target["允许急件"] not in YESNO_VALUES:
            return "“允许急件”不合法，可填写：是 / 否；也兼容英文标准值 yes/no/true/false/1/0。"

        target["__id"] = f"{op_id}|{target.get('日期')}"
        return None

    return _validate_and_normalize
