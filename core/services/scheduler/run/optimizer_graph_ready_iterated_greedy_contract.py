"""Limits, report shape and public wording of the graph-ready iterated greedy stage."""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Dict, Optional, Tuple

from core.infrastructure.errors import ValidationError

from .optimizer_graph_ready_feature_basis import SUCCESSOR_WORKLOAD_BASIS
from .optimizer_graph_ready_profiles import GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN, GraphReadyWeightProfile

IG_PHASE = "graph_ready_v2_iterated_greedy"
IG_PROFILE_SLUG = "v2_ig_destroy_repair"
IG_CANDIDATE_POLICY = "iterated_greedy"
# The decoder consumes only the pick-rank keys of an IG decision; the profile is inert but part of the
# decode input signature, so every IG decode uses this one canonical v2 profile.
IG_DECODE_FORMULA_SLUG = "edd"
IG_DECODE_FORMULA_VERSION = "graph_ready_v2_objective_features_v2"
IG_ALGORITHM = "operation_destroy_best_insertion_v3"
# Trial decodes resume from the reference decode's checkpoint whose required prefix the trial keeps;
# every accepted order is decoded in full again and both outputs must match (fail-loud otherwise).
IG_PARTIAL_EVALUATION = "checkpoint_resume_prefix_exact"
IG_ACCEPTANCE = "simulated_annealing_exponential_cooling"
IG_GENERATORS = ("time_window", "resource_window", "tardy_random")
IG_STATUSES = ("not_run", "skipped_no_parent", "skipped_by_budget", "strict_improvement", "no_strict_improvement")


