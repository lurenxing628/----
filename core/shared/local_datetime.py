"""Factory-local schedule instants with lossless microsecond storage."""

from datetime import datetime
from typing import Any, Optional

_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")


def parse_local_datetime(value: Any) -> Optional[datetime]:
    """Keep legacy local formats; never coerce timezone or excess precision."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is None else None
    text = str(value).strip().replace("/", "-").replace("T", " ").replace("：", ":")
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
