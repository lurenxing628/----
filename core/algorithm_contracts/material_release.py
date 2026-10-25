"""Optional per-operation material release; an operation without one keeps its earliest start."""

from __future__ import annotations

from datetime import datetime

from core.errors import ValidationError

from .types import OpForScheduleAlgo


def released_start(op: OpForScheduleAlgo, earliest: datetime) -> datetime:
    value = op.material_ready_date
    if value is None:
        return earliest
    try:
        bound = datetime.fromisoformat(value)
        if len(value) != 10 or bound.date().isoformat() != value:
            raise ValueError("invalid date")
    except (ValueError, TypeError) as exc:
        raise ValidationError("工序物料到齐日期无效，排产已停止。", field="material_ready_date") from exc
    return max(earliest, bound)