class _BudgetExhausted(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def ig_decode_profile(profile: GraphReadyWeightProfile) -> GraphReadyWeightProfile:
    """The canonical IG decode profile: same objective as the parent, inert formula and weights."""
    weights = {name: 0.0 for name in ("critical_path", "successor_count", "downstream_work_hours", "bottleneck_machine")}
    return replace(profile, slug=IG_PROFILE_SLUG, candidate_origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
                   candidate_policy=IG_CANDIDATE_POLICY, profile_order=0, raw_weights=weights, effective_weights=dict(weights),
                   formula_slug=IG_DECODE_FORMULA_SLUG, formula_version=IG_DECODE_FORMULA_VERSION, jitter_seed=0,
                   feature_basis=SUCCESSOR_WORKLOAD_BASIS)


@dataclass(frozen=True)
class IteratedGreedyLimits:
    enabled: bool = True
    # Initial destroy size; each generator adapts it between 1 and max_destruction_size.
    destruction_size: int = 3
    max_destruction_size: int = 6
    insertion_window: int = 6
    max_iterations: int = 200
    max_decodes: int = 400
    time_budget_ms: Optional[int] = None
    generators: Tuple[str, ...] = IG_GENERATORS
    # Checkpoints captured per full decode; 0 turns trial resumption off.
    checkpoint_count: int = 8
    pool_size: int = 3
    # One bounded order proposal from an observed independent single-resource queue.
    due_date_seed: bool = True
    stagnation_iterations: int = 10
    # Simulated annealing temperatures relative to the first usable objective delta (primary, and the
    # secondary component when primaries tie): a one-delta-worse walk step starts at e^-1 acceptance.
    temperature_ratio_start: float = 1.0
    temperature_ratio_end: float = 0.01


_ALLOWED_KEYS = frozenset({
    "enabled", "destruction_size", "max_destruction_size", "insertion_window", "max_iterations", "max_decodes",
    "time_budget_ms", "generators", "checkpoint_count", "pool_size", "stagnation_iterations",
    "temperature_ratio_start", "temperature_ratio_end", "due_date_seed",
})


def resolve_iterated_greedy_limits(construction: Optional[Dict[str, Any]], *, enabled: bool) -> IteratedGreedyLimits:
    optimization = (construction or {}).get("graph_ready_optimization", {})
    if not isinstance(optimization, dict):
        _invalid("graph_ready_optimization")
    raw = optimization.get("iterated_greedy", {})
    if not isinstance(raw, dict):
        _invalid("iterated_greedy")
    if set(raw).difference(_ALLOWED_KEYS):
        _invalid("iterated_greedy")
    active = raw.get("enabled", enabled)
    if not isinstance(active, bool):
        _invalid("enabled")
    due_date_seed = raw.get("due_date_seed", True)
    if not isinstance(due_date_seed, bool):
        _invalid("due_date_seed")
    time_budget = raw.get("time_budget_ms")
    max_size = min(_positive_int(raw.get("max_destruction_size", 6), "max_destruction_size"), 12)
    size = min(_positive_int(raw.get("destruction_size", 3), "destruction_size"), max_size)
    start_ratio = _unit_fraction(raw.get("temperature_ratio_start", 1.0), "temperature_ratio_start", low=0.0, high=1.0, low_open=True)
    end_ratio = _unit_fraction(raw.get("temperature_ratio_end", 0.01), "temperature_ratio_end", low=0.0, high=start_ratio, low_open=True)
    return IteratedGreedyLimits(
        enabled=active and enabled,
        destruction_size=size,
        max_destruction_size=max_size,
        insertion_window=min(_positive_int(raw.get("insertion_window", 6), "insertion_window"), 32),
        max_iterations=min(_positive_int(raw.get("max_iterations", 200), "max_iterations"), 10000),
        max_decodes=min(_positive_int(raw.get("max_decodes", 400), "max_decodes"), 100000),
        time_budget_ms=None if time_budget is None else _positive_int(time_budget, "time_budget_ms"),
        generators=_generators(raw.get("generators", IG_GENERATORS)),
        checkpoint_count=min(_non_negative_int(raw.get("checkpoint_count", 8), "checkpoint_count"), 64),
        pool_size=min(_positive_int(raw.get("pool_size", 3), "pool_size"), 8),
        due_date_seed=due_date_seed,
        stagnation_iterations=min(_positive_int(raw.get("stagnation_iterations", 10), "stagnation_iterations"), 1000),
        temperature_ratio_start=start_ratio,
        temperature_ratio_end=end_ratio,
    )


def new_iterated_greedy_report(limits: IteratedGreedyLimits, *, objective_name: str) -> Dict[str, Any]:
    return {
        "schema_version": 4, "phase": IG_PHASE, "algorithm": IG_ALGORITHM,
        "partial_evaluation": IG_PARTIAL_EVALUATION, "objective_name": objective_name,
        "enabled": limits.enabled, "status": "not_run", "stop_reason": None,
        "destruction_size": limits.destruction_size, "max_destruction_size": limits.max_destruction_size,
        "insertion_window": limits.insertion_window,
        "max_iterations": limits.max_iterations, "max_decodes": limits.max_decodes,
        "time_budget_ms": 0, "runtime_ms": 0, "deadline_overrun_ms": 0,
        "iterations": 0, "interrupted_iterations": 0, "incumbent_adoptions": 0, "incumbent_adoption_rollbacks": 0,
        "decodes": 0, "duplicate_decision_pruned": 0,
        "budget_pruned_before_decode": 0, "decode_admission": None,
        "context_switches": 0, "unverified_trial_decodes": 0, "validation_decodes": 0,
        "checkpoint_capture_rejections": 0, "reference_capture_decodes": 0,
        # Full decodes that only capture a known solution under the IG context (start, restart, adoption).
        "reference_captures": 0, "reference_capture_divergences": 0, "reference_capture_improvements": 0,
        "rejected_by_reason": {}, "walk_accepted": 0, "walk_improved": 0, "walk_accepted_worse": 0,
        "improvements": 0, "accepted": False, "parent_origin": None, "parent_score": None, "parent_profile_slug": None,
        "reference_basis": None,
        "starting_incumbent_origin": None, "starting_incumbent_score": None,
        "initial_seed": {"enabled": limits.due_date_seed, "status": "not_run", "reason": None,
                         "model": "observed_single_resource_due_date", "requires_sgs_validation": True,
                         "probes": 0, "runtime_ms": 0, "decodes": 0, "selected": False,
                         "incumbent_improved": False},
        "parent_order_score": None, "parent_order_consistent": None,
        "best_score": None, "mean_decode_ms": None,
        "generators": {name: {"calls": 0, "improving": 0, "fully_solved": 0, "idle": 0, "degenerate": 0,
                              "time_ms": 0, "difficulty": None, "size": None} for name in limits.generators},
        "checkpoints": {"count": limits.checkpoint_count, "full_decodes": 0, "resumed_decodes": 0,
                        "picks_total": 0, "picks_saved": 0, "equivalence_checks": 0},
        "acceptance": {"policy": IG_ACCEPTANCE, "temperature_ratio_start": limits.temperature_ratio_start,
                       "temperature_ratio_end": limits.temperature_ratio_end, "temperature_scale": None,
                       "secondary_temperature_scale": None, "rejected": 0},
        "pool": {"size": limits.pool_size, "stagnation_iterations": limits.stagnation_iterations, "restarts": 0,
                 "restart_captures_failed": 0, "start_captures_failed": 0,
                 "entries": 0, "initial_entries": 0, "selection_policy": "best_ranked_random_with_stagnation_restart"},
    }


_SKIPPED_BY_BUDGET_LABELS = {
    "decode_would_overrun": "预计一次完整解码放不进剩余预算，未执行",
    "decode_budget": "解码次数上限已用完，未执行",
}


def iterated_greedy_public_message(report: Dict[str, Any]) -> str:
    status_labels = {
        "not_run": "未启用", "skipped_no_parent": "没有可作起点的完整方案", "skipped_by_budget": "预算不足，未执行",
        "no_strict_improvement": "未得到严格更优方案", "strict_improvement": "已采纳严格更优方案",
    }
    label = status_labels[report["status"]]
    if report["status"] == "skipped_by_budget":
        label = _SKIPPED_BY_BUDGET_LABELS.get(str(report.get("stop_reason") or ""), label)
    return (
        "GraphReady 迭代贪心" + ("已启用" if report["enabled"] else "未启用")
        + "，迭代" + str(report["iterations"]) + "，解码" + str(report["decodes"])
        + "（其中续排" + str(report["checkpoints"]["resumed_decodes"]) + "）"
        + "，去重剪枝" + str(report["duplicate_decision_pruned"])
        + "；" + label
        + "。仅为预算内搜索，不构成最优性证明。"
    )


def _generators(value: Any) -> Tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)) or not value:
        _invalid("generators")
    names = []
    for item in value:
        if not isinstance(item, str) or item not in IG_GENERATORS or item in names:
            _invalid("generators")
        names.append(item)
    return tuple(names)


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _invalid(field)
    return int(value)


def _non_negative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _invalid(field)
    return int(value)


def _unit_fraction(value: Any, field: str, *, low: float, high: float, low_open: bool = False, high_open: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        _invalid(field)
    number = float(value)
    if number < low or number > high or (low_open and number == low) or (high_open and number == high):
        _invalid(field)
    return number


def _invalid(field: str) -> None:
    raise ValidationError(
        "GraphReady 迭代贪心配置无效：" + field,
        field="graph_ready_iterated_greedy",
        details={"reason": "graph_ready_bad_iterated_greedy_config"},
    )
