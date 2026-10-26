from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from core.algorithm_contracts.sort_strategies import SortStrategy
from core.errors import ValidationError
from core.models.enums import YesNo
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot
from core.services.scheduler.config.config_field_spec import choices_for
from core.shared.strict_parse import parse_required_float, parse_required_int

_FIELD_LABELS = {
    "sort_strategy": "排序策略",
    "dispatch_mode": "派工方式",
    "dispatch_rule": "派工规则",
    "objective": "优化目标",
    "algo_mode": "计算模式",
    "priority_weight": "优先级权重",
    "due_weight": "交期权重",
    "time_budget_seconds": "找更好排法先试多久",
    "ortools_time_limit_seconds": "深度优化尝试时间",
}


@dataclass(frozen=True)
class OptimizerConfig:
    strategy_enum: SortStrategy
    # 只有加权策略带参数；其余策略为空字典。
    strategy_params: Dict[str, Any]
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


def field_label(field: str) -> str:
    return _FIELD_LABELS.get(str(field).strip(), str(field).strip() or "配置项")


def require_choice(value: Any, *, field: str, valid_values: Tuple[str, ...]) -> str:
    label = field_label(field)
    text = str(value).strip().lower()
    if text not in set(valid_values):
        raise ValidationError(f"“{label}”这项设置现在不能直接用，请返回排产参数页重新选择。", field=field)
    return text


def require_float(value: Any, *, field: str, min_value: float) -> float:
    label = field_label(field)
    try:
        return float(parse_required_float(value, field=label, min_value=min_value))
    except ValidationError as exc:
        raise ValidationError(exc.message, field=field) from exc


def require_int(value: Any, *, field: str, min_value: int) -> int:
    label = field_label(field)
    try:
        return int(parse_required_int(value, field=label, min_value=min_value))
    except ValidationError as exc:
        raise ValidationError(exc.message, field=field) from exc


def weighted_strategy_params(snapshot: ScheduleConfigSnapshot) -> Dict[str, Any]:
    return {
        "priority_weight": require_float(snapshot.priority_weight, field="priority_weight", min_value=0.0),
        "due_weight": require_float(snapshot.due_weight, field="due_weight", min_value=0.0),
    }


def is_ortools_enabled(snapshot: ScheduleConfigSnapshot) -> bool:
    return snapshot.ortools_enabled == YesNo.YES.value


def ortools_time_limit_seconds(snapshot: ScheduleConfigSnapshot) -> int:
    return require_int(snapshot.ortools_time_limit_seconds, field="ortools_time_limit_seconds", min_value=1)


def resolve_optimizer_config(snapshot: ScheduleConfigSnapshot) -> OptimizerConfig:
    valid_strategies = choices_for("sort_strategy")
    valid_dispatch_modes = choices_for("dispatch_mode")
    valid_dispatch_rules = choices_for("dispatch_rule")
    valid_objectives = choices_for("objective")
    valid_algo_modes = choices_for("algo_mode")

    strategy_enum = SortStrategy(require_choice(snapshot.sort_strategy, field="sort_strategy", valid_values=valid_strategies))
    strategy_params = weighted_strategy_params(snapshot) if strategy_enum == SortStrategy.WEIGHTED else {}

    return OptimizerConfig(
        strategy_enum=strategy_enum,
        strategy_params=strategy_params,
        algo_mode=require_choice(snapshot.algo_mode, field="algo_mode", valid_values=valid_algo_modes),
        objective_name=require_choice(snapshot.objective, field="objective", valid_values=valid_objectives),
        time_budget_seconds=require_int(snapshot.time_budget_seconds, field="time_budget_seconds", min_value=1),
        dispatch_mode=require_choice(snapshot.dispatch_mode, field="dispatch_mode", valid_values=valid_dispatch_modes),
        dispatch_rule=require_choice(snapshot.dispatch_rule, field="dispatch_rule", valid_values=valid_dispatch_rules),
        valid_strategies=valid_strategies,
        valid_dispatch_modes=valid_dispatch_modes,
        valid_dispatch_rules=valid_dispatch_rules,
    )
