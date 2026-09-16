"""Bounded plan reads under a caller-owned snapshot; never allocates identities."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Dict, Union

from core.infrastructure.transaction import TransactionManager
from core.models.schedule_adjustment import ScheduleAdjustmentScenario
from core.models.schedule_plan_role import (
    ROLE_ADOPTED,
    SOURCE_ADJUSTMENT_SCENARIO_ROWS,
    SOURCE_CANDIDATE_ROWS,
    SOURCE_SCHEDULE,
    plan_candidate_label,
    plan_role_label,
)
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_plan_reference import WorkbenchPlanLocator, WorkbenchPlanReferenceError
from core.models.workbench_plan_scope import MAX_PLAN_TASKS
from core.services.scheduler.workbench_plan_catalog import _role_entry, _scenario_entry
from core.services.scheduler.workbench_plan_page import _PagePlanQueryService
from data.repositories.schedule_detail_query import build_schedule_detail_sql
from data.repositories.schedule_time_sql import DETAIL_OVERLAP_OR_BAD_TIME_SQL
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .plan_fact_serialization import plain_plan_facts
from .plan_point_evidence import annotate_plan_points
from .plan_projection import (
    check_payload_size,
    project_capacity_blocked_plan,
    project_plan,
    project_tasks,
    project_unavailable_plan,
    public_time,
    task_span,
)
from .plan_workspace_dto import resource_directory, workspace_projections
from .point_plan_query import PointPlanCatalogRepository
from .zero_duration_evidence import overlaps


def _admit_rows(repo, version, source, candidate_id=None, scenario_id=None):
    sql, extra = repo._plan_rows_sql(source_table=source, candidate_id=candidate_id, scenario_id=scenario_id)
    rows = repo.fetchall("SELECT id FROM (" + sql + ") LIMIT ?", [version] + extra + [MAX_PLAN_TASKS + 1])
    if len(rows) > MAX_PLAN_TASKS:
        raise WorkbenchCommandRejected("query_too_large", "所选计划明细超过 10000 条上限。请缩小时间范围后重试。", 413)


def _admit_version(repo, version, selected_role=None):
    rows = repo.list_plan_role_options(version)
    if selected_role is None or selected_role == "adopted":
        _admit_rows(repo, version, SOURCE_SCHEDULE)
    sources = {(row["source_table"], row["candidate_id"]) for row in rows
               if selected_role is None or row["role"] == selected_role}
    for source, candidate_id in sources:
        if source == SOURCE_CANDIDATE_ROWS and candidate_id is not None:
            _admit_rows(repo, version, source, candidate_id)
        elif source == SOURCE_SCHEDULE and selected_role not in (None, "adopted"):
            _admit_rows(repo, version, source)


def _admit_scenario(repo, row):
    if row["status"] == "active":
        _admit_rows(repo, row["base_version"], SOURCE_ADJUSTMENT_SCENARIO_ROWS, scenario_id=row["scenario_id"])
        _admit_version(repo, row["base_version"], row["base_plan_role"])


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
        repo = self._repo()
        if scope.collection == "history":
            heads, has_more = repo.history_page(page_size=scope.size, before_version=seek)
        else:
            heads, has_more = repo.scenario_page(page_size=scope.size, after_scenario_id=seek)
        query = _PagePlanQueryService(repo, repo.latest_version() if heads else None)
        plans = []
        for head in heads:
            if scope.collection == "history":
                plans.extend(self._catalog_history(query, head))
            else:
                plans.append(self._catalog_scenario(query, head))
        next_seek = heads[-1]["version" if scope.collection == "history" else "scenario_id"] if has_more else None
        data = {"plans": plans, "page": {"collection": scope.collection, "size": scope.size,
                "unit": "version" if scope.collection == "history" else "scenario", "has_more": has_more}}
        return check_payload_size(data), next_seek

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
        try:
            _admit_version(query.repo, locator.version, role)
        except WorkbenchCommandRejected as exc:
            if exc.code != "query_too_large":
                raise
            return project_capacity_blocked_plan(locator, ref, name)
        return project_plan(_role_entry(query, history, query.latest, role, option), ref)

    def _catalog_scenario(self, query, row):
        scenario = ScheduleAdjustmentScenario.from_row(row)
        locator = WorkbenchPlanLocator(scenario.base_version, scenario.base_plan_role, scenario.scenario_id)
        name = scenario.scenario_name or "试调方案（未命名）"
        ref, blocked = self._catalog_reference(locator, name)
        if blocked is not None:
            return blocked
        try:
            _admit_scenario(query.repo, row)
        except WorkbenchCommandRejected as exc:
            if exc.code != "query_too_large":
                raise
            return project_capacity_blocked_plan(locator, ref, name)
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
        repo = self._repo()
        locator = self.references.resolve_plan(plan_ref)
        query = _PagePlanQueryService(repo, repo.latest_version())
        history = repo.get_history_identity_row(locator.version)
        if locator.scenario_id is not None:
            row = repo.get_scenario_context(locator.scenario_id)
            if row is None:
                raise WorkbenchCommandRejected("entity_not_found", "所选试调方案已不存在，请到「试调排产方案」重新选择。", 404)
            _admit_scenario(repo, row)
            entry = _scenario_entry(query, ScheduleAdjustmentScenario.from_row(row), history, query.latest)
        else:
            if history is None:
                raise WorkbenchCommandRejected("entity_not_found", "所选排产记录已不存在，请刷新列表后重新选择。", 404)
            _admit_version(repo, locator.version, locator.plan_role)
            option = next((row for row in repo.list_plan_role_options(locator.version) if row["role"] == locator.plan_role), None)
            entry = _role_entry(query, history, query.latest, locator.plan_role, option)
        identity = entry.plan_identity
        if not entry.can_view or identity is None:
            raise WorkbenchCommandRejected("plan_unavailable", "所选计划的状态、摘要或明细无效，看不了。请回计划列表查看不可用原因。")
        span = repo.get_plan_time_span(version=locator.version, source_table=identity.source_table,
                                       candidate_id=identity.candidate_id, scenario_id=locator.scenario_id)
        if span is None:
            raise WorkbenchCommandRejected("plan_unavailable", "所选计划没有可查看的明细。请刷新计划列表后重新选择。")
        public_span: Dict[str, Union[str, bool]] = {
            "start": public_time(span.get("start_time")), "end": public_time(span.get("end_time")),
        }
        if span.get("end_includes_point") is True:
            public_span["end_inclusive"] = True
        return repo, entry, public_span

    def _task_rows(self, repo, entry, scope):
        identity = entry.plan_identity
        plan_sql, extra = repo._plan_rows_sql(source_table=identity.source_table, candidate_id=identity.candidate_id,
                                              scenario_id=entry.locator.scenario_id)
        params = [entry.locator.version] + extra
        where = ["1 = 1"]
        if scope.range_start is not None:
            where = [DETAIL_OVERLAP_OR_BAD_TIME_SQL]
            params += [scope.range_end, scope.range_start]
        sql = build_schedule_detail_sql(where_clauses=where, plan_rows_cte_sql=plan_sql)
        rows = repo.fetchall(sql + " LIMIT ?", params + [MAX_PLAN_TASKS + 1])
        if len(rows) > MAX_PLAN_TASKS:
            raise WorkbenchCommandRejected("query_too_large", "这次要读的安排超过上限。请缩小时间范围后重试。", 413)
        rows = annotate_plan_points(self.conn, rows, source_table=identity.source_table)
        if scope.range_start is not None:
            rows = [row for row in rows if not row.get("_point_work") or overlaps(
                public_time(row["start_time"]), public_time(row["end_time"]), scope.range_start, scope.range_end)]
        return rows

    def _resources(self, rows):
        resources, state = {}, {}
        for kind in ("machine", "operator", "supplier", "batch"):
            keys = {str(row[kind + "_id"]) for row in rows if row[kind + "_id"] not in (None, "")}
            mapping = self.entities.active_map(kind, sorted(keys))
            if keys != set(mapping):
                raise WorkbenchCommandRejected("identity_missing", "安排关联的批次、设备或人员编号缺失，请到资料总览核对。")
            resources[kind] = mapping
            state[kind] = [(key, value.ref, value.revision) for key, value in sorted(mapping.items())]
        return resources, state

    def workspace(self, scope):
        repo, entry, span = self._selected(scope.plan_ref)
        rows = self._task_rows(repo, entry, scope)
        task_refs = self.references.get_task_refs(scope.plan_ref, rows)
        operation_refs = self.references.get_operation_refs(row["op_id"] for row in rows)
        resources, resource_state = self._resources(rows)
        tasks = project_tasks(scope.plan_ref, rows, task_refs, operation_refs, resources, conn=self.conn)
        projections, facts = workspace_projections(
            self.conn, entry=entry, scope=scope, rows=rows, resources=resources, plan_span=span, logger=self.logger,
        )
        data = {"plan": project_plan(entry, scope.plan_ref), "scope": scope.scope(),
                "time_scope": scope.time_scope(span), "plan_span": span, "task_span": task_span(rows),
                "tasks": tasks, "task_count": len(tasks), "tasks_complete": True,
                "resources": resource_directory(rows, resources), "projections": projections}
        check_payload_size(data)
        state = input_fingerprint({"plan_revision": self.references.read_revision(), "data": data,
                                   "resources": resource_state, "projection_facts": plain_plan_facts(facts)})
        return data, state
