"""Local search stops on measured decodes and idle rounds, not on a budget-derived iteration count.

Before 2026-09-18 the loop counted every round as an iteration and stopped at
``time_budget_seconds * 20`` rounds, so a baseline with cheap decodes hit the count at
half its slice while duplicate and no-op rounds burned the rest. Now an iteration is a
decoder invocation; the limit comes from the slice that is left and the measured cost
of one decode; rounds that decode nothing only count toward a bounded idle streak that
ends the search as exhausted. See
``.codestable/compound/2026-09-18-decision-optimizer-budget-and-rule-pool-corrections.md``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .optimizer_candidate_profile import ITERATION_CEILING, ITERATION_FLOOR, RESTART_CEILING, RESTART_FLOOR

STOP_TIME_BUDGET = "time_budget"
STOP_ITERATION_LIMIT = "iteration_limit"
STOP_SEARCH_EXHAUSTED = "search_exhausted"

LIMIT_SOURCE_MEASURED_DECODE_COST = "measured_decode_cost"
LIMIT_SOURCE_DECODE_COST_UNKNOWN = "decode_cost_unknown"
LIMIT_SOURCE_NO_FINITE_DEADLINE = "no_finite_deadline"


@dataclass(frozen=True)
class LocalSearchLimits:
    """``decode_limit`` decoder invocations at most; ``restart_after`` rounds without a best
    improvement trigger a shake; ``idle_round_limit`` consecutive rounds that decode nothing end
    the search as exhausted."""

    decode_limit: int
    restart_after: int
    idle_round_limit: int
    source: str
    remaining_ms: Optional[int]
    decode_cost_ms: Optional[int]
    affordable_decodes: Optional[int]

    def to_report_dict(self) -> Dict[str, Any]:
        return {
            "policy": "measured_decode_budget_v1",
            "decode_limit": int(self.decode_limit),
            "restart_after": int(self.restart_after),
            "idle_round_limit": int(self.idle_round_limit),
            "source": str(self.source),
            "remaining_ms": self.remaining_ms,
            "decode_cost_ms": self.decode_cost_ms,
            "affordable_decodes": self.affordable_decodes,
        }


def _clamp(value: int, floor: int, ceiling: int) -> int:
    return max(int(floor), min(int(ceiling), int(value)))


def derive_local_search_limits(
    *, remaining_seconds: float, decode_cost_seconds: float, neighborhood_count: int,
) -> LocalSearchLimits:
    """Bound the search by what the remaining slice can pay for.

    With a finite slice and a measured positive decode cost the decode limit is the affordable
    count clamped to the profile window; without either measurement only the ceiling bounds it,
    so the no-deadline path still terminates. The restart threshold keeps its historical ratio
    (an eighth of the limit). The idle streak allows one full stall-and-shake cycle plus one
    round per neighborhood before declaring the neighborhood around the incumbent exhausted.
    """
    if isinstance(remaining_seconds, bool) or not isinstance(remaining_seconds, (int, float)):
        raise ValueError("remaining seconds must be a number")
    if (isinstance(decode_cost_seconds, bool) or not isinstance(decode_cost_seconds, (int, float))
            or not math.isfinite(decode_cost_seconds) or decode_cost_seconds < 0):
        raise ValueError("decode cost must be a finite nonnegative number")
    remaining = max(float(remaining_seconds), 0.0)
    affordable: Optional[int] = None
    if not math.isfinite(remaining):
        source = LIMIT_SOURCE_NO_FINITE_DEADLINE
        decode_limit = ITERATION_CEILING
    elif decode_cost_seconds <= 0:
        source = LIMIT_SOURCE_DECODE_COST_UNKNOWN
        decode_limit = ITERATION_CEILING
    else:
        source = LIMIT_SOURCE_MEASURED_DECODE_COST
        affordable = int(remaining / float(decode_cost_seconds))
        decode_limit = _clamp(affordable, ITERATION_FLOOR, ITERATION_CEILING)
    restart_after = _clamp(decode_limit // 8, RESTART_FLOOR, RESTART_CEILING)
    idle_round_limit = 2 * restart_after + max(int(neighborhood_count), 1)
    return LocalSearchLimits(
        decode_limit=decode_limit,
        restart_after=restart_after,
        idle_round_limit=idle_round_limit,
        source=source,
        remaining_ms=int(remaining * 1000) if math.isfinite(remaining) else None,
        decode_cost_ms=int(float(decode_cost_seconds) * 1000) if decode_cost_seconds > 0 else None,
        affordable_decodes=affordable,
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
    """Decoder invocations, the current idle streak, and rounds since the last best improvement."""

    decodes: int = 0
    idle_rounds: int = 0
    no_improve: int = 0
    duplicate_rounds: int = 0
    noop_rounds: int = 0

    def record_round(self, *, decode_attempted: bool, duplicate: bool = False, noop: bool = False) -> None:
        if decode_attempted:
            self.decodes += 1
            self.idle_rounds = 0
            return
        self.idle_rounds += 1
        if duplicate:
            self.duplicate_rounds += 1
        if noop:
            self.noop_rounds += 1

    def to_report_dict(self) -> Dict[str, Any]:
        return {
            "decodes": int(self.decodes),
            "idle_rounds_at_stop": int(self.idle_rounds),
            "duplicate_rounds": int(self.duplicate_rounds),
            "noop_rounds": int(self.noop_rounds),
        }


__all__ = [
    "LIMIT_SOURCE_DECODE_COST_UNKNOWN",
    "LIMIT_SOURCE_MEASURED_DECODE_COST",
    "LIMIT_SOURCE_NO_FINITE_DEADLINE",
    "STOP_ITERATION_LIMIT",
    "STOP_SEARCH_EXHAUSTED",
    "STOP_TIME_BUDGET",
    "LocalSearchCounters",
    "LocalSearchLimits",
    "derive_local_search_limits",
    "local_search_stop_reason",
]
