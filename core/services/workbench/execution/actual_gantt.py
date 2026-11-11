"""Read-only plan/execution composition; execution arithmetic belongs to the ledger."""

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import fsum
from typing import Any, Dict, Iterator, Optional, Tuple, cast

from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import PlanReadScope
from core.services.execution.ledger_reader import ExecutionLedgerReadScope
from core.services.workbench.facts.execution_values import execution_deviation
from core.services.workbench.facts.gantt_graph import public_gantt_graph
from core.services.workbench.facts.source_revisions import EXECUTION_SOURCE_KEYS, read_source_revisions
from core.services.workbench.plan.calendar import project_plan_calendar
from core.services.workbench.plan.calendar_context import selected_context
from core.services.workbench.plan.process_order import project_process_order
from core.services.workbench.plan.projection import project_plan
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from core.services.workbench.plan.read_context import PlanReadContext
from core.services.workbench.plan.workspace_dto import resource_directory

from .actual_gantt_scope import matches_execution_resource
from .ledger import ExecutionLedgerService

MAX_ACTUAL_RESPONSE_BYTES = 32 * 1024 * 1024
MAX_ACTUAL_REPORTS = 50000


def bind_axis_time(data, as_of):
    """The visible clock is derived from the pinned as_of, not the browser clock."""
    clock_dt = datetime.fromisoformat(as_of)
    clock = clock_dt.replace(minute=0, second=0, microsecond=0)
    start = clock.isoformat(timespec="seconds")
    end = (clock + timedelta(hours=1)).isoformat(timespec="seconds")
    data["axis_span"] = {"start": min(data["axis_span"]["start"], start), "end": max(data["axis_span"]["end"], end)}
    for item in data["items"]:
        item["deviation"] = execution_deviation(item["task"]["end"], item["execution"], clock_dt)
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
        times.extend(value for value in (e["first_actual_start"], e["confirmed_finish"]) if value is not None)
    return {"start": min(times), "end": max(times)}


@dataclass
class ActualGanttReadScope:
    stack: ExitStack
    plan_context: PlanReadContext
    ledger_scope: Optional[ExecutionLedgerReadScope] = None
    ledger_state: Optional[Tuple[Any, Dict[str, Any]]] = None
    state: Optional[str] = None


