"""Destroy neighbourhoods of the iterated greedy stage, modelled on OR-Tools CP-SAT LNS.

* ``AdaptiveValue`` ports ``AdaptiveParameterValue`` (ortools/util/adaptative_parameter_value.h):
  Increase ``v = min(1 - (1 - v) / f, v * f)``, Decrease ``v = max(v / f, 1 - (1 - v) * f)`` with
  ``f = 1 + 1 / sqrt(n + 1)`` and ``n`` the number of changes so far. Here the value drives the
  destroy size: an interrupted or worse iteration shrinks it; a completed iteration that stayed put grows it.
* ``time_window`` follows ``SchedulingTimeWindowNeighborhoodGenerator`` (cp_model_lns.cc): operations
  sorted by decoded start, one contiguous block at a random start.
* ``resource_window`` follows ``SchedulingResourceWindowsNeighborhoodGenerator`` on one machine chosen
  proportionally to its load.
* ``tardy_random`` keeps the first version's pick: half strongest tardy/critical signals, half random.
* ``GeneratorRotation`` follows the active-operator continuation of ``CompoundOperator``
  (constraint_solver/local_search.cc): repeat an improving generator, otherwise advance in configured order.
"""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Sequence, Tuple

from core.infrastructure.errors import ValidationError

from .optimizer_graph_ready_iterated_greedy_contract import IG_GENERATORS

# Beyond this many changes the OR-Tools step factor would keep shrinking towards 1: a run of failures
# then needs dozens of successes to grow the destroy size back. The factor stays at least 1 + 1/3.
_FACTOR_CHANGE_CAP = 8


class AdaptiveValue:
    def __init__(self, initial: float) -> None:
        if not 0.0 <= float(initial) <= 1.0:
            raise ValueError("AdaptiveValue initial value must lie in [0, 1]")
        self.value = float(initial)
        self.num_changes = 0

    def _factor(self) -> float:
        self.num_changes += 1
        return 1.0 + 1.0 / math.sqrt(min(self.num_changes, _FACTOR_CHANGE_CAP) + 1)

    def clamp(self, low: float, high: float) -> None:
        self.value = min(max(self.value, float(low)), float(high))

    def increase(self) -> None:
        factor = self._factor()
        self.value = min(1.0 - (1.0 - self.value) / factor, self.value * factor)

    def decrease(self) -> None:
        factor = self._factor()
        self.value = max(self.value / factor, 1.0 - (1.0 - self.value) * factor)


class DestroyGenerator:
    name = ""

    def __init__(self, *, initial_size: int, max_size: int) -> None:
        if not 1 <= int(initial_size) <= int(max_size):
            raise ValueError("destroy size must satisfy 1 <= initial <= max")
        self.initial_size = int(initial_size)
        self.max_size = int(max_size)
        self.reset()
        self.calls = 0
        self.improving = 0
        self.fully_solved = 0
        self.idle = 0
        self.degenerate = 0
        self.time_seconds = 0.0
        self.last_improved = False
        self.completion_feedback = False

    def _bounds(self) -> Tuple[float, float]:
        # AdaptiveValue's 0/1 endpoints are absorbing. Stay inside the same integer-size bin so both
        # minimum and maximum sizes can adapt: one success at the minimum size grows it by at least one.
        if self.max_size <= 1:
            return 0.0, 0.0
        inset = 0.5 / self.max_size
        return inset, 1.0 - inset

    def reset(self) -> None:
        """Restore the configured size without losing this run's generator statistics."""
        value = (self.initial_size - 1) / (self.max_size - 1) if self.max_size > 1 else 0.0
        low, high = self._bounds()
        self.difficulty = AdaptiveValue(min(max(value, low), high))

    def size(self) -> int:
        return 1 + int(round(self.difficulty.value * (self.max_size - 1)))

    def select(self, order: Sequence[int], *, size: int, rnd: random.Random, features: Dict[str, Any]) -> Tuple[int, ...]:
        raise NotImplementedError

    def record(self, elapsed_seconds: float, *, improved: bool, fully_solved: bool, idle: bool, worse: bool = False) -> None:
        self.calls += 1
        self.time_seconds += max(float(elapsed_seconds), 0.0)
        self.improving += int(improved)
        self.fully_solved += int(fully_solved)
        self.idle += int(idle)
        self.last_improved = bool(improved and fully_solved and not worse)
        # Large, independently budgeted tasks use completion feedback. Small
        # instances keep their prior idle/worse feedback. Neither completion
        # signal is a proof that an entire mathematical neighbourhood is optimal.
        if not fully_solved or (worse and not self.completion_feedback):
            self.difficulty.decrease()
        elif idle or self.completion_feedback:
            self.difficulty.increase()
        self.difficulty.clamp(*self._bounds())

    def summary(self) -> Dict[str, Any]:
        return {"calls": self.calls, "improving": self.improving, "fully_solved": self.fully_solved, "idle": self.idle,
                "degenerate": self.degenerate, "time_ms": int(self.time_seconds * 1000),
                "difficulty": round(self.difficulty.value, 4), "size": self.size()}


