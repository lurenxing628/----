"""Current-official and unified execution adapters under one caller read snapshot."""

import json
from typing import Any, Dict, Optional, cast

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.content import content_text
from core.models.enums import read_source_type
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_plan_reference import WorkbenchPlanLocator, WorkbenchPlanReferenceError
from core.models.workbench_plan_scope import PlanReadScope
from core.services.capacity.plan_calendar_io import CapturedCalendarInputs
from core.services.execution.ledger_reader import project_loaded_facts
from core.services.workbench import messages
from core.services.workbench.execution.ledger import ExecutionLedgerService
from core.services.workbench.facts.source_revisions import DASHBOARD_SOURCE_KEYS, read_source_revisions
from core.services.workbench.plan.calendar_context import resource_ids
from core.services.workbench.plan.delivery import read_plan_delivery
from core.services.workbench.plan.projection import project_plan
from core.services.workbench.plan.read_context import PlanReadContext
from data.repositories.workbench_dashboard_source_repo import DashboardSourceRepository

from .calendar_capture import ResourcePressureMetrics, capture_resource_pressure
from .catalogs import candidate_catalog
from .policy import entity_refs_from_rows

UNAVAILABLE = {"identity_missing", "plan_binding_invalid", "task_binding_invalid", "plan_unavailable",
               "execution_ledger_unavailable", "constraint_conflict", "entity_not_found"}


def source_issue(code, message):
    return {"code": code, "message": message}


class _EntityRefs:
    """The plan context consumes the dashboard's already captured identity rows."""
    def __init__(self, facts):
        self.facts = facts

    def active_map(self, kind, keys):
        return {key: WorkbenchEntityIdentity(row["ref"], row["kind"], row["entity_key"],
                    int(row["revision"]), bool(row["active"]))
                for key, row in self.facts.entity_refs(kind, keys).items()}


