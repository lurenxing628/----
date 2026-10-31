"""Limits, report shape and public wording of the graph-ready iterated greedy stage."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Tuple

from core.services.scheduler.run.optimizer.graph_ready_feature_basis import SUCCESSOR_WORKLOAD_BASIS
from core.services.scheduler.run.optimizer.graph_ready_profiles import (
    GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
    GraphReadyWeightProfile,
)

IG_PROFILE_SLUG = "v2_ig_destroy_repair"
IG_CANDIDATE_POLICY = "iterated_greedy"
# The decoder consumes only the pick-rank keys of an IG decision; the profile is inert but part of the
# decode input signature, so every IG decode uses this one canonical v2 profile.
IG_DECODE_FORMULA_SLUG = "edd"
IG_DECODE_FORMULA_VERSION = "graph_ready_v2_objective_features_v2"
IG_GENERATORS = ("time_window", "resource_window", "tardy_random")


class _BudgetExhausted(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def ig_decode_profile(profile: GraphReadyWeightProfile) -> GraphReadyWeightProfile:
    """The canonical IG decode profile: same objective as the parent, inert formula and weights."""
    weights = {name: 0.0 for name in ("critical_path", "successor_count", "downstream_work_hours", "bottleneck_machine")}
    return replace(profile, slug=IG_PROFILE_SLUG, candidate_origin=GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
                   candidate_policy=IG_CANDIDATE_POLICY, profile_order=0, raw_weights=weights, effective_weights=weights,
                   formula_slug=IG_DECODE_FORMULA_SLUG, formula_version=IG_DECODE_FORMULA_VERSION, jitter_seed=0,
                   feature_basis=SUCCESSOR_WORKLOAD_BASIS)


@dataclass(frozen=True)
class IteratedGreedyLimits:
    # Initial destroy size; each generator adapts it between 1 and max_destruction_size.
    destruction_size: int = 3
    max_destruction_size: int = 6
    insertion_window: int = 6
    max_iterations: int = 200
    max_decodes: int = 400
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


def new_iterated_greedy_report(*, objective_name: str) -> Dict[str, Any]:
    return {
        "objective_name": objective_name,
        "status": "not_run",
        "stop_reason": None,
        "iterations": 0,
        "decodes": 0,
        "improvements": 0,
        "accepted": False,
    }
