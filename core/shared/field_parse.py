from __future__ import annotations

from typing import Any, Optional

from core.errors import ValidationError
from core.shared.compat_parse import recover_compat_number
from core.shared.degradation import DegradationCollector
from core.shared.field_labels import display_field_label
from core.shared.strict_parse import parse_required_float, parse_required_int
from core.shared.value_policies import VALUE_FLOAT, VALUE_INT

_MIN_VIOLATION_USE_DEFAULT = object()


def _minimum_violation_message(*, field_label: str, fallback: Any, min_value: Any, min_inclusive: bool) -> str:
    compare_text = "大于等于" if bool(min_inclusive) else "大于"
    return (
        f"{field_label}数值太小（要求{compare_text} {min_value}），"
        f"本次先按 {fallback} 处理，请检查后保存。"
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
    field_label: Optional[str] = None,
) -> None:
    label = display_field_label(field, fallback="字段") if field_label is None else str(field_label or "字段")
    collector.add(
        code="number_below_minimum",
        scope=scope,
        field=field,
        message=_minimum_violation_message(
            field_label=label,
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
    field_label: Optional[str] = None,
) -> float:
    label = display_field_label(field, fallback="字段") if field_label is None else str(field_label or "字段")
    if strict_mode:
        try:
            return float(parse_required_float(value, field=label, min_value=min_value, min_inclusive=min_inclusive))
        except ValidationError as exc:
            raise ValidationError(exc.message, field=field) from exc

    try:
        parsed = float(parse_required_float(value, field=label))
    except ValidationError:
        compat_value = recover_compat_number(
            value,
            field=field,
            expected_kind=VALUE_FLOAT,
            scope=scope,
            collector=collector,
            fallback=fallback,
            field_label=label,
        )
        return float(compat_value)

    if min_value is not None:
        is_valid = parsed >= float(min_value) if bool(min_inclusive) else parsed > float(min_value)
        if not is_valid:
            compat_fallback = fallback if min_violation_fallback is _MIN_VIOLATION_USE_DEFAULT else float(min_violation_fallback)
            _emit_min_violation(
                collector,
                field=field,
                scope=scope,
                raw_value=value,
                fallback=compat_fallback,
                min_value=min_value,
                min_inclusive=min_inclusive,
                field_label=label,
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
    field_label: Optional[str] = None,
) -> int:
    label = display_field_label(field, fallback="字段") if field_label is None else str(field_label or "字段")
    if strict_mode:
        try:
            return int(parse_required_int(value, field=label, min_value=min_value))
        except ValidationError as exc:
            raise ValidationError(exc.message, field=field) from exc

    try:
        parsed = int(parse_required_int(value, field=label))
    except ValidationError:
        compat_value = recover_compat_number(
            value,
            field=field,
            expected_kind=VALUE_INT,
            scope=scope,
            collector=collector,
            fallback=fallback,
            field_label=label,
        )
        return int(compat_value)

    if min_value is not None and parsed < int(min_value):
        compat_fallback = fallback if min_violation_fallback is _MIN_VIOLATION_USE_DEFAULT else int(min_violation_fallback)
        _emit_min_violation(
            collector,
            field=field,
            scope=scope,
            raw_value=value,
            fallback=compat_fallback,
            min_value=min_value,
            min_inclusive=True,
            field_label=label,
        )
        return int(compat_fallback)

    return int(parsed)
