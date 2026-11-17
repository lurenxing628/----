"""Current-official and unified execution adapters under one caller read snapshot."""

from typing import Any, Dict, List, Optional, cast

from core.infrastructure.connection_guards import query_only
from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import MAX_FACT_ROWS, bounded
from core.models.workbench_plan_reference import WorkbenchPlanLocator, WorkbenchPlanReferenceError
from core.models.workbench_plan_scope import PlanReadScope
from core.services.execution.ledger_reader import project_loaded_facts
from core.services.workbench import messages
from core.services.workbench.execution.ledger import ExecutionLedgerService
from core.services.workbench.facts.delivery_projection import project_delivery_batch
from core.services.workbench.facts.source_revisions import DASHBOARD_SOURCE_KEYS, read_source_revisions
from core.services.workbench.plan.delivery import admit_plan_delivery, plan_delivery_batch, plan_delivery_view
from core.services.workbench.plan.projection import project_plan
from core.services.workbench.plan.read_context import PlanReadContext
from data.repositories.workbench_dashboard_source_repo import DashboardSourceRepository
from data.repositories.workbench_plan_delivery_repo import WorkbenchPlanDeliveryRepository

from .calendar_capture import ResourcePressureMetrics, capture_resource_pressure
from .catalogs import candidate_catalog
from .downtime import downtime, downtime_index
from .execution import actual
from .projection import safe_material

UNAVAILABLE = {"identity_missing", "plan_binding_invalid", "plan_unavailable",
               "execution_ledger_unavailable", "constraint_conflict", "entity_not_found"}
IDENTITY_GAP = "来源关联资料缺失，暂时无法评估，请联系维护人员核对。"


def source_issue(code, message):
    return {"code": code, "message": message}


