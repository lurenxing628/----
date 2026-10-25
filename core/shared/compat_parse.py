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


def _compat_message(*, field: str, field_label: str, fallback: Union[float, int]) -> str:
    # 字段策略表只登记了高级设置里的数值配置，回退文案统一指回高级设置。
    unit = " 秒" if field in {"ortools_time_limit_seconds", "time_budget_seconds"} else ""
    return f"{field_label}填得不对，本次先按默认值 {fallback}{unit} 继续，请到高级设置里重新保存。"


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
        message=_compat_message(field=field, field_label=label, fallback=compat_value),
        sample=repr(value),
    )
    return compat_value
