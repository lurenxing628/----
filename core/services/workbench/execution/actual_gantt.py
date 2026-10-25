"""Read-only plan/execution composition; execution arithmetic belongs to the ledger."""

from datetime import datetime, timedelta
from math import fsum

from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.facts.execution_values import execution_deviation
from core.services.workbench.facts.plan_serialization import plain_plan_facts
from core.services.workbench.plan.calendar import project_plan_calendar
from core.services.workbench.plan.calendar_context import selected_context
from core.services.workbench.plan.process_order import project_process_order
from core.services.workbench.plan.projection import project_plan
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from core.services.workbench.plan.read_context import PlanReadContext
from core.services.workbench.plan.workspace_dto import resource_directory

from .actual_gantt_chain import plan_chain
from .actual_gantt_scope import matches_execution_resource
from .ledger import ExecutionLedgerService

MAX_ACTUAL_RESPONSE_BYTES = 32 * 1024 * 1024
MAX_ACTUAL_REPORTS = 50000


def bind_axis_time(data, as_of, snapshot_ref):
    """The visible clock is derived from the pinned as_of, not the browser clock."""
    clock = datetime.fromisoformat(as_of).replace(minute=0, second=0, microsecond=0)
    start = clock.isoformat(timespec="seconds")
    end = (clock + timedelta(hours=1)).isoformat(timespec="seconds")
    data["axis_span"] = {"start": min(data["axis_span"]["start"], start), "end": max(data["axis_span"]["end"], end)}
    if "critical_chain" in data:
        data["critical_chain"]["snapshot_ref"] = snapshot_ref
    for item in data["items"]:
        item["deviation"] = execution_deviation(item["task"]["end"], item["execution"], as_of)
    data["execution_summary"] = _execution_summary(data)
    return data


def _execution_summary(data):
    result = {"complete": None, "reported": None, "pending": None,
              "average_finish_deviation_minutes": None, "known_finish_count": None,
              "scope": "full_response_cohort"}
    if data["availability"]["state"] != "available":
        return result
    items = data["items"]
    complete = sum(item["deviation"]["complete"] for item in items)
    pending = sum(item["execution"]["execution_state"] == "unreported" for item in items)
    values = [item["deviation"]["finish_deviation_minutes"] for item in items
              if item["deviation"]["finish_deviation_minutes"] is not None]
    result.update(complete=complete, reported=len(items) - complete - pending, pending=pending,
                  average_finish_deviation_minutes=round(fsum(values) / len(values), 2) if values else None,
                  known_finish_count=len(values))
    return result


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
                    raise WorkbenchCommandRejected("projection_invalid", "计划与报工中的设备或人员名称不一致，请核对资料。")
            resources[row["ref"]] = public
    return [resources[key] for key in sorted(resources)]


