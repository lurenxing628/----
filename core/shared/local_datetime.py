"""Factory-local schedule instants with lossless microsecond storage."""

import re
from datetime import datetime
from typing import Any, Optional

_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")
# 库里绝大多数时间都是这种标准写法；整串吻合时 fromisoformat 与上面的 strptime 结果相同，
# 却快一个数量级（整份计划读取要解析十几万次）。其余写法、以及 fromisoformat 不收的小数位数仍走 strptime。
_CANONICAL = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?")


def _canonical(text: str) -> Optional[datetime]:
    if _CANONICAL.fullmatch(text) is None:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None  # 例如 2 月 30 日：交给 strptime 按原口径判定


def parse_local_datetime(value: Any) -> Optional[datetime]:
    """Keep legacy local formats; never coerce timezone or excess precision."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is None else None
    text = str(value).strip().replace("/", "-").replace("T", " ").replace("：", ":")
    parsed = _canonical(text)
    if parsed is not None:
        return parsed
    formats = _FORMATS if "." in text else _FORMATS[1:]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except (ValueError, TypeError):
            continue
    return None


def format_local_datetime(value: datetime) -> str:
    """Preserve old whole-second strings and all six digits when needed."""
    if not isinstance(value, datetime) or value.tzinfo is not None:
        raise ValueError("Expected factory-local datetime")
    return value.isoformat(sep=" ")
