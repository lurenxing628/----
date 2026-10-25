"""Mix existing batch moves with bounded operation and qualified resource moves."""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import zip_longest
from typing import Any, Dict, Iterator, List, Optional, Tuple

from core.services.scheduler.run.optimizer.graph_ready_profiles import GraphReadyWeightProfile

from .operation_neighbors import operation_repair_decisions
from .repair_decisions import RepairDecision, RepairParentPreparation, iter_resource_decisions, prepare_repair_parent
from .repair_neighbors import RepairNeighborhood, build_repair_neighborhood


def _decision_key(
    decision: RepairDecision,
) -> Tuple[Tuple[str, ...], Tuple[int, ...], Tuple[Tuple[int, str, str], ...]]:
    return (decision.batch_order, decision.operation_order, decision.resource_overrides)


@dataclass(frozen=True)
class RepairPortfolio:
    batches: RepairNeighborhood
    extras: Tuple[Tuple[str, RepairDecision], ...]
    inherited_resources: Tuple[Tuple[int, str, str], ...]
    move_layout: Tuple[Tuple[str, int], ...] = field(init=False)

    def __post_init__(self) -> None:
        first_by_kind: Dict[str, int] = {}
        for index, (kind, _source, _target) in enumerate(self.batches.moves):
            first_by_kind.setdefault(kind, index)
        representatives = tuple(first_by_kind.values())
        raw_layout = [("batch", index) for index in representatives]
        selected = set(representatives)
        remaining = (index for index in range(len(self.batches.moves)) if index not in selected)
        for batch_index, extra_index in zip_longest(remaining, range(len(self.extras))):
            if batch_index is not None:
                raw_layout.append(("batch", batch_index))
            if extra_index is not None:
                raw_layout.append(("extra", extra_index))
        seen: set = set()
        layout: List[Tuple[str, int]] = []
        for kind, index in raw_layout:
            if kind == "batch":
                _move_kind, source, target = self.batches.moves[index]
                key: Tuple[Any, ...] = (
                    ("batch_swap", min(source, target), max(source, target))
                    if abs(source - target) == 1
                    else ("batch_insert", source, target)
                )
            else:
                _, decision = self.extras[index]
                key = ("extra", _decision_key(decision))
            if key not in seen:
                seen.add(key)
                layout.append((kind, index))
        object.__setattr__(self, "move_layout", tuple(layout))

    @property
    def candidate_count(self) -> int:
        return len(self.move_layout)

    def decisions(self, start: int = 0) -> Iterator[Tuple[str, RepairDecision]]:
        for position in range(start, len(self.move_layout)):
            kind, index = self.move_layout[position]
            yield self._batch_decision(index) if kind == "batch" else self.extras[index]

    def _batch_decision(self, index: int) -> Tuple[str, RepairDecision]:
        # Expand only a consumed move; do not materialize all batch permutations. A batch move stays a
        # batch-rank-only decision on purpose: re-picking the operations under the new ranks is this
        # neighbourhood's search freedom. Block-moving the parent's pick sequence instead (2026-09-18)
        # lost 7 of 20 end-to-end cases against this baseline and was withdrawn.
        kind, source, target = self.batches.moves[index]
        order = list(self.batches.order)
        if kind == "adjacent_swap":
            order[source], order[target] = order[target], order[source]
        else:
            order.insert(target, order.pop(source))
        return kind, RepairDecision._unvalidated(tuple(order), resource_overrides=self.inherited_resources)


@dataclass(frozen=True)
class ParentRepairPortfolio:
    """One decoded parent, with small feature-basis generator variants."""

    variants: Tuple[Tuple[GraphReadyWeightProfile, RepairPortfolio], ...]

    @property
    def candidate_count(self) -> int:
        return sum(portfolio.candidate_count for _profile, portfolio in self.variants)

    @property
    def feature_bases(self) -> Tuple[str, ...]:
        return tuple(profile.feature_basis for profile, _portfolio in self.variants)

    def with_variant(self, profile: GraphReadyWeightProfile, portfolio: RepairPortfolio) -> ParentRepairPortfolio:
        if profile.feature_basis in self.feature_bases:
            return self
        return ParentRepairPortfolio(self.variants + ((profile, portfolio),))

    def profiled_decisions(self, skip_by_basis: Optional[Dict[str, int]] = None
                           ) -> Iterator[Tuple[str, RepairDecision, GraphReadyWeightProfile]]:
        """Round-robin over the variants; each variant's stream resumes after its own consumed prefix.

        Resuming per basis keeps a variant added mid-visit from reshuffling what the other streams yield next.
        """
        consumed = skip_by_basis or {}
        streams = [portfolio.decisions(start=consumed.get(profile.feature_basis, 0))
                   for profile, portfolio in self.variants]
        for group in zip_longest(*streams):
            for (profile, _portfolio), item in zip(self.variants, group):
                if item is not None:
                    kind, decision = item
                    yield kind, decision, profile

def build_repair_portfolio(candidate: Dict[str, Any], *, operations: List[Any], metrics_by_op_id: Dict[int, Dict[str, Any]],
                           start_dt: Any, seed: int, objective_name: str, graph_context: Optional[Dict[str, Any]],
                           resource_pool: Optional[Dict[str, Any]],
                           prepared_parent: Optional[RepairParentPreparation] = None) -> RepairPortfolio:
    """Neighbourhoods of one decoded parent: batch moves on its batch order, bounded operation moves on its
    start-time order, resource moves on its actual selections. The parent's own pick sequence is not used as a
    basis on purpose (2026-09-18: it cost 6% weighted tardiness on medium_shift_pool and helped nowhere)."""
    prepared = (prepared_parent if prepared_parent is not None else prepare_repair_parent(
        candidate, operations, resource_pool, graph_context, resource_moves=graph_context is not None))
    batches = build_repair_neighborhood(
        operations=operations, metrics_by_op_id=metrics_by_op_id, start_dt=start_dt, seed=seed,
        objective_name=objective_name, prepared_parent=prepared)
    inherited = prepared.inherited_resources
    if graph_context is None:
        return RepairPortfolio(batches, (), inherited)
    operation_decisions = operation_repair_decisions(
        metrics_by_op_id=metrics_by_op_id, batch_order=batches.order, start_dt=start_dt, objective_name=objective_name,
        prepared_parent=prepared)
    resources = (("resource_alternative", decision) for decision in iter_resource_decisions(
        candidate, operations=operations, resource_pool=resource_pool, batch_order=batches.order,
        operation_order=prepared.operation_order, prepared_parent=prepared))
    extras = tuple(item for group in zip_longest(operation_decisions, resources) for item in group if item is not None)
    return RepairPortfolio(batches, extras, inherited)
