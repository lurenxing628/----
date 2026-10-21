"""Bounded plan reads under a caller-owned snapshot; never allocates identities."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Dict, Tuple, Union, cast

from core.infrastructure.read_evidence import read_evidence_scope
from core.infrastructure.transaction import TransactionManager
from core.models.schedule_adjustment import ScheduleAdjustmentScenario
from core.models.schedule_plan_role import (
    ROLE_ADOPTED,
    plan_candidate_label,
    plan_role_label,
)
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanLocator, WorkbenchPlanReferenceError
from core.models.workbench_plan_scope import MAX_PLAN_TASKS
from core.services.common.plan_query import SchedulePlanResolution
from core.services.scheduler.workbench_plan_catalog import PlanCatalogEntry, _role_entry, _scenario_entry
from core.services.workbench.facts.candidate_tasks import task_span
from core.services.workbench.facts.plan_serialization import plain_plan_facts
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .calendar import project_plan_calendar
from .point_query import PlanMetadataRepository, PointPlanCatalogRepository
from .projection import (
    project_plan,
    project_unavailable_plan,
    public_time,
)
from .read_context import PlanReadContext, PlanReadQuery
from .workspace_dto import resource_directory, workspace_projections


def _selected_plan(context, locator):
    repo = context.repo
    query = PlanReadQuery(repo, repo.latest_version())
    history = repo.get_history_identity_row(locator.version)
    if locator.scenario_id is not None:
        row = repo.get_scenario_context(locator.scenario_id)
        if row is None:
            raise WorkbenchCommandRejected("entity_not_found", "所选试调方案已不存在，请到「试调排产方案」重新选择。", 404)
        entry = _scenario_entry(query, ScheduleAdjustmentScenario.from_row(row), history, query.latest)
    else:
        if history is None:
            raise WorkbenchCommandRejected("entity_not_found", "所选排产记录已不存在，请刷新列表后重新选择。", 404)
        option = next((row for row in repo.list_plan_role_options(locator.version) if row["role"] == locator.plan_role), None)
        entry = _role_entry(query, history, query.latest, locator.plan_role, option)
    identity = entry.plan_identity
    if not entry.can_view or identity is None:
        raise WorkbenchCommandRejected("plan_unavailable", "所选计划的状态、摘要或明细无效，看不了。请回计划列表查看不可用原因。")
    span = repo.get_plan_time_span(version=locator.version, source_table=identity.source_table,
                                   candidate_id=identity.candidate_id, scenario_id=locator.scenario_id)
    if span is None:
        raise WorkbenchCommandRejected("plan_unavailable", "所选计划没有可查看的明细。请刷新计划列表后重新选择。")
    public_span: Dict[str, Union[str, bool]] = {"start": public_time(span.get("start_time")), "end": public_time(span.get("end_time"))}
    if span.get("end_includes_point") is True:
        public_span["end_inclusive"] = True
    return repo, entry, public_span


class WorkbenchPlanQueryService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        self.references = WorkbenchPlanIdentityRepository(conn, logger=logger)
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

    def _repo(self):
        if not self.conn.in_transaction:
            raise RuntimeError("Plan reads require read_snapshot() or an existing read transaction.")
        return PointPlanCatalogRepository(self.conn, logger=self.logger)

    def catalog_page(self, scope, seek=None):
        repo = PlanMetadataRepository(self.conn, self.logger, role_reader=self.references.read_role_options)
        context = PlanReadContext(self.conn, self.logger, references=self.references, entities=self.entities, repo=repo)
        with context.read_scope():
            return self._catalog_page(scope, seek, context)

    def _catalog_page(self, scope, seek, context):
        repo = context.repo
        if scope.collection == "history":
            heads, has_more = repo.history_page(page_size=scope.size, before_version=seek)
        else:
            heads, has_more = repo.scenario_page(page_size=scope.size, after_scenario_id=seek)
        query = PlanReadQuery(repo, repo.latest_version() if heads else None)
        plans = []
        for head in heads:
            if scope.collection == "history":
                plans.extend(self._catalog_history(query, head))
            else:
                plans.append(self._catalog_scenario(query, head))
        next_seek = heads[-1]["version" if scope.collection == "history" else "scenario_id"] if has_more else None
        data = {"plans": plans, "page": {"collection": scope.collection, "size": scope.size,
                "unit": "version" if scope.collection == "history" else "scenario", "has_more": has_more}}
        return data, next_seek

    def _catalog_history(self, query, history):
        options = query.repo.list_plan_role_options(history["version"])
        adopted = next((row for row in options if row["role"] == ROLE_ADOPTED), None)
        roles = [(ROLE_ADOPTED, adopted)] + [(row["role"], row) for row in options if row["role"] != ROLE_ADOPTED]
        return [self._catalog_role(query, history, role, option) for role, option in roles]

    def _catalog_role(self, query, history, role, option):
        locator = WorkbenchPlanLocator(history["version"], role)
        name = plan_candidate_label(option.get("candidate_label"), role=role, candidate_key=option.get("candidate_key")) if option is not None else plan_role_label(role)
        ref, blocked = self._catalog_reference(locator, name)
        if blocked is not None:
            return blocked
        return project_plan(_role_entry(query, history, query.latest, role, option), ref)

    def _catalog_scenario(self, query, row):
        scenario = ScheduleAdjustmentScenario.from_row(row)
        locator = WorkbenchPlanLocator(scenario.base_version, scenario.base_plan_role, scenario.scenario_id)
        name = scenario.scenario_name or "试调方案（未命名）"
        ref, blocked = self._catalog_reference(locator, name)
        if blocked is not None:
            return blocked
        history = query.repo.get_history_identity_row(scenario.base_version)
        return project_plan(_scenario_entry(query, scenario, history, query.latest), ref)

    def _catalog_reference(self, locator, display_name):
        reference = self.references.get_catalog_reference(locator)
        if not reference.binding_valid:
            return reference.plan_ref, project_unavailable_plan(
                locator, reference.plan_ref, display_name, (issue.code for issue in reference.issues),
            )
        if reference.plan_ref is None:
            raise RuntimeError("A valid catalog binding must have a permanent plan reference.")
        return reference.plan_ref, None

    def _selected(self, plan_ref):
        context = PlanReadContext(
            self.conn, self.logger, references=self.references, entities=self.entities)
        with context.read_scope():
            return context.selected(plan_ref)

    def _selected_metadata(
        self, plan_ref,
    ) -> Tuple[SchedulePlanResolution, PlanCatalogEntry, Dict[str, Union[str, bool]]]:
        repo = PlanMetadataRepository(self.conn, logger=self.logger)
        context = PlanReadContext(
            self.conn, self.logger, references=self.references, entities=self.entities, repo=repo)
        with context.read_scope():
            _, entry, span = context.selected(plan_ref)
            return cast(SchedulePlanResolution, entry.resolution), entry, span

    def _task_rows(self, repo, entry, scope):
        context = getattr(repo, "context", None)
        context = context if context is not None else PlanReadContext(
            self.conn, self.logger, references=self.references, entities=self.entities)
        with context.read_scope():
            return context.scoped_rows(entry, scope)

    def workspace(self, scope, *, context=None):
        context = context if context is not None else PlanReadContext(
            self.conn, self.logger, references=self.references, entities=self.entities)
        with context.read_scope():
            return self._workspace(scope, context=context)

    def execution_workspace(self, scope, *, include_calendar=False, context=None):
        """Read complete scoped plan tasks without unrelated comparison/dashboard DTOs.

        Field reporting and actual Gantt use the same plan admission, identities,
        captured quantities as the plan workspace. Only actual
        Gantt needs the selected-plan calendar; its full-plan chain reads tasks.
        """
        context = context if context is not None else PlanReadContext(
            self.conn, self.logger, references=self.references, entities=self.entities)
        with context.read_scope():
            return self._workspace(scope, execution_only=True, include_calendar=include_calendar, context=context)

    def _workspace(self, scope, *, execution_only=False, include_calendar=False, context):
        repo, entry, span = context.selected(scope.plan_ref)
        if not execution_only:
            # Complete comparison/delivery projections share one metadata capture.
            context.detail_rows(entry)
        rows = context.scoped_rows(entry, scope)
        if not execution_only and len(rows) > MAX_PLAN_TASKS:
            raise WorkbenchCommandRejected("query_too_large", "本次范围的安排超过 10000 条，请缩小时间范围后重试。", 413)
        tasks, task_facts, resources, resource_state = context.projected_tasks(scope.plan_ref, entry, rows)
        if execution_only:
            projections, facts = {}, {}
            if include_calendar:
                calendar, calendar_facts = project_plan_calendar(
                    self.conn, entry=entry, scope=scope, rows=rows, resources=resources, plan_span=span, context=context,
                )
                projections, facts = {"calendar": calendar}, {"calendar": calendar_facts}
        else:
            projections, facts, gantt_graph, provenance = workspace_projections(
                self.conn, entry=entry, scope=scope, rows=rows, resources=resources, plan_span=span, logger=self.logger, context=context,
            )
        baseline_facts = facts.get("baseline", {})
        source_resources = (task_facts["resource_directory"] + baseline_facts.get("resource_directory", [])
                            + baseline_facts.get("adoption", {}).get("resource_directory", []))
        data = {"plan": project_plan(entry, scope.plan_ref), "scope": scope.scope(),
                "time_scope": scope.time_scope(span), "plan_span": span, "task_span": task_span(tasks),
                "tasks": tasks, "task_count": len(tasks), "tasks_complete": True,
                "resources": resource_directory(rows, resources, tasks=tasks, baseline=projections.get("baseline"),
                                                archived=source_resources), "projections": projections}
        if not execution_only:
            data["gantt_graph"] = gantt_graph
            data["provenance"] = provenance
        state = {"plan_revision": self.references.read_revision(), "data": data,
                 "resources": resource_state, "projection_facts": plain_plan_facts(facts)}
        return data, state
