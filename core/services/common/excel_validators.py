from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Callable, Optional, Tuple

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
from core.services.common.normalize import normalize_text
from core.shared.strict_parse import parse_required_int


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
) -> Callable[[dict], Optional[str]]:
    """使用已有零件缓存构建“批次信息”Excel 原地归一化校验器。"""

    def _validate_and_normalize(row: dict) -> Optional[str]:
        target = row
        batch_id = normalize_text(target.get("批次号"))

        if batch_id is None:
            return "“批次号”不能为空"
        pn = normalize_text(target.get("图号"))
        if pn is None:
            return "“图号”不能为空"
        if pn not in parts_cache:
            return f"图号“{pn}”不存在，请先在工艺管理中维护零件。"

        qty = target.get("数量")
        try:
            q = parse_required_int(qty, field="数量")
            if q <= 0:
                return "“数量”必须大于 0"
            target["数量"] = q
        except ValidationError as e:
            return e.message

        target["优先级"] = normalize_batch_priority_value(target.get("优先级"), default=BatchPriority.NORMAL.value)
        if target["优先级"] not in BATCH_PRIORITY_VALUES:
            return "“优先级”不合法，可填写：普通 / 急件 / 特急。以前的 Excel 如果写过英文，系统会尽量按中文意思读取；新文件请直接填中文。"

        target["齐套"] = normalize_ready_status_value(target.get("齐套"), default=ReadyStatus.YES.value)
        if target["齐套"] not in READY_STATUS_VALUES:
            return "“齐套”不合法，新文件请填写：齐套 / 未齐套 / 部分齐套。以前的 Excel 如果写过 是 / 否 或英文，系统会尽量按中文意思读取；新文件请直接填中文推荐值。"

        ready_value, error = _normalize_batch_date_cell(target.get("齐套日期"), field_label="齐套日期")
        if error:
            return error
        target["齐套日期"] = ready_value

        due_value, error = _normalize_batch_date_cell(target.get("交期"), field_label="交期")
        if error:
            return error
        target["交期"] = due_value
        return None

    return _validate_and_normalize
