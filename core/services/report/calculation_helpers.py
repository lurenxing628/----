from __future__ import annotations

from datetime import datetime
from typing import Any

from core.models.enums import SourceType


def overlap_seconds(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> float:
    s = max(a_start, b_start)
    e = min(a_end, b_end)
    if e <= s:
        return 0.0
    return (e - s).total_seconds()


def is_internal_source(value: Any) -> bool:
    return str(value or "").strip().lower() == SourceType.INTERNAL.value
