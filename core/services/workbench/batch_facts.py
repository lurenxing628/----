"""Raw, SELECT-only facts used by batch projections and transaction guards."""

from contextlib import contextmanager

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.services.process.workflow_state import workflow_snapshot
from core.services.workbench.batch_execution import old_event_bindings, protects_execution, read_execution
from core.services.workbench.process_queries import _plain
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

TABLES = ("Batches", "BatchOperations", "Parts", "PartOperations", "ExternalGroups", "BatchMaterials", "Materials",
          "Machines", "Operators", "OperatorMachine", "OperatorSkill", "OpTypes", "Suppliers", "WorkbenchSupplierOpTypes",
          "WorkbenchSupplierProfiles", "WorkbenchOperatorProfiles", "Schedule", "ScheduleCandidateRows", "ScheduleAdjustmentChange",
          "ScheduleAdjustmentScenarioRow", "OperationExecutionEvents", "WorkbenchEntityRefs", "WorkbenchPlanSourceRefs")
PLAN_TABLES = ("Schedule", "ScheduleCandidateRows", "ScheduleAdjustmentChange", "ScheduleAdjustmentScenarioRow")


class BatchFacts:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)
        self.plan_refs = WorkbenchPlanIdentityRepository(conn, logger=logger)
        self._facts = None

    def load(self):
        if self._facts is not None:
            return self._facts
        with TransactionManager(self.conn).transaction():
            tables = {table: [dict(row) for row in self.conn.execute('SELECT * FROM "' + table + '" ORDER BY rowid')] for table in TABLES}
            workflow = workflow_snapshot(self.conn)
            operation_refs = self.plan_refs.get_operation_refs(row["id"] for row in tables["BatchOperations"])
            return {**tables, "workflow": workflow, "operation_refs": operation_refs,
                    "execution": read_execution(self.conn, operation_refs.values())}

    def fingerprint(self):
        return input_fingerprint(_plain(self.load()))

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            previous = self._facts
            self._facts = self.load()
            try:
                yield self.fingerprint()
            finally:
                self._facts = previous

    def resolve(self, ref, kind="batch"):
        from core.models.workbench_batch import public_ref

        public_ref(ref)
        identity = self.identities.get(ref)
        if identity is None or not identity.active or identity.kind != kind:
            raise WorkbenchCommandRejected("entity_not_found", "这条记录已经不在了，系统不会换成编号相同的新记录。请刷新后重新选择。", 404)
        return identity

    def batch(self, ref):
        identity = self.resolve(ref)
        if self._facts is None:
            stored = self.conn.execute("SELECT * FROM Batches WHERE batch_id=?", (identity.entity_key,)).fetchone()
            row = dict(stored) if stored is not None else None
        else:
            row = next((item for item in self._facts["Batches"] if item["batch_id"] == identity.entity_key), None)
        if row is None:
            raise WorkbenchCommandRejected("storage_failure", "批次和系统编号对不上，系统不会自动修补。请刷新重试；仍不行请联系维护人员。", 500)
        if identity.entity_key != identity.entity_key.strip():
            raise WorkbenchCommandRejected("constraint_conflict", "批次号存在首尾空格，请先核对原记录。")
        return row


def related(facts, batch):
    return index_relations(facts)[batch["batch_id"]]


def require_unreferenced(facts, batch):
    if related(facts, batch)["protected"]:
        raise WorkbenchCommandRejected("constraint_conflict", "这个批次已经进了计划、试调或现场报工，不能删除、重建工序或改数量。")


def group_protected(group, batch):
    return bool(group["plans"] or group["events"] or group["execution_protected"]
                or batch["status"] in ("scheduled", "processing", "completed")
                or any(row["status"] != "pending" for row in group["operations"]))


def index_relations(facts):
    result = {row["batch_id"]: {"operations": [], "plans": [], "events": [], "reports": [], "materials": [],
                              "execution_protected": False} for row in facts["Batches"]}
    owners = {}
    execution = facts["execution"]
    legacy = {} if execution["available"] else old_event_bindings(facts)
    for row in facts["BatchOperations"]:
        owners[row["id"]] = row["batch_id"]
        group = result[row["batch_id"]]
        group["operations"].append(row)
        ref = facts["operation_refs"][row["id"]]
        if execution["available"]:
            projected = execution["projections"][ref]
            group["events"].extend(projected["legacy_facts"])
            group["reports"].extend(projected["reports"])
            group["execution_protected"] |= protects_execution(projected)
        else:
            group["events"].extend(legacy.get(ref, []))
    for table in PLAN_TABLES:
        for row in facts[table]:
            owner = owners.get(row["op_id"])
            if owner in result:
                result[owner]["plans"].append(row)
    for row in facts["BatchMaterials"]:
        if row["batch_id"] in result:
            result[row["batch_id"]]["materials"].append(row)
    for batch in facts["Batches"]:
        group = result[batch["batch_id"]]
        group["protected"] = group_protected(group, batch)
    return result
