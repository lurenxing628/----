from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from core.infrastructure.errors import ValidationError
from core.services.common.degradation import DegradationCollector
from core.services.common.strict_parse import (
    is_blank_input,
    parse_optional_date,
    parse_optional_float,
    parse_optional_int,
    parse_required_date,
    parse_required_float,
    parse_required_int,
)
from core.services.common.value_policies import (
    READ_COMPAT,
    VALUE_DATE,
    VALUE_FLOAT,
    VALUE_INT,
    WRITE_OPTIONAL,
    FieldPolicy,
    get_field_policy,
)

_FALLBACK_UNSET = object()


def _resolve_compat_policy(field: str, *, expected_kind: str) -> FieldPolicy:
    policy = get_field_policy(field)
    if policy.read_mode != READ_COMPAT:
        raise ValueError(f"字段“{field}”未声明兼容读取策略")
    if policy.value_kind != expected_kind:
        raise ValueError(f"字段“{field}”的值类型与当前兼容解析入口不匹配：{policy.value_kind!r}")
    return policy


def _resolve_fallback(policy: FieldPolicy, fallback: Any) -> Any:
    if fallback is not _FALLBACK_UNSET:
        return fallback
    if policy.has_compat_default:
        return policy.compat_default
    raise ValueError(f"字段“{policy.field}”的兼容读取缺少回退值")


def _reason_code_for_failure(policy: FieldPolicy, *, raw_value: Any) -> str:
    if is_blank_input(raw_value) and policy.blank_reason_code:
        return policy.blank_reason_code
    return str(policy.compat_reason_code or policy.strict_reason_code)


def _format_fallback_value(value: Any) -> str:
    if value is None:
        return "空值"
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _compat_message(code: str, *, field: str, fallback: Any) -> str:
    prefixes = {
        "blank_required": f"字段“{field}”为空",
        "invalid_number": f"字段“{field}”历史数值无效",
        "invalid_due_date": f"字段“{field}”历史日期无效",
        "legacy_external_days_defaulted": f"字段“{field}”历史外协周期无效",
        "freeze_seed_unavailable": f"字段“{field}”历史冻结窗口配置无效",
        "bad_time_row_skipped": f"字段“{field}”历史时间值无效",
    }
    prefix = prefixes.get(code, f"字段“{field}”历史值无效")
    return f"{prefix}，已按兼容读取回退为 {_format_fallback_value(fallback)}。"


def _emit_event(
    collector: DegradationCollector,
    *,
    policy: FieldPolicy,
    scope: str,
    raw_value: Any,
    fallback: Any,
) -> None:
    code = _reason_code_for_failure(policy, raw_value=raw_value)
    collector.add(
        code=code,
        scope=scope,
        field=policy.field,
        message=_compat_message(code, field=policy.field, fallback=fallback),
        sample=repr(raw_value),
    )


def _float_fallback(value: Any, *, field: str, min_value: Optional[float], min_inclusive: bool = True) -> Optional[float]:
    if value is None:
        return None
    parsed = parse_required_float(value, field=field, min_value=min_value, min_inclusive=min_inclusive)
    return float(parsed)


def _int_fallback(value: Any, *, field: str, min_value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    parsed = parse_required_int(value, field=field, min_value=min_value)
    return int(parsed)


def _date_fallback(value: Any, *, field: str) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return parse_required_date(value, field=field)


def parse_compat_float(
    value: Any,
    *,
    field: str,
    scope: str,
    collector: DegradationCollector,
    fallback: Any = _FALLBACK_UNSET,
    min_value: Optional[float] = None,
    min_inclusive: bool = True,
) -> Optional[float]:
    policy = _resolve_compat_policy(field, expected_kind=VALUE_FLOAT)
    parser = parse_optional_float if policy.write_mode == WRITE_OPTIONAL else parse_required_float
    try:
        return parser(value, field=field, min_value=min_value, min_inclusive=min_inclusive)
    except ValidationError:
        compat_value = _float_fallback(
            _resolve_fallback(policy, fallback), field=field, min_value=min_value, min_inclusive=min_inclusive
        )
        _emit_event(collector, policy=policy, scope=scope, raw_value=value, fallback=compat_value)
        return compat_value


def parse_compat_int(
    value: Any,
    *,
    field: str,
    scope: str,
    collector: DegradationCollector,
    fallback: Any = _FALLBACK_UNSET,
    min_value: Optional[int] = None,
) -> Optional[int]:
    policy = _resolve_compat_policy(field, expected_kind=VALUE_INT)
    parser = parse_optional_int if policy.write_mode == WRITE_OPTIONAL else parse_required_int
    try:
        return parser(value, field=field, min_value=min_value)
    except ValidationError:
        compat_value = _int_fallback(_resolve_fallback(policy, fallback), field=field, min_value=min_value)
        _emit_event(collector, policy=policy, scope=scope, raw_value=value, fallback=compat_value)
        return compat_value


def parse_compat_date(
    value: Any,
    *,
    field: str,
    scope: str,
    collector: DegradationCollector,
    fallback: Any = _FALLBACK_UNSET,
) -> Optional[date]:
    policy = _resolve_compat_policy(field, expected_kind=VALUE_DATE)
    parser = parse_optional_date if policy.write_mode == WRITE_OPTIONAL else parse_required_date
    try:
        return parser(value, field=field)
    except ValidationError:
        compat_value = _date_fallback(_resolve_fallback(policy, fallback), field=field)
        _emit_event(collector, policy=policy, scope=scope, raw_value=value, fallback=compat_value)
        return compat_value
