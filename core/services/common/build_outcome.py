from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Generic, List, Optional, TypeVar

from core.shared.degradation import DegradationCollector, DegradationEvent

T = TypeVar("T")


@dataclass
class BuildOutcome(Generic[T]):
    value: T
    events: List[DegradationEvent] = field(default_factory=list)
    counters: Dict[str, int] = field(default_factory=dict)
    empty_reason: Optional[str] = None

    @classmethod
    def from_collector(
        cls: type[BuildOutcome[T]],
        value: T,
        collector: DegradationCollector,
    ) -> BuildOutcome[T]:
        """取得事件快照及对应的原因码计数。"""
        return cls(
            value=value,
            events=collector.to_list(),
            counters=collector.to_counters(),
        )

    @property
    def has_events(self) -> bool:
        return bool(self.events)
