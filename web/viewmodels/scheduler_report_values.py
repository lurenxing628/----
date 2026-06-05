from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Optional


def _text(value: Any) -> str:
    return str(value or "").strip()


class ReportPresentationValueError(ValueError):
    def __init__(self, message: str, *, field: str):
        self.field = field
        super().__init__(message)


def downtime_summary(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    items = list(rows or [])
    return {
        "machine_count": len(items),
        "downtime_hours": _sum_number(items, "downtime_hours"),
        "downtime_count": _sum_number(items, "downtime_count", integer=True),
        "schedule_overlap_hours": _sum_number(items, "schedule_overlap_hours"),
        "schedule_overlap_count": _sum_number(items, "schedule_overlap_count", integer=True),
    }


def _sum_number(rows: Iterable[Dict[str, Any]], key: str, *, integer: bool = False) -> float:
    total = 0.0
    for row in rows or []:
        label = "停机影响汇总值"
        number = _optional_number((row or {}).get(key), field=key, label=label)
        if number is not None:
            if integer and not number.is_integer():
                raise ReportPresentationValueError(f"{label}不是整数，请检查报表数据。", field=key)
            total += number
    return int(total) if integer else round(total, 2)


def _optional_number(value: Any, *, field: str, label: str) -> Optional[float]:
    try:
        if value is None or _text(value) == "":
            return None
        if isinstance(value, bool):
            raise ValueError(label)
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ReportPresentationValueError(f"{label}不是数字，请检查报表数据。", field=field) from exc
    if not math.isfinite(number):
        raise ReportPresentationValueError(f"{label}不是数字，请检查报表数据。", field=field)
    return number
