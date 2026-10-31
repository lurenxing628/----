"""Bounded plan reads under a caller-owned snapshot; never allocates identities."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Optional, Tuple, Union, cast

from core.infrastructure.transaction import TransactionManager
from core.models.schedule_plan_role import ADOPTED_PLAN_LABEL, ROLE_ADOPTED
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanLocator, WorkbenchPlanReferenceError
from core.models.workbench_plan_scope import MAX_PLAN_TASKS
from core.services.common.plan_query import SchedulePlanResolution
from core.services.scheduler.workbench_plan_catalog import PlanCatalogEntry, _role_entry
from core.services.workbench.facts.candidate_tasks import task_span
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .baseline import build_plan_baseline
from .calendar import project_plan_calendar
from .delivery import read_plan_delivery
from .occupancy import project_plan_occupancy
from .point_query import PlanMetadataRepository
from .process_order import project_process_order
from .projection import (
    project_plan,
    project_unavailable_plan,
    public_time,
)
from .read_context import PlanReadContext
from .workspace_dto import resource_directory, summarize_gantt_graph, workspace_projections

TASK_PAGE_SIZE = 5000


def selected_plan(context, locator):
    repo, query = context.repo, context.plan_query
    history = repo.get_history_identity_row(locator.version)
    if history is None:
        raise WorkbenchCommandRejected("entity_not_found", "所选排产记录已不存在，请刷新列表后重新选择。", 404)
    entry = _role_entry(query, history)
    identity = entry.plan_identity
    if not entry.can_view or identity is None:
        raise WorkbenchCommandRejected("plan_unavailable", "所选计划的状态、摘要或明细无效，看不了。请回计划列表查看不可用原因。")
    span = repo.get_plan_time_span(version=locator.version)
    if span is None:
        raise WorkbenchCommandRejected("plan_unavailable", "所选计划没有可查看的明细。请刷新计划列表后重新选择。")
    public_span: Dict[str, Union[str, bool]] = {"start": public_time(span.get("start_time")), "end": public_time(span.get("end_time"))}
    if span.get("end_includes_point") is True:
        public_span["end_inclusive"] = True
    return repo, entry, public_span


class WorkbenchPlanQueryService:
    def __init__(self, conn, logger=None, *, references=None):
        """``references`` shares a caller's identity repository and its bound read caches."""
        self.conn = conn
        self.logger = logger
        self.references = references if references is not None else WorkbenchPlanIdentityRepository(conn, logger=logger)
        self.entities = WorkbenchIdentityRepository(conn, logger=logger)
        self._active_context: Optional[PlanReadContext] = None

    @contextmanager
    def read_snapshot(self):
        previous = self._active_context
        try:
            with TransactionManager(self.conn).transaction():
                context = PlanReadContext(
                    self.conn, self.logger, references=self.references, entities=self.entities,
                )
                with context.read_scope():
                    self._active_context = context
                    yield self.references.read_revision()
        except WorkbenchPlanReferenceError as exc:
            missing = exc.code == "reference_not_found"
            raise WorkbenchCommandRejected(
                "entity_not_found" if missing else exc.code,
                "所选计划已不存在，请刷新列表后重新选择。" if missing
                else "计划或安排编号已失效，请刷新列表后重新选择。",
                404 if missing else 409,
            ) from exc
        finally:
            self._active_context = previous

    @contextmanager
    def _context_scope(self, context: Optional[PlanReadContext] = None, *, repo=None):
        if context is None:
            if self._active_context is not None and repo is None:
                context = self._active_context
            else:
                context = PlanReadContext(
                    self.conn, self.logger, references=self.references, entities=self.entities, repo=repo,
                )
        with context.read_scope():
            yield context

    def catalog_page(self, scope, seek=None):
        repo = PlanMetadataRepository(self.conn, self.logger)
        with self._context_scope(repo=repo) as context:
            return self._catalog_page(scope, seek, context)

    def _catalog_page(self, scope, seek, context):
        repo = context.repo
        heads, has_more = repo.history_page(page_size=scope.size, before_version=seek)
        plans = [self.catalog_role(context.plan_query, head) for head in heads]
        next_seek = heads[-1]["version"] if has_more else None
        data = {"plans": plans, "page": {"collection": scope.collection, "size": scope.size,
                "unit": "version", "has_more": has_more}}
        return data, next_seek

    def catalog_role(self, query, history):
        """某个版本正式计划目录投影；采用历史也用它核对正式计划身份。"""
        locator = WorkbenchPlanLocator(history["version"], ROLE_ADOPTED)
        ref, blocked = self._catalog_reference(locator, ADOPTED_PLAN_LABEL)
        if blocked is not None:
            return blocked
        return project_plan(_role_entry(query, history), ref)

    def _catalog_reference(self, locator, display_name):
        reference = self.references.get_catalog_reference(locator)
        if not reference.binding_valid:
            return reference.plan_ref, project_unavailable_plan(
                locator, reference.plan_ref, display_name, (issue.code for issue in reference.issues),
            )
        if reference.plan_ref is None:
            raise RuntimeError("A valid catalog binding must have a permanent plan reference.")
        return reference.plan_ref, None

    def selected_metadata(
        self, plan_ref,
    ) -> Tuple[SchedulePlanResolution, PlanCatalogEntry, Dict[str, Union[str, bool]]]:
        repo = PlanMetadataRepository(self.conn, logger=self.logger)
        with self._context_scope(repo=repo) as context:
            _, entry, span = context.selected(plan_ref)
            return cast(SchedulePlanResolution, entry.resolution), entry, span

    def prebind_scope(
        self, scope, *, context=None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        with self._context_scope(context) as context:
            context.resolve(scope.plan_ref)
            return scope.scope(), context.snapshot_state()

    def workspace(self, scope, *, context=None):
        with self._context_scope(context) as context:
            _, entry, span = context.selected(scope.plan_ref)
            # Complete comparison/delivery projections share one metadata capture.
            context.detail_rows(entry)
            rows = context.scoped_rows(entry, scope)
            total = len(rows)
            if total > MAX_PLAN_TASKS:
                raise WorkbenchCommandRejected("query_too_large", "本次范围的安排超过 10000 条，请缩小时间范围后重试。", 413)
            span_of_tasks = context.rows_span(rows)
            resources = context.resource_identities(rows)
            sliced_rows = rows[:TASK_PAGE_SIZE]
            sliced_tasks, _ = context.projected_tasks(scope.plan_ref, sliced_rows, resources=resources)
            archived_resources, used_refs = context.rows_resource_facts(scope.plan_ref, rows, resources)
            projections, facts, gantt_graph, provenance = workspace_projections(
                self.conn, entry=entry, scope=scope, resources=resources, plan_span=span,
                logger=self.logger, context=context,
            )
            source_resources = archived_resources + facts.pop("resource_directory", [])
            compared_tasks = facts.pop("compared_tasks", [])
            data = {
                "plan": project_plan(entry, scope.plan_ref),
                "scope": scope.scope(),
                "time_scope": scope.time_scope(span),
                "plan_span": span,
                "task_span": span_of_tasks,
                "tasks": sliced_tasks,
                "task_count": total,
                "tasks_complete": len(sliced_tasks) == total,
                "resources": resource_directory(
                    rows,
                    resources,
                    tasks=sliced_tasks,
                    baseline=projections.get("baseline"),
                    compared_tasks=compared_tasks,
                    archived=source_resources,
                    used_refs=used_refs,
                ),
                "projections": projections,
                "gantt_graph": gantt_graph,
                "provenance": provenance,
            }
            return data, context.snapshot_state()

    def baseline_comparison(
        self, scope, *, page=1, size=5000, context=None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        with self._context_scope(context) as context:
            _, entry, _ = context.selected(scope.plan_ref)
            baseline_data, _ = build_plan_baseline(
                self.conn, entry=entry, scope=scope, context=context, include_items=True,
                page=page, size=size,
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
            return result, scope.scope(), context.snapshot_state()

    def tasks_page(
        self, scope, *, page=1, size=TASK_PAGE_SIZE, context=None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        with self._context_scope(context) as context:
            _, entry, span = context.selected(scope.plan_ref)
            rows = context.scoped_rows(entry, scope)
            total = len(rows)
            if total > MAX_PLAN_TASKS:
                raise WorkbenchCommandRejected("query_too_large", "本次范围的安排超过 10000 条，请缩小时间范围后重试。", 413)
            pages = max(1, (total + size - 1) // size) if total > 0 else 1
            if page > pages:
                raise WorkbenchCommandRejected("invalid_input", "工序安排页码超出范围，请刷新后重试。", 400)
            page_rows = rows[(page - 1) * size : page * size]
            sliced, _ = context.projected_tasks(
                scope.plan_ref, page_rows, resources=context.resource_identities(page_rows))
            scope_dict = scope.scope()
            result: Dict[str, Any] = {
                "plan": project_plan(entry, scope.plan_ref),
                "scope": scope_dict,
                "time_scope": scope.time_scope(span),
                "plan_span": span,
                "task_span": context.rows_span(rows),
                "tasks": sliced,
                "task_count": total,
                "tasks_complete": len(sliced) == total,
                "page": {"number": page, "size": size, "total": total, "pages": pages, "has_more": page < pages},
            }
            return result, scope_dict, context.snapshot_state()

    def gantt_graph(
        self, scope, *, context=None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        with self._context_scope(context) as context:
            _, entry, _ = context.selected(scope.plan_ref)
            rows = context.scoped_rows(entry, scope)
            if len(rows) > MAX_PLAN_TASKS:
                raise WorkbenchCommandRejected("query_too_large", "本次范围的安排超过 10000 条，请缩小时间范围后重试。", 413)
            process_order, graph = project_process_order(self.conn, plan_ref=scope.plan_ref, context=context)
            scoped_batches = {row["batch_id"] for row in rows} if scope.range_start is not None else None
            graph = summarize_gantt_graph(graph, include_nodes=True, scoped_batch_ids=scoped_batches)
            scope_dict = scope.scope()
            result: Dict[str, Any] = {
                "plan_ref": scope.plan_ref,
                "scope": scope_dict,
                "process_order": process_order,
                "gantt_graph": graph,
            }
            return result, scope_dict, context.snapshot_state()

    def capacity_projections(
        self, scope, *, context=None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        with self._context_scope(context) as context:
            _, entry, span = context.selected(scope.plan_ref)
            rows = context.scoped_rows(entry, scope)
            if len(rows) > MAX_PLAN_TASKS:
                raise WorkbenchCommandRejected("query_too_large", "本次范围的安排超过 10000 条，请缩小时间范围后重试。", 413)
            resources = context.resource_identities(rows)
            selected = context.calendar_selection(entry, scope, span)
            calendar, calendar_facts = project_plan_calendar(
                self.conn, scope=scope, resources=resources, selected=selected, include_windows=True,
            )
            occupancy = project_plan_occupancy(
                scope=scope, resources=resources, calendar_facts=calendar_facts, selected=selected,
                include_segments=True, intervals=context.datetime_intervals(entry),
            )
            scope_dict = scope.scope()
            result: Dict[str, Any] = {
                "plan_ref": scope.plan_ref,
                "scope": scope_dict,
                "time_scope": scope.time_scope(span),
                "calendar": calendar,
                "occupancy": occupancy,
            }
            return result, scope_dict, context.snapshot_state()

    def export_workspace(self, scope, *, context=None):
        with self._context_scope(context) as context:
            _, entry, span = context.selected(scope.plan_ref)
            context.detail_rows(entry)
            rows = context.scoped_rows(entry, scope)
            if len(rows) > MAX_PLAN_TASKS:
                raise WorkbenchCommandRejected("query_too_large", "本次范围的安排超过 10000 条，请缩小时间范围后重试。", 413)
            resources = context.resource_identities(rows)
            all_tasks, task_facts = context.projected_tasks(scope.plan_ref, rows, resources=resources)
            delivery, _ = read_plan_delivery(self.conn, scope=scope, logger=self.logger, context=context)
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
                "resources": resource_directory(
                    rows, resources, tasks=all_tasks, archived=task_facts["resource_directory"],
                ),
                "projections": {"delivery_risks": delivery},
            }
            return data, context.snapshot_state()

    def execution_workspace(self, scope, *, context=None):
        """Read complete scoped plan tasks without unrelated comparison/dashboard DTOs."""
        with self._context_scope(context) as context:
            _, entry, span = context.selected(scope.plan_ref)
            rows = context.scoped_rows(entry, scope)
            tasks, _ = context.projected_tasks(scope.plan_ref, rows, resources=context.resource_identities(rows))
            return {"plan": project_plan(entry, scope.plan_ref), "scope": scope.scope(),
                    "time_scope": scope.time_scope(span), "plan_span": span, "task_span": task_span(tasks),
                    "tasks": tasks, "task_count": len(tasks), "tasks_complete": True}
