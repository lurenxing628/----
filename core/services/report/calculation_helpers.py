from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from core.models.enums import SourceType
from core.shared.local_datetime import parse_local_datetime


def parse_dt(value: Any) -> Optional[datetime]:
    return parse_local_datetime(value)


def overlap_seconds(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> float:
    s = max(a_start, b_start)
    e = min(a_end, b_end)
    if e <= s:
        return 0.0
    return float((e - s).total_seconds())


def is_valid_interval(start: datetime, end: datetime) -> bool:
    return end > start


def is_internal_source(value: Any) -> bool:
    return str(value or "").strip().lower() == SourceType.INTERNAL.value
