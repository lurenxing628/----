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

    @property
    def graph_downstream_weight(self) -> int:
        """沿用旧口径：重点工序与后续影响权重都为 0 时不按后续工时加分，否则固定为 1。"""
        return 0 if self.graph_critical_weight == 0 and self.graph_impact_weight == 0 else 1

    def public_config_snapshot(self) -> Dict[str, Any]:
        return {
            "sort_strategy": self.sort_strategy,
            "dispatch_mode": self.dispatch_mode,
            "dispatch_rule": self.dispatch_rule,
            "algo_mode": self.algo_mode,
            "objective": self.objective,
            "auto_assign_enabled": self.auto_assign_enabled,
            "freeze_window_enabled": self.freeze_window_enabled,
            "time_budget_seconds": self.time_budget_seconds,
            "freeze_window_days": self.freeze_window_days,
        }


def snapshot_from_values(values):
    """Build the shared projection after field coercion."""
    return ScheduleConfigSnapshot(
        **{spec.key: values[spec.key] for spec in list_runtime_config_fields()})


__all__ = ["ScheduleConfigSnapshot", "snapshot_from_values"]
