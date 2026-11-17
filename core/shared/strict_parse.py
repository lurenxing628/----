"""Strict admission of stored and submitted values, and the one wire encoding of integers.

Admission decides what a value means (identity, count, instant, cycle, finite number) and never coerces;
``wire_int`` is the only place that turns an integer beyond the JavaScript safe range into text, and
``wire_sequence`` applies it to stored operation sequences that their readers diagnose instead of admit.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Union

from core.errors import ValidationError
from core.shared.local_datetime import datetime_to_us

ILLEGAL_XML_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")
_INT64_MAX = (1 << 63) - 1
JS_SAFE_INT_MAX = (1 << 53) - 1
PORT_MAX = 65535
WIN32_DWORD_MAX = 0xFFFFFFFF
TIME_US_MIN = datetime_to_us(datetime.min)
TIME_US_MAX = datetime_to_us(datetime.max)
# 外协周期（自然日）的上限：100 年。外协周期、合并周期、供应商默认周期写入时都按它拒收，
# 表上的 CHECK（enums.external_days_check）与日历的同量级上限也都取这一个数。
EXTERNAL_DAYS_MAX = 36500
EXTERNAL_DAYS_RANGE_TEXT = "必须大于 0 天且不超过 " + str(EXTERNAL_DAYS_MAX) + " 天（100 年）"


def wire_int(value: int) -> Union[int, str]:
    """An admitted integer in a public DTO: itself within ±JS_SAFE_INT_MAX, its decimal text beyond, so a browser
    never rounds it. It neither admits nor defaults; callers pass the int their own boundary already accepted."""
    return value if -JS_SAFE_INT_MAX <= value <= JS_SAFE_INT_MAX else str(value)


def wire_sequence(value: Any) -> Union[int, str]:
    """A stored operation sequence (PartOperations / BatchOperations / ExternalGroups / BatchExternalContexts, INTEGER
    columns without a typeof CHECK) as shown: wire_int for an int; text or real the column kept stays visible as its
    text, beside the reader's own invalid-sequence issue, so the page still opens and template sync can replace it."""
    return wire_int(value) if type(value) is int else str(value)


def is_blank_input(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


# A stored integer is admitted by what it means, never by one catch-all rule:
#   identity, version, sequence -> is_exact_positive_int                 1..2**63-1
#   one entry's count/quantity  -> is_stored_number(value, integer=True)  0..2**53-1
#   instant in microseconds     -> is_stored_time_us                      signed, TIME_US_MIN..TIME_US_MAX
# An external cycle in natural days -> is_external_days                    (0, EXTERNAL_DAYS_MAX], int or float
# Table columns typed by enums.time_us_check / count_check / external_days_check hold these same ranges; their
# readers do not re-check.


def is_exact_positive_int(value: Any) -> bool:
    """Stored SQLite INTEGER / JSON integer identity: an exact int (no bool, text or float) in 1..2**63-1."""
    return type(value) is int and 0 < value <= _INT64_MAX


def is_stored_time_us(value: Any) -> bool:
    """A stored factory-local instant (``local_datetime.datetime_to_us``): an exact int (no bool, text or float)
    that a datetime can hold. Negative, zero and beyond 2**53-1 are ordinary instants."""
    return type(value) is int and TIME_US_MIN <= value <= TIME_US_MAX


# Shared numeric rules. Callers keep their own exception type, message and error code; these only decide
# what counts as an integer or a finite number (a bool is neither).


def is_number(value: Any) -> bool:
    """An int or float that is not a bool."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def finite_float(value: Any) -> Optional[float]:
    """float(value) for anything float() accepts except a bool; None when refused or NaN/±Inf."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def is_non_finite_number(value: Any) -> bool:
    """float() accepts value (not a bool) but gives NaN/±Inf: tells "not finite" apart from "not a number"."""
    if isinstance(value, bool):
        return False
    try:
        return not math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def is_exact_finite_number(value: Any) -> bool:
    """A stored SQLite / JSON number: an exact int or float (no bool, text or subclass) that is finite as a float;
    NaN, ±Inf and ints beyond the float range are not."""
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def is_exact_non_negative_number(value: Any, *, positive: bool = False) -> bool:
    """is_exact_finite_number and >= 0; > 0 with positive=True."""
    return is_exact_finite_number(value) and (value > 0 if positive else value >= 0)


def is_stored_number(value: Any, *, positive: bool = False, integer: bool = False) -> bool:
    """A stored count/hours/efficiency that can be used as is: an exact finite number (an exact int with
    integer=True) in 0..2**53-1, or 1..2**53-1 / (0, 2**53-1] with positive=True.

    Write admission and read judgement of stored numbers both use this one rule. It bounds one entry: sums and
    derived amounts (quantity × unit hours + setup) only have to be finite and non-negative.
    """
    if not (type(value) is int if integer else is_exact_finite_number(value)):
        return False
    return (0 < value if positive else 0 <= value) and value <= JS_SAFE_INT_MAX


def is_external_days(value: Any) -> bool:
    """An external cycle in natural days (operation cycle, merged-group cycle, supplier default): an exact int
    or float (no bool, text or subclass), finite, in (0, EXTERNAL_DAYS_MAX]. Every write admits with this one rule."""
    return is_exact_finite_number(value) and 0 < value <= EXTERNAL_DAYS_MAX


def parse_bounded_positive_int(value: Any, *, max_value: int, allow_str: bool = True) -> Optional[int]:
    """Strict positive integer admission in 1..max_value without unbounded string/int conversion."""
    if type(value) is int:
        return value if 1 <= value <= max_value else None
    if allow_str and type(value) is str:
        max_digits = len(str(max_value))
        if (
            1 <= len(value) <= max_digits
            and value.isascii()
            and value[0] in "123456789"
            and value.isdigit()
        ):
            parsed = int(value)
            return parsed if parsed <= max_value else None
    return None


def scaled_decimal(number: Decimal, scale10: int = 0) -> Decimal:
    if number.is_zero():
        return Decimal(0)
    if not scale10:
        return number
    sign, digits, exp = number.as_tuple()
    assert isinstance(exp, int)
    return Decimal((sign, digits, exp + scale10))


def decimal_integral_span(number: Decimal, *, scale10: int = 0) -> Optional[int]:
    if number.is_zero():
        return 1
    _sign, digits, exp = number.as_tuple()
    assert isinstance(exp, int)
    nz_digits = list(digits)
    while nz_digits and nz_digits[-1] == 0:
        nz_digits.pop()
    nz_exp = exp + scale10 + (len(digits) - len(nz_digits))
    if nz_exp < 0:
        return None
    return len(nz_digits) + nz_exp


def _raise_blank_required(field: str) -> None:
    raise ValidationError(f"“{field}”不能为空", field=field)


def _ensure_min_float(value: float, *, field: str, min_value: Optional[float], min_inclusive: bool = True) -> float:
    if min_value is not None:
        is_valid = value >= float(min_value) if bool(min_inclusive) else value > float(min_value)
        if not is_valid:
            raise ValidationError(f"“{field}”必须{'大于等于' if bool(min_inclusive) else '大于'} {min_value}", field=field)
    return float(value)


def _ensure_min_int(
    value: int,
    *,
    field: str,
    min_value: Optional[int],
    max_value: Optional[int] = None,
) -> int:
    if min_value is not None and value < int(min_value):
        raise ValidationError(f"“{field}”必须大于等于 {min_value}", field=field)
    if max_value is not None and value > int(max_value):
        raise ValidationError(f"“{field}”不能超过 {max_value}", field=field)
    return int(value)


def _parse_finite_float(value: Any, *, field: str) -> float:
    number = finite_float(value)
    if number is None:
        raise ValidationError(f"“{field}”必须是{'有限数字' if is_non_finite_number(value) else '数字'}", field=field)
    return number


def _looks_like_integer_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, Decimal):
        return int(value.as_tuple().exponent) != 0
    if isinstance(value, str):
        text = value.strip()
        return "." in text or "e" in text.lower()
    return False


