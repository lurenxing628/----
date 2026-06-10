from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple


# 与 services.scheduler.config.config_snapshot.ScheduleConfigSnapshot 双栈锁步；字段增删必须同步。
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
    graph_analysis_mode: str = "on"
    graph_block_on_cycle: str = "no"
    graph_critical_weight: int = 500
    graph_impact_weight: int = 10
    graph_downstream_weight: int = 1
    graph_candidate_weight_count: int = 5
    graph_selection_policy: str = "balanced"
    graph_overdue_tolerance_count: int = 1
    graph_tardiness_tolerance_ratio: float = 0.10
    graph_debug_export: str = "no"
    auto_assign_persist: str = "yes"
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
            "graph_candidate_weight_count": int(self.graph_candidate_weight_count),
            "graph_selection_policy": self.graph_selection_policy,
            "graph_overdue_tolerance_count": int(self.graph_overdue_tolerance_count),
            "graph_tardiness_tolerance_ratio": float(self.graph_tardiness_tolerance_ratio),
            "graph_debug_export": self.graph_debug_export,
        }


__all__ = ["ScheduleConfigSnapshot"]
