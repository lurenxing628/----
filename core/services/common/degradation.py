from __future__ import annotations

from core.shared.degradation import (
    STABLE_DEGRADATION_CODES,
    DegradationCollector,
    DegradationEvent,
    degradation_event_to_dict,
    degradation_events_to_dicts,
)

__all__ = [
    "STABLE_DEGRADATION_CODES",
    "DegradationCollector",
    "DegradationEvent",
    "degradation_event_to_dict",
    "degradation_events_to_dicts",
]
