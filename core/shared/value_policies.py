from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

WRITE_REQUIRED = "write_required"
WRITE_OPTIONAL = "write_optional"
WRITE_NOT_APPLICABLE = "write_not_applicable"
WRITE_INTERNAL_ONLY = "write_internal_only"

READ_COMPAT = "read_compat"
READ_FILTER_ONLY = "read_filter_only"

VALUE_FLOAT = "float"
VALUE_INT = "int"
VALUE_DATE = "date"
VALUE_DATETIME = "datetime"

_COMPAT_DEFAULT_UNSET = object()


@dataclass(frozen=True)
class FieldPolicy:
    field: str
    write_mode: str
    read_mode: str
    value_kind: str
    strict_reason_code: str
    compat_reason_code: Optional[str] = None
    blank_reason_code: Optional[str] = None
    compat_default: Any = _COMPAT_DEFAULT_UNSET
    notes: Optional[str] = None

    @property
    def allows_compat_read(self) -> bool:
        return self.read_mode == READ_COMPAT

    @property
    def has_compat_default(self) -> bool:
        return self.compat_default is not _COMPAT_DEFAULT_UNSET


_FIELD_POLICIES = (
    FieldPolicy(
        field="default_days",
        write_mode=WRITE_REQUIRED,
        read_mode=READ_COMPAT,
        value_kind=VALUE_FLOAT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
        compat_default=1.0,
        notes="供应商默认周期：写入必填；历史读取允许按 1.0 天兼容回退。",
    ),
    FieldPolicy(
        field="ext_days",
        write_mode=WRITE_REQUIRED,
        read_mode=READ_COMPAT,
        value_kind=VALUE_FLOAT,
        strict_reason_code="invalid_number",
        compat_reason_code="legacy_external_days_defaulted",
        blank_reason_code="blank_required",
        compat_default=1.0,
        notes="外协工序周期：仅历史读取链允许回退；兼容回退必须留痕。",
    ),
    FieldPolicy(
        field="setup_hours",
        write_mode=WRITE_REQUIRED,
        read_mode=READ_COMPAT,
        value_kind=VALUE_FLOAT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
        compat_default=0.0,
        notes="排产输入准备工时：写入严格，历史读取允许按 0.0 兼容并产出退化事件。",
    ),
    FieldPolicy(
        field="unit_hours",
        write_mode=WRITE_REQUIRED,
        read_mode=READ_COMPAT,
        value_kind=VALUE_FLOAT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
        compat_default=0.0,
        notes="排产输入单件工时：写入严格，历史读取允许按 0.0 兼容并产出退化事件。",
    ),
    FieldPolicy(
        field="priority_weight",
        write_mode=WRITE_REQUIRED,
        read_mode=READ_COMPAT,
        value_kind=VALUE_FLOAT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
        notes="排产优先级权重：兼容读取必须由调用方显式传入运行时默认值。",
    ),
    FieldPolicy(
        field="due_weight",
        write_mode=WRITE_REQUIRED,
        read_mode=READ_COMPAT,
        value_kind=VALUE_FLOAT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
        notes="排产交期权重：兼容读取必须由调用方显式传入运行时默认值。",
    ),
    FieldPolicy(
        field="ready_weight",
        write_mode=WRITE_REQUIRED,
        read_mode=READ_COMPAT,
        value_kind=VALUE_FLOAT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
        notes="排产齐套权重：兼容读取必须由调用方显式传入运行时默认值。",
    ),
    FieldPolicy(
        field="holiday_default_efficiency",
        write_mode=WRITE_REQUIRED,
        read_mode=READ_COMPAT,
        value_kind=VALUE_FLOAT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
        notes="假期默认效率：兼容读取必须由调用方显式传入运行时默认值。",
    ),
    FieldPolicy(
        field="freeze_window_days",
        write_mode=WRITE_REQUIRED,
        read_mode=READ_COMPAT,
        value_kind=VALUE_INT,
        strict_reason_code="invalid_number",
        compat_reason_code="freeze_seed_unavailable",
        blank_reason_code="blank_required",
        compat_default=0,
        notes="冻结窗口天数：历史读取允许回退为 0，并以稳定原因码留痕。",
    ),
    FieldPolicy(
        field="ortools_time_limit_seconds",
        write_mode=WRITE_REQUIRED,
        read_mode=READ_COMPAT,
        value_kind=VALUE_INT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
        notes="自动优化计算时间：兼容读取必须由调用方显式传入运行时默认值。",
    ),
    FieldPolicy(
        field="time_budget_seconds",
        write_mode=WRITE_REQUIRED,
        read_mode=READ_COMPAT,
        value_kind=VALUE_INT,
        strict_reason_code="invalid_number",
        compat_reason_code="invalid_number",
        blank_reason_code="blank_required",
        notes="排产计算时间预算：兼容读取必须由调用方显式传入运行时默认值。",
    ),
    FieldPolicy(
        field="due_date",
        write_mode=WRITE_OPTIONAL,
        read_mode=READ_COMPAT,
        value_kind=VALUE_DATE,
        strict_reason_code="invalid_due_date",
        compat_reason_code="invalid_due_date",
        compat_default=None,
        notes="批次交期：写入允许为空，但只要提供就必须是合法日期。",
    ),
    FieldPolicy(
        field="start_time",
        write_mode=WRITE_NOT_APPLICABLE,
        read_mode=READ_FILTER_ONLY,
        value_kind=VALUE_DATETIME,
        strict_reason_code="bad_time_row_skipped",
        compat_reason_code="bad_time_row_skipped",
        compat_default=None,
        notes="展示读侧时间字段：仅允许过滤并产出跳过事件，不参与写入。",
    ),
    FieldPolicy(
        field="end_time",
        write_mode=WRITE_NOT_APPLICABLE,
        read_mode=READ_FILTER_ONLY,
        value_kind=VALUE_DATETIME,
        strict_reason_code="bad_time_row_skipped",
        compat_reason_code="bad_time_row_skipped",
        compat_default=None,
        notes="展示读侧时间字段：仅允许过滤并产出跳过事件，不参与写入。",
    ),
)

FIELD_POLICIES_BY_FIELD: Dict[str, FieldPolicy] = {policy.field: policy for policy in _FIELD_POLICIES}


def list_field_policies() -> Tuple[FieldPolicy, ...]:
    return tuple(_FIELD_POLICIES)


def has_field_policy(field: str) -> bool:
    key = str(field or "").strip()
    return key in FIELD_POLICIES_BY_FIELD


def get_field_policy(field: str) -> FieldPolicy:
    key = str(field or "").strip()
    if not key or key not in FIELD_POLICIES_BY_FIELD:
        raise KeyError(f"未定义字段策略：{field!r}")
    return FIELD_POLICIES_BY_FIELD[key]
