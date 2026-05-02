from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.infrastructure.errors import ValidationError
from core.shared.boolean_normalize import normalize_yes_no_wide
from core.shared.degradation import DegradationCollector, degradation_events_to_dicts
from core.shared.field_parse import parse_field_float, parse_field_int

from .schedule_config_runtime_fields import (
    MISSING_POLICY_ERROR,
    MISSING_POLICY_FALLBACK_WITH_DEGRADATION,
    default_snapshot_values,
    get_field_spec,
    list_runtime_config_fields,
)
from .schedule_config_runtime_read import (
    merge_degradation_counters,
    read_runtime_cfg_raw_value,
    seed_snapshot_degradation_collector,
)
from .schedule_config_runtime_snapshot import ScheduleConfigSnapshot
from .schedule_config_runtime_weights import normalize_weight_triplet


def _format_choice_allow_text(valid_values: Tuple[str, ...]) -> str:
    return " / ".join(valid_values) if valid_values else "<empty>"


def _normalize_valid_texts(values: Tuple[str, ...]) -> Tuple[str, ...]:
    out = []
    seen = set()
    for item in values or ():
        text = str(item).strip().lower()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return tuple(out)


def _handle_missing_value(
    collector: DegradationCollector,
    *,
    field_name: str,
    fallback: Any,
    scope: str,
    missing_policy: str,
) -> Any:
    policy = str(missing_policy or MISSING_POLICY_FALLBACK_WITH_DEGRADATION).strip().lower()
    if policy == MISSING_POLICY_ERROR:
        raise ValidationError(f"缺少“{field_name}”配置", field=field_name)
    collector.add(
        code="missing_required",
        scope=scope,
        field=field_name,
        message=f"缺少“{field_name}”配置，本次先按默认值 {fallback} 处理。",
        sample=None,
    )
    return fallback


def _record_blank_choice_degradation(
    collector: DegradationCollector,
    *,
    scope: str,
    field_name: str,
    raw_value: Any,
    fallback: str,
) -> None:
    collector.add(
        code="blank_required",
        scope=scope,
        field=field_name,
        message=f"“{field_name}”没有填写，本次先按默认值 {fallback} 处理。",
        sample=None,
    )


def _record_invalid_choice_degradation(
    collector: DegradationCollector,
    *,
    scope: str,
    field_name: str,
    raw_value: Any,
    fallback: str,
    valid_values: Tuple[str, ...],
) -> None:
    collector.add(
        code="invalid_choice",
        scope=scope,
        field=field_name,
        message=(
            f"“{field_name}”填写不正确（当前值：{raw_value}，可选值：{_format_choice_allow_text(valid_values)}），"
            f"本次先按默认值 {fallback} 处理。"
        ),
        sample=str(raw_value or ""),
    )


def _choice_with_degradation(
    raw_value: Any,
    *,
    field_name: str,
    fallback: str,
    valid_values: Tuple[str, ...],
    strict_mode: bool,
    collector: DegradationCollector,
    scope: str,
    missing: bool,
    missing_policy: str,
) -> str:
    normalized_valid = _normalize_valid_texts(valid_values)
    fallback_text = str(fallback or "").strip().lower()
    if normalized_valid and fallback_text not in normalized_valid:
        fallback_text = normalized_valid[0]
    if missing:
        return str(
            _handle_missing_value(
                collector,
                field_name=field_name,
                fallback=fallback_text,
                scope=scope,
                missing_policy=missing_policy,
            )
        ).strip().lower()

    text = "" if raw_value is None else str(raw_value).strip().lower()
    if strict_mode and text == "":
        raise ValidationError(f"“{field_name}”不能为空", field=field_name)
    if text == "":
        _record_blank_choice_degradation(
            collector,
            scope=scope,
            field_name=field_name,
            raw_value=raw_value,
            fallback=fallback_text,
        )
        return fallback_text
    if normalized_valid and text not in normalized_valid:
        if strict_mode:
            raise ValidationError(
                f"“{field_name}”填写不正确：{raw_value}（可填写：{_format_choice_allow_text(normalized_valid)}）",
                field=field_name,
            )
        _record_invalid_choice_degradation(
            collector,
            scope=scope,
            field_name=field_name,
            raw_value=raw_value,
            fallback=fallback_text,
            valid_values=normalized_valid,
        )
        return fallback_text
    return text if normalized_valid else fallback_text


