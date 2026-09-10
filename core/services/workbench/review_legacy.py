"""Legacy pause/exception display only; completion belongs to ExecutionProjection."""

from collections import defaultdict
from typing import Optional, TypedDict

from core.models.operation_execution_labels import (
    exception_reason_label,
    handling_status_label,
    severity_label,
    suggest_reschedule_label,
)

from .review_values import local_time, minutes


class LegacyReview(TypedDict):
    pause_duration_minutes: Optional[float]
    exception_reason: Optional[str]
    exception_severity: Optional[str]
    exception_impact_minutes: Optional[int]
    exception_handling_status: Optional[str]
    exception_suggest_reschedule: Optional[str]
    exception_machine_ref: Optional[str]
    exception_operator_ref: Optional[str]


def _pause_duration(timed_rows):
    groups = defaultdict(list)
    for time, row in timed_rows:
        groups[row["recorded_against_task_ref"]].append((time, row))
    duration, open_pause = 0, False
    for events in groups.values():
        paused = None
        for time, row in events:
            if row["event_type"] == "pause":
                paused = time
            elif paused and row["event_type"] in ("resume", "finish"):
                elapsed = minutes(paused, time)
                if elapsed is None or elapsed < 0:
                    return None
                duration += elapsed
                paused = None
        open_pause = open_pause or paused is not None
    return None if open_pause else round(duration, 2)


def legacy_review(projection) -> LegacyReview:
    rows = projection["legacy_facts"]
    unavailable = any(gap["code"] in ("invalid_legacy_sequence", "legacy_identity_unresolved")
                      for gap in projection["data_gaps"])
    result: LegacyReview = {"pause_duration_minutes": None, "exception_reason": None, "exception_severity": None,
              "exception_impact_minutes": None, "exception_handling_status": None,
              "exception_suggest_reschedule": None, "exception_machine_ref": None, "exception_operator_ref": None}
    if not rows or unavailable:
        return result
    timed_rows = []
    for row in rows:
        time = local_time(row["event_time"])
        if time is None:
            return result
        timed_rows.append((time, row))
    result["pause_duration_minutes"] = _pause_duration(timed_rows)
    exceptions = [(time, row) for time, row in timed_rows if row["event_type"] == "exception"]
    if exceptions:
        _, row = max(exceptions, key=lambda item: item[0])
        result.update({"exception_reason": exception_reason_label(row["reason_code"]),
            "exception_severity": severity_label(row["severity"]), "exception_impact_minutes": row["impact_minutes"],
            "exception_handling_status": handling_status_label(row["handling_status"]),
            "exception_suggest_reschedule": suggest_reschedule_label(row["suggest_reschedule"]),
            "exception_machine_ref": row["actual_machine_ref"], "exception_operator_ref": row["actual_operator_ref"]})
    return result
