"""Actual registered downtime versus the exact current formal task intervals."""

from bisect import bisect_left, bisect_right
from collections import defaultdict

from core.models.workbench_dashboard import MAX_FACT_ROWS, bounded
from core.services.capacity.plan_calendar_intervals import IntervalIndex, instant, union

from .projection import category, observation


def _instant(value):
    try:
        return instant(value)
    except ValueError:
        return None


def downtime_index(raw, refs):
    """Parse each non-cancelled downtime's two endpoints once, independently; an unreadable endpoint is None.

    ``parsed`` keeps every non-cancelled row in rowid order, invalid ones included, for analysis records;
    windows, invalid machines and interval indexes are derived from it.
    """
    identities = {row["source_id"]: row for row in refs if row["active"] == 1}
    by_machine, all_rows, identity_rows, invalid, parsed = defaultdict(list), defaultdict(list), defaultdict(list), set(), []
    for row in refs:
        identity_rows[row["source_id"]].append(row)
    for row in raw:
        all_rows[row["machine_id"]].append(row)
        if row["status"] == "cancelled":
            continue
        low, high = _instant(row["start_time"]), _instant(row["end_time"])
        parsed.append((row, low, high))
        if (row["status"] != "active" or low is None or high is None or low >= high
                or row["id"] not in identities):
            invalid.add(row["machine_id"])
        else:
            by_machine[row["machine_id"]].append((low, high, row))
    indexes = {key: IntervalIndex.from_normalized(union([(low, high) for low, high, _ in values]))
               for key, values in by_machine.items()}
    machine_identities = defaultdict(list, {
        key: [identity for row in values for identity in identity_rows[row["id"]]]
        for key, values in all_rows.items()})
    return {"identities": identities, "parsed": parsed, "windows": by_machine, "invalid": invalid, "indexes": indexes,
            "all_rows": all_rows, "machine_identities": machine_identities}


def _overlaps(windows, identities, low, high):
    details = []
    for start, end, row in windows:
        if start < high and end > low:
            details.append({"downtime_ref": identities[row["id"]]["ref"], "start": start.isoformat(),
                            "end": end.isoformat(), "overlap_start": max(start, low).isoformat(),
                            "overlap_end": min(end, high).isoformat(),
                            "reason": row["reason_detail"] if type(row["reason_detail"]) is str else None})
    return details


def _task(task, raw_task, resource_rows, index, *, interval):
    key = raw_task["machine_id"]
    low, high = interval
    resource = resource_rows.get(key)
    bad = key in index["invalid"] or resource is None or raw_task["source"] != "internal"
    amount = index["indexes"][key].hours_between(low, high) if key in index["indexes"] else 0.0
    windows, identities = index["windows"][key], index["identities"]
    details = _overlaps(windows, identities, low, high) if amount else []
    source = {"kind": "registered_downtime_overlap", "plan_ref": task["plan_ref"], "task_ref": task["task_ref"],
              "operation_ref": task["operation_ref"], "machine_ref": task["machine_ref"],
              "planned_start": task["start"], "planned_end": task["end"], "downtimes": details,
              "overlap_hours": amount if not bad else None, "known_overlap_hours": amount,
              "delay_after_reschedule_hours": None, "basis": "union_of_registered_downtime_intersections"}
    active = True if amount else None if bad else False
    code, message = {True: ("downtime_overlap", "计划安排与停机时段重叠。"),
                     None: ("downtime_unknown", "停机记录或设备资料填得不对，还判断不了。"),
                     False: ("no_overlap", "正式安排与已登记有效停机无重叠。")}[active]
    result = observation("downtime", task["task_ref"], task["batch_id"] + " · " + task["process_label"], source, active, code, message,
                         {"task": raw_task, "resource": resource, "downtimes": index["all_rows"][key],
                          "identity": index["machine_identities"][key]})
    return result, bad, len(details)


def downtime_overlap_count(facts):
    if "downtime" in facts._observations:
        return sum(1 for item in facts._observations["downtime"][0] if item["source"]["known_overlap_hours"])
    index = facts.downtime_index()
    bounds = {
        key: (
            sorted(start for start, _, _ in windows),
            sorted(end for _, end, _ in windows),
        )
        for key, windows in index["windows"].items()
    }
    overlaps, intersections = 0, 0
    for raw_task in facts.task_rows:
        if raw_task["source"] == "external":
            continue
        key = raw_task["machine_id"]
        if key not in index["indexes"]:
            continue
        low, high = facts.task_intervals[raw_task["schedule_id"]]
        if index["indexes"][key].hours_between(low, high):
            overlaps += 1
            starts, ends = bounds[key]
            intersections += bisect_left(starts, high) - bisect_right(ends, low)
            bounded(range(intersections), MAX_FACT_ROWS)
    return overlaps


def downtime(facts):
    if facts.plan_state != "loaded":
        return [], category(facts.plan_state, issues=facts.plan_issues)
    index, resource_rows = facts.downtime_index(), {row["machine_id"]: row for row in facts.raw["Machines"]}
    result, unknown, intersections = [], 0, 0
    for task, raw_task in zip(facts.tasks, facts.task_rows):
        if raw_task["source"] == "external":
            continue
        item, bad, count = _task(
            task, raw_task, resource_rows, index,
            interval=facts.task_intervals[raw_task["schedule_id"]],
        )
        result.append(item)
        unknown += bad
        intersections += count
        bounded(range(intersections), MAX_FACT_ROWS)
    return result, category("loaded" if result else "no_data", assessed=len(result) - unknown, unknown=unknown)
