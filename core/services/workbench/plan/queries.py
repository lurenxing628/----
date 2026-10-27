"""Bounded plan reads under a caller-owned snapshot; never allocates identities."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Dict, Tuple, Union, cast

from core.infrastructure.transaction import TransactionManager
from core.models.schedule_plan_role import ROLE_ADOPTED, plan_role_label
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanLocator, WorkbenchPlanReferenceError
from core.models.workbench_plan_scope import MAX_PLAN_TASKS
from core.services.common.bounded_plan_query import PagePlanQueryService
from core.services.common.plan_query import SchedulePlanResolution
from core.services.scheduler.workbench_plan_catalog import PlanCatalogEntry, _role_entry
from core.services.workbench.facts.candidate_tasks import task_span
from core.services.workbench.facts.plan_serialization import plain_plan_facts
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .point_query import PlanMetadataRepository
from .projection import (
    project_plan,
    project_unavailable_plan,
    public_time,
)
from .read_context import PlanReadContext
from .workspace_dto import resource_directory, workspace_projections


def selected_plan(context, locator):
    repo = context.repo
    query = PagePlanQueryService(repo, repo.latest_version())
    history = repo.get_history_identity_row(locator.version)
    if history is None:
        raise WorkbenchCommandRejected("entity_not_found", "所选排产记录已不存在，请刷新列表后重新选择。", 404)
    entry = _role_entry(query, history, query.latest)
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

    @contextmanager
    def read_snapshot(self):
        try:
            with TransactionManager(self.conn).transaction():
                with self.references.read_bindings():
                    yield self.references.read_revision()
        except WorkbenchPlanReferenceError as exc:
            missing = exc.code == "reference_not_found"
            raise WorkbenchCommandRejected(
                "entity_not_found" if missing else exc.code,
                "所选计划已不存在，请刷新列表后重新选择。" if missing
                else "计划或安排编号已失效，请刷新列表后重新选择。",
                404 if missing else 409,
            ) from exc

    def catalog_page(self, scope, seek=None):
        repo = PlanMetadataRepository(self.conn, self.logger)
        context = PlanReadContext(self.conn, self.logger, references=self.references, entities=self.entities, repo=repo)
        with context.read_scope():
            return self._catalog_page(scope, seek, context)

    def _catalog_page(self, scope, seek, context):
        repo = context.repo
        heads, has_more = repo.history_page(page_size=scope.size, before_version=seek)
        query = PagePlanQueryService(repo, repo.latest_version() if heads else None)
        plans = [self.catalog_role(query, head) for head in heads]
        next_seek = heads[-1]["version"] if has_more else None
        data = {"plans": plans, "page": {"collection": scope.collection, "size": scope.size,
                "unit": "version", "has_more": has_more}}
        return data, next_seek

    def catalog_role(self, query, history):
        """某个版本正式计划目录投影；采用历史也用它核对正式计划身份。"""
        locator = WorkbenchPlanLocator(history["version"], ROLE_ADOPTED)
        name = plan_role_label(ROLE_ADOPTED)
        ref, blocked = self._catalog_reference(locator, name)
        if blocked is not None:
            return blocked
        return project_plan(_role_entry(query, history, query.latest), ref)

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
        context = PlanReadContext(
            self.conn, self.logger, references=self.references, entities=self.entities, repo=repo)
        with context.read_scope():
            _, entry, span = context.selected(plan_ref)
            return cast(SchedulePlanResolution, entry.resolution), entry, span

    def workspace(self, scope, *, context=None):
        context = context if context is not None else PlanReadContext(
            self.conn, self.logger, references=self.references, entities=self.entities)
        with context.read_scope():
            return self._workspace(scope, context=context)

    def execution_workspace(self, scope):
        """Read complete scoped plan tasks without unrelated comparison/dashboard DTOs."""
        context = PlanReadContext(self.conn, self.logger, references=self.references, entities=self.entities)
        with context.read_scope():
            _, entry, span = context.selected(scope.plan_ref)
            rows = context.scoped_rows(entry, scope)
            tasks, _, _, resource_state = context.projected_tasks(scope.plan_ref, rows)
            data = {"plan": project_plan(entry, scope.plan_ref), "scope": scope.scope(),
                    "time_scope": scope.time_scope(span), "plan_span": span, "task_span": task_span(tasks),
                    "tasks": tasks, "task_count": len(tasks), "tasks_complete": True}
            state = {"plan_revision": self.references.read_revision(), "data": data, "resources": resource_state}
            return data, state

    def _workspace(self, scope, *, context):
        _, entry, span = context.selected(scope.plan_ref)
        # Complete comparison/delivery projections share one metadata capture.
        context.detail_rows(entry)
        rows = context.scoped_rows(entry, scope)
        if len(rows) > MAX_PLAN_TASKS:
            raise WorkbenchCommandRejected("query_too_large", "本次范围的安排超过 10000 条，请缩小时间范围后重试。", 413)
        tasks, task_facts, resources, resource_state = context.projected_tasks(scope.plan_ref, rows)
        projections, facts, gantt_graph, provenance = workspace_projections(
            self.conn, entry=entry, scope=scope, resources=resources, plan_span=span, logger=self.logger, context=context,
        )
        baseline_facts = facts.get("baseline", {})
        source_resources = (task_facts["resource_directory"] + baseline_facts.get("resource_directory", [])
                            + baseline_facts.get("adoption", {}).get("resource_directory", []))
        data = {"plan": project_plan(entry, scope.plan_ref), "scope": scope.scope(),
                "time_scope": scope.time_scope(span), "plan_span": span, "task_span": task_span(tasks),
                "tasks": tasks, "task_count": len(tasks), "tasks_complete": True,
                "resources": resource_directory(rows, resources, tasks=tasks, baseline=projections.get("baseline"),
                                                archived=source_resources), "projections": projections,
                "gantt_graph": gantt_graph, "provenance": provenance}
        state = {"plan_revision": self.references.read_revision(), "data": data,
                 "resources": resource_state, "projection_facts": plain_plan_facts(facts)}
        return data, state
