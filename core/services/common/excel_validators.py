from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Callable, Optional, Tuple

from core.errors import ValidationError
from core.models.enums import (
    BATCH_PRIORITY_LABELS,
    BATCH_PRIORITY_VALUES,
    READY_STATUS_LABELS,
    READY_STATUS_VALUES,
    BatchPriority,
    ReadyStatus,
)
from core.services.common.normalize import normalize_text
from core.shared.strict_parse import parse_required_int

# 导入只认导出和模板下拉写出的中文；空格子按默认值处理。
_PRIORITY_LABELS = {BATCH_PRIORITY_LABELS[value]: value for value in BATCH_PRIORITY_VALUES}
_READY_LABELS = {READY_STATUS_LABELS[value]: value for value in READY_STATUS_VALUES}


def _label_code(value: Any, labels: dict, default: str) -> Optional[str]:
    text = normalize_text(value)
    return default if text is None else labels.get(text)


def _normalize_batch_date_cell(value: Any, field_label: str) -> Tuple[Optional[str], Optional[str]]:
    if value is None:
        return None, None
    if isinstance(value, datetime):
        return value.date().isoformat(), None
    if isinstance(value, date):
        return value.isoformat(), None

    s = str(value).strip()
    if not s:
        return None, None
    if "T" in s or " " in s:
        return None, f"“{field_label}”不合法：日期字段不允许包含时间（当前值：{s}）。请仅填写日期：YYYY-MM-DD 或 YYYY/MM/DD（例：2026-01-25）。"

    m = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", s)
    if not m:
        return None, f"“{field_label}”不合法：期望格式 YYYY-MM-DD 或 YYYY/MM/DD（当前值：{s}）。"

    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        v = date(y, mo, d).isoformat()
    except ValueError:
        return None, f"“{field_label}”不合法：日期值不存在（当前值：{s}）。期望：YYYY-MM-DD 或 YYYY/MM/DD。"
    return v, None


def get_batch_row_validate_and_normalize(
    *,
    parts_cache: dict,
    max_quantity: Optional[int] = None,
) -> Callable[[dict], Optional[str]]:
    """使用已有零件缓存构建“批次信息”Excel 原地归一化校验器。"""

    def _validate_and_normalize(row: dict) -> Optional[str]:
        pn = row["图号"]
        if pn not in parts_cache:
            return f"图号“{pn}”不存在，请先在工艺管理中维护零件。"

        qty = row.get("数量")
        try:
            q = parse_required_int(qty, field="数量", max_value=max_quantity)
            if q <= 0:
                return "“数量”必须大于 0"
            row["数量"] = q
        except ValidationError as e:
            return e.message

        row["优先级"] = _label_code(row.get("优先级"), _PRIORITY_LABELS, BatchPriority.NORMAL.value)
        if row["优先级"] is None:
            return "“优先级”不合法，只能填写：" + " / ".join(_PRIORITY_LABELS) + "。"

        row["维护齐套标记"] = _label_code(row.get("维护齐套标记"), _READY_LABELS, ReadyStatus.YES.value)
        if row["维护齐套标记"] is None:
            return "“维护齐套标记”不合法，只能填写：" + " / ".join(_READY_LABELS) + "。"

        ready_value, error = _normalize_batch_date_cell(row.get("齐套日期"), field_label="齐套日期")
        if error:
            return error
        row["齐套日期"] = ready_value

        due_value, error = _normalize_batch_date_cell(row.get("交期"), field_label="交期")
        if error:
            return error
        row["交期"] = due_value
        return None

    return _validate_and_normalize
