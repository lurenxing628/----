"""Dashboard analysis projected from an already captured source snapshot."""

from collections import defaultdict

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.capacity.plan_calendar_intervals import instant, wire
from core.services.workbench import messages
from core.services.workbench.facts.resource_pressure import (
    MAX_RESOURCE_DAYS,
    daily_resource_pressure,
    pressure_summary,
    range_days,
)

from .downtime import downtime
from .execution import actual


def _time(value):
    try:
        return wire(instant(value))
    except (TypeError, ValueError):
        return None


def _stored_time(value):
    """数据库 created_at 由 SQLite 按 UTC 写入；发给界面前统一走 messages.stored_utc_text 换算，外发格式仍是接口约定的 ISO。"""
    try:
        return messages.stored_utc_text(str(value)).replace(" ", "T")
    except (TypeError, ValueError, OverflowError):  # 9999-12-31 16:00 以后换算北京时间会越过 9999 年
        return None


def _pending(facts, material):
    observations, state = material
    batches = facts.raw["Batches"]
    if batches is None or state["state"] == "unavailable":
        return {"state": "unavailable", "count": None, "known_count": 0, "items": [],
                "issues": state["issues"], "basis": "stored_pending_batch_pool"}
    names = {row["batch_id"]: row["part_name"] for row in batches}
    items = [{**row["source"], "part_label": names[row["source"]["batch_id"]]} for row in observations if row["source"]["stored_status"] == "pending"]
    unknown = sum(row["status"] not in ("pending", "scheduled", "processing", "completed") for row in batches)
    return {"state": "partial" if unknown else "available", "count": None if unknown else len(items),
            "known_count": len(items), "unknown_status_count": unknown, "items": items,
            "issues": [] if not unknown else [{"code": "batch_status_unknown", "message": "有批次的状态填得不对，待排总数算不出来。"}],
            "basis": "stored_pending_batch_pool", "scheduling_input": None}


def _tasks(facts):
    refs = facts.raw["analysis_batch_refs"]
    result = []
    for task, raw in zip(facts.tasks, facts.task_rows):
        result.append({**task, "batch_ref": refs[task["batch_id"]]["ref"],
                       "machine_label": raw["machine_name"], "operator_label": raw["operator_name"],
                       "source": raw["source"], "span_hours": (instant(task["end"]) - instant(task["start"])).total_seconds() / 3600})
    return result


def _resources(facts, tasks, scope):
    grouped, keys = defaultdict(list), {}
    for task, raw in zip(tasks, facts.task_rows):
        if raw["source"] == "internal" and task["machine_ref"] is not None:
            grouped[task["machine_ref"]].append(task)
            keys[task["machine_ref"]] = str(raw["machine_id"])
    private = facts.raw["resource_pressure"]["calendar"].get("resources")
    calendars = private["machine"] if private is not None else {}
    start, end = scope["range_start"], scope["range_end"]
    _, _, day_count = range_days(start, end)
    result = []
    for resource in facts.pressure["resources"] or []:
        if resource["kind"] != "machine":
            continue
        ref = resource["resource_ref"]
        if day_count * len(grouped) > MAX_RESOURCE_DAYS:
            values = {"state": "unavailable", "days": [], "peak_utilization": None,
                      "reason": "calendar_cell_limit", "zero_capacity_days": 0, "unknown_days": day_count}
        else:
            values = daily_resource_pressure(grouped[ref], calendars.get(keys.get(ref)), start, end)
        result.append({"resource_ref": ref, "label": resource["label"], "kind": "machine", **values,
                       "task_refs": [row["task_ref"] for row in grouped[ref]], "issues": resource["issues"]})
    return result


def _downtime_record(raw, ref, machine_ref):
    if ref is None:
        raise WorkbenchCommandRejected("identity_missing", "停机登记编号缺失，请刷新重试。")
    start, end = _time(raw["start_time"]), _time(raw["end_time"])
    valid = raw["status"] == "active" and start is not None and end is not None and start < end
    return {"downtime_ref": ref, "machine_ref": machine_ref, "start": start, "end": end,
            "valid": valid, "reason": raw["reason_detail"], "recorded_at": _stored_time(raw["created_at"]),
            "recorded_at_basis": "local_time"}


def _downtime_overlaps(observations, tasks):
    by_ref = {row["task_ref"]: row for row in tasks}
    overlaps = []
    for item in observations:
        source = item["source"]
        if source["known_overlap_hours"]:
            task = by_ref[source["task_ref"]]
            overlaps.append({"task_ref": task["task_ref"], "batch_ref": task["batch_ref"], "batch_id": task["batch_id"],
                             "process_label": task["process_label"], "source": source})
    return overlaps


def _downtimes(facts, tasks):
    machines = {str(raw["machine_id"]): task["machine_ref"] for task, raw in zip(tasks, facts.task_rows)
                if task["machine_ref"] is not None and raw["source"] == "internal"}
    identities = {row["source_id"]: row["ref"] for row in facts.raw["WorkbenchDashboardDowntimeRefs"] or [] if row["active"] == 1}
    records, issues = [], []
    for raw in facts.raw["MachineDowntimes"] or []:
        if raw["status"] == "cancelled" or str(raw["machine_id"]) not in machines:
            continue
        record = _downtime_record(raw, identities.get(raw["id"]), machines[str(raw["machine_id"])])
        records.append(record)
        if not record["valid"]:
            issues.append({"code": "downtime_invalid", "message": "有停机记录的起止时间或状态填得不对，没有画成有效的停机条。"})
    observations, state = downtime(facts)
    return records, _downtime_overlaps(observations, tasks), issues + state["issues"]


def _projection(facts, material):
    pending = _pending(facts, material)
    if facts.plan_state != "loaded":
        return {"plan": None, "state": facts.plan_state, "time_scope": None, "tasks": [], "resources": [],
                "downtimes": [], "overlaps": [], "deliveries": [], "execution": [], "pending": pending,
                "pressure": {**pressure_summary([]), "count": None}, "issues": facts.plan_issues}
    tasks = _tasks(facts)
    scope = facts.pressure["time_scope"]
    resources = _resources(facts, tasks, scope)
    records, overlaps, issues = _downtimes(facts, tasks)
    batches = {row["batch_id"]: row for row in facts.raw["Batches"] or []}
    deliveries = [{**row, "priority": batches.get(row["batch_id"], {}).get("priority")} for row in facts.delivery["items"]]
    execution, execution_state = actual(facts)
    by_ref = {row["task_ref"]: row for row in tasks}
    # The task already carries identity, label and planned times. Analysis links
    # execution by task_ref; list/detail retain the complete evidence source.
    duplicate_task_fields = {"kind", "plan_ref", "operation_ref", "batch_id", "planned_start", "planned_end"}
    execution = [{"source": {key: value for key, value in row["source"].items() if key not in duplicate_task_fields},
                  "batch_ref": by_ref[row["source"]["task_ref"]]["batch_ref"]} for row in execution]
    return {"plan": facts.plan, "state": "available", "time_scope": scope, "tasks": tasks, "resources": resources,
            "downtimes": records, "overlaps": overlaps, "deliveries": deliveries, "execution": execution, "pending": pending,
            "pressure": pressure_summary(resources), "issues": facts.pressure["issues"] + issues + execution_state["issues"]}


def project_dashboard_analysis(facts, material):
    data = _projection(facts, material)
    data.update(as_of=facts.now.isoformat(timespec="seconds"), capabilities={"view": True, "adopt": False},
                basis="current_official_plan_and_readiness_sources")
    return data
