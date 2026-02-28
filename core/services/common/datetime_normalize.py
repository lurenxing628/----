from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from core.infrastructure.errors import ValidationError


def normalize_date(value: Any) -> str:
    """
    日期标准化为 YYYY-MM-DD。

    约定：
    - 支持 date/datetime
    - 支持字符串：YYYY-MM-DD / YYYY/MM/DD
    - 为空则抛 ValidationError（字段名：日期）
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
    except Exception as e:
        raise ValidationError("“日期”格式不合法（期望：YYYY-MM-DD）", field="日期") from e


def normalize_hhmm(value: Any, *, field: str, allow_none: bool = True) -> Optional[str]:
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

