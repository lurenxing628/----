"""Walk acceptance and the start-solution pool of the iterated greedy stage.

* ``sa_accept`` is the ILS criterion of OR-Tools routing (routing_ils.cc, SimulatedAnnealingAcceptanceCriterion):
  ``candidate + T * log(U) < reference`` with U uniform in (0, 1). Scores are lexicographic tuples
  ``(failed_ops, primary objective, ...)``: failed operations are never traded, the temperature acts on
  the primary objective only, and equal primaries fall back to the plain lexicographic order.
* ``ExponentialCooling`` is ``ExponentialCoolingSchedule``: ``T(progress) = T0 * (Tf / T0) ** progress``.
  OR-Tools derives T0/Tf from the mean arc cost; ``TemperatureScale`` freezes the first finite, nonzero
  primary-objective delta as our decision-cost scale. Later samples cannot reheat the walk.
* ``SolutionPool`` follows ``SharedSolutionRepository`` (synchronization.h): a bounded set of distinct
  solutions, diversity selection at an equal-score capacity boundary, and ``GetRandomBiasedSolution``
  picks uniformly among the best-ranked ones not selected often, else uniformly over the pool.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .optimizer_graph_ready_profiles import GraphReadyWeightProfile

_EXPLORATION_THRESHOLD = 100
_MAX_POOL_SIZE = 8


class ExponentialCooling:
    def __init__(self, start_ratio: float, end_ratio: float) -> None:
        if not 0.0 < float(end_ratio) <= float(start_ratio) <= 1.0:
            raise ValueError("cooling ratios must satisfy 0 < end <= start <= 1")
        self.start_ratio = float(start_ratio)
        self.end_ratio = float(end_ratio)

    def temperature(self, scale: float, progress: float) -> float:
        if not scale or scale <= 0.0:
            return 0.0
        progress = min(max(float(progress), 0.0), 1.0)
        return self.start_ratio * float(scale) * (self.end_ratio / self.start_ratio) ** progress


class TemperatureScale:
    """Fix the scale at the first usable delta; retain sample counts for reporting."""

    def __init__(self) -> None:
        self.count = 0
        self.total = 0.0
        self._value = 0.0

    def observe(self, candidate: Sequence[float], reference: Sequence[float]) -> None:
        if len(candidate) < 2 or len(reference) < 2 or candidate[0] != reference[0]:
            return
        delta = abs(float(candidate[1]) - float(reference[1]))
        if delta > 0.0 and math.isfinite(delta):
            if not self.count:
                self._value = delta
            self.count += 1
            self.total += delta

    @property
    def value(self) -> float:
        return self._value


def sa_accept(candidate: Sequence[float], reference: Sequence[float], *, temperature: float, u: float) -> bool:
    candidate, reference = tuple(candidate), tuple(reference)
    if not candidate or not reference:
        raise ValueError("scores must be non-empty tuples")
    if candidate[0] != reference[0]:
        return candidate[0] < reference[0]
    if len(candidate) < 2 or len(reference) < 2:
        return candidate <= reference
    if candidate[1] != reference[1]:
        if temperature <= 0.0:
            return candidate[1] < reference[1]
        u = min(max(float(u), 1e-12), 1.0)
        return float(candidate[1]) + float(temperature) * math.log(u) < float(reference[1])
    return candidate[2:] <= reference[2:]


@dataclass
class PoolEntry:
    order: Tuple[int, ...]
    score: Tuple[float, ...]
    candidate: Dict[str, Any]
    checkpoints: List[Any] = field(default_factory=list)
    features: Optional[Dict[str, Any]] = None
    num_selected: int = 0
    sequence: int = 0
    batch_order: Tuple[str, ...] = ()
    resource_overrides: Tuple[Tuple[int, str, str], ...] = ()
    profile: Optional[GraphReadyWeightProfile] = None
    decoded_order: bool = False

    def decision_key(self) -> Tuple[Any, ...]:
        return (self.batch_order, self.order, tuple(sorted(self.resource_overrides)), profile_identity(self.profile))


def profile_identity(profile: Optional[GraphReadyWeightProfile]) -> Tuple[Any, ...]:
    """Only stable profile values enter identity; candidate objects and addresses never do."""
    if profile is None:
        return ()
    return (profile.slug, profile.profile_order, profile.candidate_origin, profile.candidate_policy,
            profile.formula_slug, profile.formula_version, profile.jitter_seed, profile.objective_name,
            profile.feature_basis, tuple(sorted(profile.raw_weights.items())), tuple(sorted(profile.effective_weights.items())))


def _entry_distance(left: PoolEntry, right: PoolEntry) -> int:
    order_distance = sum(a != b for a, b in zip(left.order, right.order)) + abs(len(left.order) - len(right.order))
    batch_distance = sum(a != b for a, b in zip(left.batch_order, right.batch_order)) + abs(len(left.batch_order) - len(right.batch_order))
    left_resources = {op_id: (machine, operator) for op_id, machine, operator in left.resource_overrides}
    right_resources = {op_id: (machine, operator) for op_id, machine, operator in right.resource_overrides}
    resource_distance = sum(left_resources.get(op_id) != right_resources.get(op_id) for op_id in set(left_resources) | set(right_resources))
    return order_distance + batch_distance + resource_distance + int(profile_identity(left.profile) != profile_identity(right.profile))


class SolutionPool:
    def __init__(self, size: int) -> None:
        if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= _MAX_POOL_SIZE:
            raise ValueError("pool size must be an integer between 1 and 8")
        self.size = int(size)
        self.entries: List[PoolEntry] = []
        self._sequence = 0

    def add(self, entry: PoolEntry) -> bool:
        key = entry.decision_key()
        if any(item.decision_key() == key for item in self.entries):
            return False
        self._sequence += 1
        entry.sequence = self._sequence
        self.entries.append(entry)
        self.entries.sort(key=lambda item: (item.score, item.sequence))
        if len(self.entries) > self.size:
            self._retain_diverse_boundary()
        return any(item is entry for item in self.entries)

    def refresh(self, entry: PoolEntry) -> bool:
        """Replace a formally decoded decision's older entry, preserving its selection history.

        Its score may improve or worsen after the first formal decode. New decisions still pass
        through the ordinary bounded admission and diversity selection used by ``add``.
        """
        key = entry.decision_key()
        for index, previous in enumerate(self.entries):
            if previous.decision_key() != key:
                continue
            entry.num_selected = previous.num_selected
            entry.sequence = previous.sequence
            self.entries[index] = entry
            self.entries.sort(key=lambda item: (item.score, item.sequence))
            if len(self.entries) > self.size:
                self._retain_diverse_boundary()
            return any(item is entry for item in self.entries)
        return self.add(entry)

    def _retain_diverse_boundary(self) -> None:
        """Keep better scores unconditionally, then maximise distance only within the tied boundary.

        At most nine entries are inspected: O(9**2 * decision_size) for distances and at most
        C(9, 4) = 126 subsets. No history-wide or operation-permutation search is performed.
        """
        boundary = self.entries[self.size - 1].score
        kept = [i for i, entry in enumerate(self.entries) if entry.score < boundary]
        tied = [i for i, entry in enumerate(self.entries) if entry.score == boundary]
        count = self.size - len(kept)
        if len(tied) == count:
            self.entries = [self.entries[i] for i in kept + tied]
            return
        distances = {(i, j): _entry_distance(self.entries[i], self.entries[j])
                     for i, j in combinations(kept + tied, 2)}

        def diversity(indices: Tuple[int, ...]) -> int:
            return sum(distances[(i, j)] for i, j in combinations(kept + list(indices), 2))

        selected = max(combinations(tied, count), key=diversity)
        self.entries = [self.entries[i] for i in kept + list(selected)]

    def pick(self, rnd: random.Random, *, exclude_order: Optional[Tuple[int, ...]] = None,
             exclude_entry: Optional[PoolEntry] = None) -> Optional[PoolEntry]:
        if exclude_entry is not None:
            candidates = [item for item in self.entries if item.decision_key() != exclude_entry.decision_key()]
        else:
            candidates = [item for item in self.entries if item.order != exclude_order]
        candidates = candidates or list(self.entries)
        if not candidates:
            return None
        best_score = candidates[0].score
        preferred = [item for item in candidates if item.score == best_score and item.num_selected <= _EXPLORATION_THRESHOLD]
        chosen = rnd.choice(preferred or candidates)
        chosen.num_selected += 1
        return chosen


__all__ = ["ExponentialCooling", "PoolEntry", "SolutionPool", "TemperatureScale", "profile_identity", "sa_accept"]
