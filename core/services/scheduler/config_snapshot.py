from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from .number_utils import to_yes_no


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
) -> ScheduleConfigSnapshot:
    def _choice(key: str, default: Any, valid: Tuple[str, ...]) -> str:
        valid_norm = tuple(str(item).strip().lower() for item in (valid or ()) if str(item).strip())
        default_s = str(default or "").strip().lower()
        if default_s not in valid_norm and valid_norm:
            default_s = valid_norm[0]
        raw = repo.get_value(key, default=default_s)
        text = str(raw if raw is not None else default_s).strip().lower()
        return text if text in valid_norm else default_s

    strategy = _choice("sort_strategy", defaults["sort_strategy"], valid_strategies)

    def _get_float(key: str, default: float) -> float:
        raw = repo.get_value(key, default=str(default))
        try:
            if raw is None:
                return float(default)
            f = float(raw)
            if not math.isfinite(f):
                return float(default)
            return float(f)
        except Exception:
            return float(default)

    pw = _get_float("priority_weight", float(defaults["priority_weight"]))
    dw = _get_float("due_weight", float(defaults["due_weight"]))
    rw = _get_float("ready_weight", float(defaults["ready_weight"]))
    hde = _get_float("holiday_default_efficiency", float(defaults["holiday_default_efficiency"]))
    if hde <= 0:
        hde = float(defaults["holiday_default_efficiency"])

    raw_enforce = repo.get_value("enforce_ready_default", default=str(defaults["enforce_ready_default"]))
    enforce_ready_default = to_yes_no(raw_enforce, default=str(defaults["enforce_ready_default"]))

    raw_pref = repo.get_value("prefer_primary_skill", default="no")
    pref = to_yes_no(raw_pref, default="no")

    dm = _choice("dispatch_mode", defaults["dispatch_mode"], valid_dispatch_modes)
    dr = _choice("dispatch_rule", defaults["dispatch_rule"], valid_dispatch_rules)

    aa_raw = repo.get_value("auto_assign_enabled", default=defaults["auto_assign_enabled"])
    aa = to_yes_no(aa_raw, default=defaults["auto_assign_enabled"])

    ort_raw = repo.get_value("ortools_enabled", default=defaults["ortools_enabled"])
    ort = to_yes_no(ort_raw, default=defaults["ortools_enabled"])

    def _get_int(key: str, default: int) -> int:
        raw = repo.get_value(key, default=str(default))
        try:
            return int(float(raw)) if raw is not None else int(default)
        except Exception:
            return int(default)

    ort_limit = _get_int("ortools_time_limit_seconds", int(defaults["ortools_time_limit_seconds"]))
    ort_limit = max(1, int(ort_limit))

    algo_mode = _choice("algo_mode", defaults["algo_mode"], valid_algo_modes)
    obj = _choice("objective", defaults["objective"], valid_objectives)

    time_budget = _get_int("time_budget_seconds", int(defaults["time_budget_seconds"]))
    time_budget = max(1, int(time_budget))

    fw_enabled_raw = repo.get_value("freeze_window_enabled", default=defaults["freeze_window_enabled"])
    fw_enabled = to_yes_no(fw_enabled_raw, default=defaults["freeze_window_enabled"])
    fw_days = _get_int("freeze_window_days", int(defaults["freeze_window_days"]))
    fw_days = max(0, int(fw_days))

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