class ActualGanttService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.plans = WorkbenchPlanQueryService(conn, logger)
        self.ledger = ExecutionLedgerService(conn)

    @contextmanager
    def read_snapshot(self) -> Iterator[ActualGanttReadScope]:
        with ExitStack() as stack:
            plan_context = stack.enter_context(self.plans.read_snapshot())
            yield ActualGanttReadScope(stack=stack, plan_context=plan_context)

    def _ledger_state(self, gantt_scope: ActualGanttReadScope, scope):
        if gantt_scope.ledger_state is None:
            availability = {"state": "available", "reason_code": None, "reason": None}
            try:
                ledger_scope = gantt_scope.stack.enter_context(self.ledger.read_snapshot())
                gantt_scope.ledger_scope = ledger_scope
                clock = self.ledger.revision_clock(ledger_scope)
                self.ledger.current_plan(ledger_scope)
            except WorkbenchCommandRejected as exc:
                if exc.code != "execution_ledger_unavailable":
                    raise
                availability = {
                    "state": "unavailable",
                    "reason_code": exc.code,
                    "reason": str(exc) + " 当前仅显示计划安排。",
                }
                clock = None
            gantt_scope.ledger_state = (clock, availability)
        clock, availability = gantt_scope.ledger_state
        if clock is None and scope.resource_ref is not None:
            raise WorkbenchCommandRejected(
                "execution_ledger_unavailable",
                availability["reason"] + " 当前资源筛选需要完整的现场报工记录。",
            )
        return clock, availability

    def _snapshot_state(self, gantt_scope: ActualGanttReadScope, scope):
        ledger_revision, availability = self._ledger_state(gantt_scope, scope)
        if gantt_scope.state is None:
            gantt_scope.state = content_text({
                "plan_revision": gantt_scope.plan_context.plan_revision,
                "ledger_revision": ledger_revision,
                "revisions": read_source_revisions(self.conn, EXECUTION_SOURCE_KEYS),
                "availability": availability,
            })
        return gantt_scope.state

    def prebind_scope(self, gantt_scope: ActualGanttReadScope, scope):
        gantt_scope.plan_context.resolve(scope.plan_ref)
        return scope.scope(), self._snapshot_state(gantt_scope, scope)

    def _planned(self, scope, context: PlanReadContext, *, include_calendar):
        plan_scope = PlanReadScope(scope.plan_ref, scope.range_start, scope.range_end)
        _, entry, span = context.selected(scope.plan_ref)
        if scope.range_start is None and scope.plan_finish_date_from is not None:
            dt_intervals = context.datetime_intervals(entry)
            finish_from = date.fromisoformat(scope.plan_finish_date_from)
            finish_to = date.fromisoformat(scope.plan_finish_date_to)
            prepared = context.repo.prepared_rows(**context.query(entry))
            rows = context.enrich_rows(entry, [row for row in prepared
                if finish_from <= dt_intervals[row["id"]][1].date() <= finish_to])
        else:
            rows = context.scoped_rows(entry, plan_scope)
            if scope.plan_finish_date_from is not None:
                dt_intervals = context.datetime_intervals(entry)
                finish_from = date.fromisoformat(scope.plan_finish_date_from)
                finish_to = date.fromisoformat(scope.plan_finish_date_to)
                rows = [row for row in rows if finish_from <=
                        dt_intervals[row["schedule_id"]][1].date() <= finish_to]
        if scope.batch_ids:
            batches = set(scope.batch_ids)
            rows = [row for row in rows if row["batch_id"] in batches]
        resources = context.resource_identities(rows)
        tasks, task_facts = context.projected_tasks(scope.plan_ref, rows, resources=resources)
        calendar = None
        if include_calendar:
            selected = selected_context(
                plan_scope, rows, span, intervals=context.datetime_intervals(entry)
            )
            calendar, _ = project_plan_calendar(self.conn, scope=plan_scope, resources=resources, selected=selected)
        return {"plan": project_plan(entry, scope.plan_ref), "plan_span": span, "tasks": tasks,
                "resources": resource_directory(rows, resources, tasks=tasks, archived=task_facts["resource_directory"]),
                "projections": {"calendar": calendar}}

    def _execution(self, gantt_scope: ActualGanttReadScope, planned, scope, *, include_history):
        clock, availability = self._ledger_state(gantt_scope, scope)
        if clock is None:
            return None, [{"task": task, "execution": None} for task in planned["tasks"]], planned["resources"], availability
        ledger_scope = cast(ExecutionLedgerReadScope, gantt_scope.ledger_scope)
        try:
            projection = self.ledger.workspace_projection(
                ledger_scope,
                scope.plan_ref,
                planned["tasks"],
                include_history=include_history,
            )
        except WorkbenchCommandRejected as exc:
            if exc.code == "query_too_large":
                raise WorkbenchCommandRejected(exc.code,
                    str(exc) + " 请缩小计划完工日期范围或减少所选批次后重试。", exc.status) from exc
            raise
        items = _items(planned["tasks"], projection)
        resources = _merge_resources(planned["resources"], projection["resources"])
        return projection, items, resources, availability

    def workspace(self, gantt_scope: ActualGanttReadScope, scope, *, full_workspace):
        context = gantt_scope.plan_context
        planned = self._planned(scope, context, include_calendar=full_workspace)
        projection, items, resources, availability = self._execution(
            gantt_scope, planned, scope, include_history=full_workspace
        )
        if scope.resource_ref is not None:
            items = [item for item in items if matches_execution_resource(
                item["task"], item["execution"], scope.resource_type, scope.resource_ref)]
        gantt_graph = None
        if full_workspace:
            _, gantt_graph = project_process_order(self.conn, plan_ref=scope.plan_ref, context=context)
            gantt_graph = public_gantt_graph(gantt_graph)
        data = {"plan": planned["plan"], "scope": scope.scope(), "plan_span": planned["plan_span"],
                "axis_span": _span(planned["plan_span"], items), "availability": availability,
                "items": items, "task_count": len(items), "items_complete": True,
                "report_count": sum(len(item["execution"]["reports"]) for item in items) if projection else None,
                "resources": resources, "calendar": planned["projections"]["calendar"],
                "gantt_graph": gantt_graph,
                "semantics": {"cohort": "plan_finish_date_and_plan_overlap", "resources": "planned_or_actual_or_recorded_remaining",
                              "reports": "all_effective_reports_of_selected_operations", "local_filters": "search_late_selected",
                              "export": "full_snapshot_cohort_or_explicit_local_view", "time_basis": "factory_local"}}
        state = self._snapshot_state(gantt_scope, scope)
        return data, state
