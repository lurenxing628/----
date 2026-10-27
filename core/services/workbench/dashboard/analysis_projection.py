"""Dashboard analysis projected from an already captured source snapshot."""

from core.models.workbench_batch import STATUSES
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import page
from core.services.capacity.plan_calendar_intervals import instant, wire
from core.services.workbench import messages
from core.services.workbench.facts.resource_pressure import pressure_summary
from core.services.workbench.facts.resource_projection import RESOURCE_METRIC_VERSION, resource_summary

from .downtime import downtime_overlap_count


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
    if state["state"] == "unavailable":
        return {"state": "unavailable", "count": None, "known_count": 0, "items": [],
                "issues": state["issues"], "basis": "stored_pending_batch_pool"}, []
    rows = [row["source"] for row in observations if row["source"]["stored_status"] == "pending"]
    unknown = sum(row["status"] not in STATUSES for row in batches)
    return {"state": "partial" if unknown else "available", "count": None if unknown else len(rows),
            "known_count": len(rows), "unknown_status_count": unknown, "items": [],
            "issues": [] if not unknown else [{"code": "batch_status_unknown", "message": "有批次的状态填得不对，待排总数算不出来。"}],
            "basis": "stored_pending_batch_pool", "scheduling_input": None}, rows


def _pending_items(facts, rows):
    if not rows:
        return []
    names = {row["batch_id"]: row["part_name"] for row in facts.raw["Batches"]}
    return [{**row, "part_label": names[row["batch_id"]]} for row in rows]


def _tasks(facts, *, selected_refs=None, slice_range=None):
    refs = facts.raw["analysis_batch_refs"]
    tasks = facts.tasks if slice_range is None else facts.tasks[slice_range[0]:slice_range[1]]
    raw_rows = facts.task_rows if slice_range is None else facts.task_rows[slice_range[0]:slice_range[1]]
    result = []
    for task, raw in zip(tasks, raw_rows):
        if selected_refs is not None and task["task_ref"] not in selected_refs:
            continue
        result.append({**task, "batch_ref": refs[task["batch_id"]]["ref"],
                       "machine_label": raw["machine_name"], "operator_label": raw["operator_name"],
                       "source": raw["source"] if type(raw["source"]) is str else None,
                       "span_hours": (instant(task["end"]) - instant(task["start"])).total_seconds() / 3600})
    return result


def _resources(facts, scope, query):
    metrics = facts.pressure_metrics
    result = [{"resource_ref": resource["ref"], "label": resource["label"], "kind": resource["kind"],
               **values, "task_refs": [], "issues": values["window_metrics"]["issues"]}
              for resource, values in metrics.resource_values(query.resource_ref)]
    windows = [row["window_metrics"] for row in result]
    common = {"metric_version": RESOURCE_METRIC_VERSION, "source": "current_transaction_snapshot",
              "start": scope["range_start"], "end": scope["range_end"], "time_basis": "factory_local",
              "cohort_basis": "current_official_plan", "cohort": metrics.cohort,
              **{kind: resource_summary(windows, kind=kind,
                                        identity_issues=metrics.identity_issues) for kind in ("machine", "operator")}}
    return result, common


def _downtime_record(raw, ref, machine_ref, machine_label, start, end, valid):
    return {"downtime_ref": ref, "machine_ref": machine_ref, "machine_label": machine_label,
            "start": start, "end": end, "valid": valid, "reason": raw["reason_detail"],
            "recorded_at": _stored_time(raw["created_at"]), "recorded_at_basis": "local_time"}


def _downtime_overlaps(sources, tasks):
    by_ref = {row["task_ref"]: row for row in tasks}
    overlaps = []
    for source in sources:
        task = by_ref[source["task_ref"]]
        overlaps.append({"task_ref": task["task_ref"], "batch_ref": task["batch_ref"], "batch_id": task["batch_id"],
                         "process_label": task["process_label"], "source": source})
    return overlaps


def _downtime_records(facts, *, include_records):
    machines = {str(raw["machine_id"]): task["machine_ref"] for task, raw in zip(facts.tasks, facts.task_rows)
                if task["machine_ref"] is not None and raw["source"] == "internal"}
    labels = {str(row["machine_id"]): row["machine_name"] for row in facts.task_rows} if include_records else {}
    identities = {row["source_id"]: row["ref"] for row in facts.raw["WorkbenchDashboardDowntimeRefs"] if row["active"] == 1}
    records, count, issues = [], 0, []
    for raw in facts.raw["MachineDowntimes"]:
        machine_id = str(raw["machine_id"])
        if raw["status"] == "cancelled" or machine_id not in machines:
            continue
        ref = identities.get(raw["id"])
        if ref is None:
            raise WorkbenchCommandRejected("identity_missing", "停机登记编号缺失，请刷新重试。")
        start, end = _time(raw["start_time"]), _time(raw["end_time"])
        valid = raw["status"] == "active" and start is not None and end is not None and start < end
        count += 1
        if include_records:
            records.append((raw, ref, machines[machine_id], labels.get(machine_id), start, end, valid))
        if not valid:
            issues.append({"code": "downtime_invalid", "message": "有停机记录的起止时间或状态填得不对，没有画成有效的停机条。"})
    return records, count, issues


