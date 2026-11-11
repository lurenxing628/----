"""Calendar business contents for SGS checkpoints, computed from immutable CalendarInputs."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Tuple

from core.errors import ValidationError

if TYPE_CHECKING:
    from .engine import CalendarInputs


def _storage_order(value: Any) -> Tuple[Any, ...]:
    # SQLite ORDER BY compares storage classes before their native values.
    if value is None:
        return (0,)
    if isinstance(value, (int, float)):
        return 1, value
    if isinstance(value, bytes):
        return 3, value
    return 2, str(value)


def calendar_checkpoint_signature(inputs: CalendarInputs) -> Tuple[str, Tuple[Tuple[Tuple[Any, ...], ...], ...]]:
    """One tuple of row tuples per business table, preserving query fields and storage-class order."""
    tables = (
        (inputs.defaults, ("singleton", "periods_json"), ("singleton",)),
        (
            inputs.public_days,
            ("date", "day_type", "efficiency", "allow_normal", "allow_urgent", "periods_json"),
            ("date",),
        ),
        (
            inputs.personal_days,
            ("operator_id", "date", "day_type", "efficiency", "allow_normal", "allow_urgent", "periods_json"),
            ("operator_id", "date"),
        ),
        (inputs.operator_profiles, ("operator_id", "shift_profile_id"), ("operator_id",)),
        (inputs.shift_profiles, ("profile_id", "anchor_date", "cycle_days", "status"), ("profile_id",)),
        (inputs.shift_patterns, ("profile_id", "day_offset", "is_rest", "periods_json"), ("profile_id", "day_offset")),
    )
    result = []
    for rows, fields, order in tables:
        if rows is None:
            raise ValidationError(
                "无法读取断点所需的日历业务证书，请使用全量解码。",
                field="decode_checkpoint",
                details={"reason": "decode_checkpoint_calendar_unavailable"},
            )
        originals = sorted(
            rows,
            key=lambda row: tuple(_storage_order(row[field]) for field in order),
        )
        result.append(tuple(tuple(row[field] for field in fields) for row in originals))
    return "calendar-business-v1", tuple(result)
