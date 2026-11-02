"""Shared selected-plan admission and public resource identities."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

from core.services.capacity.plan_calendar_intervals import instant


@dataclass(frozen=True)
class SelectedPlanContext:
    rows: List[Dict[str, Any]]
    start: datetime
    end: datetime
    time_scope: Dict[str, Any]
    intervals: Dict[Any, Tuple[datetime, datetime]]

    @property
    def calendar_days(self) -> Tuple[date, date, int]:
        first = self.start.date()
        if first > date.min:
            first -= timedelta(days=1)
        last = (
            self.end.date()
            if self.start == self.end
            else (self.end - timedelta(microseconds=1)).date()
        )
        for row in self.rows:
            if row.get("_point_work"):
                at = self.intervals[row["schedule_id"]][0]
                last = max(last, at.date())
        return first, last, (last - first).days + 1


def selected_context(scope, rows, plan_span, *, intervals):
    time_scope = scope.time_scope(plan_span)
    start, end = instant(time_scope["range_start"]), instant(time_scope["range_end"])
    return SelectedPlanContext(rows, start, end, time_scope, intervals)


def resource_ids(rows, kind):
    return sorted({str(row[kind + "_id"]) for row in rows if (row.get("_point_work") or
                   str(row["source"]).strip().lower() == "internal") and row[kind + "_id"] not in (None, "")})


def public_resource(kind, key, identities, raw):
    identity = identities[kind][key]
    return {"kind": kind, "resource_ref": identity.ref, "label": raw["name"] if raw is not None else None}
