"""Read-only plan/execution composition; execution arithmetic belongs to the ledger."""

from datetime import datetime, timedelta

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json, input_fingerprint
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.plan_queries import WorkbenchPlanQueryService

from .actual_gantt_scope import cohort_match
from .execution_ledger import ExecutionLedgerService

MAX_ACTUAL_RESPONSE_BYTES = 32 * 1024 * 1024
MAX_ACTUAL_REPORTS = 50000


def ledger_projection(conn, plan_ref, tasks):
    return ExecutionLedgerService(conn).workspace_projection(plan_ref, tasks)


def check_actual_size(data):
    if len(canonical_json(data).encode("utf-8")) > MAX_ACTUAL_RESPONSE_BYTES:
        raise WorkbenchCommandRejected("query_too_large", "现场甘特超过 32 MiB 读取上限，未返回截断数据。", 413)
    return data


def bind_axis_time(data, as_of):
    """The visible clock is derived from the pinned as_of, not the browser clock."""
    clock = datetime.fromisoformat(as_of).replace(minute=0, second=0, microsecond=0)
    start = clock.isoformat(timespec="seconds")
    end = (clock + timedelta(hours=1)).isoformat(timespec="seconds")
    data["axis_span"] = {"start": min(data["axis_span"]["start"], start), "end": max(data["axis_span"]["end"], end)}
    return data


def _merge_resources(planned, actual):
    resources = {row["ref"]: row for row in planned}
    for kind, key in (("machine", "machines"), ("operator", "operators")):
        for row in actual[key]:
            public = {"kind": kind, "ref": row["ref"], "business_code": row["business_code"], "label": row["label"]}
            previous = resources.get(row["ref"])
            if previous is not None:
                if previous["label"] is None and public["label"] == public["business_code"]:
                    public["label"] = None
                if previous != public:
                    raise WorkbenchCommandRejected("projection_invalid", "计划和实际资源名称不一致，未合并不同来源。")
            resources[row["ref"]] = public
    return [resources[key] for key in sorted(resources)]


def _items(tasks, projection):
    by_operation = {row["operation_ref"]: row for row in projection["projections"]}
    if len(by_operation) != len(projection["projections"]) or set(by_operation) != {t["operation_ref"] for t in tasks}:
        raise WorkbenchCommandRejected("projection_invalid", "执行投影未完整对应计划工序，未按批次序号猜测关联。")
    items = []
    for task in tasks:
        execution = by_operation[task["operation_ref"]]
        if execution["comparison_task_ref"] != task["task_ref"]:
            raise WorkbenchCommandRejected("projection_invalid", "执行投影的比较任务与所选计划不一致。")
        items.append({"task": task, "execution": execution})
    if sum(len(item["execution"]["reports"]) for item in items) > MAX_ACTUAL_REPORTS:
        raise WorkbenchCommandRejected("query_too_large", "所选范围超过 50000 条报工读取上限，未返回截断记录。", 413)
    return items


def _span(plan_span, items):
    times = [plan_span["start"], plan_span["end"]]
    for item in items:
        e = item["execution"]
        if e is None:
            continue
        for report in e["reports"]:
            times.extend(value for value in (report["actual_start"], report["actual_end"]) if value is not None)
        if e["remaining_plan"]:
            times.extend((e["remaining_plan"]["start"], e["remaining_plan"]["end"]))
        times.extend(value for value in (e["first_actual_start"], e["confirmed_finish"]) if value is not None)
    return {"start": min(times), "end": max(times)}


class ActualGanttService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.plans = WorkbenchPlanQueryService(conn, logger)

    def read_snapshot(self):
        return self.plans.read_snapshot()

    def workspace(self, scope):
        planned, plan_state = self.plans.workspace(PlanReadScope(scope.plan_ref))
        availability = {"state": "available", "reason_code": None, "reason": None}
        try:
            projection = ledger_projection(self.conn, scope.plan_ref, planned["tasks"])
        except WorkbenchCommandRejected as exc:
            if exc.code != "execution_ledger_unavailable":
                raise
            projection = None
            availability = {"state": "unavailable", "reason_code": exc.code,
                            "reason": "新报工执行投影尚未安装或安装不完整；当前仅显示计划，实际与剩余状态不可核实。"}
        if projection is None:
            if scope.resource_ref is not None:
                raise WorkbenchCommandRejected("execution_ledger_unavailable", "执行投影不可用，无法完整核实计划或实际资源范围。")
            items = [{"task": task, "execution": None} for task in planned["tasks"]]
            resources = planned["resources"]
        else:
            if projection["available"] is not True or projection["time_basis"] != "factory_local":
                raise WorkbenchCommandRejected("projection_invalid", "执行投影不可用或时间口径不一致。")
            items = _items(planned["tasks"], projection)
            resources = _merge_resources(planned["resources"], projection["resources"])
        items = [item for item in items if cohort_match(item, scope)]
        data = {"plan": planned["plan"], "scope": scope.scope(), "plan_span": planned["plan_span"],
                "axis_span": _span(planned["plan_span"], items), "availability": availability,
                "items": items, "task_count": len(items), "items_complete": True,
                "report_count": sum(len(item["execution"]["reports"]) for item in items) if projection else None,
                "resources": resources, "calendar": planned["projections"]["calendar"],
                "critical_chain": {"state": "unavailable", "reason": "尚无绑定本次执行快照的真实引擎关键链证据。", "task_refs": [], "edges": []},
                "semantics": {"cohort": "plan_finish_date_and_plan_overlap", "resources": "planned_or_actual_or_recorded_remaining",
                              "reports": "all_effective_reports_of_selected_operations", "local_filters": "search_late_selected",
                              "export": "full_snapshot_cohort_or_explicit_local_view", "time_basis": "factory_local"}}
        check_actual_size(data)
        state = input_fingerprint({"plan": plan_state, "execution": projection["snapshot_facts"] if projection else None,
                                   "data": data})
        return data, state
