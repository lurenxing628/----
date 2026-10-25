"""Shared local search round limits, restart thresholds, and idle-round counters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .candidate_profile import ITERATION_CEILING, RESTART_CEILING, RESTART_FLOOR

STOP_TIME_BUDGET = "time_budget"
STOP_ITERATION_LIMIT = "iteration_limit"
STOP_SEARCH_EXHAUSTED = "search_exhausted"


@dataclass(frozen=True)
class LocalSearchLimits:
    """Bound shared search rounds, rounds without improvement, and consecutive idle rounds."""

    decode_limit: int
    restart_after: int
    idle_round_limit: int


def _clamp(value: int, floor: int, ceiling: int) -> int:
    return max(int(floor), min(int(ceiling), int(value)))


def derive_local_search_limits(*, neighborhood_count: int) -> LocalSearchLimits:
    """Use the shared round ceiling and allow a full stall-and-shake cycle before exhaustion."""
    decode_limit = ITERATION_CEILING
    restart_after = _clamp(decode_limit // 8, RESTART_FLOOR, RESTART_CEILING)
    idle_round_limit = 2 * restart_after + max(int(neighborhood_count), 1)
    return LocalSearchLimits(
        decode_limit=decode_limit,
        restart_after=restart_after,
        idle_round_limit=idle_round_limit,
    )


def local_search_stop_reason(
    *, now_value: float, deadline: float, decodes: int, decode_limit: int, idle_rounds: int, idle_round_limit: int,
) -> Optional[str]:
    if now_value >= deadline:
        return STOP_TIME_BUDGET
    if decodes >= decode_limit:
        return STOP_ITERATION_LIMIT
    if idle_rounds >= idle_round_limit:
        return STOP_SEARCH_EXHAUSTED
    return None


@dataclass
class LocalSearchCounters:
    """The current idle streak and rounds since the last best improvement."""

    idle_rounds: int = 0
    no_improve: int = 0

    def record_round(self, *, decode_attempted: bool) -> None:
        if decode_attempted:
            self.idle_rounds = 0
            return
        self.idle_rounds += 1


__all__ = [
    "STOP_ITERATION_LIMIT",
    "STOP_SEARCH_EXHAUSTED",
    "STOP_TIME_BUDGET",
    "LocalSearchCounters",
    "LocalSearchLimits",
    "derive_local_search_limits",
    "local_search_stop_reason",
]
