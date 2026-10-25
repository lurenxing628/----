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


def normalize_hhmm(value: Any, *, field: str) -> Optional[str]:
    """
    时间标准化为 HH:MM（支持 HH:MM / HH:MM:SS）。
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    s = str(value).strip().replace("：", ":")
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            t = datetime.strptime(s, fmt).time()
            return t.strftime("%H:%M")
        except ValueError:
            continue
    raise ValidationError(f"“{field}”格式不合法（期望：HH:MM）", field=field)

