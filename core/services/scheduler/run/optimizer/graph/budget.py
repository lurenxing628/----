from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from .repair_contract import EliteRepairLimits

if TYPE_CHECKING:
    from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession


class GraphReadySearchBudget:
    """Graph stage deadline and actual profile/repair execution counters."""

    def __init__(self, *, limits: EliteRepairLimits, deadline: float, clock: Callable[[], float],
                 decode_session: SharedDecodeSession) -> None:
        self.deadline = deadline
        self.clock = clock
        self.decode_session = decode_session
        self.repair_enabled = bool(limits.enabled)
        self.profile_decodes = 0
        self.repair_decodes = 0
        self.profile_cost_samples = 0
        self.profile_cost_seconds = 0.0
        self.stop_reason: Optional[str] = None

    def available(self) -> bool:
        if self.clock() >= self.deadline:
            self.stop_reason = "time_budget"
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