class DashboardFacts:
    def __init__(self, conn, now, *, source_revisions=None):
        self.conn, self.now = conn, now
        self.repo: DashboardSourceRepository
        # The snapshot's plan context; its identity cache serves every dashboard identity lookup.
        self.context: PlanReadContext
        self.raw: Dict[str, Any] = {}
        self.plan, self.delivery, self.tasks, self.execution = None, None, [], None
        self.item_plan_ref: Optional[str] = None
        self.delivery_items: List[Dict[str, Any]] = []
        self.plan_state, self.plan_issues, self.execution_issues = "no_official_plan", [], []
        self.task_rows, self.execution_facts = [], None
        self.pressure = {"state": "unavailable", "resource_count": None, "issues": []}
        self.candidates = {"state": "unavailable", "run_count": None, "issues": []}
        self._ledger = None
        self.pressure_metrics: Optional[ResourcePressureMetrics] = None
        self.source_revisions: Optional[Dict[str, int]] = source_revisions
        self._observations = {}
        self._downtime_index: Optional[Dict[str, Any]] = None

    @staticmethod
    def precheck_binding(conn, scope, binding) -> Dict[str, int]:
        """This snapshot's source revisions; a token issued under other revisions is stale before anything loads.

        Every dashboard-scope token binds the revisions its read was admitted under (``ReadBinding.revisions``)."""
        revisions = read_source_revisions(conn, DASHBOARD_SOURCE_KEYS)
        if binding is not None and (binding.scope != content_text(scope) or binding.revisions != revisions):
            raise WorkbenchCommandRejected("snapshot_stale", messages.STALE)
        return revisions

    def valid_entity_refs(self, kind, keys):
        """Active identities by business key, plus an identity_missing issue when any key has none."""
        refs = self.context.active_map(kind, keys)
        return refs, None if len(refs) == len(set(keys)) else source_issue("identity_missing", IDENTITY_GAP)

    def entity_refs(self, kind, keys):
        """Active identities by business key; a key without one rejects the read."""
        refs, issue = self.valid_entity_refs(kind, keys)
        if issue is not None:
            raise WorkbenchCommandRejected("identity_missing", IDENTITY_GAP)
        return refs

    def _row_identities(self, rows):
        """The rows' machine, operator and batch identities, plus an issue when any of them has none."""
        identities, issue = {}, None
        for kind in ("machine", "operator", "batch"):
            keys = [str(row[kind + "_id"]) for row in rows if row[kind + "_id"] not in (None, "")]
            identities[kind], missing = self.valid_entity_refs(kind, keys)
            issue = issue or missing
        return identities, issue

    def load(self, *, include_candidates=True):
        """Read sources under the caller's snapshot; project() then works on them without SQLite."""
        with query_only(self.conn):
            self.repo = DashboardSourceRepository(self.conn)
            self.context = PlanReadContext(self.conn)
            return self._load_sources(include_candidates=include_candidates)

    def _load_sources(self, *, include_candidates=True):
        if self.source_revisions is None:
            self.source_revisions = read_source_revisions(self.conn, DASHBOARD_SOURCE_KEYS)
        for table in ("SchemaVersion", "BatchMaterialReviews", "BatchMaterialArrivals", "Batches", "BatchMaterials", "Materials", "Machines",
                      "MachineDowntimes", "WorkbenchDashboardDowntimeRefs"):
            self.raw[table] = self.repo.table(table)
        with self.context.read_scope():
            self._captured_plan(self.context)
        if self.plan_state == "loaded" or self.tasks:
            self._load_execution()
        if self.plan_state == "loaded":
            self.raw["analysis_batch_refs"] = self.entity_refs("batch", [row["batch_id"] for row in self.tasks])
        if include_candidates:
            self.candidates = candidate_catalog(self.conn)
        return self

    def observations(self, category):
        """List and analysis share each full projection and summary; a caller that changes a summary copies it."""
        self.project()
        if category not in self._observations:
            self._observations[category] = {"actual": actual, "downtime": downtime}[category](self)
        return self._observations[category]

    def downtime_index(self):
        """One parse of the captured downtime rows, shared by the downtime list, overlap count and analysis records."""
        if self._downtime_index is None:
            self._downtime_index = downtime_index(self.raw["MachineDowntimes"], self.raw["WorkbenchDashboardDowntimeRefs"])
        return self._downtime_index

    def project(self):
        """报工投影只用已读出的台账事实，可在读事务结束后做，不再碰数据库。"""
        if self._ledger is not None:
            facts = self._ledger
            self._ledger = None
            self._project_execution(facts)
        return self

    def _captured_plan(self, context):
        version = context.repo.latest_version()
        if version is None:
            self.plan_issues = [source_issue("no_official_plan", "当前没有正式计划，未改读候选结果。")]
            return
        original_rows = context.source_rows(version=version)
        self.raw["Schedule"] = original_rows
        try:
            ref = context.plan_ref(WorkbenchPlanLocator(version, "adopted"))
            entry, span = context.selected(ref)
            plan = project_plan(entry, ref)
            if not plan["is_current_official"]:
                raise WorkbenchCommandRejected("plan_unavailable", "正式计划记录无效，请刷新重试。")
        except WorkbenchPlanReferenceError:
            self._plan_failure("plan_binding_invalid", "正式计划记录已失效，请刷新重试。")
            return
        except WorkbenchCommandRejected as exc:
            if exc.code not in UNAVAILABLE:
                raise
            self._plan_failure(exc.code, str(exc))
            return

        self.item_plan_ref = ref
        scope = PlanReadScope(ref)
        admission = admit_plan_delivery(context, entry, scope)
        # 看板逐批只看本批闭包，全局原因不连坐（单条读取同口径）；兄弟批次读不出时其余批次照常评估。
        self.delivery_items = admission.items(scope_issues=())
        identities, identity_issue = self._row_identities(original_rows)
        if admission.missing_batch_ids:
            failure = "plan_unavailable", "计划涉及的批次已不存在，请到批次管理核对。"
        elif admission.missing_identity_ids or identity_issue is not None:
            failure = "identity_missing", IDENTITY_GAP
        else:
            try:
                self._load_plan(context, entry, scope, span, plan, original_rows, admission)
                return
            except WorkbenchCommandRejected as exc:
                if exc.code not in UNAVAILABLE:
                    raise
                failure = exc.code, str(exc)
        admitted = {item.batch["batch_id"] for item in admission.batches}
        admitted_rows = [
            row
            for row in original_rows
            if row["batch_id"] in admitted
            and (row["machine_id"] in (None, "") or str(row["machine_id"]) in identities["machine"])
            and (row["operator_id"] in (None, "") or str(row["operator_id"]) in identities["operator"])
        ]
        if admitted_rows:
            self.task_rows = admitted_rows
            self.tasks = context.projected_tasks(ref, admitted_rows, resources=identities)
        self._plan_failure(*failure)

    def _load_plan(self, context, entry, scope, span, plan, original_rows, admission):
        resources, resource_state = context.resources(original_rows)
        self.tasks = context.projected_tasks(scope.plan_ref, original_rows, resources=resources)
        self.task_rows = original_rows
        self.plan = plan
        self.plan_state = "loaded"
        self.pressure, self.pressure_metrics = capture_resource_pressure(
            self.conn, entry=entry, scope=scope, resources=resources, identities=resource_state, plan_span=span,
            context=context, machines=self.raw["Machines"], downtimes=self.raw["MachineDowntimes"],
            schema_version=self.raw["SchemaVersion"], plan_tasks=(self.tasks, self.task_rows))
        # 分类汇总与分析交付沿用正式计划口径（全局原因让每批都不能宣称完成）；没有全局原因时两种口径相同。
        planned = admission.items(scope_issues=admission.scope_issues) if admission.scope_issues else self.delivery_items
        self.delivery = plan_delivery_view(scope, planned)

    def _plan_failure(self, code, message):
        self.plan_state, self.plan, self.delivery = "unavailable", None, None
        self.plan_issues = [source_issue(code, message)]

    def _load_execution(self):
        plan_ref = cast(str, self.item_plan_ref)
        ledger = ExecutionLedgerService(self.conn)
        try:
            with ledger.read_snapshot() as scope:
                refs = [task["operation_ref"] for task in self.tasks]
                self._ledger = (
                    ledger.load(scope, refs, comparison_plan_ref=plan_ref, include_history=False)
                    if len(refs) == 1
                    else ledger.load_many(scope, refs, comparison_plan_ref=plan_ref, include_history=False)
                )
        except WorkbenchCommandRejected as exc:
            self._execution_unavailable(exc)

    def load_material_item(self, batch_ref):
        """Read only the single batch's readiness closure under the caller's snapshot."""
        with query_only(self.conn):
            self.repo = DashboardSourceRepository(self.conn)
            self.context = PlanReadContext(self.conn)
            batch_entity = self.context.entity_by_ref(batch_ref)
            if not batch_entity.active:
                return []
            batch_id = batch_entity.entity_key
            batch_rows = self.repo.point_rows("Batches", "batch_id", batch_id)
            if not batch_rows:
                return []
            req_rows = self.repo.child_rows("BatchMaterials", "batch_id", batch_id)
            req_ids = [row["id"] for row in req_rows]
            reviews = self.repo.rows_in("BatchMaterialReviews", "requirement_id", req_ids)
            arrivals = self.repo.rows_in("BatchMaterialArrivals", "requirement_id", req_ids)
            mat_rows = self.repo.rows_in(
                "Materials",
                "material_id",
                [row["material_id"] for row in req_rows if row["material_id"] is not None],
            )
            self.raw = {
                "Batches": batch_rows,
                "BatchMaterials": req_rows,
                "BatchMaterialReviews": reviews,
                "BatchMaterialArrivals": arrivals,
                "Materials": mat_rows,
            }
            return safe_material(self)[0]

    def load_plan_item(self, identity):
        """Read only the official plan header and the single item's source closure."""
        with query_only(self.conn):
            self.repo = DashboardSourceRepository(self.conn)
            self.context = PlanReadContext(self.conn)
            with self.context.read_scope():
                self._load_scoped_plan_item(self.context, identity)

    def _load_scoped_plan_item(self, context, identity):
        version = context.repo.latest_version()
        if version is None:
            self.plan_issues = [source_issue("no_official_plan", "当前没有正式计划，未改读候选结果。")]
            return
        try:
            ref = context.plan_ref(WorkbenchPlanLocator(version, "adopted"))
            entry, _ = context.selected(ref)
            plan = project_plan(entry, ref)
            if not plan["is_current_official"]:
                raise WorkbenchCommandRejected("plan_unavailable", "正式计划记录无效，请刷新重试。")
            self.item_plan_ref = ref
            category_name = identity["category"]
            if category_name == "delivery":
                self._load_delivery_item(context, entry, identity["batch_ref"])
            else:
                self._load_task_item(context, entry, category_name, identity["task_ref"])
        except WorkbenchPlanReferenceError:
            self._plan_failure("plan_binding_invalid", "正式计划记录已失效，请刷新重试。")
        except WorkbenchCommandRejected as exc:
            if exc.code not in UNAVAILABLE:
                raise
            self._plan_failure(exc.code, str(exc))

    def _load_task_item(self, context, entry, category_name, task_ref):
        version = entry.locator.version
        raw_row = context.repo.get_schedule_row_by_task_ref(version, task_ref)
        if raw_row is None or (category_name == "downtime" and raw_row["source"] == "external"):
            return
        if not self.repo.batch_exists(raw_row["batch_id"]):
            return
        rows = context.named_rows([raw_row])
        identities, identity_issue = self._row_identities(rows)
        if identity_issue is not None:
            self._plan_failure("identity_missing", IDENTITY_GAP)
            return
        self.task_rows = rows
        self.tasks = context.projected_tasks(cast(str, self.item_plan_ref), rows, resources=identities)
        if category_name == "actual":
            self._load_execution()
            return
        machine_id = raw_row["machine_id"]
        if machine_id is not None:
            machine_rows = self.repo.point_rows("Machines", "machine_id", machine_id)
            downtime_rows = self.repo.child_rows("MachineDowntimes", "machine_id", machine_id)
            downtime_refs = self.repo.rows_in(
                "WorkbenchDashboardDowntimeRefs",
                "source_id",
                [row["id"] for row in downtime_rows],
            )
            self.raw = {
                "Machines": machine_rows,
                "MachineDowntimes": downtime_rows,
                "WorkbenchDashboardDowntimeRefs": downtime_refs,
            }
        else:
            self.raw = {"Machines": [], "MachineDowntimes": [], "WorkbenchDashboardDowntimeRefs": []}

    def _load_delivery_item(self, context, entry, batch_ref):
        """One batch's delivery under the same per-batch rule as the list; nothing is read for a batch the plan
        neither arranges nor defers."""
        version = entry.locator.version
        deferred = context.history_documents(version).deferred_operation_ids
        batch_entity = context.entity_by_ref(batch_ref)
        if not batch_entity.active:
            return
        batch_id = batch_entity.entity_key
        raw_rows = bounded(
            context.repo.list_schedule_rows_by_batch(version, batch_id, MAX_FACT_ROWS + 1),
            MAX_FACT_ROWS,
        )
        operation_ids = (
            {row["op_id"] for row in WorkbenchPlanDeliveryRepository(self.conn).list_batch_operations_by_ids([batch_id])}
            if raw_rows or deferred
            else set()
        )
        if not raw_rows and not operation_ids & deferred:
            return
        batch_rows = self.repo.point_rows("Batches", "batch_id", batch_id)
        if not batch_rows:
            return
        rows = context.named_rows(raw_rows)
        self.raw["Batches"] = batch_rows
        self.raw["Schedule"] = rows
        item = plan_delivery_batch(batch_rows[0], batch_ref, rows, operation_ids)
        self.delivery_items = [project_delivery_batch(item, deferred_operation_ids=deferred, scope_issues=())]

    def _project_execution(self, facts):
        try:
            projected = {
                row.operation_ref: row.to_dict()
                for row in project_loaded_facts(facts, include_history=False)
            }
        except WorkbenchCommandRejected as exc:
            self._execution_unavailable(exc)
            return
        self.execution_facts = facts
        self.execution = projected
        for task in self.tasks:
            projection = projected[task["operation_ref"]]
            if projection["current_task_ref"] != task["task_ref"] or projection["comparison_task_ref"] != task["task_ref"]:
                self.execution_issues = [
                    source_issue(
                        "task_binding_invalid",
                        "报工记录对应的任务和当前正式计划里的安排不是同一条。请刷新后重试。",
                    )
                ]
                break

    def _execution_unavailable(self, exc):
        if exc.code not in UNAVAILABLE:
            raise exc
        self.execution = None
        self.execution_issues = [source_issue(exc.code, str(exc))]

    def snapshot_contents(self):
        """Encode source revisions and view state once, without nested source documents."""
        return content_text({"revisions": self.source_revisions, "plan_state": self.plan_state,
                             "plan_issues": self.plan_issues, "execution_issues": self.execution_issues})
