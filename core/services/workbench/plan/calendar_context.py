"""Shared selected-plan admission and public resource identities."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

from core.services.capacity.plan_calendar_intervals import instant
from core.shared.local_datetime import us_to_datetime


@dataclass(frozen=True)
class SelectedPlanContext:
    rows: List[Dict[str, Any]]
    start: datetime
    end: datetime
    time_scope: Dict[str, Any]

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
            if row["is_point_event"]:
                last = max(last, us_to_datetime(row["start_us"]).date())
        return first, last, (last - first).days + 1


def selected_context(scope, rows, plan_span):
    time_scope = scope.time_scope(plan_span)
    start, end = instant(time_scope["range_start"]), instant(time_scope["range_end"])
    return SelectedPlanContext(rows, start, end, time_scope)


def resource_ids(rows, kind):
    return sorted({
        str(row[kind + "_id"])
        for row in rows
        if row["source"] == "internal" and row[kind + "_id"] not in (None, "")
    })


def public_resource(kind, key, identities, raw):
    identity = identities[kind][key]
    return {"kind": kind, "resource_ref": identity.ref, "label": raw["name"] if raw is not None else None}
