from __future__ import annotations

from core.models.scheduler_degradation_messages import (
    DOWNTIME_EXTEND_FAILED_MESSAGE,
    DOWNTIME_LOAD_FAILED_MESSAGE,
    FREEZE_WINDOW_DEGRADED_MESSAGE,
    FREEZE_WINDOW_PARTIALLY_APPLIED_MESSAGE,
    RESOURCE_POOL_BUILD_FAILED_MESSAGE,
    SCHEDULE_OPERATION_FAILED_MESSAGE,
    is_public_freeze_degradation_message,
    public_degradation_event_message,
    public_degradation_events,
    public_summary_merge_error_code,
    public_summary_warning_messages,
)

__all__ = [
    "DOWNTIME_EXTEND_FAILED_MESSAGE",
    "DOWNTIME_LOAD_FAILED_MESSAGE",
    "FREEZE_WINDOW_DEGRADED_MESSAGE",
    "FREEZE_WINDOW_PARTIALLY_APPLIED_MESSAGE",
    "SCHEDULE_OPERATION_FAILED_MESSAGE",
    "RESOURCE_POOL_BUILD_FAILED_MESSAGE",
    "is_public_freeze_degradation_message",
    "public_degradation_events",
    "public_degradation_event_message",
    "public_summary_merge_error_code",
    "public_summary_warning_messages",
]
