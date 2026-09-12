"""Mix existing batch moves with bounded operation and qualified resource moves."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import zip_longest
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .optimizer_graph_ready_operation_neighbors import operation_repair_decisions
from .optimizer_graph_ready_profiles import GraphReadyWeightProfile
from .optimizer_graph_ready_repair_decisions import RepairDecision, iter_resource_decisions
from .optimizer_graph_ready_repair_neighbors import RepairNeighborhood, build_repair_neighborhood


@dataclass(frozen=True)
class RepairPortfolio:
    batches: RepairNeighborhood
    extras: Tuple[Tuple[str, RepairDecision], ...]
    inherited_resources: Tuple[Tuple[int, str, str], ...]

    @property
    def candidate_count(self) -> int:
        return len(self.batches.moves) + len(self.extras)

    @property
    def batch_family_representative_indices(self) -> Tuple[int, ...]:
        first_by_kind: Dict[str, int] = {}
        for index, (kind, _source, _target) in enumerate(self.batches.moves):
            first_by_kind.setdefault(kind, index)
        return tuple(first_by_kind.values())

    @property
    def batch_family_representative_count(self) -> int:
        return len(self.batch_family_representative_indices)

    def decisions(self) -> Iterator[Tuple[str, RepairDecision]]:
        representatives = self.batch_family_representative_indices
        for index in representatives:
            yield self._batch_decision(index)
        selected = set(representatives)
        batch_decisions = (self._batch_decision(index) for index in range(len(self.batches.moves))
                           if index not in selected)
        for group in zip_longest(batch_decisions, self.extras):
            for item in group:
                if item is not None:
                    yield item

    def _batch_decision(self, index: int) -> Tuple[str, RepairDecision]:
        # Expand only a consumed move; do not materialize all batch permutations.
        neighbor = RepairNeighborhood(self.batches.order, (self.batches.moves[index],))
        kind, order = next(neighbor.neighbors())
        return kind, RepairDecision(tuple(order), resource_overrides=self.inherited_resources)


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

    @property
    def batch_family_representative_count(self) -> int:
        return len({kind for _profile, portfolio in self.variants for kind, _source, _target in portfolio.batches.moves})

    def with_variant(self, profile: GraphReadyWeightProfile, portfolio: RepairPortfolio) -> ParentRepairPortfolio:
        if profile.feature_basis in self.feature_bases:
            return self
        return ParentRepairPortfolio(self.variants + ((profile, portfolio),))

    def profiled_decisions(self) -> Iterator[Tuple[str, RepairDecision, GraphReadyWeightProfile]]:
        streams = [portfolio.decisions() for _profile, portfolio in self.variants]
        for group in zip_longest(*streams):
            for (profile, _portfolio), item in zip(self.variants, group):
                if item is not None:
                    kind, decision = item
                    yield kind, decision, profile

    def decisions(self) -> Iterator[Tuple[str, RepairDecision]]:
        for kind, decision, _profile in self.profiled_decisions():
            yield kind, decision


def build_repair_portfolio(candidate: Dict[str, Any], *, operations: List[Any], metrics_by_op_id: Dict[int, Dict[str, Any]],
                           start_dt: Any, seed: int, objective_name: str,
                           graph_context: Optional[Dict[str, Any]], resource_pool: Optional[Dict[str, Any]]) -> RepairPortfolio:
    batches = build_repair_neighborhood(candidate, operations=operations, metrics_by_op_id=metrics_by_op_id,
                                        start_dt=start_dt, seed=seed, objective_name=objective_name)
    inherited = tuple(tuple(item) for item in candidate.get("repair_decision", {}).get("resource_overrides", ()))
    if graph_context is None:
        return RepairPortfolio(batches, (), inherited)
    operation_decisions = operation_repair_decisions(
        candidate, operations=operations, graph_context=graph_context, metrics_by_op_id=metrics_by_op_id,
        batch_order=batches.order, start_dt=start_dt, objective_name=objective_name)
    resources = (("resource_alternative", decision) for decision in iter_resource_decisions(
        candidate, operations=operations, resource_pool=resource_pool, batch_order=batches.order,
        operation_order=tuple(candidate.get("repair_decision", {}).get("operation_order", ()))))
    extras = tuple(item for group in zip_longest(operation_decisions, resources) for item in group if item is not None)
    return RepairPortfolio(batches, extras, inherited)
