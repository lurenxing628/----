"""Bounded plan reads under a caller-owned snapshot; never allocates identities."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from typing import Any, Dict, Iterator, Optional, Tuple, Union, cast

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_load_limits import MAX_WINDOW_OPERATIONS
from core.models.workbench_plan_reference import WorkbenchPlanLocator, WorkbenchPlanReferenceError
from core.services.common.plan_query import SchedulePlanResolution
from core.services.scheduler.workbench_plan_catalog import PlanCatalogEntry, plan_catalog_entry
from core.services.workbench.facts.candidate_tasks import task_span
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .baseline import build_plan_baseline
from .calendar import project_plan_calendar
from .delivery import read_plan_delivery
from .occupancy import project_plan_occupancy
from .projection import project_plan, resource_directory, row_resource_entries
from .read_context import PlanReadContext
from .workspace_dto import plan_gantt_graph, plan_process_order, workspace_projections

TASK_PAGE_SIZE = 5000


def _bound_window(count):
    if count > MAX_WINDOW_OPERATIONS:
        raise WorkbenchCommandRejected(
            "query_too_large", f"本次范围的安排超过 {MAX_WINDOW_OPERATIONS} 条，请缩小时间范围后重试。", 413
        )


class WorkbenchPlanQueryService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        self.references = WorkbenchPlanIdentityRepository(conn, logger=logger)
        self.entities = WorkbenchIdentityRepository(conn, logger=logger)

    @contextmanager
    def read_snapshot(self) -> Iterator[PlanReadContext]:
        try:
            scope = nullcontext() if self.conn.in_transaction else TransactionManager(self.conn).transaction()
            with scope:
                context = PlanReadContext(
                    self.conn,
                    self.logger,
                    references=self.references,
                    entities=self.entities,
                )
                with context.read_scope():
                    yield context
        except WorkbenchPlanReferenceError as exc:
            missing = exc.code == "reference_not_found"
            raise WorkbenchCommandRejected(
                "entity_not_found" if missing else exc.code,
                "所选计划已不存在，请刷新列表后重新选择。" if missing
                else "计划或安排编号已失效，请刷新列表后重新选择。",
                404 if missing else 409,
            ) from exc

    def latest_official_plan_ref(self, context: PlanReadContext) -> Optional[str]:
        version = context.repo.latest_version()
        if not version:
            return None
        return context.plan_ref(WorkbenchPlanLocator(version))

    def catalog_page(self, context: PlanReadContext, scope, seek=None):
        heads, has_more = context.repo.history_page(page_size=scope.size, before_version=seek)
        plans = [self.catalog_role(context, head) for head in heads]
        next_seek = heads[-1]["version"] if has_more else None
        data = {
            "plans": plans,
            "page": {
                "collection": scope.collection,
                "size": scope.size,
                "unit": "version",
                "has_more": has_more,
            },
        }
        return data, next_seek

    @staticmethod
    def catalog_role(context: PlanReadContext, history):
        """某个版本正式计划目录投影；采用历史也用它核对正式计划身份。``history`` 是本快照读出的计划头行。"""
        return project_plan(plan_catalog_entry(context.plan_query, history), history["plan_ref"])

    def selected_metadata(
        self, context: PlanReadContext, plan_ref,
    ) -> Tuple[SchedulePlanResolution, PlanCatalogEntry, Dict[str, Union[str, bool]]]:
        entry, span = context.selected(plan_ref)
        return cast(SchedulePlanResolution, entry.resolution), entry, span

    def prebind_scope(
        self, context: PlanReadContext, scope,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        context.resolve(scope.plan_ref)
        return scope.scope(), context.state

    def workspace(self, context: PlanReadContext, scope):
        entry, span = context.selected(scope.plan_ref)
        context.detail_rows(entry)
        rows = context.scoped_rows(entry, scope)
        total = len(rows)
        _bound_window(total)
        span_of_tasks = context.rows_span(rows)
        resources = context.resource_identities(rows)
        sliced_tasks = context.projected_tasks(scope.plan_ref, rows[:TASK_PAGE_SIZE], resources=resources)
        projections, baseline_facts, gantt_graph = workspace_projections(
            self.conn,
            entry=entry,
            scope=scope,
            resources=resources,
            plan_span=span,
            logger=self.logger,
            context=context,
        )
        data = {
            "plan": project_plan(entry, scope.plan_ref),
            "scope": scope.scope(),
            "time_scope": scope.time_scope(span),
            "plan_span": span,
            "task_span": span_of_tasks,
            "tasks": sliced_tasks,
            "task_count": total,
            "tasks_complete": len(sliced_tasks) == total,
            "resources": resource_directory(row_resource_entries(rows, resources) + baseline_facts.resource_entries),
            "projections": projections,
            "gantt_graph": gantt_graph,
            "provenance": baseline_facts.provenance,
        }
        return data, context.state

    def baseline_comparison(
        self, context: PlanReadContext, scope, *, page=1, size=5000,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        entry, _ = context.selected(scope.plan_ref)
        baseline_data, _ = build_plan_baseline(
            self.conn,
            entry=entry,
            scope=scope,
            context=context,
            include_items=True,
            page=page,
            size=size,
        )
        total = baseline_data["item_count"]
        pages = max(1, (total + size - 1) // size) if total > 0 else 1
        if page > pages:
            raise WorkbenchCommandRejected("invalid_input", "原安排对比页码超出范围，请刷新后重试。", 400)
        sliced = baseline_data["items"]
        result: Dict[str, Any] = dict(
            baseline_data,
            items=sliced,
            items_complete=(baseline_data["state"] == "available" and len(sliced) == total),
            page={"number": page, "size": size, "total": total, "pages": pages, "has_more": page < pages},
        )
        return result, scope.scope(), context.state

    def tasks_page(
        self, context: PlanReadContext, scope, *, page=1, size=TASK_PAGE_SIZE,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        entry, span = context.selected(scope.plan_ref)
        count_info = context.count_and_span(entry, scope)
        total = count_info["total"]
        _bound_window(total)
        pages = max(1, (total + size - 1) // size) if total > 0 else 1
        if page > pages:
            raise WorkbenchCommandRejected("invalid_input", "工序安排页码超出范围，请刷新后重试。", 400)
        offset = (page - 1) * size
        page_rows = context.schedule_page(entry, scope, limit=size, offset=offset) if total > 0 else []
        sliced = context.projected_tasks(scope.plan_ref, page_rows, resources=context.resource_identities(page_rows))
        task_span_dto = (
            {"start": count_info["start_time"], "end": count_info["end_time"]}
            if total > 0
            else None
        )
        scope_dict = scope.scope()
        result: Dict[str, Any] = {
            "plan": project_plan(entry, scope.plan_ref),
            "scope": scope_dict,
            "time_scope": scope.time_scope(span),
            "plan_span": span,
            "task_span": task_span_dto,
            "tasks": sliced,
            "task_count": total,
            "tasks_complete": len(sliced) == total,
            "page": {"number": page, "size": size, "total": total, "pages": pages, "has_more": page < pages},
        }
        return result, scope_dict, context.state

    def gantt_graph(
        self, context: PlanReadContext, scope,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        entry, _ = context.selected(scope.plan_ref)
        version = entry.locator.version
        history = cast(Dict[str, Any], context.history(version))
        if scope.range_start is None:
            _bound_window(history["op_count"])
            scoped_batch_ids = None
        else:
            scoped_rows = context.scoped_rows(entry, scope)
            _bound_window(len(scoped_rows))
            scoped_batch_ids = {row["batch_id"] for row in scoped_rows}
        scope_dict = scope.scope()
        result: Dict[str, Any] = {
            "plan_ref": scope.plan_ref,
            "scope": scope_dict,
            "process_order": plan_process_order(history),
            "gantt_graph": plan_gantt_graph(context, version, scoped_batch_ids, include_nodes=True),
        }
        return result, scope_dict, context.state

    def capacity_projections(
        self, context: PlanReadContext, scope,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        entry, span = context.selected(scope.plan_ref)
        rows = context.scoped_rows(entry, scope)
        _bound_window(len(rows))
        resources = context.resource_identities(rows)
        selected = context.calendar_selection(entry, scope, span)
        calendar, calendar_facts = project_plan_calendar(
            self.conn, scope=scope, resources=resources, selected=selected, include_windows=True
        )
        occupancy = project_plan_occupancy(
            scope=scope,
            resources=resources,
            calendar_facts=calendar_facts,
            selected=selected,
            include_segments=True,
        )
        scope_dict = scope.scope()
        result: Dict[str, Any] = {
            "plan_ref": scope.plan_ref,
            "scope": scope_dict,
            "time_scope": scope.time_scope(span),
            "calendar": calendar,
            "occupancy": occupancy,
        }
        return result, scope_dict, context.state

    def export_workspace(self, context: PlanReadContext, scope):
        entry, span = context.selected(scope.plan_ref)
        context.detail_rows(entry)
        rows = context.scoped_rows(entry, scope)
        _bound_window(len(rows))
        resources = context.resource_identities(rows)
        all_tasks = context.projected_tasks(scope.plan_ref, rows, resources=resources)
        delivery = read_plan_delivery(self.conn, scope=scope, logger=self.logger, context=context)
        delivery_state = delivery["summary"]["state"]
        delivery = dict(delivery, state="available" if delivery_state == "complete" else delivery_state)
        data = {
            "plan": project_plan(entry, scope.plan_ref),
            "scope": scope.scope(),
            "time_scope": scope.time_scope(span),
            "plan_span": span,
            "task_span": task_span(all_tasks),
            "tasks": all_tasks,
            "task_count": len(all_tasks),
            "tasks_complete": True,
            "resources": resource_directory(row_resource_entries(rows, resources)),
            "projections": {"delivery_risks": delivery},
        }
        return data, context.state
