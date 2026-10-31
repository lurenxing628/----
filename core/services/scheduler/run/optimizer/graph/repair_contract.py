from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class EliteRepairLimits:
    top_k: int = 3
    max_neighbors_per_elite: int = 8
    max_rounds: int = 3


def new_repair_report() -> Dict[str, Any]:
    return {
        "repair_rounds_completed": 0,
        "repair_stop_reason": None,
    }
