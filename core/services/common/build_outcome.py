from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Generic, Iterable, List, Mapping, Optional, TypeVar

from core.services.common.degradation import DegradationCollector, DegradationEvent

T = TypeVar("T")


@dataclass(init=False)
class BuildOutcome(Generic[T]):
    value: T
    events: List[DegradationEvent] = field(default_factory=list)
    counters: Dict[str, int] = field(default_factory=dict)
    empty_reason: Optional[str] = None

    def __init__(
        self,
        value: T,
        events: Optional[Iterable[DegradationEvent]] = None,
        counters: Optional[Mapping[str, int]] = None,
        empty_reason: Optional[str] = None,
    ) -> None:
        self.value = value
        self.events = list(events or [])
        self.counters = dict(counters or {})
        self.empty_reason = empty_reason
        self.__post_init__()

    def __post_init__(self) -> None:
        collector = DegradationCollector(self.events)
        self.events = collector.to_list()

        merged_counters = collector.to_counters()
        external_counters = {str(key): int(value) for key, value in list(self.counters.items())}
        overlapping_keys = sorted(set(merged_counters.keys()) & set(external_counters.keys()))
        if overlapping_keys:
            joined = "、".join(overlapping_keys)
            raise ValueError(f"BuildOutcome.counters 与 events 导出的原因码重复：{joined}")

        merged_counters.update(external_counters)
        self.counters = merged_counters

    @classmethod
    def from_collector(
        cls: type[BuildOutcome[T]],
        value: T,
        collector: Optional[DegradationCollector] = None,
        *,
        counters: Optional[Dict[str, int]] = None,
        empty_reason: Optional[str] = None,
    ) -> BuildOutcome[T]:
        """
        从 DegradationCollector 构建 BuildOutcome。

        counters 仅允许补充 collector 事件之外的额外统计；
        若键名与 collector 导出的原因码重复，将直接抛出异常。
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
