"""Bounded resource calendars using the workbench's exact policy projection."""

from collections import defaultdict
from datetime import date, timedelta

from core.services.capacity.plan_calendar_engine import SnapshotCalendarEngine
from core.services.capacity.plan_calendar_io import CalendarFacts, ProjectionLimit
from core.services.capacity.plan_calendar_limits import MAX_CALENDAR_DATES, MAX_POLICY_CELLS
from core.services.capacity.plan_calendar_windows import apply_resource, policy_projection, unavailable
from data.repositories.schedule_time_sql import overlap_or_bad_time_sql


def resource_calendars(conn, rows, start, end):
    ids = _internal_resource_ids(rows)
    first, last = _projection_dates(start, end)
    limit = _projection_limit_reason(ids, first, last)
    if limit is not None:
        return _unavailable(ids, limit)
    reader = CalendarFacts(conn)
    try:
        _read_calendar_facts(reader, ids, first, last, start, end)
    except ProjectionLimit as exc:
        return _unavailable(ids, str(exc))
    return _project_resources(ids, reader.rows, first, last, start, end)


def _internal_resource_ids(rows):
    """Sorted machine and operator ids referenced by internal-source rows."""
    return {kind: sorted({str(row[kind + "_id"]) for row in rows if row.get(kind + "_id") not in (None, "")
                          and str(row.get("source") or "").strip().lower() == "internal"})
            for kind in ("machine", "operator")}


def _projection_dates(start, end):
    """Dates to project: the day before the window through the last day it covers."""
    first = start.date() - timedelta(days=1) if start.date() > date.min else date.min
    last = (end - timedelta(microseconds=1)).date()
    return first, last


def _projection_limit_reason(ids, first, last):
    """Why the projection is refused before reading, or None when it fits the size limits."""
    dates = (last - first).days + 1
    if dates > MAX_CALENDAR_DATES:
        return "calendar_range_limit"
    if dates * (1 + sum(len(keys) for keys in ids.values())) > MAX_POLICY_CELLS:
        return "calendar_cell_limit"
    return None


def _read_calendar_facts(reader, ids, first, last, start, end):
    """Load calendar, resource and machine downtime facts for the projected dates into ``reader``."""
    reader.calendar(first.isoformat(), last.isoformat(), ids["operator"])
    for kind in ids:
        reader.keyed(kind + "s", "SELECT " + kind + "_id,name,status FROM " +
                     ("Machines" if kind == "machine" else "Operators") +
                     " WHERE " + kind + "_id IN ({marks}) ORDER BY " + kind + "_id", ids[kind])
    reader.keyed("downtimes", "SELECT machine_id,start_time,end_time,status FROM MachineDowntimes md "
                 "WHERE machine_id IN ({marks}) AND (status='active' OR status IS NULL OR status NOT IN ('active','cancelled')) "
                 "AND " + overlap_or_bad_time_sql("md") + " ORDER BY machine_id,start_time,end_time",
                 ids["machine"], (end, start))


def _project_resources(ids, facts, first, last, start, end):
    """Per-resource calendars: machines share the global projection, operators get their own."""
    engine = SnapshotCalendarEngine(facts)
    global_calendar = policy_projection(engine, first, last, start, end)
    downtime = defaultdict(list)
    for row in facts["downtimes"]:
        downtime[row["machine_id"]].append(row)
    result = {}
    for kind, keys in ids.items():
        records = {row[kind + "_id"]: row for row in facts[kind + "s"]}
        for key in keys:
            base = global_calendar if kind == "machine" else policy_projection(engine, first, last, start, end, key)
            result[kind, key] = apply_resource(base, records.get(key), kind, downtime[key] if kind == "machine" else [], start, end)
    return result


def _unavailable(ids, reason):
    return {(kind, key): unavailable("resource_calendar", reason) for kind, keys in ids.items() for key in keys}
