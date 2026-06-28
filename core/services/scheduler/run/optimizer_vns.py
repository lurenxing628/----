from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from core.infrastructure.errors import ValidationError

VNS_SCHEMA_VERSION = 1


@dataclass
class VnsState:
    neighborhoods: Tuple[str, ...]
    neighborhood_index: int = 0
    shake_count: int = 0
    no_improve_count: int = 0
    noop_count: int = 0
    fallback_count: int = 0
    switch_events: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.neighborhoods:
            raise ValidationError("VNS 邻域列表不能为空。", field="neighborhood")

    def current_neighborhood(self) -> str:
        return self.neighborhoods[int(self.neighborhood_index) % len(self.neighborhoods)]

    def current_choice(self) -> Tuple[str, ...]:
        return (self.current_neighborhood(),)

    def record_round(self, *, best_improved: bool, noop: bool, fallback_used: bool) -> Dict[str, Any]:
        old_index = int(self.neighborhood_index) % len(self.neighborhoods)
        if noop:
            self.noop_count += 1
        if fallback_used:
            self.fallback_count += 1

        if best_improved:
            self.no_improve_count = 0
            self.neighborhood_index = 0
            reason = "best_improved_reset"
        else:
            self.no_improve_count += 1
            self.neighborhood_index = (old_index + 1) % len(self.neighborhoods)
            reason = "no_best_improvement_next_neighborhood"

        event = {
            "schema_version": VNS_SCHEMA_VERSION,
            "current_neighborhood": self.neighborhoods[old_index],
            "neighborhood_index": old_index,
            "next_neighborhood": self.current_neighborhood(),
            "next_neighborhood_index": int(self.neighborhood_index),
            "neighborhood_switch_reason": reason,
            "shake_count": int(self.shake_count),
            "no_improve_count": int(self.no_improve_count),
            "noop_count": int(self.noop_count),
            "fallback_count": int(self.fallback_count),
            "best_improved": bool(best_improved),
        }
        if len(self.switch_events) < 50:
            self.switch_events.append(event)
        return event

    def mark_shake(self) -> None:
        self.shake_count += 1

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": VNS_SCHEMA_VERSION,
            "current_neighborhood": self.current_neighborhood(),
            "neighborhood_index": int(self.neighborhood_index),
            "shake_count": int(self.shake_count),
            "no_improve_count": int(self.no_improve_count),
            "noop_count": int(self.noop_count),
            "fallback_count": int(self.fallback_count),
        }


__all__ = ["VNS_SCHEMA_VERSION", "VnsState"]
