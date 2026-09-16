"""Candidate comparison metrics from the same verified admission capture only."""

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from core.algorithms.evaluation import _count_changeovers
from core.algorithms.types import ScheduleResult
from core.infrastructure.errors import ValidationError
from core.models.workbench_run_candidate import local_time
from core.services.capacity.plan_calendar_engine import SnapshotCalendarEngine
from core.services.capacity.plan_calendar_intervals import instant
from core.services.capacity.plan_calendar_windows import apply_resource, policy_projection, unavailable

from .dashboard_resource_metrics import MAX_RESOURCE_DAYS, daily_resource_pressure, range_days
from .run_candidate_facts import _table
from .run_candidate_values import stored_json


def scoped_rows(rows, batch_refs, start, end):
    low, high = local_time(start), local_time(end)
    result = []
    for row in rows:
        if row["batch_ref"] not in batch_refs:
            continue
        if row["start"] is None or row["end"] is None:
            result.append(row)
            continue
        first, last = local_time(row["start"]), local_time(row["end"])
        if first == last:
            if low <= first < high:
                result.append(row)
        elif first < high and last > low:
            result.append(row)
    return result


def changeovers(rows, facts, available=True):
    if not available:
        return {"value": None, "reason": "no_admission_baseline"}
    machines = defaultdict(list)
    for row in rows:
        if row["source"] == "external":
            continue
        machine = row["machine"]
        if row["source"] != "internal" or not machine or machine["ref"] is None:
            return {"value": None, "reason": "assignment_resource_unknown"}
        if not _proven_interval(row) or not row["process_label"] or row["sequence"] is None:
            return {"value": None, "reason": "comparison_metadata_unknown"}
        if row["start"] == row["end"]:
            continue
        op_id = facts.operations[row["operation_ref"]]
        machines[machine["ref"]].append(ScheduleResult(
            op_id=op_id, op_code=str(op_id), batch_id=row["batch_ref"], seq=int(row["sequence"]),
            machine_id=machine["ref"], start_time=local_time(row["start"]), end_time=local_time(row["end"]),
            source="internal", op_type_name=row["process_label"]))
    return {"value": _count_changeovers(machines), "reason": None}


def _global_rows(archive, first, last):
    rows = _table(archive, "WorkCalendar")
    if rows is None:
        return None
    selected = []
    for row in rows:
        raw = row["date"]
        try:
            parsed = date.fromisoformat(raw) if isinstance(raw, str) else None
        except ValueError:
            parsed = None
        if parsed is None or parsed.isoformat() != raw or first <= parsed <= last:
            selected.append(row)
    return selected


def _downtime_rows(rows, machine, start, end):
    selected = []
    for row in rows:
        if row["machine_id"] != machine or row["status"] == "cancelled":
            continue
        try:
            low, high = instant(row["start_time"]), instant(row["end_time"])
            intersects = low < end and high > start
        except (TypeError, ValueError):
            intersects = True
        if intersects:
            selected.append(row)
    return selected


def archived_calendars(capture, facts, refs, start, end):
    low, high, days = range_days(start, end)
    if days > 3660 or days * len(refs) > MAX_RESOURCE_DAYS:
        return {ref: unavailable("admission_machine_calendar", "calendar_cell_limit") for ref in refs}
    archive = stored_json(capture["facts_text"])
    first = low.date() - timedelta(days=1) if low.date() > date.min else low.date()
    last = (high - timedelta(microseconds=1)).date()
    calendar_start = datetime.combine(low.date(), time.min)
    calendar_end = datetime.combine(last + timedelta(days=1), time.min) if last < date.max else datetime.max
    global_rows, stops = _global_rows(archive, first, last), _table(archive, "MachineDowntimes")
    if global_rows is None or stops is None:
        return {ref: unavailable("admission_machine_calendar", "calendar_unavailable") for ref in refs}
    try:
        engine = SnapshotCalendarEngine({"global": global_rows, "personal": [], "profiles": [], "patterns": []})
        base = policy_projection(engine, first, last, calendar_start, calendar_end)
    except (ValidationError, ValueError, TypeError, KeyError):
        base = unavailable("admission_machine_calendar", "calendar_invalid")
    keys = {ref: key for (kind, key), ref in facts.entity_refs.items() if kind == "machine"}
    return {ref: apply_resource(base, facts.tables["Machines"].get(keys.get(ref)), "machine",
                                _downtime_rows(stops, keys.get(ref), calendar_start, calendar_end), calendar_start, calendar_end) for ref in refs}


def _by_machine(rows):
    grouped = defaultdict(list)
    for row in rows:
        if row["source"] == "internal" and row["machine"] and row["machine"]["ref"]:
            grouped[row["machine"]["ref"]].append(row)
    return grouped


def _proven_interval(row):
    if row["start"] is None or row["end"] is None or row.get("interval_comparable") is False:
        return False
    if local_time(row["start"]) < local_time(row["end"]):
        return True
    return (row["start"] == row["end"] and row.get("event_kind") == "point"
            and row.get("occupies_resources") is False)


def _valid_intervals(rows):
    return all(_proven_interval(row) for row in rows)


def resource_comparison(before, after, capture, facts, start, end, baseline_available):
    refs = {}
    for row in before + after:
        if row["source"] == "internal" and row["machine"] and row["machine"]["ref"]:
            refs[row["machine"]["ref"]] = row["machine"]["label"]
    calendars = archived_calendars(capture, facts, refs, start, end)
    _, _, days = range_days(start, end)
    old, new = _by_machine(before), _by_machine(after)
    result = []
    for ref, label in sorted(refs.items()):
        selected_before, selected_after = old[ref], new[ref]
        if days * len(refs) > MAX_RESOURCE_DAYS:
            sides = [{"state": "unavailable", "days": [], "peak_utilization": None, "reason": "calendar_cell_limit",
                      "zero_capacity_days": 0, "unknown_days": days} for _ in range(2)]
        else:
            sides = [daily_resource_pressure(rows if _valid_intervals(rows) else [], calendars[ref] if enabled and _valid_intervals(rows) else None, start, end)
                     for rows, enabled in ((selected_before, baseline_available), (selected_after, True))]
        previous, current = (side["peak_utilization"] for side in sides)
        result.append({"resource_ref": ref, "label": label, "before": sides[0], "after": sides[1],
                       "delta": None if previous is None or current is None else round(current - previous, 6)})
    return result
