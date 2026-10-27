from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class DegradationEvent:
    code: str
    scope: str
    field: Optional[str]
    message: str
    count: int = 1
    sample: Optional[str] = None


class DegradationCollector:
    def __init__(self):
        self._events: List[DegradationEvent] = []
        self._index: Dict[Tuple[str, str, Optional[str], str], int] = {}

    def __bool__(self) -> bool:
        return bool(self._events)

    def add(
        self,
        *,
        code: str,
        scope: str,
        field: str,
        message: str,
        count: int = 1,
        sample: Any = None,
    ) -> DegradationEvent:
        event = DegradationEvent(
            code=str(code),
            scope=str(scope),
            field=field,
            message=str(message),
            count=max(1, int(count)),
            sample=sample,
        )

        key = (event.code, event.scope, event.field, event.message)
        existing_index = self._index.get(key)
        if existing_index is None:
            self._index[key] = len(self._events)
            self._events.append(event)
            return event

        existing = self._events[existing_index]
        merged = DegradationEvent(
            code=existing.code,
            scope=existing.scope,
            field=existing.field,
            message=existing.message,
            count=existing.count + event.count,
            sample=existing.sample if existing.sample is not None else event.sample,
        )
        self._events[existing_index] = merged
        return merged

    def to_list(self) -> List[DegradationEvent]:
        return list(self._events)

    def to_counters(self) -> Dict[str, int]:
        counters: Dict[str, int] = {}
        for event in self._events:
            counters[event.code] = counters.get(event.code, 0) + event.count
        return counters


def _degradation_event_to_dict(event: DegradationEvent) -> Dict[str, Any]:
    return {
        "code": str(event.code),
        "scope": str(event.scope),
        "field": event.field,
        "message": str(event.message),
        "count": event.count,
        "sample": event.sample,
    }


def degradation_events_to_dicts(events: Iterable[DegradationEvent]) -> List[Dict[str, Any]]:
    return [_degradation_event_to_dict(event) for event in events]
