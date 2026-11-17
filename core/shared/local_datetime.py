"""Factory-local schedule instants with lossless microsecond storage."""

import re
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional, Tuple

_EPOCH = datetime(1970, 1, 1)
_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")
# 库里绝大多数时间都是这种标准写法；整串吻合时 fromisoformat 与上面的 strptime 结果相同，
# 却快一个数量级（整份计划读取要解析十几万次）。其余写法、以及 fromisoformat 不收的小数位数仍走 strptime。
_CANONICAL = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} (?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\.[0-9]{1,6})?")


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
    if value.tzinfo is not None:
        raise ValueError("Expected factory-local datetime")
    return value.isoformat(sep=" ")


def datetime_to_us(dt: datetime) -> int:
    delta = dt - _EPOCH
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def us_to_datetime(us: int) -> datetime:
    return _EPOCH + timedelta(microseconds=us)


def row_interval(row: Mapping[str, Any]) -> Tuple[datetime, datetime]:
    """A stored row's own ``start_us``/``end_us`` as local datetimes; a point event's two are equal."""
    return us_to_datetime(row["start_us"]), us_to_datetime(row["end_us"])


def us_to_iso(us: int) -> str:
    dt = _EPOCH + timedelta(microseconds=us)
    return dt.isoformat(timespec="microseconds" if dt.microsecond else "seconds")
