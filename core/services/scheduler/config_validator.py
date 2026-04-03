from __future__ import annotations

from typing import Any, Dict, Tuple

from core.infrastructure.errors import ValidationError
from core.services.common.degradation import DegradationCollector, degradation_events_to_dicts
from core.services.common.field_parse import parse_field_float, parse_field_int

from .config_snapshot import ScheduleConfigSnapshot
from .number_utils import to_yes_no


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
    def _valid_norm(values: Tuple[str, ...]) -> Tuple[str, ...]:
        out = []
        seen = set()
        for item in values or ():
            text = str(item).strip().lower()
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text)
        return tuple(out)

    def _is_blank(value: Any) -> bool:
        return value is None or (isinstance(value, str) and value.strip() == "")

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
            return float(
                parse_field_float(
                    raw,
                    field=key,
                    strict_mode=True,
                    scope="config_validator.preset",
                    fallback=float(default),
                    collector=collector,
                    min_value=min_value,
                    min_inclusive=min_inclusive,
                )
            )

        parse_field_float(
            raw,
            field=key,
            strict_mode=True,
            scope="config_validator.preset",
            fallback=float(default),
            collector=collector,
        )
        return float(
            parse_field_float(
                raw,
                field=key,
                strict_mode=False,
                scope="config_validator.preset",
                fallback=float(default),
                collector=collector,
                min_value=min_value,
                min_inclusive=min_inclusive,
            )
        )

    def _get_int(key: str, default: int, *, min_v: int) -> int:
        raw = data.get(key)
        if _is_blank(raw):
            return int(default)
        if strict_mode:
            return int(
                parse_field_int(
                    raw,
                    field=key,
                    strict_mode=True,
                    scope="config_validator.preset",
                    fallback=int(default),
                    collector=collector,
                    min_value=min_v,
                )
            )

        parse_field_int(
            raw,
            field=key,
            strict_mode=True,
            scope="config_validator.preset",
            fallback=int(default),
            collector=collector,
        )
        return int(
            parse_field_int(
                raw,
                field=key,
                strict_mode=False,
                scope="config_validator.preset",
                fallback=int(default),
                collector=collector,
                min_value=min_v,
                min_violation_fallback=int(min_v),
            )
        )

    valid_strategies_norm = _valid_norm(valid_strategies)
    valid_dispatch_modes_norm = _valid_norm(valid_dispatch_modes)
    valid_dispatch_rules_norm = _valid_norm(valid_dispatch_rules)
    valid_algo_modes_norm = _valid_norm(valid_algo_modes)
    valid_objectives_norm = _valid_norm(valid_objectives)

    st = str(data.get("sort_strategy") or base.sort_strategy).strip().lower()
    base_strategy = str(base.sort_strategy).strip().lower()
    if st not in valid_strategies_norm:
        if strict_mode and not _is_blank(data.get("sort_strategy")):
            raise ValidationError(f"“sort_strategy”取值不合法：{data.get('sort_strategy')!r}", field="sort_strategy")
        st = base_strategy

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

    def _yesno(v: Any, key: str, default: str = "no", *, strict: bool = False) -> str:
        text = "" if v is None else str(v).strip().lower()
        true_vals = {"yes", "y", "true", "1", "on"}
        false_vals = {"no", "n", "false", "0", "off", ""}
        if strict and text not in true_vals and text not in false_vals:
            raise ValidationError(f"“{key}”取值不合法：{v!r}（允许值：yes / no）", field=key)
        return to_yes_no(v, default=default)

    enforce_ready_default = _yesno(
        data.get("enforce_ready_default"),
        "enforce_ready_default",
        default=str(base.enforce_ready_default),
        strict=bool(strict_mode),
    )
    prefer_primary_skill = _yesno(
        data.get("prefer_primary_skill"),
        "prefer_primary_skill",
        default=str(base.prefer_primary_skill),
        strict=bool(strict_mode),
    )
    auto_assign_enabled = _yesno(
        data.get("auto_assign_enabled"),
        "auto_assign_enabled",
        default=str(base.auto_assign_enabled),
        strict=bool(strict_mode),
    )
    ortools_enabled = _yesno(
        data.get("ortools_enabled"),
        "ortools_enabled",
        default=str(base.ortools_enabled),
        strict=bool(strict_mode),
    )
    freeze_window_enabled = _yesno(
        data.get("freeze_window_enabled"),
        "freeze_window_enabled",
        default=str(base.freeze_window_enabled),
        strict=bool(strict_mode),
    )

    raw_dispatch_mode = data.get("dispatch_mode")
    dm = str(base.dispatch_mode if raw_dispatch_mode is None else raw_dispatch_mode).strip().lower()
    base_dispatch_mode = str(base.dispatch_mode).strip().lower()
    if dm == "":
        dm = base_dispatch_mode
    if dm not in valid_dispatch_modes_norm:
        if strict_mode and not _is_blank(raw_dispatch_mode):
            raise ValidationError(f"“dispatch_mode”取值不合法：{raw_dispatch_mode!r}", field="dispatch_mode")
        dm = base_dispatch_mode

    raw_dispatch_rule = data.get("dispatch_rule")
    dr = str(base.dispatch_rule if raw_dispatch_rule is None else raw_dispatch_rule).strip().lower()
    base_dispatch_rule = str(base.dispatch_rule).strip().lower()
    if dr == "":
        dr = base_dispatch_rule
    if dr not in valid_dispatch_rules_norm:
        if strict_mode and not _is_blank(raw_dispatch_rule):
            raise ValidationError(f"“dispatch_rule”取值不合法：{raw_dispatch_rule!r}", field="dispatch_rule")
        dr = base_dispatch_rule

    algo_mode = str(data.get("algo_mode") or base.algo_mode).strip().lower()
    base_algo_mode = str(base.algo_mode).strip().lower()
    if algo_mode not in valid_algo_modes_norm:
        if strict_mode and not _is_blank(data.get("algo_mode")):
            raise ValidationError(f"“algo_mode”取值不合法：{data.get('algo_mode')!r}", field="algo_mode")
        algo_mode = base_algo_mode

    objective = str(data.get("objective") or base.objective).strip().lower()
    base_objective = str(base.objective).strip().lower()
    if objective not in valid_objectives_norm:
        if strict_mode and not _is_blank(data.get("objective")):
            raise ValidationError(f"“objective”取值不合法：{data.get('objective')!r}", field="objective")
        objective = base_objective

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