class DashboardFacts:
    def __init__(self, conn, now, *, source_revisions=None):
        self.conn, self.now = conn, now
        self.repo: DashboardSourceRepository
        self.raw, self.plan, self.delivery, self.tasks, self.execution = {}, None, None, [], None
        self.plan_state, self.plan_issues, self.execution_issues = "no_official_plan", [], []
        self.task_rows, self.execution_facts, self.delivery_facts = [], None, None
        self.task_intervals = {}
        self.pressure = {"state": "unavailable", "resource_count": None, "issues": []}
        self.candidates = {"state": "unavailable", "run_count": None, "issues": []}
        self._ledger = None
        self.pressure_metrics: Optional[ResourcePressureMetrics] = None
        self.source_revisions: Optional[Dict[str, int]] = source_revisions
        self._entity_refs = {}
        self._observations = {}
        self._downtime_index: Optional[Dict[str, Any]] = None

    @staticmethod
    def precheck_binding(conn, scope, binding) -> Dict[str, int]:
        revisions = read_source_revisions(conn, DASHBOARD_SOURCE_KEYS)
        if binding is not None:
            if binding.scope != content_text(scope):
                raise WorkbenchCommandRejected("snapshot_stale", messages.STALE)
            # Same-scope bindings were issued here from snapshot_contents(), which always records revisions.
            if json.loads(binding.fingerprint[1])["revisions"] != revisions:
                raise WorkbenchCommandRejected("snapshot_stale", messages.STALE)
        return revisions

    def entity_refs(self, kind, keys):
        """Active permanent refs keyed by business key; missing or duplicated keys are identity gaps."""
        keys = list(dict.fromkeys(keys))
        known = self._entity_refs.setdefault(kind, {})
        missing = [key for key in keys if key not in known]
        if missing:
            captured = {key: [] for key in missing}
            for row in self.repo.entity_ref_rows(kind, missing):
                captured[row["entity_key"]].append(row)
            known.update(captured)
        return entity_refs_from_rows([row for key in keys for row in known[key]], keys)

    def load(self, *, include_candidates=True):
        """Read sources under the caller's snapshot; project() then works on them without SQLite."""
        with read_evidence_scope(self.conn):
            self.repo = DashboardSourceRepository(self.conn)
            return self._load_sources(include_candidates=include_candidates)

    def _load_sources(self, *, include_candidates=True):
        if self.source_revisions is None:
            self.source_revisions = read_source_revisions(self.conn, DASHBOARD_SOURCE_KEYS)
        for table in ("SchemaVersion", "BatchMaterialReviews", "BatchMaterialArrivals", "Batches", "BatchMaterials", "Materials", "Machines", "WorkbenchDashboardDowntimeRefs"):
            self.raw[table] = self.repo.table(table)
        self._plan()
        if "MachineDowntimes" not in self.raw:
            self._capture_calendar_inputs(())
        if self.plan_state == "loaded":
            self._load_execution()
            self.raw["analysis_batch_refs"] = self.entity_refs("batch", [row["batch_id"] for row in self.tasks])
        if include_candidates:
            self.candidates = candidate_catalog(self.conn)
        return self

    def _capture_calendar_inputs(self, machine_ids):
        self.raw["MachineDowntimes"], prepared = self.repo.downtime_capture(machine_ids=machine_ids)
        self.calendar_inputs = CapturedCalendarInputs(machines=self.raw["Machines"], downtimes=prepared,
            schema_version=self.raw["SchemaVersion"], downtime_machine_ids=machine_ids)

    def observations(self, category):
        """List and analysis share each full projection and summary; a caller that changes a summary copies it."""
        self.project()
        if category not in self._observations:
            from .downtime import downtime
            from .execution import actual

            self._observations[category] = {"actual": actual, "downtime": downtime}[category](self)
        return self._observations[category]

    def downtime_index(self):
        """One parse of the captured downtime rows, shared by the downtime list, overlap count and analysis records."""
        if self._downtime_index is None:
            from .downtime import downtime_index

            self._downtime_index = downtime_index(self.raw["MachineDowntimes"], self.raw["WorkbenchDashboardDowntimeRefs"])
        return self._downtime_index

    def project(self):
        """报工投影只用已读出的台账事实，可在读事务结束后做，不再碰数据库。"""
        if self._ledger is not None:
            facts = self._ledger
            self._ledger = None
            self._project_execution(facts)
        return self

    def _plan(self):
        context = PlanReadContext(self.conn, entities=_EntityRefs(self), captured_machines=self.raw["Machines"])
        with context.read_scope():
            self._captured_plan(context)

    def _captured_plan(self, context):
        version = context.repo.latest_version()
        if version is None:
            self.plan_issues = [source_issue("no_official_plan", "当前没有正式计划，未改读候选结果。")]
            return
        self.raw["Schedule"] = context.source_rows(version=version)
        try:
            ref = context.plan_ref(WorkbenchPlanLocator(version, "adopted"))
            _, entry, span = context.selected(ref)
            plan = project_plan(entry, ref)
            if not plan["is_current_official"]:
                raise WorkbenchCommandRejected("plan_unavailable", "正式计划记录无效，请刷新重试。")
            self.plan = plan
            scope = PlanReadScope(ref)
            self.delivery, self.delivery_facts = read_plan_delivery(self.conn, scope=scope, context=context)
            original_rows = context.scoped_rows(entry, scope)
            self.task_rows = [dict(row, source=read_source_type(row["source"])) for row in original_rows]
            self.raw["plan_task_sources"] = [(row["schedule_id"], row["source"]) for row in original_rows]
            resources, resource_state = context.resources(original_rows)
            self.tasks, _ = context.projected_tasks(ref, original_rows, resources=resources)
            self.task_intervals = context.datetime_intervals(entry)
            self.plan_state = "loaded"
            self._capture_calendar_inputs(resource_ids(original_rows, "machine"))
            self.pressure, self.pressure_metrics = capture_resource_pressure(
                self.conn, entry=entry, scope=scope, resources=resources, identities=resource_state, plan_span=span,
                context=context, plan_tasks=(self.tasks, self.task_rows), captured_calendar=self.calendar_inputs)
        except WorkbenchPlanReferenceError:
            self._plan_failure("plan_binding_invalid", "正式计划记录已失效，请刷新重试。")
        except WorkbenchCommandRejected as exc:
            if exc.code not in UNAVAILABLE:
                raise
            self._plan_failure(exc.code, str(exc))

    def _plan_failure(self, code, message):
        self.plan_state, self.plan, self.tasks, self.task_intervals = "unavailable", None, [], {}
        self.plan_issues = [source_issue(code, message)]

    def _load_execution(self):
        # 只在 plan_state == "loaded" 时调用，正式计划这时已经读出。
        plan = cast(Dict[str, Any], self.plan)
        ledger = ExecutionLedgerService(self.conn)
        try:
            with ledger.read_snapshot() as scope:
                facts = ledger.load_many(
                    scope, [task["operation_ref"] for task in self.tasks], comparison_plan_ref=plan["plan_ref"]
                )
            self.raw["execution_operation_sources"] = {ref: row["source"] for ref, row in facts["operations"].items()}
            facts = {**facts, "operations": {ref: dict(row, source=read_source_type(row["source"]))
                                            for ref, row in facts["operations"].items()}}
            self._ledger = facts
        except WorkbenchCommandRejected as exc:
            self._execution_unavailable(exc)

    def _project_execution(self, facts):
        try:
            self.execution_facts = facts
            self.execution = {
                row.operation_ref: row.to_dict()
                for row in project_loaded_facts(facts, include_history=False)
            }
            for task in self.tasks:
                projection = self.execution[task["operation_ref"]]
                if projection["current_task_ref"] != task["task_ref"] or projection["comparison_task_ref"] != task["task_ref"]:
                    raise WorkbenchCommandRejected("task_binding_invalid", "报工记录对应的任务和当前正式计划里的安排不是同一条。请刷新后重试。")
        except WorkbenchCommandRejected as exc:
            self._execution_unavailable(exc)

    def _execution_unavailable(self, exc):
        if exc.code not in UNAVAILABLE:
            raise exc
        self.execution = None
        self.execution_issues = [source_issue(exc.code, str(exc))]

    def snapshot_contents(self):
        """Encode source revisions and view state once, without nested source documents."""
        return content_text({"revisions": self.source_revisions, "plan_state": self.plan_state,
                             "plan_issues": self.plan_issues, "execution_issues": self.execution_issues})
