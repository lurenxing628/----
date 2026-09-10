"""Current-official and unified execution adapters under one caller read snapshot."""

from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_plan_reference import WorkbenchPlanLocator, WorkbenchPlanReferenceError
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.execution_ledger import ExecutionLedgerService
from core.services.workbench.plan_delivery import read_plan_delivery
from core.services.workbench.plan_fact_serialization import plain_plan_facts
from core.services.workbench.plan_projection import project_plan, project_tasks
from core.services.workbench.plan_queries import WorkbenchPlanQueryService
from data.repositories.workbench_dashboard_source_repo import DashboardSourceRepository
from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository

from .dashboard_catalogs import candidate_catalog, resource_pressure

UNAVAILABLE = {"identity_missing", "plan_binding_invalid", "task_binding_invalid", "plan_unavailable",
               "execution_ledger_unavailable", "constraint_conflict", "entity_not_found"}


def typed(value):
    if isinstance(value, set):
        return sorted(typed(item) for item in value)
    if isinstance(value, dict):
        return {key: typed(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [typed(item) for item in value]
    return plain_plan_facts(value)


def source_issue(code, message):
    return {"code": code, "message": message}


class DashboardFacts:
    def __init__(self, conn, now):
        self.conn, self.now = conn, now
        self.repo = DashboardSourceRepository(conn)
        self.raw, self.plan, self.delivery, self.tasks, self.execution = {}, None, None, [], None
        self.plan_state, self.plan_issues, self.execution_issues = "no_official_plan", [], []
        self.task_rows, self.execution_facts, self.delivery_facts = [], None, None
        self.pressure = {"state": "unavailable", "resources": None, "issues": []}
        self.candidates = {"state": "unavailable", "run_count": None, "issues": []}

    def load(self):
        for table in ("Batches", "BatchMaterials", "Materials", "MachineDowntimes", "Machines", "WorkbenchDashboardDowntimeRefs"):
            self.raw[table] = self.repo.table(table)
        self._plan()
        if self.plan_state == "loaded":
            self._execution()
        self.candidates, self.raw["candidate_catalog"] = candidate_catalog(self.conn)
        return self

    def _plan(self):
        required = {"ScheduleHistory", "Schedule", "BatchOperations", "WorkbenchPlanSourceRefs", "WorkbenchTaskRefs"}
        if not required <= self.repo.present:
            self.plan_state = "unavailable"
            self.plan_issues = [source_issue("source_not_read", "正式计划来源尚未完整安装或读取，不能计算零风险。")]
            return
        reader = WorkbenchPlanQueryService(self.conn)
        version = WorkbenchPlanCatalogRepository(self.conn).latest_version()
        self.raw["latest_official_version"] = version
        if version is None:
            self.plan_issues = [source_issue("no_official_plan", "当前没有正式计划，未改读候选结果。")]
            return
        self.raw["ScheduleHistory"] = self.repo.selected_raw("ScheduleHistory", version)
        self.raw["Schedule"] = self.repo.selected_raw("Schedule", version)
        try:
            ref = reader.references.get_plan_ref(WorkbenchPlanLocator(version, "adopted"))
            repo, entry, span = reader._selected(ref)
            plan = project_plan(entry, ref)
            identity = entry.plan_identity
            if identity is None or not plan["is_current_official"] or plan["kind"] != "official" or identity.source_table != "schedule":
                raise WorkbenchCommandRejected("plan_unavailable", "当前正式计划身份未通过校验，未选取其他版本或候选。")
            self.plan = plan
            scope = PlanReadScope(ref)
            self.delivery, self.delivery_facts = read_plan_delivery(self.conn, scope=scope, identity=identity)
            self.task_rows = reader._task_rows(repo, entry, scope)
            tasks = reader.references.get_task_refs(ref, self.task_rows)
            operations = reader.references.get_operation_refs(row["op_id"] for row in self.task_rows)
            resources, resource_state = reader._resources(self.task_rows)
            self.tasks = project_tasks(ref, self.task_rows, tasks, operations, resources)
            self.raw["plan_resource_identities"] = resource_state
            self.raw["plan_identity_revision"] = reader.references.read_revision()
            self.plan_state = "loaded"
            self.pressure, self.raw["resource_pressure"] = resource_pressure(self.conn, {
                "entry": entry, "scope": scope, "rows": self.task_rows, "resources": resources, "plan_span": span})
        except WorkbenchPlanReferenceError as exc:
            self._plan_failure("plan_binding_invalid", "当前正式来源永久身份失效，未改读同号或其他计划。")
            self.raw["plan_reference_failure"] = exc.code
        except WorkbenchCommandRejected as exc:
            if exc.code not in UNAVAILABLE:
                raise
            self._plan_failure(exc.code, str(exc))

    def _plan_failure(self, code, message):
        self.plan_state, self.tasks = "unavailable", []
        self.plan_issues = [source_issue(code, message)]

    def _execution(self):
        if self.plan is None:
            raise RuntimeError("Execution risk requires the resolved current official plan")
        ledger = ExecutionLedgerService(self.conn, clock=lambda: self.now)
        try:
            ledger.repo.require_schema()
            facts = ledger.load([task["operation_ref"] for task in self.tasks], comparison_plan_ref=self.plan["plan_ref"])
            self.execution_facts = typed(facts)
            self.execution = {row.operation_ref: row.to_dict() for row in ledger.project_loaded(facts, contexts=False)}
            for task in self.tasks:
                projection = self.execution[task["operation_ref"]]
                if projection["current_task_ref"] != task["task_ref"] or projection["comparison_task_ref"] != task["task_ref"]:
                    raise WorkbenchCommandRejected("task_binding_invalid", "执行投影与当前正式安排身份不一致。")
        except WorkbenchCommandRejected as exc:
            if exc.code not in UNAVAILABLE:
                raise
            self.execution = None
            self.execution_issues = [source_issue(exc.code, str(exc))]

    def fingerprint(self):
        return input_fingerprint(typed({"raw": self.raw, "plan": self.plan, "state": self.plan_state,
                                       "tasks": self.tasks, "task_rows": self.task_rows,
                                       "delivery": self.delivery_facts, "execution": self.execution_facts,
                                       "plan_issues": self.plan_issues, "execution_issues": self.execution_issues}))
