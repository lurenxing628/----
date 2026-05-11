from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from core.infrastructure.errors import ValidationError
from core.shared.degradation import DegradationCollector
from core.shared.field_labels import display_field_label
from core.shared.strict_parse import (
    is_blank_input,
    parse_optional_date,
    parse_optional_float,
    parse_optional_int,
    parse_required_date,
    parse_required_float,
    parse_required_int,
)
from core.shared.value_policies import (
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


def _unit_for_field(field: str) -> str:
    if field in {"default_days", "ext_days", "ext_group_total_days"}:
        return " 天"
    if field in {"setup_hours", "unit_hours"}:
        return " 小时"
    if field in {"ortools_time_limit_seconds", "time_budget_seconds"}:
        return " 秒"
    return ""


def _format_fallback_with_unit(field: str, fallback: Any) -> str:
    return f"{_format_fallback_value(fallback)}{_unit_for_field(field)}"


def _compat_message(code: str, *, field: str, field_label: str, fallback: Any) -> str:
    fallback_text = _format_fallback_value(fallback)
    label = str(field_label or "").strip() or display_field_label(field, fallback="这项内容")
    if field in {"setup_hours", "unit_hours"}:
        return f"{label}没有填或填得不对，本次先按 {_format_fallback_with_unit(field, fallback)} 继续排，请到批次工序或零件工序工时里补正。"
    if field in {"ext_days", "default_days", "ext_group_total_days"}:
        return f"{label}没有填或填得不对，本次先按 {_format_fallback_with_unit(field, fallback)} 继续排，请到批次工序或供应商/工艺资料里补正。"
    if field in {
        "priority_weight",
        "due_weight",
        "ready_weight",
        "holiday_default_efficiency",
        "freeze_window_days",
        "ortools_time_limit_seconds",
        "time_budget_seconds",
    }:
        return f"{label}填得不对，本次先按默认值 {_format_fallback_with_unit(field, fallback)} 继续，请到高级设置里重新保存。"
    prefixes = {
        "blank_required": f"{label}为空",
        "invalid_number": f"{label}数值无效",
        "invalid_due_date": f"{label}日期无效",
        "legacy_external_days_defaulted": f"{label}无效",
        "freeze_seed_unavailable": f"{label}配置无效",
        "bad_time_row_skipped": f"{label}时间值无效",
    }
    prefix = prefixes.get(code, f"{label}历史值无效")
    if code == "legacy_external_days_defaulted":
        return f"{prefix}，本次先按 {_format_fallback_with_unit(field, fallback)} 计算，请补上真实周期。"
    if fallback is None:
        return f"{prefix}，本次先留空，请检查后保存。"
    return f"{prefix}，本次先按 {fallback_text} 处理，请检查后保存。"


def _emit_event(
    collector: DegradationCollector,
    *,
    policy: FieldPolicy,
    scope: str,
    raw_value: Any,
    fallback: Any,
    field_label: Optional[str] = None,
) -> None:
    code = _reason_code_for_failure(policy, raw_value=raw_value)
    label = display_field_label(policy.field, fallback="这项内容") if field_label is None else str(field_label or "这项内容")
    collector.add(
        code=code,
        scope=scope,
        field=policy.field,
        message=_compat_message(code, field=policy.field, field_label=label, fallback=fallback),
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
    field_label: Optional[str] = None,
) -> Optional[float]:
    policy = _resolve_compat_policy(field, expected_kind=VALUE_FLOAT)
    parser = parse_optional_float if policy.write_mode == WRITE_OPTIONAL else parse_required_float
    label = display_field_label(field, fallback="这项内容") if field_label is None else str(field_label or "这项内容")
    try:
        return parser(value, field=label, min_value=min_value, min_inclusive=min_inclusive)
    except ValidationError:
        compat_value = _float_fallback(
            _resolve_fallback(policy, fallback), field=label, min_value=min_value, min_inclusive=min_inclusive
        )
        _emit_event(collector, policy=policy, scope=scope, raw_value=value, fallback=compat_value, field_label=label)
        return compat_value


def parse_compat_int(
    value: Any,
    *,
    field: str,
    scope: str,
    collector: DegradationCollector,
    fallback: Any = _FALLBACK_UNSET,
    min_value: Optional[int] = None,
    field_label: Optional[str] = None,
) -> Optional[int]:
    policy = _resolve_compat_policy(field, expected_kind=VALUE_INT)
    parser = parse_optional_int if policy.write_mode == WRITE_OPTIONAL else parse_required_int
    label = display_field_label(field, fallback="这项内容") if field_label is None else str(field_label or "这项内容")
    try:
        return parser(value, field=label, min_value=min_value)
    except ValidationError:
        compat_value = _int_fallback(_resolve_fallback(policy, fallback), field=label, min_value=min_value)
        _emit_event(collector, policy=policy, scope=scope, raw_value=value, fallback=compat_value, field_label=label)
        return compat_value


def parse_compat_date(
    value: Any,
    *,
    field: str,
    scope: str,
    collector: DegradationCollector,
    fallback: Any = _FALLBACK_UNSET,
    field_label: Optional[str] = None,
) -> Optional[date]:
    policy = _resolve_compat_policy(field, expected_kind=VALUE_DATE)
    parser = parse_optional_date if policy.write_mode == WRITE_OPTIONAL else parse_required_date
    label = display_field_label(field, fallback="这项内容") if field_label is None else str(field_label or "这项内容")
    try:
        return parser(value, field=label)
    except ValidationError:
        compat_value = _date_fallback(_resolve_fallback(policy, fallback), field=label)
        _emit_event(collector, policy=policy, scope=scope, raw_value=value, fallback=compat_value, field_label=label)
        return compat_value