def _downtimes(facts):
    records, _count, issues = _downtime_records(facts, include_records=True)
    observations, state = facts.observations("downtime")
    overlaps = [item["source"] for item in observations if item["source"]["known_overlap_hours"]]
    return records, overlaps, issues + state["issues"]


def _project_execution_slice(selected_execution, tasks):
    by_ref = {row["task_ref"]: row for row in tasks}
    # The task already carries identity, label and planned times. Analysis links
    # execution by task_ref; list/detail retain the complete evidence source.
    duplicate_task_fields = {"kind", "plan_ref", "operation_ref", "batch_id", "planned_start", "planned_end"}
    return [{"source": {key: value for key, value in row["source"].items() if key not in duplicate_task_fields},
             "batch_ref": by_ref[row["source"]["task_ref"]]["batch_ref"]} for row in selected_execution]


def project_dashboard_analysis(facts, material, *, query):
    pending, pending_rows = _pending(facts, material)
    section = query.section
    if facts.plan_state != "loaded":
        resources, downtimes, overlaps, deliveries, execution_obs = [], [], [], [], []
        downtime_count = overlap_count = 0
        result = {"plan": None, "state": facts.plan_state, "time_scope": None, "tasks": [], "resources": [],
                  "downtimes": [], "overlaps": [], "deliveries": [], "execution": [], "pending": pending,
                  "pressure": {**pressure_summary([]), "count": None}, "resource_common": None, "issues": facts.plan_issues}
    else:
        scope = facts.pressure["time_scope"]
        resources, resource_common = _resources(facts, scope, query)
        if section == "downtime":
            downtimes, overlaps, issues = _downtimes(facts)
            downtime_count, overlap_count = len(downtimes), len(overlaps)
        else:
            downtimes, overlaps = [], []
            _, downtime_count, issues = _downtime_records(facts, include_records=False)
            overlap_count = downtime_overlap_count(facts)
        deliveries = facts.delivery["items"]
        execution_obs, execution_state = facts.observations("actual")
        result = {"plan": facts.plan, "state": "available", "time_scope": scope, "tasks": [], "resources": [],
                  "downtimes": [], "overlaps": [], "deliveries": [], "execution": [], "pending": pending,
                  "pressure": pressure_summary(resources), "resource_common": resource_common,
                  "issues": facts.pressure["issues"] + issues + execution_state["issues"]}
    totals = {
        "tasks": len(facts.tasks) if facts.plan_state == "loaded" else 0,
        "resources": len(resources),
        "downtimes": downtime_count,
        "overlaps": overlap_count,
        "deliveries": len(deliveries),
        "execution": len(execution_obs),
        "pending": pending["known_count"],
        "resource_days": 0,
    }
    resource = None
    if section == "resource_days":
        resource = next((row for row in resources if row["resource_ref"] == query.resource_ref), None)
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
        refs = facts.raw["analysis_batch_refs"] if facts.plan_state == "loaded" else {}
        index = next((index for index, (task, raw) in enumerate(zip(facts.tasks, facts.task_rows))
                      if refs[task["batch_id"]]["ref"] == query.locate_batch_ref
                      and raw["source"] == "internal" and task["machine_ref"]), None) if facts.plan_state == "loaded" else None
        if index is None:
            raise WorkbenchCommandRejected("entity_not_found", "所选批次在当前正式计划中没有可显示的设备安排。", 404)
        number = index // query.size + 1
    _, pagination = page(range(total), number, query.size, [])
    low, high = (number - 1) * query.size, number * query.size
    if section == "delivery":
        result["deliveries"] = deliveries[low:high]
    elif section == "timeline" and facts.plan_state == "loaded":
        result["tasks"] = _tasks(facts, slice_range=(low, high))
        batches = {task["batch_ref"] for task in result["tasks"]}
        result["deliveries"] = [row for row in deliveries if row["batch_ref"] in batches]
    elif section == "actual" and facts.plan_state == "loaded":
        selected_execution = execution_obs[low:high]
        task_refs = {row["source"]["task_ref"] for row in selected_execution}
        result["tasks"] = _tasks(facts, selected_refs=task_refs)
        result["execution"] = _project_execution_slice(selected_execution, result["tasks"])
    elif section == "downtime" and facts.plan_state == "loaded":
        selected_overlaps = overlaps[low:high]
        task_refs = {source["task_ref"] for source in selected_overlaps}
        result["tasks"] = _tasks(facts, selected_refs=task_refs)
        result["overlaps"] = _downtime_overlaps(selected_overlaps, result["tasks"])
        result["downtimes"] = [_downtime_record(*item) for item in downtimes[low:high]]
        batches = {task["batch_ref"] for task in result["tasks"]}
        result["deliveries"] = [row for row in deliveries if row["batch_ref"] in batches]
    elif section == "material":
        result["pending"] = {**pending, "items": _pending_items(facts, pending_rows[low:high])}
    elif section == "pressure":
        result["resources"] = resources[low:high]
    elif section == "resource_days" and resource is not None:
        result["resources"] = [{**resource, "days": resource["days"][low:high]}]
    result["pagination"] = {key: pagination[key] for key in ("number", "size", "total", "pages")}
    result["pagination"].update(section=section, totals=totals)
    result.update(as_of=facts.now.isoformat(timespec="seconds"), capabilities={"view": True, "adopt": False},
                  basis="current_official_plan_and_readiness_sources")
    return result
