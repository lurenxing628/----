from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from core.algorithm_contracts.sort_strategies import WeightedParams
from core.models.enums import SortStrategy
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot
from core.services.scheduler.config.config_field_spec import choices_for


@dataclass(frozen=True)
class OptimizerConfig:
    strategy_enum: SortStrategy
    # 只有加权策略带权重；其余策略为 None。
    strategy_params: Optional[WeightedParams]
    algo_mode: str
    objective_name: str
    time_budget_seconds: int
    dispatch_mode: str
    dispatch_rule: str
    valid_strategies: Tuple[str, ...]
    valid_dispatch_modes: Tuple[str, ...]
    valid_dispatch_rules: Tuple[str, ...]

    def strategy_keys(self) -> List[str]:
        current_key = self.strategy_enum.value
        if self.algo_mode != "improve":
            return [current_key]
        return [current_key] + [item for item in self.valid_strategies if item != current_key]

    def dispatch_modes(self) -> List[str]:
        if self.algo_mode != "improve":
            return [self.dispatch_mode]
        return [self.dispatch_mode] + [item for item in self.valid_dispatch_modes if item != self.dispatch_mode]


def strategy_weights(strategy: SortStrategy, snapshot: ScheduleConfigSnapshot) -> Optional[WeightedParams]:
    """The weights a strategy decodes with: the configured pair for the weighted strategy, none otherwise."""
    if strategy != SortStrategy.WEIGHTED:
        return None
    return WeightedParams(snapshot.priority_weight, snapshot.due_weight)


def resolve_optimizer_config(snapshot: ScheduleConfigSnapshot) -> OptimizerConfig:
    valid_strategies = choices_for("sort_strategy")
    valid_dispatch_modes = choices_for("dispatch_mode")
    valid_dispatch_rules = choices_for("dispatch_rule")

    return OptimizerConfig(
        strategy_enum=snapshot.sort_strategy,
        strategy_params=strategy_weights(snapshot.sort_strategy, snapshot),
        algo_mode=snapshot.algo_mode,
        objective_name=snapshot.objective,
        time_budget_seconds=snapshot.time_budget_seconds,
        dispatch_mode=snapshot.dispatch_mode,
        dispatch_rule=snapshot.dispatch_rule,
        valid_strategies=valid_strategies,
        valid_dispatch_modes=valid_dispatch_modes,
        valid_dispatch_rules=valid_dispatch_rules,
    )
