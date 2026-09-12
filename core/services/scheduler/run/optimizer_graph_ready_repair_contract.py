from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from core.infrastructure.errors import ValidationError

REPAIR_PHASE = "graph_ready_v2_elite_repair"
REPAIR_GENERATORS = ("adjacent_swap", "single_insert", "tardy_boundary_move", "critical_block_swap",
                     "operation_time_insert", "resource_alternative")


@dataclass(frozen=True)
class EliteRepairLimits:
    enabled: bool = True
    top_k: int = 3
    max_neighbors_per_elite: int = 8
    time_budget_ms: Optional[int] = None
    max_candidates: int = 60
    max_rounds: int = 3


def resolve_elite_repair_limits(construction: Optional[Dict[str, Any]], *, enabled: bool) -> EliteRepairLimits:
    optimization = (construction or {}).get("graph_ready_optimization", {})
    if not isinstance(optimization, dict):
        _invalid("graph_ready_optimization")
    raw = optimization.get("elite_repair", {})
    if not isinstance(raw, dict):
        _invalid("elite_repair")
    allowed = {"enabled", "top_k", "max_neighbors_per_elite", "time_budget_ms", "max_rounds"}
    if set(raw).difference(allowed):
        _invalid("elite_repair")
    active = raw.get("enabled", enabled)
    if not isinstance(active, bool):
        _invalid("enabled")
    time_budget = raw.get("time_budget_ms")
    return EliteRepairLimits(
        enabled=active and enabled,
        top_k=min(_positive_int(raw.get("top_k", 3), "top_k"), 8),
        max_neighbors_per_elite=min(_positive_int(raw.get("max_neighbors_per_elite", 8), "max_neighbors_per_elite"), 32),
        time_budget_ms=None if time_budget is None else _positive_int(time_budget, "time_budget_ms"),
        max_candidates=_positive_int(optimization.get("max_candidate_profiles", 60), "max_candidate_profiles"),
        max_rounds=min(_positive_int(raw.get("max_rounds", 3), "max_rounds"), 8),
    )


def new_repair_report(limits: EliteRepairLimits, *, objective_name: str) -> Dict[str, Any]:
    pruning = {
        "schema_version": 1, "phase": REPAIR_PHASE,
        "pruning_enabled": limits.enabled, "pruning_strategy": "hybrid",
        "pruning_rule_version": "elite_top_k_duplicate_budget_v1",
        "candidate_space_total": 0, "candidate_space_total_status": "exact",
        "generated_candidates": 0, "evaluated_candidates": 0, "pruned_candidates": 0,
        "rejected_candidates": 0, "skipped_by_budget": 0,
        "pruned_by_rule": {}, "rejected_by_reason": {},
        "duplicate_decision_pruned": 0, "duplicate_output_rejected": 0,
        "same_fingerprint_rejected": 0, "pruned_by_bound": 0, "pruned_by_dominance": 0,
        "pruned_by_feasibility_guard": 0, "pruned_by_scope_filter": 0,
        "pruning_safety_status": "heuristic_scope_reduction",
        "objective_name": objective_name, "objective_compatibility": "same_objective",
        "bound_metric": None, "bound_value": None, "bound_reason": None,
        "budget_ms": 0, "runtime_ms": 0, "rule_trace": [],
    }
    return {
        "repair_enabled": limits.enabled, "repair_top_k": limits.top_k,
        "repair_max_rounds": limits.max_rounds, "repair_rounds_completed": 0,
        "repair_stop_reason": None, "repair_round_improvements": [],
        "repair_round_policy": "improvement_first", "repair_deferred_by_improvement": 0,
        "repair_max_neighbors_per_elite": limits.max_neighbors_per_elite,
        "repair_time_budget_ms": 0, "repair_candidate_budget": 0,
        "repair_candidate_space_total": 0, "repair_candidate_space_total_status": "exact",
        "repair_generated_candidates": 0, "repair_evaluated_candidates": 0,
        "repair_pruned_candidates": 0, "repair_skipped_by_budget": 0,
        "repair_rejection_summary": {}, "repair_pruning_report": pruning,
        "repair_best_origin": None, "repair_accepted": False, "repair_status": "not_run",
        "neighbor_generators": list(REPAIR_GENERATORS),
        "pruning_strategy": ["elite_top_k", "duplicate_decision", "budget_guard"],
        "eligible_elites": 0, "selected_elites": 0,
        "skipped_elites_by_top_k": 0, "skipped_neighbors_by_top_k": 0,
        "repair_scope": "production_core", "deadline_overrun_ms": 0,
    }


def finish_repair_report(report: Dict[str, Any]) -> None:
    pruning = report["repair_pruning_report"]
    for key in ("candidate_space_total", "candidate_space_total_status", "generated_candidates",
                "evaluated_candidates", "pruned_candidates", "skipped_by_budget"):
        report["repair_" + key] = pruning[key]
    report["repair_rejection_summary"] = dict(pruning["rejected_by_reason"])


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _invalid(field)
    return int(value)


def _invalid(field: str) -> None:
    raise ValidationError(
        "GraphReady repair 配置无效：" + field,
        field="graph_ready_elite_repair",
        details={"reason": "graph_ready_bad_repair_config"},
    )
