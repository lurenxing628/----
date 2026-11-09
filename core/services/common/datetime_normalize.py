from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from core.errors import ValidationError


def normalize_date(value: Any) -> Optional[str]:
    """Web 日期输入可带时间；保存为 YYYY-MM-DD，Excel 仍使用严格单元格校验。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("/", "-").split("T", 1)[0].split(" ", 1)[0]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise ValidationError("日期写法不对，请填写类似 2026-05-20 的日期。", field="日期") from exc

