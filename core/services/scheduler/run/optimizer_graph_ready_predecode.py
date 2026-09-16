from __future__ import annotations

import math
from itertools import groupby
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.infrastructure.errors import ValidationError

from .optimizer_graph_ready_budget import GraphReadySearchBudget
from .optimizer_graph_ready_profiles import GRAPH_READY_PHASE, GraphReadyWeightProfile


def graph_priority_preorder(keys: Dict[int, Tuple[float, ...]]) -> Tuple[Tuple[int, ...], ...]:
    """Exact ordered equality classes, not an op-id-tiebroken permutation.

    SGS compares (dynamic penalty, *graph key, *dynamic dispatch key). With
    fixed-length graph keys within each candidate, this weak order preserves
    all pairwise comparisons for ANY common dynamic prefix/suffix. Induction
    over identical ready sets and resource states gives identical SGS decisions.
    Variable-length keys are excluded: a prefix key could consume dispatch data.
    """
    normalized: Dict[int, Tuple[float, ...]] = {}
    for op_id, key in keys.items():
        if not key or any(isinstance(value, bool) or not math.isfinite(value) for value in key):
            raise ValidationError("GraphReady predecode requires finite nonempty keys.", field="graph_ready_predecode")
        normalized[op_id] = tuple(float(value) for value in key)
    if len({len(key) for key in normalized.values()}) > 1:
        raise ValidationError("GraphReady predecode requires uniform key arity.", field="graph_ready_predecode")
    ordered = sorted(normalized, key=lambda op_id: (normalized[op_id], op_id))
    return tuple(tuple(group) for _key, group in groupby(ordered, key=normalized.__getitem__))


class _EquivalentDecision(RuntimeError):
    def __init__(self, candidate: Dict[str, Any]) -> None:
        self.candidate = candidate


class _ProfileBudgetExhausted(RuntimeError):
    pass


class GraphReadyProfileSearch:
    """Cache bound to ONE evaluator closure: input/seed/resource/rule cannot vary.

    Only order and graph keys vary here. Never share this cache with a restart,
    another resource pool, or repair. Failed decodes do not become representatives.
    """

    def __init__(self, *, evaluate: Callable[..., Dict[str, Any]], pool: Any,
                 budget: GraphReadySearchBudget, profile_count: int, initial_decode_seconds: float = 0.0) -> None:
        self._evaluate = evaluate
        self.pool = pool
        self.budget = budget
        self.initial_decode_seconds = initial_decode_seconds
        self.cost_stopped = False
        self._decoded: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        self.report: Dict[str, Any] = {
            "proof": "exact_graph_key_weak_order_v1", "cache_scope": "single_fixed_evaluator",
            "configured_profiles": profile_count, "considered_profiles": 0,
            "predecode_pruned_profiles": 0, "construction_rejected_profiles": 0,
            "skipped_before_decode": 0, "equivalent_profiles": [],
            "skipped_by_estimated_decode_cost": 0,
        }

    def can_start(self) -> bool:
        return not self.cost_stopped and self.budget.available()

    def evaluate(self, *, profile: GraphReadyWeightProfile, order: List[str]) -> Optional[Dict[str, Any]]:
        self.report["considered_profiles"] += 1
        decision: List[Tuple[Any, ...]] = []
        started = False

        def inspect(context: Dict[str, Any]) -> None:
            nonlocal started
            key = (tuple(order), graph_priority_preorder(context["graph_priority_key_by_op_id"]))
            if key in self._decoded:
                raise _EquivalentDecision(self._decoded[key])
            # Construction and proof computation consume the SAME wall-clock budget.
            if not self.can_start():
                raise _ProfileBudgetExhausted()
            if self.initial_decode_seconds > max(self.budget.deadline - self.budget.clock(), 0.0):
                self.cost_stopped = True
                self.report["skipped_by_estimated_decode_cost"] += 1
                raise _ProfileBudgetExhausted()
            decision.append(key)
            self.budget.profile_decodes += 1
            started = True

        evaluation_started = self.budget.clock()
        try:
            candidate = self._evaluate(profile=profile, order=order, inspect_decision=inspect)
        except _EquivalentDecision as exc:
            self.report["predecode_pruned_profiles"] += 1
            self.report["equivalent_profiles"].append({
                "profile_slug": profile.slug,
                "representative_slug": exc.candidate["graph_ready_profile"]["weight_profile_slug"],
            })
            # A v1 representative can still supply a proven-equivalent v2 elite.
            # Do not relabel the decoded payload or count it as another evaluation.
            self.pool.observe(exc.candidate, profile)
            return None
        except _ProfileBudgetExhausted:
            self.report["skipped_before_decode"] += 1
            return None
        except ValidationError:
            if not started:
                self.report["construction_rejected_profiles"] += 1
            raise
        self.budget.record_profile_cost(self.budget.clock() - evaluation_started)
        self._decoded[decision[0]] = candidate
        return candidate

    def publish(self, *, attempts: List[Dict[str, Any]], report_state: Any) -> None:
        self.report["unvisited_profiles"] = self.report["configured_profiles"] - self.report["considered_profiles"]
        self.report.update(self.budget.summary())
        attempts.append({"tag": "graph_ready_profile_efficiency", "candidate_status": "phase_summary",
                         "profile_efficiency": self.report})
        if report_state is None:
            return
        graph = dict((report_state.candidate_profile or {}).get("graph_ready_optimization") or {})
        graph["profile_efficiency"] = self.report
        report_state.update_candidate_profile(graph_ready_optimization=graph)
        if self.budget.stop_reason == "time_budget":
            report_state.mark_deadline_reached()
            report_state.mark_phase_skipped(GRAPH_READY_PHASE, "time_budget")