def _bounded(size: int, order: Sequence[int]) -> int:
    return min(int(size), len(order) - 1) if len(order) > 1 else 0


def _window(items: List[int], *, size: int, rnd: random.Random) -> Tuple[int, ...]:
    size = min(size, len(items))
    if size <= 0:
        return ()
    start = rnd.randint(0, len(items) - size)
    return tuple(items[start:start + size])


class TimeWindowGenerator(DestroyGenerator):
    name = "time_window"

    def select(self, order: Sequence[int], *, size: int, rnd: random.Random, features: Dict[str, Any]) -> Tuple[int, ...]:
        count = _bounded(size, order)
        if count <= 0:
            return ()
        starts = features["starts"]
        position = {op_id: index for index, op_id in enumerate(order)}
        by_start = sorted(order, key=lambda op_id: (starts.get(op_id, math.inf), position[op_id]))
        return _window(by_start, size=count, rnd=rnd)


class ResourceWindowGenerator(DestroyGenerator):
    name = "resource_window"

    def select(self, order: Sequence[int], *, size: int, rnd: random.Random, features: Dict[str, Any]) -> Tuple[int, ...]:
        count = _bounded(size, order)
        if count <= 0:
            return ()
        starts, machines = features["starts"], features["machines"]
        position = {op_id: index for index, op_id in enumerate(order)}
        loaded = [op_id for op_id in order if machines.get(op_id)]
        by_machine: Dict[str, List[int]] = {}
        for op_id in loaded:
            by_machine.setdefault(machines[op_id], []).append(op_id)
        candidates = [op_id for op_id in loaded if len(by_machine[machines[op_id]]) >= 2]
        if not candidates:
            # No machine carries two operations: the window degenerates to a time window (reported).
            self.degenerate += 1
            by_start = sorted(order, key=lambda op_id: (starts.get(op_id, math.inf), position[op_id]))
            return _window(by_start, size=count, rnd=rnd)
        machine = machines[rnd.choice(candidates)]  # proportional to the machine's load
        on_machine = sorted(by_machine[machine], key=lambda op_id: (starts.get(op_id, math.inf), position[op_id]))
        return _window(on_machine, size=count, rnd=rnd)


class TardyRandomGenerator(DestroyGenerator):
    name = "tardy_random"

    def select(self, order: Sequence[int], *, size: int, rnd: random.Random, features: Dict[str, Any]) -> Tuple[int, ...]:
        return tardy_random_destroy(order, rnd=rnd, size=size, signals=features["signals"])


def tardy_random_destroy(order: Sequence[int], *, rnd: random.Random, size: int, signals: Dict[int, float]) -> Tuple[int, ...]:
    """Half of the removed operations come from the strongest tardy/critical signals, the rest at random."""
    count = _bounded(size, order)
    if count <= 0:
        return ()
    flagged = [op_id for op_id in order if signals.get(op_id, 0.0) > 0.0]
    rnd.shuffle(flagged)
    flagged.sort(key=lambda op_id: -signals[op_id])
    chosen = flagged[:min(len(flagged), (count + 1) // 2)]
    remaining = [op_id for op_id in order if op_id not in chosen]
    chosen.extend(rnd.sample(remaining, count - len(chosen)))
    return tuple(chosen)


_GENERATOR_TYPES = {
    TimeWindowGenerator.name: TimeWindowGenerator,
    ResourceWindowGenerator.name: ResourceWindowGenerator,
    TardyRandomGenerator.name: TardyRandomGenerator,
}
if tuple(_GENERATOR_TYPES) != IG_GENERATORS:
    raise RuntimeError("Destroy generator registry must list exactly IG_GENERATORS in order.")


def build_generators(names: Sequence[str], *, initial_size: int, max_size: int) -> List[DestroyGenerator]:
    generators = []
    for name in names:
        if name not in _GENERATOR_TYPES:
            raise ValidationError("GraphReady 迭代贪心配置无效：generators", field="graph_ready_iterated_greedy",
                                  details={"reason": "graph_ready_bad_iterated_greedy_config"})
        generators.append(_GENERATOR_TYPES[name](initial_size=initial_size, max_size=max_size))
    return generators


class GeneratorRotation:
    """Continue after an improvement; consume each failed call once before rotating."""

    def __init__(self, generators: Sequence[DestroyGenerator]) -> None:
        if not generators:
            raise ValueError("at least one destroy generator is required")
        self.generators = list(generators)
        self._index = 0
        self._completed_calls = self.generators[0].calls

    def pick(self) -> DestroyGenerator:
        current = self.generators[self._index]
        if current.calls > self._completed_calls and not current.last_improved:
            self._index = (self._index + 1) % len(self.generators)
        selected = self.generators[self._index]
        self._completed_calls = selected.calls
        return selected

    def reset_sizes(self) -> None:
        for generator in self.generators:
            generator.reset()


__all__ = [
    "AdaptiveValue",
    "DestroyGenerator",
    "GeneratorRotation",
    "ResourceWindowGenerator",
    "TardyRandomGenerator",
    "TimeWindowGenerator",
    "build_generators",
    "tardy_random_destroy",
]
