from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from core.shared.strict_parse import is_exact_non_negative_number


class GraphReadySearchBudget:
    """Graph stage deadline and actual profile/repair execution counters."""

    def __init__(self, *, deadline: float, clock: Callable[[], float]) -> None:
        self.deadline = deadline
        self.clock = clock
        self.profile_decodes = 0
        self.repair_decodes = 0
        self.profile_cost_samples = 0
        self.profile_cost_seconds = 0.0
        self.stop_reason: Optional[str] = None

    def available(self) -> bool:
        if self.stop_reason is not None:
            return False
        if self.clock() >= self.deadline:
            self.stop_reason = "time_budget"
            return False
        return True

    def record_profile_cost(self, elapsed_seconds: float) -> None:
        if not is_exact_non_negative_number(elapsed_seconds):
            raise ValueError("GraphReady profile elapsed time must be finite and nonnegative")
        if elapsed_seconds > 0:
            self.profile_cost_samples += 1
            self.profile_cost_seconds += elapsed_seconds

    def summary(self) -> Dict[str, Any]:
        return {
            "policy": "shared_decode_admission",
            "max_candidates": None,
            "candidate_cap_scope": "shared_session",
            "profile_decodes": self.profile_decodes, "repair_decodes": self.repair_decodes,
            "profile_cost_scope": "completed_profile_construction_decode_and_metrics",
            "profile_cost_samples": self.profile_cost_samples,
            "mean_profile_cost_ms": (self.profile_cost_seconds * 1000 / self.profile_cost_samples
                                     if self.profile_cost_samples else None),
            "stop_reason": self.stop_reason,
        }
