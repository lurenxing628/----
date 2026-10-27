from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .schedule_config_runtime_fields import list_runtime_config_fields


# 页面服务与算法共同使用的配置值对象。
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
    graph_debug_export: str = "no"
    auto_assign_persist: str = "yes"

    @property
    def graph_downstream_weight(self) -> int:
        """沿用旧口径：重点工序与后续影响权重都为 0 时不按后续工时加分，否则固定为 1。"""
        return 0 if self.graph_critical_weight == 0 and self.graph_impact_weight == 0 else 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sort_strategy": self.sort_strategy,
            "priority_weight": self.priority_weight,
            "due_weight": self.due_weight,
            "ready_weight": self.ready_weight,
            "holiday_default_efficiency": self.holiday_default_efficiency,
            "enforce_ready_default": self.enforce_ready_default,
            "prefer_primary_skill": self.prefer_primary_skill,
            "dispatch_mode": self.dispatch_mode,
            "dispatch_rule": self.dispatch_rule,
            "auto_assign_enabled": self.auto_assign_enabled,
            "auto_assign_persist": self.auto_assign_persist,
            "ortools_enabled": self.ortools_enabled,
            "ortools_time_limit_seconds": self.ortools_time_limit_seconds,
            "algo_mode": self.algo_mode,
            "time_budget_seconds": self.time_budget_seconds,
            "objective": self.objective,
            "freeze_window_enabled": self.freeze_window_enabled,
            "freeze_window_days": self.freeze_window_days,
            "graph_analysis_mode": self.graph_analysis_mode,
            "graph_block_on_cycle": self.graph_block_on_cycle,
            "graph_critical_weight": self.graph_critical_weight,
            "graph_impact_weight": self.graph_impact_weight,
            "graph_debug_export": self.graph_debug_export,
        }


def snapshot_from_values(values):
    """Build the shared projection after field coercion."""
    return ScheduleConfigSnapshot(
        **{spec.key: values[spec.key] for spec in list_runtime_config_fields()})


__all__ = ["ScheduleConfigSnapshot", "snapshot_from_values"]
