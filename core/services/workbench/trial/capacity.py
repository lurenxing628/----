"""Real calendar windows and selected-trial occupancy, never fixed sample loads."""

from collections import defaultdict
from datetime import datetime, timedelta

from core.errors import AppError
from core.services.capacity.plan_calendar_windows import apply_resource, available_intervals, policy_projection
from core.services.capacity.resource_utilization_metrics import ResourceUtilizationMetrics

from .calendar import calendar_engine


def trial_capacity(rows, live):
    start = min(datetime.fromisoformat(row["current"]["start"]) for row in rows)
    end = max(datetime.fromisoformat(row["current"]["end"]) for row in rows)
    groups = _groups(rows)
    scope = {"start": start.isoformat(), "end": end.isoformat(), "basis": "selected_trial_only"}
    days = (end.date() - start.date()).days + 2
    if days < 1 or days * max(len(groups), 1) > 50000:
        return {**scope, "state": "unavailable", "resources": [],
                "reason": "日历计算范围超过 50000 个资源日，暂无法计算资源占用率。"}
    try:
        engine = calendar_engine(live["facts"]["tables"])
        first = start.date() - timedelta(days=1)
    except (AppError, ValueError, TypeError, OverflowError):
        return {**scope, "state": "unavailable", "resources": [], "reason": "日历数据无效，暂无法计算资源占用率。"}
    output = _projections(engine, groups, live["facts"]["tables"], first, start, end)
    return {**scope, "state": "available" if all(row["state"] == "available" for row in output) else "partial",
            "resources": output, "reason": None}


def _groups(rows):
    groups = defaultdict(list)
    for row in rows:
        if row["original"]["operation"]["source"] != "internal":
            continue
        value = row["current"]
        for kind in ("machine", "operator"):
            if value[kind + "_ref"] is not None:
                groups[kind, value[kind + "_id"], value[kind + "_ref"]].append(
                    (datetime.fromisoformat(value["start"]), datetime.fromisoformat(value["end"])))
    return groups


def _projections(engine, groups, sources, first, start, end):
    records = {kind: {row[kind + "_id"]: row for row in sources[table]}
               for kind, table in (("machine", "Machines"), ("operator", "Operators"))}
    downtimes = defaultdict(list)
    for row in sources["MachineDowntimes"]:
        if row["status"] != "cancelled":
            downtimes[row["machine_id"]].append(row)
    output, global_calendar = [], None
    for (kind, key, ref), intervals in groups.items():
        if kind == "machine":
            if global_calendar is None:
                global_calendar = policy_projection(engine, first, end.date(), start, end)
            base = global_calendar
        else:
            base = policy_projection(engine, first, end.date(), start, end, operator_id=key)
        calendar = apply_resource(base, records[kind].get(key), kind, downtimes[key] if kind == "machine" else [], start, end)
        output.append(_resource(kind, ref, intervals, calendar, start, end))
    return output


def _resource(kind, ref, intervals, calendar, start, end):
    valid = [(start, end) for start, end in intervals if start < end]
    metrics = ResourceUtilizationMetrics(valid, available_intervals(calendar))
    # Trial keeps full precision and reports the wall-clock overlap span. The
    # shared overlap_hours instead measures the excess load inside the calendar.
    values = metrics.window(start, end, precision=None)
    return {"resource_type": kind, "resource_ref": ref, "state": calendar["state"], "calendar": calendar,
            "arranged_hours": values["span_summed_hours"], "occupied_hours": values["span_occupied_hours"],
            "overlap_hours": values["span_overlap_hours"],
            "available_hours": values["available_hours"], "available_occupied_hours": values["occupied_hours"],
            "outside_available_hours": values["outside_calendar_hours"],
            "utilization": values["utilization_ratio"],
            "segments": [{"start": start.isoformat(), "end": end.isoformat(), "concurrent_operations": count}
                         for start, end, count in metrics.segments]}
