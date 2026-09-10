from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .optimizer_graph_ready_repair_contract import EliteRepairLimits


class GraphReadySearchBudget:
    """One global budget, with a soft profile cutoff once a usable elite exists."""

    def __init__(self, *, limits: EliteRepairLimits, deadline: float, clock: Callable[[], float]) -> None:
        self.deadline = deadline
        self.clock = clock
        self.max_candidates = limits.max_candidates
        self.profile_decodes = 0
        self.stop_reason: Optional[str] = None
        started = clock()
        remaining = max(deadline - started, 0.0)
        # At least two profile slots precede the reserved repair slot. Budgets below
        # three cannot promise v1 + v2 + repair, and do not reserve count or time.
        reserve = 0
        if limits.enabled and limits.max_candidates >= 3:
            reserve = min(max(1, limits.max_candidates // 4), limits.max_candidates - 2,
                          limits.top_k * limits.max_neighbors_per_elite)
        self.reserved_candidates = reserve
        self.reserved_seconds = remaining * 0.25 if reserve else 0.0
        if limits.time_budget_ms is not None:
            self.reserved_seconds = min(self.reserved_seconds, limits.time_budget_ms / 1000.0)
        self.profile_deadline = deadline - self.reserved_seconds

    def available(self, *, has_elite: bool) -> bool:
        now = self.clock()
        if now >= self.deadline:
            self.stop_reason = "time_budget"
        elif self.profile_decodes >= self.max_candidates:
            self.stop_reason = "candidate_budget"
        elif has_elite and self.reserved_candidates and self.profile_decodes >= self.max_candidates - self.reserved_candidates:
            self.stop_reason = "repair_candidate_reservation"
        elif has_elite and self.reserved_seconds and now >= self.profile_deadline:
            self.stop_reason = "repair_time_reservation"
        else:
            return True
        return False

    def summary(self) -> Dict[str, Any]:
        return {
            "policy": "profiles_then_reserved_repair_v1", "max_candidates": self.max_candidates,
            "profile_decodes": self.profile_decodes, "reserved_repair_candidates": self.reserved_candidates,
            "reserved_repair_time_ms": int(self.reserved_seconds * 1000),
            "stop_reason": self.stop_reason,
        }
