from __future__ import annotations

from typing import Any, Optional

from core.infrastructure.errors import ValidationError
from core.shared.compat_parse import parse_compat_float, parse_compat_int
from core.shared.degradation import DegradationCollector
from core.shared.strict_parse import parse_required_float, parse_required_int

_MIN_VIOLATION_USE_DEFAULT = object()


def _require_collector(collector: Optional[DegradationCollector]) -> DegradationCollector:
    if collector is None:
        raise TypeError("collector 不能为空")
    return collector


def _format_fallback_value(value: Any) -> str:
    if value is None:
        return "空值"
    return str(value)


def _minimum_violation_message(*, field: str, fallback: Any, min_value: Any, min_inclusive: bool) -> str:
    compare_text = "大于等于" if bool(min_inclusive) else "大于"
    return (
        f"字段“{field}”数值太小（要求{compare_text} {min_value}），"
        f"本次先按 {_format_fallback_value(fallback)} 处理，请检查后保存。"
    )


def _emit_min_violation(
    collector: DegradationCollector,
    *,
    field: str,
    scope: str,
    raw_value: Any,
    fallback: Any,
    min_value: Any,
    min_inclusive: bool,
) -> None:
    collector.add(
        code="number_below_minimum",
        scope=scope,
        field=field,
        message=_minimum_violation_message(
            field=field,
            fallback=fallback,
            min_value=min_value,
            min_inclusive=min_inclusive,
        ),
        sample=repr(raw_value),
    )


def parse_field_float(
    value: Any,
    *,
    field: str,
    strict_mode: bool,
    scope: str,
    fallback: float,
    collector: DegradationCollector,
    min_value: Optional[float] = None,
    min_inclusive: bool = True,
    min_violation_fallback: Any = _MIN_VIOLATION_USE_DEFAULT,
) -> float:
    active_collector = _require_collector(collector)
    if strict_mode:
        return float(parse_required_float(value, field=field, min_value=min_value, min_inclusive=min_inclusive))

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
            compat_fallback = fallback if min_violation_fallback is _MIN_VIOLATION_USE_DEFAULT else float(min_violation_fallback)
            _emit_min_violation(
                active_collector,
                field=field,
                scope=scope,
                raw_value=value,
                fallback=compat_fallback,
                min_value=min_value,
                min_inclusive=min_inclusive,
            )
            return float(compat_fallback)

    return float(parsed)


def parse_field_int(
    value: Any,
    *,
    field: str,
    strict_mode: bool,
    scope: str,
    fallback: int,
    collector: DegradationCollector,
    min_value: Optional[int] = None,
    min_violation_fallback: Any = _MIN_VIOLATION_USE_DEFAULT,
) -> int:
    active_collector = _require_collector(collector)
    if strict_mode:
        return int(parse_required_int(value, field=field, min_value=min_value))

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
        _emit_min_violation(
            active_collector,
            field=field,
            scope=scope,
            raw_value=value,
            fallback=compat_fallback,
            min_value=min_value,
            min_inclusive=True,
        )
        return int(compat_fallback)

    return int(parsed)
