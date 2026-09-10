"""Actual registered downtime versus the exact current formal task intervals."""

from collections import defaultdict

from core.models.workbench_dashboard import MAX_FACT_ROWS, bounded
from core.services.workbench.dashboard_facts import source_issue
from core.services.workbench.dashboard_projection import category, observation
from core.services.workbench.plan_calendar_intervals import IntervalIndex, instant, union


def _index(raw, refs):
    identities = {row["source_id"]: row for row in refs if row["active"] == 1}
    by_machine, invalid = defaultdict(list), set()
    for row in raw:
        if row["status"] == "cancelled":
            continue
        try:
            low, high = instant(row["start_time"]), instant(row["end_time"])
            if row["status"] != "active" or low >= high or row["id"] not in identities:
                raise ValueError()
            by_machine[row["machine_id"]].append((low, high, row))
        except (TypeError, ValueError):
            invalid.add(row["machine_id"])
    indexes = {key: IntervalIndex(union([(low, high) for low, high, _ in values])) for key, values in by_machine.items()}
    return {"identities": identities, "windows": by_machine, "invalid": invalid, "indexes": indexes}


def _overlaps(windows, identities, low, high):
    details = []
    for start, end, row in windows:
        if start < high and end > low:
            details.append({"downtime_ref": identities[row["id"]]["ref"], "start": start.isoformat(timespec="seconds"),
                            "end": end.isoformat(timespec="seconds"), "overlap_start": max(start, low).isoformat(timespec="seconds"),
                            "overlap_end": min(end, high).isoformat(timespec="seconds"),
                            "reason": row["reason_detail"] if type(row["reason_detail"]) is str else None})
    return details


def _task(task, raw_task, resource_rows, index):
    key = raw_task["machine_id"]
    low, high = instant(task["start"]), instant(task["end"])
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
    code, message = {True: ("downtime_overlap", "正式安排与有效停机窗口重叠；重叠时长不代表最终延期。"),
                     None: ("downtime_unknown", "停机或设备依据无效，尚不能判断。"),
                     False: ("no_overlap", "正式安排与已登记有效停机无重叠。")}[active]
    result = observation("downtime", task["task_ref"], task["batch_id"] + " · " + task["process_label"], source, active, code, message,
                         {"task": raw_task, "resource": resource, "downtimes": [row for _, _, row in windows],
                          "identity": [identities[row["id"]] for _, _, row in windows]})
    return result, bad, len(details)


def downtime(facts):
    if facts.plan_state != "loaded":
        return [], category(facts.plan_state, issues=facts.plan_issues)
    raw, refs, machines = (facts.raw[key] for key in ("MachineDowntimes", "WorkbenchDashboardDowntimeRefs", "Machines"))
    if any(value is None for value in (raw, refs, machines)):
        return [], category("unavailable", issues=[source_issue("source_not_read", "停机台账或资源事实尚未读取。")])
    index, resource_rows = _index(raw, refs), {row["machine_id"]: row for row in machines}
    result, unknown, intersections = [], 0, 0
    for task, raw_task in zip(facts.tasks, facts.task_rows):
        if raw_task["source"] == "external":
            continue
        item, bad, count = _task(task, raw_task, resource_rows, index)
        result.append(item)
        unknown += bad
        intersections += count
        bounded(range(intersections), MAX_FACT_ROWS)
    return result, category("loaded" if result else "no_data", assessed=len(result) - unknown, unknown=unknown)
