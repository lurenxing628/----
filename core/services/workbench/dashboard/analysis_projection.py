"""Dashboard analysis projected from an already captured source snapshot."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import DashboardAnalysisQuery, page
from core.services.capacity.plan_calendar_intervals import instant, wire
from core.services.workbench import messages
from core.services.workbench.facts.current_resource_calendar import current_resource_calendar
from core.services.workbench.facts.resource_pressure import _legacy_day, pressure_from_index, pressure_summary
from core.services.workbench.facts.resource_projection import (
    RESOURCE_METRIC_VERSION,
    ResourceTaskIndex,
    resource_cohort,
    resource_summary,
)

from .calendar_capture import resource_pressure_tasks


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
                       "source": raw["source"] if type(raw["source"]) is str else None,
                       "span_hours": (instant(task["end"]) - instant(task["start"])).total_seconds() / 3600})
    return result


def _resources(facts, scope, query):
    cohort = facts._resource_pressure_cohort
    normalized = None
    if cohort is None:
        normalized = resource_pressure_tasks(facts)
        cohort = resource_cohort([normalized])
    start, end = scope["range_start"], scope["range_end"]
    cache = facts._resource_pressure_cache
    needed = [resource for resource in cohort if (resource["kind"], resource["ref"], start, end) not in cache
              or query.section == "resource_days" and query.resource_ref == resource["ref"]]
    projected = {}
    identity_issues = facts._resource_pressure_identity_issues
    if needed:
        index = None
        if facts._resource_pressure_index is not None and facts._resource_pressure_window == (start, end):
            index = facts._resource_pressure_index
        if index is None:
            if normalized is None:
                normalized = resource_pressure_tasks(facts)
            index = ResourceTaskIndex(normalized, start, end, source="current_transaction_snapshot")
        identity_issues = index.identity_issues
        factory = current_resource_calendar(facts, scope)
        specs = [dict(row, saved_id=factory.bindings.get((row["kind"], row["ref"]))) for row in needed] if factory else []
        calendars = factory.iter_resources(specs, start, end) if factory else ((row["ref"], None) for row in needed)
        previous_retain = index.retain_statistics_values
        index.retain_statistics_values = (query.section == "resource_days")
        for resource, (_, calendar) in zip(needed, calendars):
            key = resource["kind"], resource["ref"]
            cache_key = key + (start, end)
            if cache_key not in cache:
                cache[cache_key] = pressure_from_index(index, resource, calendar, include_days=False)
            values = cache[cache_key]
            if query.section == "resource_days" and query.resource_ref == resource["ref"]:
                values = dict(values, days=[_legacy_day(day) for day in index.days(resource, calendar)])
            projected[key] = values
            index._measurements.pop(key)
        index.retain_statistics_values = previous_retain
    result = []
    for resource in cohort:
        key = resource["kind"], resource["ref"]
        values = projected[key] if key in projected else cache[key + (start, end)]
        result.append({"resource_ref": resource["ref"], "label": resource["label"], "kind": resource["kind"],
                       **values, "task_refs": [], "issues": values["window_metrics"]["issues"]})
    windows = [row["window_metrics"] for row in result]
    common = {"metric_version": RESOURCE_METRIC_VERSION, "source": "current_transaction_snapshot",
              "start": start, "end": end, "time_basis": "factory_local", "cohort_basis": "current_official_plan",
              "cohort": cohort,
              **{kind: resource_summary(windows, kind=kind,
                                        identity_issues=identity_issues) for kind in ("machine", "operator")}}
    return result, common


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
    labels = {str(row["machine_id"]): row["machine_name"] for row in facts.task_rows}
    identities = {row["source_id"]: row["ref"] for row in facts.raw["WorkbenchDashboardDowntimeRefs"] or [] if row["active"] == 1}
    records, issues = [], []
    for raw in facts.raw["MachineDowntimes"] or []:
        if raw["status"] == "cancelled" or str(raw["machine_id"]) not in machines:
            continue
        record = _downtime_record(raw, identities.get(raw["id"]), machines[str(raw["machine_id"])])
        record["machine_label"] = labels.get(str(raw["machine_id"]))
        records.append(record)
        if not record["valid"]:
            issues.append({"code": "downtime_invalid", "message": "有停机记录的起止时间或状态填得不对，没有画成有效的停机条。"})
    observations, state = facts.observations("downtime")
    return records, _downtime_overlaps(observations, tasks), issues + state["issues"]


def _projection(facts, material, query):
    pending = _pending(facts, material)
    if facts.plan_state != "loaded":
        return {"plan": None, "state": facts.plan_state, "time_scope": None, "tasks": [], "resources": [],
                "downtimes": [], "overlaps": [], "deliveries": [], "execution": [], "pending": pending,
                "pressure": {**pressure_summary([]), "count": None}, "resource_common": None, "issues": facts.plan_issues}
    tasks = _tasks(facts)
    scope = facts.pressure["time_scope"]
    resources, resource_common = _resources(facts, scope, query)
    records, overlaps, issues = _downtimes(facts, tasks)
    deliveries = facts.delivery["items"]
    execution, execution_state = facts.observations("actual")
    by_ref = {row["task_ref"]: row for row in tasks}
    # The task already carries identity, label and planned times. Analysis links
    # execution by task_ref; list/detail retain the complete evidence source.
    duplicate_task_fields = {"kind", "plan_ref", "operation_ref", "batch_id", "planned_start", "planned_end"}
    execution = [{"source": {key: value for key, value in row["source"].items() if key not in duplicate_task_fields},
                  "batch_ref": by_ref[row["source"]["task_ref"]]["batch_ref"]} for row in execution]
    return {"plan": facts.plan, "state": "available", "time_scope": scope, "tasks": tasks, "resources": resources,
            "downtimes": records, "overlaps": overlaps, "deliveries": deliveries, "execution": execution, "pending": pending,
            "pressure": pressure_summary(resources), "resource_common": resource_common, "issues": facts.pressure["issues"] + issues + execution_state["issues"]}


def _view(data, query):
    """Page each detail in its own units; complete summaries stay independent."""
    totals = {key: len(data[key]) for key in ("tasks", "resources", "downtimes", "overlaps", "deliveries", "execution")}
    totals.update(pending=data["pending"]["known_count"], resource_days=0)
    result = {**data, **{key: [] for key in ("tasks", "resources", "downtimes", "overlaps", "deliveries", "execution")},
              "pending": {**data["pending"], "items": []}}
    section = query.section
    if section == "resource_days":
        resource = next((row for row in data["resources"] if row["resource_ref"] == query.resource_ref), None)
        if resource is None:
            raise WorkbenchCommandRejected("entity_not_found", "所选资源不在当前正式计划范围内，请刷新后重新选择。", 404)
        total = totals["resource_days"] = len(resource["days"])
    elif section == "downtime":
        total = max(totals["overlaps"], totals["downtimes"])
    else:
        total = 0 if section == "overview" else totals[{"delivery": "deliveries", "timeline": "tasks", "actual": "execution",
                                                     "material": "pending", "pressure": "resources"}[section]]
    number = query.number
    if query.locate_batch_ref is not None:
        index = next((index for index, task in enumerate(data["tasks"])
                      if task["batch_ref"] == query.locate_batch_ref and task["source"] == "internal" and task["machine_ref"]), None)
        if index is None:
            raise WorkbenchCommandRejected("entity_not_found", "所选批次在当前正式计划中没有可显示的设备安排。", 404)
        number = index // query.size + 1
    _, pagination = page(range(total), number, query.size, [])
    low, high = (number - 1) * query.size, number * query.size
    if section == "delivery":
        result["deliveries"] = data["deliveries"][low:high]
    elif section == "timeline":
        result["tasks"] = data["tasks"][low:high]
        batches = {task["batch_ref"] for task in result["tasks"]}
        result["deliveries"] = [row for row in data["deliveries"] if row["batch_ref"] in batches]
    elif section in ("actual", "downtime"):
        field = "execution" if section == "actual" else "overlaps"
        result[field] = data[field][low:high]
        task_refs = {row["source"]["task_ref"] for row in result[field]}
        result["tasks"] = [row for row in data["tasks"] if row["task_ref"] in task_refs]
        if section == "downtime":
            result["downtimes"] = data["downtimes"][low:high]
            batches = {task["batch_ref"] for task in result["tasks"]}
            result["deliveries"] = [row for row in data["deliveries"] if row["batch_ref"] in batches]
    elif section == "material":
        result["pending"]["items"] = data["pending"]["items"][low:high]
    elif section == "pressure":
        result["resources"] = data["resources"][low:high]
    elif section == "resource_days":
        result["resources"] = [{**resource, "days": resource["days"][low:high]}]
    result["pagination"] = {key: pagination[key] for key in ("number", "size", "total", "pages")}
    result["pagination"].update(section=section, totals=totals)
    return result


def project_dashboard_analysis(facts, material, *, query=None):
    query = query or DashboardAnalysisQuery("overview")
    data = _view(_projection(facts, material, query), query)
    data.update(as_of=facts.now.isoformat(timespec="seconds"), capabilities={"view": True, "adopt": False},
                basis="current_official_plan_and_readiness_sources")
    return data
