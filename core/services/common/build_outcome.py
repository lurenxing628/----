from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Generic, List, Optional, TypeVar

from core.services.common.degradation import DegradationCollector, DegradationEvent

T = TypeVar("T")


@dataclass
class BuildOutcome(Generic[T]):
    value: T
    events: List[DegradationEvent] = field(default_factory=list)
    counters: Dict[str, int] = field(default_factory=dict)
    empty_reason: Optional[str] = None

    def __post_init__(self) -> None:
        # 合并规则：先根据 events 归并退化事件并生成原因码计数，
        # 再把外部 counters 逐项叠加到事件计数之上。
        # 注意：若 counters 中的键与 events 导出的原因码重叠，会产生双倍计数。
        # from_collector() 的 counters 参数仅应用于追加 collector 事件之外的额外统计。
        collector = DegradationCollector(self.events)
        self.events = collector.to_list()

        merged_counters = collector.to_counters()
        for key, value in list(self.counters.items()):
            merged_counters[str(key)] = merged_counters.get(str(key), 0) + int(value)
        self.counters = merged_counters

    @classmethod
    def from_collector(
        cls,
        value: T,
        collector: Optional[DegradationCollector] = None,
        *,
        counters: Optional[Dict[str, int]] = None,
        empty_reason: Optional[str] = None,
    ) -> BuildOutcome[T]:
        """
        从 DegradationCollector 构建 BuildOutcome。

        counters 仅用于补充 collector 事件之外的额外统计。
        若 counters 中的键与 collector 事件原因码重叠，__post_init__ 会继续叠加计数。
        """
        return cls(
            value=value,
            events=collector.to_list() if collector is not None else [],
            counters=dict(counters or {}),
            empty_reason=empty_reason,
        )

    @property
    def has_events(self) -> bool:
        return bool(self.events)
