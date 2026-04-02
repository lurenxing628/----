from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from core.infrastructure.errors import ValidationError

from .number_utils import parse_finite_float, parse_finite_int, to_yes_no


@dataclass
class ScheduleConfigSnapshot:
    sort_strategy: str
    priority_weight: float
    due_weight: float
    ready_weight: float
    holiday_default_efficiency: float
    enforce_ready_default: str
    prefer_primary_skill: str
    dispatch_mode: str
    dispatch_rule: str
    auto_assign_enabled: str
    ortools_enabled: str
    ortools_time_limit_seconds: int
    algo_mode: str
    time_budget_seconds: int
    objective: str
    freeze_window_enabled: str
    freeze_window_days: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sort_strategy": self.sort_strategy,
            "priority_weight": self.priority_weight,
            "due_weight": self.due_weight,
            "ready_weight": self.ready_weight,
            "holiday_default_efficiency": float(self.holiday_default_efficiency),
            "enforce_ready_default": self.enforce_ready_default,
            "prefer_primary_skill": self.prefer_primary_skill,
            "dispatch_mode": self.dispatch_mode,
            "dispatch_rule": self.dispatch_rule,
            "auto_assign_enabled": self.auto_assign_enabled,
            "ortools_enabled": self.ortools_enabled,
            "ortools_time_limit_seconds": int(self.ortools_time_limit_seconds),
            "algo_mode": self.algo_mode,
            "time_budget_seconds": int(self.time_budget_seconds),
            "objective": self.objective,
            "freeze_window_enabled": self.freeze_window_enabled,
            "freeze_window_days": int(self.freeze_window_days),
        }


