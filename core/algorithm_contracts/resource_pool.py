"""The run's automatic-assignment resources: one frozen value built once from the run's captured facts.

``build_resource_pool`` is its only producer; ``DISABLED_RESOURCE_POOL`` is the pool of a run without automatic
assignment. A candidate records only its pair-rank overrides; ``with_pair_rank`` derives the pool it decodes with.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field, replace
from functools import cached_property
from typing import Any, Dict, FrozenSet, Iterable, Mapping, Optional, Tuple

# A pair without a rank sorts after every ranked pair (automatic assignment and the resource neighborhood).
_MISSING_PAIR_RANK = 9999

_ResourceKey = Tuple[Optional[str], Optional[str], str]


class _StaticCandidates:
    """One pool's static machine candidates, kept per (fixed machine, fixed operator, work type) as computed,
    and the machines of each listed work type as a set for filtering. Both read only the machine mappings."""

    def __init__(self) -> None:
        self.by_resources: Dict[_ResourceKey, Tuple[str, ...]] = {}
        self.allowed_sets: Dict[str, FrozenSet[str]] = {}


@dataclass(frozen=True)
class ResourcePool:
    """``machines_by_op_type`` lists the active machines of every work type the run's internal operations need
    (every machine work type when the run schedules no internal operation); ``operators_by_machine`` lists each
    machine's qualified operators in rank order and ``machines_by_operator`` each operator's machines;
    ``pair_rank`` ranks each (operator, machine) link, lower first.

    ``operator_skills`` is None when no machine supports several work types: operators are then not filtered by
    work type. Otherwise it holds each operator's declared work types, None meaning the operator declared none
    (every work type of a linked machine).

    ``static_candidates`` is only for ``with_pair_rank``: a derived pool keeps its origin's machine mappings,
    so it shares the origin's static candidates. Every other pool starts its own; they are not pool content.
    """

    enabled: bool
    machines_by_op_type: Mapping[str, Tuple[str, ...]]
    operators_by_machine: Mapping[str, Tuple[str, ...]]
    machines_by_operator: Mapping[str, Tuple[str, ...]]
    pair_rank: Mapping[Tuple[str, str], int]
    operator_skills: Optional[Mapping[str, Optional[FrozenSet[str]]]]
    static_candidates: InitVar[Optional[_StaticCandidates]] = None
    _static: _StaticCandidates = field(init=False, repr=False, compare=False)

    def __post_init__(self, static_candidates: Optional[_StaticCandidates]) -> None:
        object.__setattr__(self, "_static", _StaticCandidates() if static_candidates is None else static_candidates)

    def with_pair_rank(self, overrides: Mapping[Tuple[str, str], int]) -> ResourcePool:
        """This pool with ``overrides`` replacing pair ranks; without overrides it is this very pool."""
        if not overrides:
            return self
        ranks = dict(self.pair_rank)
        ranks.update(overrides)
        return replace(self, pair_rank=ranks, static_candidates=self._static)

    def rank(self, operator_id: str, machine_id: str) -> int:
        return self.pair_rank.get((operator_id, machine_id), _MISSING_PAIR_RANK)

    def static_machine_candidates(
        self, fixed_machine: Optional[str], fixed_operator: Optional[str], op_type_id: str,
    ) -> Tuple[str, ...]:
        """The machines an internal operation may use before timing, in pool order; equal inputs share one tuple.

        A fixed machine is the only candidate and a fixed operator offers its machines, both kept to the work
        type's machines when the pool lists that work type; a free operation takes its work type's machines.
        """
        key = (fixed_machine, fixed_operator, op_type_id)
        known = self._static.by_resources
        if key not in known:
            known[key] = self._machine_candidates(fixed_machine, fixed_operator, op_type_id)
        return known[key]

    def _machine_candidates(
        self, fixed_machine: Optional[str], fixed_operator: Optional[str], op_type_id: str,
    ) -> Tuple[str, ...]:
        allowed = self.machines_by_op_type.get(op_type_id)
        if fixed_machine:
            candidates: Tuple[str, ...] = (fixed_machine,)
        elif fixed_operator:
            candidates = self.machines_by_operator.get(fixed_operator, ())
        else:
            return () if allowed is None else allowed
        if allowed is None:
            return candidates
        allowed_sets = self._static.allowed_sets
        if op_type_id not in allowed_sets:
            allowed_sets[op_type_id] = frozenset(allowed)
        allowed_set = allowed_sets[op_type_id]
        return tuple(machine_id for machine_id in candidates if machine_id in allowed_set)

    def qualified_operators(self, candidates: Iterable[str], op_type_id: str) -> Tuple[str, ...]:
        """``candidates`` that may perform ``op_type_id``, in their order."""
        skills = self.operator_skills
        if skills is None:
            return tuple(candidates)
        qualified = []
        for oid in candidates:
            declared = skills[oid]
            if declared is None or op_type_id in declared:
                qualified.append(oid)
        return tuple(qualified)

    @cached_property
    def fingerprint(self) -> Tuple[Any, ...]:
        """The pool's content as plain values, for decode checkpoints: equal content gives an equal fingerprint,
        any different rank a different one. Mapping order carries no meaning, list order does."""
        skills = self.operator_skills
        return (
            self.enabled,
            tuple(sorted(self.machines_by_op_type.items())),
            tuple(sorted(self.operators_by_machine.items())),
            tuple(sorted(self.machines_by_operator.items())),
            tuple(sorted(self.pair_rank.items())),
            None if skills is None else tuple(sorted(
                (oid, None if declared is None else tuple(sorted(declared))) for oid, declared in skills.items()
            )),
        )


DISABLED_RESOURCE_POOL = ResourcePool(
    enabled=False, machines_by_op_type={}, operators_by_machine={}, machines_by_operator={}, pair_rank={},
    operator_skills=None,
)


__all__ = ["DISABLED_RESOURCE_POOL", "ResourcePool"]
