from __future__ import annotations

from itertools import groupby
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.errors import ValidationError
from core.services.scheduler.run.optimizer.graph_ready_profiles import GraphReadyWeightProfile
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

    def __init__(self, *, evaluate: Callable[..., Dict[str, Any]], budget: GraphReadySearchBudget) -> None:
        self._evaluate = evaluate
        self.budget = budget

    def can_start(self) -> bool:
        return self.budget.available()

    def evaluate(self, *, profile: GraphReadyWeightProfile, order: List[str]) -> Optional[Dict[str, Any]]:
        try:
            return self._evaluate(profile=profile, order=order)
        except SharedSearchSkip as exc:
            if exc.reason in ("estimated_decode_cost", "time_budget"):
                self.budget.stop_reason = exc.reason
            return None
