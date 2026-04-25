from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from core.models.objective import objective_choice_labels

MISSING_POLICY_ERROR = "error"
MISSING_POLICY_FALLBACK_WITH_DEGRADATION = "fallback_with_degradation"


@dataclass(frozen=True)
class RuntimeConfigFieldSpec:
    key: str
    field_type: str
    default: Any
    min_value: Optional[float] = None
    min_inclusive: bool = True
    choices: Tuple[str, ...] = field(default_factory=tuple)


_YES_NO_CHOICES = ("yes", "no")
_OBJECTIVE_CHOICES = tuple(objective_choice_labels().keys())

_FIELD_SPECS: Tuple[RuntimeConfigFieldSpec, ...] = (
    RuntimeConfigFieldSpec(
        key="sort_strategy",
        field_type="enum",
        default="priority_first",
        choices=("priority_first", "due_date_first", "weighted", "fifo"),
    ),
    RuntimeConfigFieldSpec(key="priority_weight", field_type="float", default=0.4, min_value=0.0),
    RuntimeConfigFieldSpec(key="due_weight", field_type="float", default=0.5, min_value=0.0),
    RuntimeConfigFieldSpec(key="ready_weight", field_type="float", default=0.1, min_value=0.0),
    RuntimeConfigFieldSpec(
        key="holiday_default_efficiency",
        field_type="float",
        default=0.8,
        min_value=0.0,
        min_inclusive=False,
    ),
    RuntimeConfigFieldSpec(
        key="enforce_ready_default",
        field_type="yes_no",
        default="no",
        choices=_YES_NO_CHOICES,
    ),
    RuntimeConfigFieldSpec(
        key="prefer_primary_skill",
        field_type="yes_no",
        default="no",
        choices=_YES_NO_CHOICES,
    ),
    RuntimeConfigFieldSpec(
        key="dispatch_mode",
        field_type="enum",
        default="batch_order",
        choices=("batch_order", "sgs"),
    ),
    RuntimeConfigFieldSpec(
        key="dispatch_rule",
        field_type="enum",
        default="slack",
        choices=("slack", "cr", "atc"),
    ),
    RuntimeConfigFieldSpec(
        key="auto_assign_enabled",
        field_type="yes_no",
        default="no",
        choices=_YES_NO_CHOICES,
    ),
    RuntimeConfigFieldSpec(
        key="auto_assign_persist",
        field_type="yes_no",
        default="yes",
        choices=_YES_NO_CHOICES,
    ),
    RuntimeConfigFieldSpec(
        key="ortools_enabled",
        field_type="yes_no",
        default="no",
        choices=_YES_NO_CHOICES,
    ),
    RuntimeConfigFieldSpec(key="ortools_time_limit_seconds", field_type="int", default=5, min_value=1),
    RuntimeConfigFieldSpec(
        key="algo_mode",
        field_type="enum",
        default="greedy",
        choices=("greedy", "improve"),
    ),
    RuntimeConfigFieldSpec(key="time_budget_seconds", field_type="int", default=20, min_value=1),
    RuntimeConfigFieldSpec(
        key="objective",
        field_type="enum",
        default="min_overdue",
        choices=_OBJECTIVE_CHOICES,
    ),
    RuntimeConfigFieldSpec(
        key="freeze_window_enabled",
        field_type="yes_no",
        default="no",
        choices=_YES_NO_CHOICES,
    ),
    RuntimeConfigFieldSpec(key="freeze_window_days", field_type="int", default=0, min_value=0),
)
_FIELD_SPEC_BY_KEY: Dict[str, RuntimeConfigFieldSpec] = {spec.key: spec for spec in _FIELD_SPECS}


def list_runtime_config_fields() -> Tuple[RuntimeConfigFieldSpec, ...]:
    return tuple(_FIELD_SPECS)


def get_field_spec(key: str) -> RuntimeConfigFieldSpec:
    normalized_key = str(key or "").strip()
    if normalized_key not in _FIELD_SPEC_BY_KEY:
        raise KeyError(f"未定义运行期配置字段：{key!r}")
    return _FIELD_SPEC_BY_KEY[normalized_key]


def default_for(key: str) -> Any:
    return get_field_spec(key).default


def default_snapshot_values() -> Dict[str, Any]:
    return {spec.key: spec.default for spec in list_runtime_config_fields()}


__all__ = [
    "MISSING_POLICY_ERROR",
    "MISSING_POLICY_FALLBACK_WITH_DEGRADATION",
    "RuntimeConfigFieldSpec",
    "default_for",
    "default_snapshot_values",
    "get_field_spec",
    "list_runtime_config_fields",
]
