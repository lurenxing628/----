from __future__ import annotations

import math
from typing import Any, Callable, Dict, Optional

from .optimizer_graph_ready_repair_contract import EliteRepairLimits
from .optimizer_graph_ready_stage_scheduler import ROTATION_POLICY


class GraphReadySearchBudget:
    """Shared clock and decode cap of the graph phase.

    Wall time is shared between the stages by the rotation (no reserved slices);
    the candidate cap only bounds profile and repair decodes as a safety valve.
    Iterated greedy reports and enforces its independent decode cap.
    """

    def __init__(self, *, limits: EliteRepairLimits, deadline: float, clock: Callable[[], float]) -> None:
        self.deadline = deadline
        self.clock = clock
        self.max_candidates = limits.max_candidates
        self.repair_enabled = bool(limits.enabled)
        self.profile_decodes = 0
        self.repair_decodes = 0
        self.profile_cost_samples = 0
        self.profile_cost_seconds = 0.0
        self.stop_reason: Optional[str] = None

    def remaining_candidates(self) -> int:
        return max(self.max_candidates - self.profile_decodes - self.repair_decodes, 0)

    def available(self) -> bool:
        if self.clock() >= self.deadline:
            self.stop_reason = "time_budget"
        elif self.remaining_candidates() <= 0:
            self.stop_reason = "candidate_budget"
        else:
            return True
        return False

    def record_profile_cost(self, elapsed_seconds: float) -> None:
        if isinstance(elapsed_seconds, bool) or not math.isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError("GraphReady profile elapsed time must be finite and nonnegative")
        if elapsed_seconds > 0:
            self.profile_cost_samples += 1
            self.profile_cost_seconds += elapsed_seconds

    def summary(self) -> Dict[str, Any]:
        return {
            "policy": ROTATION_POLICY, "max_candidates": self.max_candidates,
            "candidate_cap_scope": "profiles_and_elite_repair",
            "profile_decodes": self.profile_decodes, "repair_decodes": self.repair_decodes,
            "profile_cost_scope": "completed_profile_construction_decode_and_metrics",
            "profile_cost_samples": self.profile_cost_samples,
            "mean_profile_cost_ms": (self.profile_cost_seconds * 1000 / self.profile_cost_samples
                                     if self.profile_cost_samples else None),
            "stop_reason": self.stop_reason,
        }