def _yes_no_with_degradation(
    raw_value: Any,
    *,
    field_name: str,
    fallback: str,
    strict_mode: bool,
    collector: DegradationCollector,
    scope: str,
    missing: bool,
    missing_policy: str,
) -> str:
    normalized_default = normalize_yes_no_wide(fallback, default=fallback, unknown_policy="no")
    if missing:
        handled = _handle_missing_value(
            collector,
            field_name=field_name,
            fallback=normalized_default,
            scope=scope,
            missing_policy=missing_policy,
        )
        return normalize_yes_no_wide(handled, default=normalized_default, unknown_policy="no")

    text = "" if raw_value is None else str(raw_value).strip().lower()
    true_vals = {"yes", "y", "true", "1", "on"}
    false_vals = {"no", "n", "false", "0", "off"}
    if strict_mode and text == "":
        raise ValidationError(f"“{field_name}”不能为空", field=field_name)
    if text == "":
        _record_blank_choice_degradation(
            collector,
            scope=scope,
            field_name=field_name,
            raw_value=raw_value,
            fallback=normalized_default,
        )
        return normalized_default
    if text not in true_vals and text not in false_vals:
        if strict_mode:
            raise ValidationError(f"“{field_name}”填写不正确：{raw_value}（请填写：是 / 否）", field=field_name)
        _record_invalid_choice_degradation(
            collector,
            scope=scope,
            field_name=field_name,
            raw_value=raw_value,
            fallback=normalized_default,
            valid_values=("yes", "no"),
        )
        return normalized_default
    return normalize_yes_no_wide(raw_value, default=normalized_default, unknown_policy="no")


def _coerce_config_field(
    key: str,
    value: Any,
    *,
    strict_mode: bool,
    source: str,
    collector: Optional[DegradationCollector] = None,
    missing: bool = False,
    fallback: Any = None,
    missing_policy: str = MISSING_POLICY_FALLBACK_WITH_DEGRADATION,
) -> Any:
    spec = get_field_spec(key)
    active_collector = collector if collector is not None else DegradationCollector()
    effective_fallback = spec.default if fallback is None else fallback

    if spec.field_type == "enum":
        return _choice_with_degradation(
            value,
            field_name=spec.key,
            fallback=str(effective_fallback or "").strip().lower(),
            valid_values=spec.choices,
            strict_mode=bool(strict_mode),
            collector=active_collector,
            scope=source,
            missing=bool(missing),
            missing_policy=missing_policy,
        )
    if spec.field_type == "yes_no":
        return _yes_no_with_degradation(
            value,
            field_name=spec.key,
            fallback=str(effective_fallback or "").strip().lower(),
            strict_mode=bool(strict_mode),
            collector=active_collector,
            scope=source,
            missing=bool(missing),
            missing_policy=missing_policy,
        )
    if missing:
        return _handle_missing_value(
            active_collector,
            field_name=spec.key,
            fallback=effective_fallback,
            scope=source,
            missing_policy=missing_policy,
        )
    if spec.field_type == "float":
        return float(
            parse_field_float(
                value,
                field=spec.key,
                strict_mode=bool(strict_mode),
                scope=source,
                fallback=float(effective_fallback),
                collector=active_collector,
                min_value=spec.min_value,
                min_inclusive=bool(spec.min_inclusive),
            )
        )
    if spec.field_type == "int":
        min_violation_fallback = int(effective_fallback)
        if spec.min_value is not None:
            min_violation_fallback = int(spec.min_value)
        return int(
            parse_field_int(
                value,
                field=spec.key,
                strict_mode=bool(strict_mode),
                scope=source,
                fallback=int(effective_fallback),
                collector=active_collector,
                min_value=(None if spec.min_value is None else int(spec.min_value)),
                min_violation_fallback=min_violation_fallback,
            )
        )
    raise TypeError(f"不支持的运行期配置字段类型：{spec.field_type!r}")


