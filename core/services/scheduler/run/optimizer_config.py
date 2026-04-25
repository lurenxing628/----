from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms import SortStrategy
from core.algorithms.greedy.algo_stats import increment_counter
from core.infrastructure.errors import ValidationError
from core.models.enums import YesNo
from core.services.scheduler.config.config_field_spec import choices_for
from core.services.scheduler.config.config_snapshot import ensure_schedule_config_snapshot
from core.shared.strict_parse import parse_required_float, parse_required_int

from ..number_utils import to_yes_no

_FIELD_LABELS = {
    "sort_strategy": "排序策略",
    "dispatch_mode": "派工方式",
    "dispatch_rule": "派工规则",
    "objective": "优化目标",
    "algo_mode": "计算模式",
    "seed_results": "种子排产结果",
}


@dataclass(frozen=True)
class OptimizerConfig:
    snapshot: Any
    strategy_enum: SortStrategy
    strategy_params: Optional[Dict[str, Any]]
    algo_mode: str
    objective_name: str
    time_budget_seconds: int
    dispatch_mode: str
    dispatch_rule: str
    valid_strategies: Tuple[str, ...]
    valid_dispatch_modes: Tuple[str, ...]
    valid_dispatch_rules: Tuple[str, ...]
    valid_objectives: Tuple[str, ...]
    valid_algo_modes: Tuple[str, ...]

    def strategy_keys(self) -> List[str]:
        current_key = str(self.strategy_enum.value)
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
    text = str(value or "").strip().lower()
    if text not in set(valid_values):
        raise ValidationError(f"“{label}”配置无效，请返回排产参数页重新选择。", field=field)
    return text


def require_float(value: Any, *, field: str, min_value: float) -> float:
    return float(parse_required_float(value, field=field, min_value=min_value))


def require_int(value: Any, *, field: str, min_value: int) -> int:
    return int(parse_required_int(value, field=field, min_value=min_value))


def normalized_choice_values(values: Any) -> Tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    out: List[str] = []
    seen = set()
    for item in values:
        text = str(item or "").strip().lower()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return tuple(out)


def effective_choice_values(field: str, *, cfg_svc: Any, allowlist_attr: Optional[str] = None) -> Tuple[str, ...]:
    registry_values = tuple(str(item).strip().lower() for item in choices_for(field))
    if not allowlist_attr:
        return registry_values
    narrowed = normalized_choice_values(getattr(cfg_svc, allowlist_attr, ()))
    if not narrowed:
        return registry_values
    narrowed_set = set(narrowed)
    return tuple(item for item in registry_values if item in narrowed_set)


def record_optimizer_cfg_degradations(
    snapshot: Any,
    optimizer_algo_stats: Dict[str, Any],
    *,
    mapping: Dict[str, str],
) -> None:
    degradation_events = getattr(snapshot, "degradation_events", ()) or ()
    degraded_fields = {
        str((event or {}).get("field") or "").strip()
        for event in degradation_events
        if isinstance(event, dict)
    }
    for config_field, counter_key in mapping.items():
        if config_field in degraded_fields:
            increment_counter(optimizer_algo_stats, counter_key, bucket="param_fallbacks")


def ensure_optimizer_config_snapshot(cfg: Any, *, strict_mode: bool) -> Any:
    return ensure_schedule_config_snapshot(
        cfg,
        strict_mode=bool(strict_mode),
        source="scheduler.optimize_schedule",
    )


def weighted_strategy_params(snapshot: Any, *, strict_mode: bool) -> Dict[str, Any]:
    return {
        "priority_weight": require_float(snapshot.priority_weight, field="priority_weight", min_value=0.0),
        "due_weight": require_float(snapshot.due_weight, field="due_weight", min_value=0.0),
    }


def is_ortools_enabled(snapshot: Any) -> bool:
    return to_yes_no(getattr(snapshot, "ortools_enabled", YesNo.NO.value), default=YesNo.NO.value) == YesNo.YES.value


def ortools_time_limit_seconds(snapshot: Any) -> int:
    return require_int(snapshot.ortools_time_limit_seconds, field="ortools_time_limit_seconds", min_value=1)


def resolve_optimizer_config(
    *,
    cfg_svc: Any,
    snapshot: Any,
    optimizer_algo_stats: Dict[str, Any],
    strict_mode: bool,
) -> OptimizerConfig:
    valid_strategies = effective_choice_values("sort_strategy", cfg_svc=cfg_svc, allowlist_attr="VALID_STRATEGIES")
    valid_dispatch_modes = effective_choice_values("dispatch_mode", cfg_svc=cfg_svc, allowlist_attr="VALID_DISPATCH_MODES")
    valid_dispatch_rules = effective_choice_values("dispatch_rule", cfg_svc=cfg_svc, allowlist_attr="VALID_DISPATCH_RULES")
    valid_objectives = effective_choice_values("objective", cfg_svc=cfg_svc, allowlist_attr="VALID_OBJECTIVES")
    valid_algo_modes = effective_choice_values("algo_mode", cfg_svc=cfg_svc, allowlist_attr="VALID_ALGO_MODES")

    strategy_enum = SortStrategy(require_choice(snapshot.sort_strategy, field="sort_strategy", valid_values=valid_strategies))
    if strategy_enum == SortStrategy.WEIGHTED:
        record_optimizer_cfg_degradations(
            snapshot,
            optimizer_algo_stats,
            mapping={
                "priority_weight": "optimizer_priority_weight_defaulted_count",
                "due_weight": "optimizer_due_weight_defaulted_count",
            },
        )

    strategy_params: Optional[Dict[str, Any]] = None
    if strategy_enum == SortStrategy.WEIGHTED:
        strategy_params = weighted_strategy_params(snapshot, strict_mode=bool(strict_mode))

    return OptimizerConfig(
        snapshot=snapshot,
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
        valid_objectives=valid_objectives,
        valid_algo_modes=valid_algo_modes,
    )