def build_schedule_config_snapshot(
    repo,
    *,
    defaults: Dict[str, Any],
    valid_strategies: Tuple[str, ...],
    valid_dispatch_modes: Tuple[str, ...],
    valid_dispatch_rules: Tuple[str, ...],
    valid_algo_modes: Tuple[str, ...],
    valid_objectives: Tuple[str, ...],
    strict_mode: bool = False,
) -> ScheduleConfigSnapshot:
    def _choice(key: str, default: Any, valid: Tuple[str, ...], *, strict: bool = False) -> str:
        valid_norm = tuple(str(item).strip().lower() for item in (valid or ()) if str(item).strip())
        default_s = str(default or "").strip().lower()
        if default_s not in valid_norm and valid_norm:
            default_s = valid_norm[0]
        raw = repo.get_value(key, default=default_s)
        text = str(raw if raw is not None else default_s).strip().lower()
        if strict and text and text not in valid_norm:
            allow_text = " / ".join(valid_norm) if valid_norm else "<empty>"
            raise ValidationError(f"“{key}”取值不合法：{raw!r}（允许值：{allow_text}）", field=key)
        return text if text in valid_norm else default_s

    def _yes_no(key: str, default: str, *, strict: bool = False) -> str:
        raw = repo.get_value(key, default=str(default))
        text = "" if raw is None else str(raw).strip().lower()
        true_vals = {"yes", "y", "true", "1", "on"}
        false_vals = {"no", "n", "false", "0", "off", ""}
        if strict and text not in true_vals and text not in false_vals:
            raise ValidationError(f"“{key}”取值不合法：{raw!r}（允许值：yes / no）", field=key)
        return to_yes_no(raw, default=default)

    strategy = _choice("sort_strategy", defaults["sort_strategy"], valid_strategies)

    def _get_float(
        key: str,
        default: float,
        *,
        strict: bool = False,
        min_value: float | None = None,
        min_inclusive: bool = True,
    ) -> float:
        raw = repo.get_value(key, default=str(default))
        if strict:
            value = float(parse_finite_float(raw, field=key, allow_none=False))
            if min_value is not None:
                is_valid = value >= float(min_value) if min_inclusive else value > float(min_value)
                if not is_valid:
                    comparator = "大于等于" if min_inclusive else "大于"
                    raise ValidationError(f"“{key}”必须{comparator} {min_value}", field=key)
            return value
        try:
            if raw is None:
                return float(default)
            f = float(raw)
            if not math.isfinite(f):
                return float(default)
            value = float(f)
            if min_value is not None:
                is_valid = value >= float(min_value) if min_inclusive else value > float(min_value)
                if not is_valid:
                    return float(default)
            return value
        except Exception:
            return float(default)

    pw = _get_float("priority_weight", float(defaults["priority_weight"]), strict=bool(strict_mode), min_value=0.0)
    dw = _get_float("due_weight", float(defaults["due_weight"]), strict=bool(strict_mode), min_value=0.0)
    rw = _get_float("ready_weight", float(defaults["ready_weight"]), strict=bool(strict_mode), min_value=0.0)
    hde = _get_float(
        "holiday_default_efficiency",
        float(defaults["holiday_default_efficiency"]),
        strict=bool(strict_mode),
        min_value=0.0,
        min_inclusive=False,
    )

    raw_enforce = repo.get_value("enforce_ready_default", default=str(defaults["enforce_ready_default"]))
    enforce_ready_default = to_yes_no(raw_enforce, default=str(defaults["enforce_ready_default"]))

    raw_pref = repo.get_value("prefer_primary_skill", default="no")
    pref = to_yes_no(raw_pref, default="no")

    dm = _choice("dispatch_mode", defaults["dispatch_mode"], valid_dispatch_modes, strict=bool(strict_mode))
    dr = _choice("dispatch_rule", defaults["dispatch_rule"], valid_dispatch_rules, strict=bool(strict_mode))

    aa = _yes_no("auto_assign_enabled", str(defaults["auto_assign_enabled"]), strict=bool(strict_mode))

    ort_raw = repo.get_value("ortools_enabled", default=defaults["ortools_enabled"])
    ort = to_yes_no(ort_raw, default=defaults["ortools_enabled"])

    def _get_int(
        key: str,
        default: int,
        *,
        strict: bool = False,
        min_value: int | None = None,
    ) -> int:
        raw = repo.get_value(key, default=str(default))
        if strict:
            value = int(parse_finite_int(raw, field=key, allow_none=False))
            if min_value is not None and value < int(min_value):
                raise ValidationError(f"“{key}”必须大于等于 {min_value}", field=key)
            return value
        try:
            value = int(float(raw)) if raw is not None else int(default)
        except Exception:
            return int(default)
        if min_value is not None and value < int(min_value):
            return int(min_value)
        return int(value)

    ort_limit = _get_int(
        "ortools_time_limit_seconds",
        int(defaults["ortools_time_limit_seconds"]),
        strict=bool(strict_mode),
        min_value=1,
    )

    algo_mode = _choice("algo_mode", defaults["algo_mode"], valid_algo_modes)
    obj = _choice("objective", defaults["objective"], valid_objectives)

    time_budget = _get_int(
        "time_budget_seconds",
        int(defaults["time_budget_seconds"]),
        strict=bool(strict_mode),
        min_value=1,
    )

    fw_enabled_raw = repo.get_value("freeze_window_enabled", default=defaults["freeze_window_enabled"])
    fw_enabled = to_yes_no(fw_enabled_raw, default=defaults["freeze_window_enabled"])
    fw_days = _get_int(
        "freeze_window_days",
        int(defaults["freeze_window_days"]),
        strict=bool(strict_mode),
        min_value=0,
    )

    return ScheduleConfigSnapshot(
        sort_strategy=strategy,
        priority_weight=pw,
        due_weight=dw,
        ready_weight=rw,
        holiday_default_efficiency=float(hde),
        enforce_ready_default=enforce_ready_default,
        prefer_primary_skill=pref,
        dispatch_mode=dm,
        dispatch_rule=dr,
        auto_assign_enabled=aa,
        ortools_enabled=ort,
        ortools_time_limit_seconds=int(ort_limit),
        algo_mode=algo_mode,
        time_budget_seconds=int(time_budget),
        objective=obj,
        freeze_window_enabled=fw_enabled,
        freeze_window_days=int(fw_days),
    )

