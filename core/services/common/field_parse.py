from __future__ import annotations

from typing import Any, Optional

from core.infrastructure.errors import ValidationError
from core.services.common.compat_parse import parse_compat_float, parse_compat_int
from core.services.common.degradation import DegradationCollector
from core.services.common.strict_parse import parse_required_float, parse_required_int

_MIN_VIOLATION_USE_DEFAULT = object()


def parse_field_float(
    value: Any,
    *,
    field: str,
    strict_mode: bool,
    scope: str,
    fallback: float,
    collector: Optional[DegradationCollector] = None,
    min_value: Optional[float] = None,
    min_inclusive: bool = True,
    min_violation_fallback: Any = _MIN_VIOLATION_USE_DEFAULT,
) -> float:
    if strict_mode:
        return float(
            parse_required_float(value, field=field, min_value=min_value, min_inclusive=min_inclusive)
        )

    active_collector = collector if collector is not None else DegradationCollector()
    try:
        parsed = float(parse_required_float(value, field=field))
    except ValidationError:
        compat_value = parse_compat_float(
            value,
            field=field,
            scope=scope,
            collector=active_collector,
            fallback=fallback,
        )
        return float(fallback if compat_value is None else compat_value)

    if min_value is not None:
        is_valid = parsed >= float(min_value) if bool(min_inclusive) else parsed > float(min_value)
        if not is_valid:
            compat_fallback = (
                fallback if min_violation_fallback is _MIN_VIOLATION_USE_DEFAULT else float(min_violation_fallback)
            )
            compat_value = parse_compat_float(
                value,
                field=field,
                scope=scope,
                collector=active_collector,
                fallback=compat_fallback,
                min_value=min_value,
                min_inclusive=min_inclusive,
            )
            return float(compat_fallback if compat_value is None else compat_value)

    return float(parsed)


def parse_field_int(
    value: Any,
    *,
    field: str,
    strict_mode: bool,
    scope: str,
    fallback: int,
    collector: Optional[DegradationCollector] = None,
    min_value: Optional[int] = None,
    min_violation_fallback: Any = _MIN_VIOLATION_USE_DEFAULT,
) -> int:
    if strict_mode:
        return int(parse_required_int(value, field=field, min_value=min_value))

    active_collector = collector if collector is not None else DegradationCollector()
    try:
        parsed = int(parse_required_int(value, field=field))
    except ValidationError:
        compat_value = parse_compat_int(
            value,
            field=field,
            scope=scope,
            collector=active_collector,
            fallback=fallback,
        )
        return int(fallback if compat_value is None else compat_value)

    if min_value is not None and parsed < int(min_value):
        compat_fallback = fallback if min_violation_fallback is _MIN_VIOLATION_USE_DEFAULT else int(min_violation_fallback)
        compat_value = parse_compat_int(
            value,
            field=field,
            scope=scope,
            collector=active_collector,
            fallback=compat_fallback,
            min_value=min_value,
        )
        return int(compat_fallback if compat_value is None else compat_value)

    return int(parsed)