def _parse_finite_int(
    value: Any,
    *,
    field: str,
    reject_integer_float: bool = False,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"“{field}”必须是整数", field=field)
    if isinstance(value, int):
        return _ensure_min_int(int(value), field=field, min_value=min_value, max_value=max_value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValidationError(f"“{field}”必须是{'有限整数' if math.isinf(value) else '整数'}", field=field)
        if reject_integer_float or not value.is_integer():
            raise ValidationError(f"“{field}”必须是整数", field=field)
        return _ensure_min_int(int(value), field=field, min_value=min_value, max_value=max_value)
    if isinstance(value, str) and not _looks_like_integer_float(value) and len(value.strip()) <= 4300:
        try:
            parsed_int = int(value.strip())
        except ValueError as exc:
            raise ValidationError(f"“{field}”必须是整数", field=field) from exc
        return _ensure_min_int(parsed_int, field=field, min_value=min_value, max_value=max_value)
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise ValidationError(f"“{field}”必须是整数", field=field) from exc
    if number.is_nan():
        raise ValidationError(f"“{field}”必须是整数", field=field)
    if number.is_infinite():
        raise ValidationError(f"“{field}”必须是有限整数", field=field)
    span = decimal_integral_span(number)
    if span is None or (reject_integer_float and _looks_like_integer_float(value)):
        raise ValidationError(f"“{field}”必须是整数", field=field)
    if min_value is not None and number < int(min_value):
        raise ValidationError(f"“{field}”必须大于等于 {min_value}", field=field)
    if max_value is not None and number > int(max_value):
        raise ValidationError(f"“{field}”不能超过 {max_value}", field=field)
    if span > 4300:
        raise ValidationError(f"“{field}”必须是有限整数", field=field)
    return 0 if number.is_zero() else int(number)


def parse_required_float(
    value: Any, *, field: str, min_value: Optional[float] = None, min_inclusive: bool = True
) -> float:
    if is_blank_input(value):
        _raise_blank_required(field)
    return _ensure_min_float(_parse_finite_float(value, field=field), field=field, min_value=min_value, min_inclusive=min_inclusive)


def parse_optional_float(value: Any, *, field: str) -> Optional[float]:
    if is_blank_input(value):
        return None
    return _parse_finite_float(value, field=field)


def parse_required_int(
    value: Any,
    *,
    field: str,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
    reject_integer_float: bool = False,
) -> int:
    if is_blank_input(value):
        _raise_blank_required(field)
    return _parse_finite_int(
        value,
        field=field,
        reject_integer_float=bool(reject_integer_float),
        min_value=min_value,
        max_value=max_value,
    )
