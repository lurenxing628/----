from __future__ import annotations

from typing import Any, Dict, Tuple

from core.infrastructure.errors import ValidationError
from core.services.common.degradation import DegradationCollector, degradation_events_to_dicts
from core.services.common.strict_parse import parse_required_float, parse_required_int

from .config_snapshot import (
    ScheduleConfigSnapshot,
    _choice_with_degradation,
    _normalize_valid_texts,
    _yes_no_with_degradation,
)


def normalize_preset_snapshot(
    data: Dict[str, Any],
    *,
    base: ScheduleConfigSnapshot,
    valid_strategies: Tuple[str, ...],
    valid_dispatch_modes: Tuple[str, ...],
    valid_dispatch_rules: Tuple[str, ...],
    valid_algo_modes: Tuple[str, ...],
    valid_objectives: Tuple[str, ...],
    strict_mode: bool = False,
) -> ScheduleConfigSnapshot:
    def _is_blank(value: Any) -> bool:
        return value is None or (isinstance(value, str) and value.strip() == "")

    def _format_fallback_value(value: Any) -> str:
        return "空值" if value is None else str(value)

    def _record_min_violation(
        *,
        key: str,
        raw: Any,
        fallback: Any,
        min_value: Any,
        min_inclusive: bool = True,
    ) -> None:
        compare_text = "大于等于" if bool(min_inclusive) else "大于"
        collector.add(
            code="number_below_minimum",
            scope="config_validator.preset",
            field=key,
            message=f"字段“{key}”数值低于最小值约束（要求{compare_text} {min_value}），已按兼容读取回退为 {_format_fallback_value(fallback)}。",
            sample=repr(raw),
        )

    collector = DegradationCollector()

    def _get_float(
        key: str,
        default: float,
        *,
        min_value: float | None = None,
        min_inclusive: bool = True,
    ) -> float:
        raw = data.get(key)
        if _is_blank(raw):
            return float(default)

        if strict_mode:
            return float(parse_required_float(raw, field=key, min_value=min_value, min_inclusive=min_inclusive))

        parsed = float(parse_required_float(raw, field=key))
        if min_value is not None:
            is_valid = parsed >= float(min_value) if bool(min_inclusive) else parsed > float(min_value)
            if not is_valid:
                fallback_value = float(default)
                _record_min_violation(
                    key=key,
                    raw=raw,
                    fallback=fallback_value,
                    min_value=min_value,
                    min_inclusive=min_inclusive,
                )
                return fallback_value
        return float(parsed)

    def _get_int(key: str, default: int, *, min_v: int) -> int:
        raw = data.get(key)
        if _is_blank(raw):
            return int(default)
        if strict_mode:
            return int(parse_required_int(raw, field=key, min_value=min_v))

        parsed = int(parse_required_int(raw, field=key))
        if parsed < int(min_v):
            fallback_value = int(min_v)
            _record_min_violation(key=key, raw=raw, fallback=fallback_value, min_value=min_v)
            return fallback_value
        return int(parsed)

    valid_strategies_norm = _normalize_valid_texts(valid_strategies)
    valid_dispatch_modes_norm = _normalize_valid_texts(valid_dispatch_modes)
    valid_dispatch_rules_norm = _normalize_valid_texts(valid_dispatch_rules)
    valid_algo_modes_norm = _normalize_valid_texts(valid_algo_modes)
    valid_objectives_norm = _normalize_valid_texts(valid_objectives)

    raw_sort_strategy = data.get("sort_strategy")
    sort_strategy_present = "sort_strategy" in data
    base_strategy = str(base.sort_strategy).strip().lower()
    st = _choice_with_degradation(
        raw_sort_strategy,
        field="sort_strategy",
        fallback=base_strategy,
        valid_values=valid_strategies_norm,
        strict_mode=bool(strict_mode),
        collector=collector,
        scope="config_validator.preset",
        missing=not sort_strategy_present,
    )

    pw = _get_float("priority_weight", float(base.priority_weight), min_value=0.0)
    dw = _get_float("due_weight", float(base.due_weight), min_value=0.0)
    if pw < 0 or dw < 0:
        raise ValidationError("权重不能为负数", field="权重")
    percent_mode = (pw > 1.0) or (dw > 1.0)
    if percent_mode:
        if (0 < pw < 1) or (0 < dw < 1):
            raise ValidationError("权重输入疑似混用小数与百分比，请统一使用 0~1 或 0~100（%）。", field="权重")
        if pw > 100.0 or dw > 100.0:
            raise ValidationError("权重范围不合理（期望 0~1 或 0~100%）", field="权重")
        pw = pw / 100.0
        dw = dw / 100.0
    if pw > 1.0 or dw > 1.0:
        raise ValidationError("权重范围不合理（期望 0~1 或 0~100%）", field="权重")
    rw = 1.0 - float(pw) - float(dw)
    if rw < -1e-9:
        raise ValidationError("优先级权重 + 交期权重 之和不能超过 1（或 100%）。", field="权重")
    rw = max(0.0, float(rw))

    hde = _get_float(
        "holiday_default_efficiency",
        float(base.holiday_default_efficiency),
        min_value=0.0,
        min_inclusive=False,
    )

    def _yesno(v: Any, key: str, default: str = "no", *, strict: bool = False, missing: bool = False) -> str:
        return _yes_no_with_degradation(
            v,
            field=key,
            fallback=default,
            strict_mode=bool(strict),
            collector=collector,
            scope="config_validator.preset",
            missing=missing,
        )

    enforce_ready_default = _yesno(
        data.get("enforce_ready_default"),
        "enforce_ready_default",
        default=str(base.enforce_ready_default),
        strict=bool(strict_mode),
        missing="enforce_ready_default" not in data,
    )
    prefer_primary_skill = _yesno(
        data.get("prefer_primary_skill"),
        "prefer_primary_skill",
        default=str(base.prefer_primary_skill),
        strict=bool(strict_mode),
        missing="prefer_primary_skill" not in data,
    )
    auto_assign_enabled = _yesno(
        data.get("auto_assign_enabled"),
        "auto_assign_enabled",
        default=str(base.auto_assign_enabled),
        strict=bool(strict_mode),
        missing="auto_assign_enabled" not in data,
    )
    ortools_enabled = _yesno(
        data.get("ortools_enabled"),
        "ortools_enabled",
        default=str(base.ortools_enabled),
        strict=bool(strict_mode),
        missing="ortools_enabled" not in data,
    )
    freeze_window_enabled = _yesno(
        data.get("freeze_window_enabled"),
        "freeze_window_enabled",
        default=str(base.freeze_window_enabled),
        strict=bool(strict_mode),
        missing="freeze_window_enabled" not in data,
    )

    raw_dispatch_mode = data.get("dispatch_mode")
    dispatch_mode_present = "dispatch_mode" in data
    base_dispatch_mode = str(base.dispatch_mode).strip().lower()
    dm = _choice_with_degradation(
        raw_dispatch_mode,
        field="dispatch_mode",
        fallback=base_dispatch_mode,
        valid_values=valid_dispatch_modes_norm,
        strict_mode=bool(strict_mode),
        collector=collector,
        scope="config_validator.preset",
        missing=not dispatch_mode_present,
    )

    raw_dispatch_rule = data.get("dispatch_rule")
    dispatch_rule_present = "dispatch_rule" in data
    base_dispatch_rule = str(base.dispatch_rule).strip().lower()
    dr = _choice_with_degradation(
        raw_dispatch_rule,
        field="dispatch_rule",
        fallback=base_dispatch_rule,
        valid_values=valid_dispatch_rules_norm,
        strict_mode=bool(strict_mode),
        collector=collector,
        scope="config_validator.preset",
        missing=not dispatch_rule_present,
    )

    raw_algo_mode = data.get("algo_mode")
    algo_mode_present = "algo_mode" in data
    base_algo_mode = str(base.algo_mode).strip().lower()
    algo_mode = _choice_with_degradation(
        raw_algo_mode,
        field="algo_mode",
        fallback=base_algo_mode,
        valid_values=valid_algo_modes_norm,
        strict_mode=bool(strict_mode),
        collector=collector,
        scope="config_validator.preset",
        missing=not algo_mode_present,
    )

    raw_objective = data.get("objective")
    objective_present = "objective" in data
    base_objective = str(base.objective).strip().lower()
    objective = _choice_with_degradation(
        raw_objective,
        field="objective",
        fallback=base_objective,
        valid_values=valid_objectives_norm,
        strict_mode=bool(strict_mode),
        collector=collector,
        scope="config_validator.preset",
        missing=not objective_present,
    )

    ort_limit = _get_int("ortools_time_limit_seconds", int(base.ortools_time_limit_seconds), min_v=1)
    time_budget = _get_int("time_budget_seconds", int(base.time_budget_seconds), min_v=1)
    fw_days = _get_int("freeze_window_days", int(base.freeze_window_days), min_v=0)

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
