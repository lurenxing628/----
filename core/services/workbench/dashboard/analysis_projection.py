"""Dashboard analysis projected from an already captured source snapshot."""

from collections import defaultdict

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.capacity.plan_calendar_intervals import instant, wire
from core.services.workbench import messages
from core.services.workbench.facts.current_resource_calendar import current_resource_calendar
from core.services.workbench.facts.resource_pressure import pressure_from_index, pressure_summary
from core.services.workbench.facts.resource_projection import (
    RESOURCE_METRIC_VERSION,
    ResourceTaskIndex,
    resource_cohort,
    resource_summary,
)


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
    normalized = [dict(task, **{kind: {"ref": task[kind + "_ref"], "label": task[kind + "_label"]}
                                if task[kind + "_ref"] is not None else None for kind in ("machine", "operator")})
                  for task in tasks]
    cohort = resource_cohort([normalized])
    start, end = scope["range_start"], scope["range_end"]
    factory = current_resource_calendar(facts, scope)
    specs = [dict(row, saved_id=factory.bindings.get((row["kind"], row["ref"]))) for row in cohort] if factory else []
    calendars = factory.iter_resources(specs, start, end) if factory else ((row["ref"], None) for row in cohort)
    index = ResourceTaskIndex(normalized, start, end, source="current_transaction_snapshot")
    task_refs = defaultdict(list)
    for task in tasks:
        if task["source"] != "external":
            for kind in ("machine", "operator"):
                task_refs[kind, task[kind + "_ref"]].append(task["task_ref"])
    result = []
    for resource, (_, calendar) in zip(cohort, calendars):
        values = pressure_from_index(index, resource, calendar)
        selected = task_refs[resource["kind"], resource["ref"]]
        result.append({"resource_ref": resource["ref"], "label": resource["label"], "kind": resource["kind"],
                       **values, "task_refs": selected, "issues": values["window_metrics"]["issues"]})
    common = {"metric_version": RESOURCE_METRIC_VERSION, "source": "current_transaction_snapshot",
              "start": start, "end": end, "time_basis": "factory_local", "cohort_basis": "current_official_plan",
              "cohort": cohort,
              **{kind: resource_summary([row["window_metrics"] for row in result], kind=kind,
                                        identity_issues=index.identity_issues) for kind in ("machine", "operator")}}
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
    identities = {row["source_id"]: row["ref"] for row in facts.raw["WorkbenchDashboardDowntimeRefs"] or [] if row["active"] == 1}
    records, issues = [], []
    for raw in facts.raw["MachineDowntimes"] or []:
        if raw["status"] == "cancelled" or str(raw["machine_id"]) not in machines:
            continue
        record = _downtime_record(raw, identities.get(raw["id"]), machines[str(raw["machine_id"])])
        records.append(record)
        if not record["valid"]:
            issues.append({"code": "downtime_invalid", "message": "有停机记录的起止时间或状态填得不对，没有画成有效的停机条。"})
    observations, state = facts.observations("downtime")
    return records, _downtime_overlaps(observations, tasks), issues + state["issues"]


def _projection(facts, material):
    pending = _pending(facts, material)
    if facts.plan_state != "loaded":
        return {"plan": None, "state": facts.plan_state, "time_scope": None, "tasks": [], "resources": [],
                "downtimes": [], "overlaps": [], "deliveries": [], "execution": [], "pending": pending,
                "pressure": {**pressure_summary([]), "count": None}, "resource_common": None, "issues": facts.plan_issues}
    tasks = _tasks(facts)
    scope = facts.pressure["time_scope"]
    resources, resource_common = _resources(facts, tasks, scope)
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


def project_dashboard_analysis(facts, material):
    data = _projection(facts, material)
    data.update(as_of=facts.now.isoformat(timespec="seconds"), capabilities={"view": True, "adopt": False},
                basis="current_official_plan_and_readiness_sources")
    return data
