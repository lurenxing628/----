from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Dict, Literal, Mapping

from core.models.enums import SortStrategy, YesNo

from .schedule_config_runtime_fields import get_field_spec

# The admitted choice values of the field specs (schedule_config_runtime_fields), for the type checker.
DispatchModeName = Literal["batch_order", "sgs"]
AlgoModeName = Literal["greedy", "improve"]
ObjectiveName = Literal["min_overdue", "min_tardiness", "min_weighted_tardiness", "min_changeover"]
GraphAnalysisModeName = Literal["off", "report", "on"]

_YES_NO_FLAGS = {YesNo.YES.value: True, YesNo.NO.value: False}


def _yes_no(flag: bool) -> str:
    return YesNo.YES.value if flag else YesNo.NO.value


# 页面服务与算法共同使用的配置值对象：只放排产真用的字段，开关已是 bool。
@dataclass(frozen=True)
class ScheduleConfigSnapshot:
    sort_strategy: SortStrategy
    priority_weight: float
    due_weight: float
    dispatch_mode: DispatchModeName
    dispatch_rule: str
    auto_assign_enabled: bool
    algo_mode: AlgoModeName
    time_budget_seconds: int
    objective: ObjectiveName
    freeze_window_enabled: bool
    freeze_window_days: int
    graph_analysis_mode: GraphAnalysisModeName
    graph_block_on_cycle: bool
    graph_critical_weight: int
    graph_impact_weight: int

    @property
    def graph_downstream_weight(self) -> int:
        """沿用旧口径：重点工序与后续影响权重都为 0 时不按后续工时加分，否则固定为 1。"""
        return 0 if self.graph_critical_weight == 0 and self.graph_impact_weight == 0 else 1

    def public_config_snapshot(self) -> Dict[str, Any]:
        return {
            "sort_strategy": self.sort_strategy.value,
            "dispatch_mode": self.dispatch_mode,
            "dispatch_rule": self.dispatch_rule,
            "algo_mode": self.algo_mode,
            "objective": self.objective,
            "auto_assign_enabled": _yes_no(self.auto_assign_enabled),
            "freeze_window_enabled": _yes_no(self.freeze_window_enabled),
            "time_budget_seconds": self.time_budget_seconds,
            "freeze_window_days": self.freeze_window_days,
        }


_SNAPSHOT_FIELDS = tuple(item.name for item in fields(ScheduleConfigSnapshot))


def snapshot_from_values(values: Mapping[str, Any]) -> ScheduleConfigSnapshot:
    """The one typed projection of coerced field values: yes/no become bool, the strategy name becomes
    SortStrategy, other fields stay as admitted."""
    typed: Dict[str, Any] = {key: _typed_value(key, values[key]) for key in _SNAPSHOT_FIELDS}
    return ScheduleConfigSnapshot(**typed)


def _typed_value(key: str, value: Any) -> Any:
    if key == "sort_strategy":
        return SortStrategy(value)
    return _YES_NO_FLAGS[value] if get_field_spec(key).field_type == "yes_no" else value


__all__ = ["ScheduleConfigSnapshot", "snapshot_from_values"]
