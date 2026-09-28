"""Optional per-operation material release; absence preserves legacy decodes."""

from datetime import datetime

from core.errors import ValidationError


def released_start(op, earliest):
    value = getattr(op, "material_ready_date", None)
    if value is None:
        return earliest
    try:
        bound = datetime.fromisoformat(value)
        if len(value) != 10 or bound.date().isoformat() != value:
            raise ValueError("invalid date")
    except (ValueError, TypeError) as exc:
        raise ValidationError("工序物料到齐日期无效，排产已停止。", field="material_ready_date") from exc
    return max(earliest, bound)
