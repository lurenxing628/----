from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

VALUE_FLOAT = "float"
VALUE_INT = "int"


@dataclass(frozen=True)
class FieldPolicy:
    field: str
    value_kind: str
    strict_reason_code: str
    compat_reason_code: Optional[str] = None
    blank_reason_code: Optional[str] = None


_FIELD_POLICIES = (
    FieldPolicy(
        field="ext_days",
        value_kind=VALUE_FLOAT,
        strict_reason_code="invalid_number",
        compat_reason_code="legacy_external_days_defaulted",
        blank_reason_code="blank_required",
    ),
    FieldPolicy(
        field="setup_hours",
        value_kind=VALUE_FLOAT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
    ),
    FieldPolicy(
        field="unit_hours",
        value_kind=VALUE_FLOAT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
    ),
    FieldPolicy(
        field="priority_weight",
        value_kind=VALUE_FLOAT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
    ),
    FieldPolicy(
        field="due_weight",
        value_kind=VALUE_FLOAT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
    ),
    FieldPolicy(
        field="ready_weight",
        value_kind=VALUE_FLOAT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
    ),
    FieldPolicy(
        field="holiday_default_efficiency",
        value_kind=VALUE_FLOAT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
    ),
    FieldPolicy(
        field="freeze_window_days",
        value_kind=VALUE_INT,
        strict_reason_code="invalid_number",
        compat_reason_code="freeze_seed_unavailable",
        blank_reason_code="blank_required",
    ),
    FieldPolicy(
        field="ortools_time_limit_seconds",
        value_kind=VALUE_INT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
    ),
    FieldPolicy(
        field="graph_critical_weight",
        value_kind=VALUE_INT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
    ),
    FieldPolicy(
        field="graph_impact_weight",
        value_kind=VALUE_INT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
    ),
    FieldPolicy(
        field="time_budget_seconds",
        value_kind=VALUE_INT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
    ),
)

FIELD_POLICIES_BY_FIELD: Dict[str, FieldPolicy] = {policy.field: policy for policy in _FIELD_POLICIES}


def get_field_policy(field: str) -> FieldPolicy:
    key = str(field or "").strip()
    if not key or key not in FIELD_POLICIES_BY_FIELD:
        raise KeyError(f"未定义字段策略：{field!r}")
    return FIELD_POLICIES_BY_FIELD[key]
