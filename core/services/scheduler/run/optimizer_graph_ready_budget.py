from __future__ import annotations

import math
from typing import Any, Callable, Dict, Optional

from .optimizer_graph_ready_repair_contract import EliteRepairLimits


class GraphReadySearchBudget:
    """One global budget, with a soft profile cutoff once a usable elite exists."""

    def __init__(self, *, limits: EliteRepairLimits, deadline: float, clock: Callable[[], float]) -> None:
        self.deadline = deadline
        self.clock = clock
        self.max_candidates = limits.max_candidates
        self.max_neighbors_per_elite = limits.max_neighbors_per_elite
        self.profile_decodes = 0
        self.profile_cost_samples = 0
        self.profile_cost_seconds = 0.0
        self.repair_family_representatives = 0
        self.estimated_repair_family_seconds = 0.0
        self.cost_aware_reserved_seconds = 0.0
        self.stop_reason: Optional[str] = None
        started = clock()
        remaining = max(deadline - started, 0.0)
        self.repair_time_ceiling_seconds = (remaining if limits.time_budget_ms is None
                                            else min(remaining, limits.time_budget_ms / 1000.0))
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

    def available(self, *, has_elite: bool, repair_family_count: int = 0) -> bool:
        now = self.clock()
        if now >= self.deadline:
            self.stop_reason = "time_budget"
        elif self.profile_decodes >= self.max_candidates:
            self.stop_reason = "candidate_budget"
        elif has_elite and self.reserved_candidates and self.profile_decodes >= self.max_candidates - self.reserved_candidates:
            self.stop_reason = "repair_candidate_reservation"
        elif has_elite and self.reserved_seconds and now >= self.profile_deadline:
            self.stop_reason = "repair_time_reservation"
        elif has_elite and self._would_displace_repair_families(now, repair_family_count):
            self.stop_reason = "measured_repair_family_time_reservation"
        else:
            return True
        return False

    def record_profile_cost(self, elapsed_seconds: float) -> None:
        if isinstance(elapsed_seconds, bool) or not math.isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError("GraphReady profile elapsed time must be finite and nonnegative")
        if elapsed_seconds > 0:
            self.profile_cost_samples += 1
            self.profile_cost_seconds += elapsed_seconds

    def _would_displace_repair_families(self, now: float, family_count: int) -> bool:
        if type(family_count) is not int or family_count < 0:
            raise ValueError("GraphReady repair family count must be a nonnegative integer")
        if not self.reserved_candidates or not self.profile_cost_samples:
            return False
        self.repair_family_representatives = min(
            family_count, self.max_neighbors_per_elite, self.reserved_candidates,
            max(self.max_candidates - self.profile_decodes - 1, 0))
        mean_cost = self.profile_cost_seconds / self.profile_cost_samples
        self.estimated_repair_family_seconds = self.repair_family_representatives * mean_cost
        self.cost_aware_reserved_seconds = min(self.estimated_repair_family_seconds, self.repair_time_ceiling_seconds)
        # This predicts opportunity cost, not future quality or a guaranteed
        # decode duration. The hard deadline and candidate guards remain final.
        return bool(self.repair_family_representatives and self.cost_aware_reserved_seconds
                    and self.deadline - now < mean_cost + self.cost_aware_reserved_seconds)

    def summary(self) -> Dict[str, Any]:
        return {
            "policy": "profiles_then_reserved_repair_v1", "max_candidates": self.max_candidates,
            "profile_decodes": self.profile_decodes, "reserved_repair_candidates": self.reserved_candidates,
            "reserved_repair_time_ms": int(self.reserved_seconds * 1000),
            "profile_cost_scope": "completed_profile_construction_decode_and_metrics",
            "cost_aware_reservation_policy": "observed_mean_batch_family_opportunity_v1",
            "profile_cost_samples": self.profile_cost_samples,
            "mean_profile_cost_ms": (self.profile_cost_seconds * 1000 / self.profile_cost_samples
                                     if self.profile_cost_samples else None),
            "repair_family_representatives": self.repair_family_representatives,
            "estimated_repair_family_time_ms": self.estimated_repair_family_seconds * 1000,
            "cost_aware_reserved_repair_time_ms": self.cost_aware_reserved_seconds * 1000,
            "stop_reason": self.stop_reason,
        }