def _validate_present_runtime_cfg_fields(
    cfg: Any,
    *,
    source: str,
) -> None:
    default_map = default_snapshot_values()
    for spec in list_runtime_config_fields():
        missing, raw = read_runtime_cfg_raw_value(cfg, spec.key)
        if missing:
            continue
        _coerce_config_field(
            spec.key,
            raw,
            strict_mode=True,
            source=source,
            collector=DegradationCollector(),
            missing=False,
            fallback=default_map[spec.key],
            missing_policy=MISSING_POLICY_ERROR,
        )


def ensure_schedule_config_snapshot(
    cfg: Any,
    *,
    strict_mode: bool = False,
    source: str = "scheduler.runtime_config",
) -> ScheduleConfigSnapshot:
    if bool(strict_mode):
        _validate_present_runtime_cfg_fields(
            cfg,
            source=source,
        )
    collector = seed_snapshot_degradation_collector(cfg)
    default_map = default_snapshot_values()
    values: Dict[str, Any] = {}

    for spec in list_runtime_config_fields():
        missing, raw = read_runtime_cfg_raw_value(cfg, spec.key)
        values[spec.key] = _coerce_config_field(
            spec.key,
            raw,
            strict_mode=bool(strict_mode),
            source=source,
            collector=collector,
            missing=missing,
            fallback=default_map[spec.key],
            missing_policy=(MISSING_POLICY_ERROR if bool(strict_mode) else MISSING_POLICY_FALLBACK_WITH_DEGRADATION),
        )
    if bool(strict_mode):
        values["priority_weight"], values["due_weight"], values["ready_weight"] = normalize_weight_triplet(
            values["priority_weight"],
            values["due_weight"],
            values["ready_weight"],
            require_sum_1=True,
            priority_field="priority_weight",
            due_field="due_weight",
            ready_field="ready_weight",
        )

    return ScheduleConfigSnapshot(
        sort_strategy=str(values["sort_strategy"]),
        priority_weight=float(values["priority_weight"]),
        due_weight=float(values["due_weight"]),
        ready_weight=float(values["ready_weight"]),
        holiday_default_efficiency=float(values["holiday_default_efficiency"]),
        enforce_ready_default=str(values["enforce_ready_default"]),
        prefer_primary_skill=str(values["prefer_primary_skill"]),
        dispatch_mode=str(values["dispatch_mode"]),
        dispatch_rule=str(values["dispatch_rule"]),
        auto_assign_enabled=str(values["auto_assign_enabled"]),
        auto_assign_persist=str(values["auto_assign_persist"]),
        ortools_enabled=str(values["ortools_enabled"]),
        ortools_time_limit_seconds=int(values["ortools_time_limit_seconds"]),
        algo_mode=str(values["algo_mode"]),
        time_budget_seconds=int(values["time_budget_seconds"]),
        objective=str(values["objective"]),
        freeze_window_enabled=str(values["freeze_window_enabled"]),
        freeze_window_days=int(values["freeze_window_days"]),
        degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),
        degradation_counters=merge_degradation_counters(
            getattr(cfg, "degradation_counters", None),
            collector.to_counters(),
        ),
    )


def coerce_runtime_config_field(
    cfg: Any,
    key: str,
    *,
    strict_mode: bool,
    source: str,
    collector: Optional[DegradationCollector] = None,
    missing_policy: str = MISSING_POLICY_FALLBACK_WITH_DEGRADATION,
) -> Any:
    default_map = default_snapshot_values()
    missing, raw = read_runtime_cfg_raw_value(cfg, key)
    active_collector = collector if collector is not None else DegradationCollector()
    return _coerce_config_field(
        key,
        raw,
        strict_mode=bool(strict_mode),
        source=source,
        collector=active_collector,
        missing=missing,
        fallback=default_map[key],
        missing_policy=missing_policy,
    )


__all__ = [
    "coerce_runtime_config_field",
    "ensure_schedule_config_snapshot",
]
