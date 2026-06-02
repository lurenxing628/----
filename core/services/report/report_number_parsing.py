from __future__ import annotations

import re
from typing import Any, Optional

from core.infrastructure.errors import ValidationError
from core.shared.strict_parse import is_blank_input, parse_required_float, parse_required_int

_INT_TEXT_PATTERN = re.compile(r"^[+-]?\d+$")


def parse_report_float(
    value: Any,
    *,
    field: str,
    label: str,
    source_label: str,
    blank_default: Optional[float] = None,
) -> float:
    if is_blank_input(value):
        if blank_default is None:
            raise ValidationError(f"{label}不能为空，请检查{source_label}。", field=field)
        return float(blank_default)
    try:
        return float(parse_required_float(value, field=label))
    except ValidationError as exc:
        raise ValidationError(f"{label}不是有效数字，请检查{source_label}。", field=field) from exc


def parse_optional_report_float(value: Any, *, field: str, label: str, source_label: str) -> Optional[float]:
    if is_blank_input(value):
        return None
    return parse_report_float(value, field=field, label=label, source_label=source_label)


def parse_report_int(
    value: Any,
    *,
    field: str,
    label: str,
    source_label: str,
    blank_default: Optional[int] = None,
) -> int:
    if is_blank_input(value):
        if blank_default is None:
            raise ValidationError(f"{label}不能为空，请检查{source_label}。", field=field)
        return int(blank_default)
    try:
        return int(parse_required_int(value, field=label))
    except ValidationError as exc:
        raise ValidationError(f"{label}不是有效整数，请检查{source_label}。", field=field) from exc


def _parse_plain_report_int(
    value: Any,
    *,
    field: str,
    label: str,
    source_label: str,
    blank_default: int,
) -> int:
    if is_blank_input(value):
        return int(blank_default)
    if isinstance(value, bool):
        raise ValidationError(f"{label}不是有效整数，请检查{source_label}。", field=field)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, str) and _INT_TEXT_PATTERN.fullmatch(value.strip()):
        return int(value.strip())
    raise ValidationError(f"{label}不是有效整数，请检查{source_label}。", field=field)


def parse_report_nonnegative_int(
    value: Any,
    *,
    field: str,
    label: str,
    source_label: str,
    blank_default: int = 0,
) -> int:
    number = _parse_plain_report_int(
        value,
        field=field,
        label=label,
        source_label=source_label,
        blank_default=blank_default,
    )
    if number < 0:
        raise ValidationError(f"{label}不是有效整数，请检查{source_label}。", field=field)
    return number


__all__ = [
    "parse_optional_report_float",
    "parse_report_float",
    "parse_report_int",
    "parse_report_nonnegative_int",
]