def _items(tasks, projection):
    by_operation = {row["operation_ref"]: row for row in projection["projections"]}
    items = []
    for task in tasks:
        execution = by_operation[task["operation_ref"]]
        items.append({"task": task, "execution": execution})
    if sum(len(item["execution"]["reports"]) for item in items) > MAX_ACTUAL_REPORTS:
        raise WorkbenchCommandRejected("query_too_large", "所选范围超过一次能读的 50000 条报工上限，系统没有返回截断后的记录。请缩小范围后重试。", 413)
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
        self.ledger = ExecutionLedgerService(conn)

    def read_snapshot(self):
        return self.plans.read_snapshot()

    def _planned(self, scope, context):
        plan_scope = PlanReadScope(scope.plan_ref, scope.range_start, scope.range_end)
        _, entry, span = context.selected(scope.plan_ref)
        if scope.range_start is None and scope.plan_finish_date_from is not None:
            times = context.intervals(entry)
            prepared = context.repo.prepared_rows(**context.query(entry))
            rows = context._enrich_rows(entry, [row for row in prepared
                if scope.plan_finish_date_from <= times[row["id"]][1][:10] <= scope.plan_finish_date_to])
        else:
            rows = context.scoped_rows(entry, plan_scope)
            if scope.plan_finish_date_from is not None:
                times = context.intervals(entry)
                rows = [row for row in rows if scope.plan_finish_date_from <=
                        times[row["schedule_id"]][1][:10] <= scope.plan_finish_date_to]
        if scope.batch_ids:
            batches = set(scope.batch_ids)
            rows = [row for row in rows if row["batch_id"] in batches]
        tasks, task_facts, resources, resource_state = context.projected_tasks(scope.plan_ref, entry, rows)
        selected = selected_context(self.conn, entry, plan_scope, rows, resources, span, read_context=context)
        calendar, calendar_facts = project_plan_calendar(self.conn, entry=entry, scope=plan_scope, rows=rows,
            resources=resources, plan_span=span, context=context, selected=selected)
        planned = {"plan": project_plan(entry, scope.plan_ref), "plan_span": span, "tasks": tasks,
                   "resources": resource_directory(rows, resources, tasks=tasks, archived=task_facts["resource_directory"]),
                   "projections": {"calendar": calendar}}
        return planned, {"plan_revision": context.references.read_revision(), "resources": resource_state,
                         "calendar": plain_plan_facts(calendar_facts)}

    def _execution(self, planned, scope):
        availability = {"state": "available", "reason_code": None, "reason": None}
        try:
            projection = self.ledger.workspace_projection(scope.plan_ref, planned["tasks"])
        except WorkbenchCommandRejected as exc:
            if exc.code == "query_too_large":
                raise WorkbenchCommandRejected(exc.code,
                    str(exc) + " 请缩小计划完工日期范围或减少所选批次后重试。", exc.status) from exc
            if exc.code != "execution_ledger_unavailable":
                raise
            projection = None
            availability = {"state": "unavailable", "reason_code": exc.code,
                            "reason": str(exc) + " 当前仅显示计划安排。"}
        if projection is None:
            if scope.resource_ref is not None:
                raise WorkbenchCommandRejected("execution_ledger_unavailable", availability["reason"] + " 当前资源筛选需要完整的现场报工记录。")
            items = [{"task": task, "execution": None} for task in planned["tasks"]]
            resources = planned["resources"]
        else:
            items = _items(planned["tasks"], projection)
            resources = _merge_resources(planned["resources"], projection["resources"])
        return projection, items, resources, availability

    def workspace(self, scope, *, chain_target=None, include_chain=True):
        context = PlanReadContext(self.conn, references=self.plans.references, entities=self.plans.entities)
        with context.read_scope():
            planned, plan_state = self._planned(scope, context)
            projection, items, resources, availability = self._execution(planned, scope)
            if scope.resource_ref is not None:
                items = [item for item in items if matches_execution_resource(
                    item["task"], item["execution"], scope.resource_type, scope.resource_ref)]
            _, _, gantt_graph = project_process_order(self.conn, plan_ref=scope.plan_ref, context=context)
            data = {"plan": planned["plan"], "scope": scope.scope(), "plan_span": planned["plan_span"],
                    "axis_span": _span(planned["plan_span"], items), "availability": availability,
                    "items": items, "task_count": len(items), "items_complete": True,
                    "report_count": sum(len(item["execution"]["reports"]) for item in items) if projection else None,
                    "resources": resources, "calendar": planned["projections"]["calendar"],
                    "gantt_graph": gantt_graph,
                    "semantics": {"cohort": "plan_finish_date_and_plan_overlap", "resources": "planned_or_actual_or_recorded_remaining",
                                  "reports": "all_effective_reports_of_selected_operations", "local_filters": "search_late_selected",
                                  "export": "full_snapshot_cohort_or_explicit_local_view", "time_basis": "factory_local"}}
            state = content_text({"plan": plan_state, "execution": projection["snapshot_facts"] if projection else None,
                                  "tasks": [item["task"] for item in items], "resources": resources,
                                  "gantt_graph": gantt_graph, "availability": availability})
            if include_chain:
                data["critical_chain"] = plan_chain(scope.plan_ref,
                    {item["task"]["task_ref"] for item in items}, target_task_ref=chain_target, context=context)
            return data, state
