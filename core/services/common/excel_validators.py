from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Callable, Dict, Optional

from core.errors import ValidationError
from core.models.enums import (
    BATCH_PRIORITY_VALUES,
    READY_STATUS_VALUES,
    BatchPriority,
    ReadyStatus,
)
from core.services.common.normalization_matrix import (
    normalize_batch_priority_value,
    normalize_ready_status_value,
)
from core.services.common.normalize import is_blank_value, to_str_or_blank
from core.services.common.number_utils import parse_finite_int
from data.repositories import PartRepository


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
    parts_cache: Optional[dict] = None,
    inplace: bool = True,
) -> Callable[[dict], Optional[str]]:
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

    def _validate_and_normalize(row: dict) -> Optional[str]:
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
            return "“优先级”不合法，可填写：普通 / 急件 / 特急。以前的 Excel 如果写过英文，系统会尽量按中文意思读取；新文件请直接填中文。"

        target["齐套"] = _normalize_ready_status(target.get("齐套"))
        if target["齐套"] not in READY_STATUS_VALUES:
            return "“齐套”不合法，新文件请填写：齐套 / 未齐套 / 部分齐套。以前的 Excel 如果写过 是 / 否 或英文，系统会尽量按中文意思读取；新文件请直接填中文推荐值。"

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
