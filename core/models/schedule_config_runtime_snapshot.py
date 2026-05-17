from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple


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
    graph_analysis_mode: str
    graph_block_on_cycle: str
    graph_critical_weight: int
    graph_impact_weight: int
    graph_debug_export: str
    auto_assign_persist: str = "yes"
    graph_analysis_mode: str = "off"
    graph_block_on_cycle: str = "no"
    graph_critical_weight: int = 500
    graph_impact_weight: int = 10
    graph_debug_export: str = "no"
    degradation_events: Tuple[Dict[str, Any], ...] = field(default_factory=tuple, repr=False)
    degradation_counters: Dict[str, int] = field(default_factory=dict, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sort_strategy": self.sort_strategy,
            "priority_weight": float(self.priority_weight),
            "due_weight": float(self.due_weight),
            "ready_weight": float(self.ready_weight),
            "holiday_default_efficiency": float(self.holiday_default_efficiency),
            "enforce_ready_default": self.enforce_ready_default,
            "prefer_primary_skill": self.prefer_primary_skill,
            "dispatch_mode": self.dispatch_mode,
            "dispatch_rule": self.dispatch_rule,
            "auto_assign_enabled": self.auto_assign_enabled,
            "auto_assign_persist": self.auto_assign_persist,
            "ortools_enabled": self.ortools_enabled,
            "ortools_time_limit_seconds": int(self.ortools_time_limit_seconds),
            "algo_mode": self.algo_mode,
            "time_budget_seconds": int(self.time_budget_seconds),
            "objective": self.objective,
            "freeze_window_enabled": self.freeze_window_enabled,
            "freeze_window_days": int(self.freeze_window_days),
            "graph_analysis_mode": self.graph_analysis_mode,
            "graph_block_on_cycle": self.graph_block_on_cycle,
            "graph_critical_weight": int(self.graph_critical_weight),
            "graph_impact_weight": int(self.graph_impact_weight),
            "graph_debug_export": self.graph_debug_export,
        }


__all__ = ["ScheduleConfigSnapshot"]
