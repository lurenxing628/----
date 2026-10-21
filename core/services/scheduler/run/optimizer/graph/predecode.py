from __future__ import annotations

from itertools import groupby
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.errors import ValidationError
from core.services.scheduler.run.optimizer.graph_ready_profiles import GRAPH_READY_PHASE, GraphReadyWeightProfile
from core.services.scheduler.run.optimizer.shared_budget import SharedSearchSkip

from .budget import GraphReadySearchBudget


def graph_priority_preorder(keys: Dict[int, Tuple[float, ...]]) -> Tuple[Tuple[int, ...], ...]:
    """Exact ordered equality classes, not an op-id-tiebroken permutation.

    SGS compares (dynamic penalty, *graph key, *dynamic dispatch key). With
    fixed-length graph keys within each candidate, this weak order preserves
    all pairwise comparisons for ANY common dynamic prefix/suffix. Induction
    over identical ready sets and resource states gives identical SGS decisions.
    Variable-length keys are excluded: a prefix key could consume dispatch data.
    """
    if len({len(key) for key in keys.values()}) > 1:
        raise ValidationError("GraphReady predecode requires uniform key arity.", field="graph_ready_predecode")
    ordered = sorted(keys, key=lambda op_id: (keys[op_id], op_id))
    return tuple(tuple(group) for _key, group in groupby(ordered, key=keys.__getitem__))


class GraphReadyProfileSearch:
    """Profile construction uses the run's shared decode admission and receipts."""

    def __init__(self, *, evaluate: Callable[..., Dict[str, Any]],
                 budget: GraphReadySearchBudget, profile_count: int) -> None:
        self._evaluate = evaluate
        self.budget = budget
        self.report: Dict[str, Any] = {
            "proof": "shared_decode_request_v1", "cache_scope": "shared_session", "shared_skip_by_reason": {},
            "configured_profiles": profile_count, "considered_profiles": 0,
            "predecode_pruned_profiles": 0, "construction_rejected_profiles": 0,
            "skipped_before_decode": 0, "equivalent_profiles": [],
            "skipped_by_estimated_decode_cost": 0, "stagnation_stop": None,
        }

    def can_start(self) -> bool:
        return self.budget.available()

    def evaluate(self, *, profile: GraphReadyWeightProfile, order: List[str]) -> Optional[Dict[str, Any]]:
        self.report["considered_profiles"] += 1
        started = False

        def before_decode() -> None:
            nonlocal started
            self.budget.profile_decodes += 1
            started = True

        evaluation_started = self.budget.clock()
        try:
            candidate = self._evaluate(profile=profile, order=order, before_decode=before_decode)
        except SharedSearchSkip as exc:
            self.report["skipped_before_decode"] += 1
            counts = self.report["shared_skip_by_reason"]
            counts[exc.reason] = counts.get(exc.reason, 0) + 1
            return None
        except ValidationError:
            if not started:
                self.report["construction_rejected_profiles"] += 1
            raise
        if started:
            self.budget.record_profile_cost(self.budget.clock() - evaluation_started)
        else:
            self.report["predecode_pruned_profiles"] += 1
            self.report["equivalent_profiles"].append({"profile_slug": profile.slug,
                                                        "request_id": candidate["decode_receipt"]["request_id"]})
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
            # The phase ran once any profile was decoded; only a phase without decodes was skipped for time.
            if self.budget.profile_decodes == 0:
                report_state.mark_phase_skipped(GRAPH_READY_PHASE, "time_budget")
