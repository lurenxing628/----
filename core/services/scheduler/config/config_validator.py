from __future__ import annotations

from typing import Any, Dict

from core.infrastructure.errors import ValidationError
from core.shared.degradation import DegradationCollector, degradation_events_to_dicts

from .config_field_spec import MISSING_POLICY_INHERIT_LEGACY_OMISSION, coerce_config_field
from .config_snapshot import ScheduleConfigSnapshot
from .config_weight_policy import derive_ready_weight_from_priority_due, normalize_single_weight


def _emit_number_below_minimum(
    collector: DegradationCollector,
    *,
    key: str,
    raw_value: Any,
    fallback: Any,
) -> None:
    collector.add(
        code="number_below_minimum",
        scope="config_validator.preset",
        field=key,
        message=f"“{key}”数字太小，本次先按默认值 {fallback} 处理。",
        sample=str(raw_value or ""),
    )


def _preset_float(
    key: str,
    raw_value: Any,
    *,
    missing: bool,
    fallback: float,
    strict_mode: bool,
    collector: DegradationCollector,
) -> float:
    return float(
        coerce_config_field(
            key,
            raw_value,
            strict_mode=bool(strict_mode),
            source="config_validator.preset",
            collector=collector,
            missing=missing,
            fallback=float(fallback),
            missing_policy=MISSING_POLICY_INHERIT_LEGACY_OMISSION,
        )
    )


def _preset_int(
    key: str,
    raw_value: Any,
    *,
    missing: bool,
    fallback: int,
    strict_mode: bool,
    collector: DegradationCollector,
) -> int:
    return int(
        coerce_config_field(
            key,
            raw_value,
            strict_mode=bool(strict_mode),
            source="config_validator.preset",
            collector=collector,
            missing=missing,
            fallback=int(fallback),
            missing_policy=MISSING_POLICY_INHERIT_LEGACY_OMISSION,
        )
    )


def normalize_preset_snapshot(
    data: Dict[str, Any],
    *,
    base: ScheduleConfigSnapshot,
    strict_mode: bool = False,
) -> ScheduleConfigSnapshot:
    payload = dict(data or {})
    collector = DegradationCollector()

    def _read(key: str) -> tuple[bool, Any]:
        return (key not in payload), payload.get(key)

    st_missing, st_raw = _read("sort_strategy")
    st = coerce_config_field(
        "sort_strategy",
        st_raw,
        strict_mode=bool(strict_mode),
        source="config_validator.preset",
        collector=collector,
        missing=st_missing,
        fallback=base.sort_strategy,
        missing_policy=MISSING_POLICY_INHERIT_LEGACY_OMISSION,
    )

    pw_missing, pw_raw = _read("priority_weight")
    dw_missing, dw_raw = _read("due_weight")
    pw = _preset_float(
        "priority_weight",
        pw_raw,
        strict_mode=bool(strict_mode),
        collector=collector,
        missing=pw_missing,
        fallback=float(base.priority_weight),
    )
    dw = _preset_float(
        "due_weight",
        dw_raw,
        strict_mode=bool(strict_mode),
        collector=collector,
        missing=dw_missing,
        fallback=float(base.due_weight),
    )
    rw_missing, rw_raw = _read("ready_weight")
    rw = _preset_float(
        "ready_weight",
        rw_raw,
        strict_mode=bool(strict_mode),
        collector=collector,
        missing=rw_missing,
        fallback=float(base.ready_weight),
    )
    derived_pw, derived_dw, derived_rw = derive_ready_weight_from_priority_due(
        pw,
        dw,
        priority_field="priority_weight",
        due_field="due_weight",
    )
    if strict_mode:
        explicit_ready_weight = normalize_single_weight(rw, field="ready_weight")
        if abs(float(explicit_ready_weight) - float(derived_rw)) > 1e-6:
            raise ValidationError("齐套权重应与优先级权重、交期权重的派生值一致。", field="权重")
    pw = derived_pw
    dw = derived_dw
    rw = derived_rw

    hde_missing, hde_raw = _read("holiday_default_efficiency")
    hde = _preset_float(
        "holiday_default_efficiency",
        hde_raw,
        strict_mode=bool(strict_mode),
        collector=collector,
        missing=hde_missing,
        fallback=float(base.holiday_default_efficiency),
    )

    def _yes_no(key: str, fallback: str) -> str:
        missing, raw = _read(key)
        return str(
            coerce_config_field(
                key,
                raw,
                strict_mode=bool(strict_mode),
                source="config_validator.preset",
                collector=collector,
                missing=missing,
                fallback=fallback,
                missing_policy=MISSING_POLICY_INHERIT_LEGACY_OMISSION,
            )
        )

    enforce_ready_default = _yes_no("enforce_ready_default", str(base.enforce_ready_default))
    prefer_primary_skill = _yes_no("prefer_primary_skill", str(base.prefer_primary_skill))
    auto_assign_enabled = _yes_no("auto_assign_enabled", str(base.auto_assign_enabled))
    auto_assign_persist = _yes_no("auto_assign_persist", str(base.auto_assign_persist))
    ortools_enabled = _yes_no("ortools_enabled", str(base.ortools_enabled))
    freeze_window_enabled = _yes_no("freeze_window_enabled", str(base.freeze_window_enabled))

    def _choice(key: str, fallback: str) -> str:
        missing, raw = _read(key)
        return str(
            coerce_config_field(
                key,
                raw,
                strict_mode=bool(strict_mode),
                source="config_validator.preset",
                collector=collector,
                missing=missing,
                fallback=fallback,
                missing_policy=MISSING_POLICY_INHERIT_LEGACY_OMISSION,
            )
        )

    dm = _choice("dispatch_mode", str(base.dispatch_mode))
    dr = _choice("dispatch_rule", str(base.dispatch_rule))
    algo_mode = _choice("algo_mode", str(base.algo_mode))
    objective = _choice("objective", str(base.objective))

    ort_missing, ort_raw = _read("ortools_time_limit_seconds")
    ort_limit = _preset_int(
        "ortools_time_limit_seconds",
        ort_raw,
        strict_mode=bool(strict_mode),
        collector=collector,
        missing=ort_missing,
        fallback=int(base.ortools_time_limit_seconds),
    )
    budget_missing, budget_raw = _read("time_budget_seconds")
    time_budget = _preset_int(
        "time_budget_seconds",
        budget_raw,
        strict_mode=bool(strict_mode),
        collector=collector,
        missing=budget_missing,
        fallback=int(base.time_budget_seconds),
    )
    fw_missing, fw_raw = _read("freeze_window_days")
    fw_days = _preset_int(
        "freeze_window_days",
        fw_raw,
        strict_mode=bool(strict_mode),
        collector=collector,
        missing=fw_missing,
        fallback=int(base.freeze_window_days),
    )

    return ScheduleConfigSnapshot(
        sort_strategy=st,
        priority_weight=float(pw),
        due_weight=float(dw),
        ready_weight=float(rw),
        holiday_default_efficiency=float(hde),
        enforce_ready_default=enforce_ready_default,
        prefer_primary_skill=prefer_primary_skill,
        dispatch_mode=dm,
        dispatch_rule=dr,
        auto_assign_enabled=auto_assign_enabled,
        auto_assign_persist=auto_assign_persist,
        ortools_enabled=ortools_enabled,
        ortools_time_limit_seconds=int(ort_limit),
        algo_mode=algo_mode,
        time_budget_seconds=int(time_budget),
        objective=objective,
        freeze_window_enabled=freeze_window_enabled,
        freeze_window_days=int(fw_days),
        degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),
        degradation_counters=collector.to_counters(),
    )
