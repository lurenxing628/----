from __future__ import annotations

import math
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from core.errors import ValidationError

ILLEGAL_XML_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")
_DATETIME_FORMAT_HINT = "YYYY-MM-DD / YYYY-MM-DD HH:MM / YYYY-MM-DD HH:MM:SS"
_INT64_MAX = (1 << 63) - 1


def is_blank_input(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def is_exact_positive_int(value: Any) -> bool:
    """Stored SQLite INTEGER / JSON integer identity: an exact int (no bool, text or float) in 1..2**63-1."""
    return type(value) is int and 0 < value <= _INT64_MAX


# Shared numeric rules. Callers keep their own exception type, message and error code; these only decide
# what counts as an integer or a finite number (a bool is neither).


def is_int(value: Any) -> bool:
    """An int that is not a bool."""
    return isinstance(value, int) and not isinstance(value, bool)


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


def integer_value(value: Any) -> Optional[int]:
    """A stored integer: an int (not bool) as is, an integral float, or UTF-8 bytes / text / other value whose
    literal is an integer ('1', ' 1 ', '1.0', '1e3'); None for anything else, blank included."""
    if is_int(value):
        return int(value)
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    text = str(value).strip()
    if len(text) <= 4300:
        try:
            return int(text)
        except ValueError:
            pass
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    span = decimal_integral_span(number)
    if span is None or span > 4300:
        return None
    return 0 if number.is_zero() else int(number)


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


def parse_optional_date(value: Any, *, field: str) -> Optional[date]:
    if is_blank_input(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().replace("/", "-")
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"“{field}”格式不合法（期望：YYYY-MM-DD）", field=field) from exc


def parse_optional_datetime(value: Any, *, field: str) -> Optional[datetime]:
    if is_blank_input(value):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, 0, 0, 0)
    text = str(value).strip().replace("/", "-").replace("T", " ").replace("：", ":")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except (TypeError, ValueError, OverflowError):
            continue
    raise ValidationError(f"“{field}”格式不合法（期望：{_DATETIME_FORMAT_HINT}）", field=field)
