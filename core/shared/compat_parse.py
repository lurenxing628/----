from __future__ import annotations

from typing import Any, Optional, Union

from core.shared.degradation import DegradationCollector
from core.shared.field_labels import display_field_label
from core.shared.strict_parse import is_blank_input, parse_required_float, parse_required_int
from core.shared.value_policies import VALUE_FLOAT, FieldPolicy, get_field_policy


def _resolve_compat_policy(field: str, *, expected_kind: str) -> FieldPolicy:
    policy = get_field_policy(field)
    if policy.value_kind != expected_kind:
        raise ValueError(f"字段“{field}”的值类型与当前兼容解析入口不匹配：{policy.value_kind!r}")
    return policy


def _reason_code_for_failure(policy: FieldPolicy, *, raw_value: Any) -> str:
    if is_blank_input(raw_value) and policy.blank_reason_code:
        return policy.blank_reason_code
    return str(policy.compat_reason_code or policy.strict_reason_code)


def _unit_for_field(field: str) -> str:
    if field == "ext_days":
        return " 天"
    if field in {"setup_hours", "unit_hours"}:
        return " 小时"
    if field in {"ortools_time_limit_seconds", "time_budget_seconds"}:
        return " 秒"
    return ""


def _compat_message(code: str, *, field: str, field_label: str, fallback: Union[float, int]) -> str:
    fallback_text = str(fallback)
    fallback_with_unit = f"{fallback_text}{_unit_for_field(field)}"
    if field in {"setup_hours", "unit_hours"}:
        return f"{field_label}没有填或填得不对，本次先按 {fallback_with_unit} 继续排，请到批次工序或零件工序工时里补正。"
    if field == "ext_days":
        return f"{field_label}没有填或填得不对，本次先按 {fallback_with_unit} 继续排，请到批次工序或供应商/工艺资料里补正。"
    if field in {
        "priority_weight",
        "due_weight",
        "ready_weight",
        "graph_critical_weight",
        "graph_impact_weight",
        "holiday_default_efficiency",
        "freeze_window_days",
        "ortools_time_limit_seconds",
        "time_budget_seconds",
    }:
        return f"{field_label}填得不对，本次先按默认值 {fallback_with_unit} 继续，请到高级设置里重新保存。"
    prefixes = {
        "blank_required": f"{field_label}为空",
        "invalid_number": f"{field_label}数值无效",
        "freeze_seed_unavailable": f"{field_label}配置无效",
    }
    prefix = prefixes.get(code, f"{field_label}历史值无效")
    return f"{prefix}，本次先按 {fallback_text} 处理，请检查后保存。"


def recover_compat_number(
    value: Any,
    *,
    field: str,
    expected_kind: str,
    scope: str,
    collector: DegradationCollector,
    fallback: Union[float, int],
    field_label: Optional[str] = None,
) -> Union[float, int]:
    """Validate the explicit numeric fallback and record the rejected historical value."""
    policy = _resolve_compat_policy(field, expected_kind=expected_kind)
    label = display_field_label(field, fallback="这项内容") if field_label is None else str(field_label or "这项内容")
    if policy.value_kind == VALUE_FLOAT:
        compat_value = parse_required_float(fallback, field=label)
    else:
        compat_value = parse_required_int(fallback, field=label)
    code = _reason_code_for_failure(policy, raw_value=value)
    collector.add(
        code=code,
        scope=scope,
        field=field,
        message=_compat_message(code, field=field, field_label=label, fallback=compat_value),
        sample=repr(value),
    )
    return compat_value
