"""Raw, SELECT-only facts used by batch projections and transaction guards."""

from contextlib import contextmanager
from datetime import date
from typing import Any, Dict

from core.infrastructure.connection_guards import data_version
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.services.process.workflow_state import load_workflow_snapshot, project_workflow_snapshot
from core.services.workbench.process.queries import plain_fingerprint
from data.repositories.workbench_batch_facts_repo import WorkbenchBatchFactsRepository
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .execution import load_execution, old_event_bindings, project_execution_snapshot, protects_execution

PLAN_TABLES = ("Schedule", "ScheduleCandidateRows", "ScheduleAdjustmentChange", "ScheduleAdjustmentScenarioRow")


class BatchFacts:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.repo = WorkbenchBatchFactsRepository(conn, logger=logger)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)
        self.plan_refs = WorkbenchPlanIdentityRepository(conn, logger=logger)
        self._facts = None
        # A read snapshot pins _facts unconditionally (stamp None); a write command's
        # load is stamped and only reused while that stamp still matches.
        self._stamp = None
        self._command = False
        self._lookups = {}
        # The evaluation day belongs to the operation scope, not the raw write-cache stamp.
        self._material_day = None

    def load(self) -> Dict[str, Any]:
        """Expose the captured material day while keeping the source cache unchanged."""
        facts = self._load()
        day = self._material_day
        if day is None:
            day = date.today().isoformat()
            if self._command:
                self._material_day = day
        return dict(facts, material_day=day)

    def _load(self):
        facts = self._pinned()
        if facts is not None:
            return facts
        with TransactionManager(self.conn).transaction():
            tables = self.repo.whole_tables()
            tables.update(self._versioned_tables())
            workflow = load_workflow_snapshot(self.conn)
            operation_refs = self.plan_refs.get_operation_refs(row["id"] for row in tables["BatchOperations"])
            execution = load_execution(self.conn, operation_refs.values())
        facts = {**tables, "workflow": project_workflow_snapshot(workflow), "operation_refs": operation_refs,
                 "execution": project_execution_snapshot(execution)}
        if self._command and self.conn.in_transaction:
            self._facts, self._stamp = facts, self._write_stamp()
        return facts

    def _write_stamp(self):
        return self.conn.total_changes, data_version(self.conn)

    def _pinned(self):
        if self._stamp is not None and (not self.conn.in_transaction or self._write_stamp() != self._stamp):
            # The command wrote, or its transaction ended: the next read must see the database again.
            # Drop the lookups with it, so an index never outlives (or keeps alive) its ledger.
            self._facts = self._stamp = None
            self._lookups = {}
        return self._facts

    def _versioned_tables(self):
        state = self.repo.versioned_facts()
        version = state["version"]["version"] if state["version"] else None
        result = {}
        for name, since in (("WorkbenchOutsourcingReceipts", 30), ("BatchExternalContexts", 33)):
            rows = state["tables"][name]
            if rows is None:
                if (type(version) is not int or version >= since or
                        name == "WorkbenchOutsourcingReceipts" and state["has_outsourcing_commands"]):
                    raise WorkbenchCommandRejected("batch_facts_unavailable", "批次外协资料结构不完整，不能继续维护，请联系维护人员核对。", 503)
                # An explicitly older schema has never supplied this table; no current records are inferred.
                rows = []
            result[name] = rows
        return result

    def fingerprint(self):
        # One pass over the facts; the execution projections inside carry no hash of their own.
        return plain_fingerprint(self.load())

    @contextmanager
    def _pin(self, facts):
        previous = self._facts, self._stamp, self._material_day
        self._facts, self._stamp = facts, None
        self._material_day = self._material_day or date.today().isoformat()
        try:
            yield self.fingerprint()
        finally:
            self._facts, self._stamp, self._material_day = previous
            self._lookups = {}

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            with self._pin(self._load()) as fingerprint:
                yield fingerprint

    @contextmanager
    def detached_read_snapshot(self):
        """Keep one materialized snapshot while projection runs without a DB lock.

        Commands and previews that perform additional SQL use read_snapshot instead.
        An existing caller transaction is never committed or released here.
        """
        with self._pin(self._load()) as fingerprint:
            yield fingerprint

    @contextmanager
    def command_snapshot(self):
        """Let one write command reuse the facts its guard loaded instead of reloading them.

        Loads are kept only inside the command's own BEGIN IMMEDIATE transaction, where
        no other connection can commit. Any write by this connection, or the end of the
        transaction, drops the copy and the next read loads again; so does leaving here.

        Precondition: a command must not write inside a savepoint, read through this
        reader, roll that savepoint back and swallow the error, then read again.
        total_changes does not go back on rollback, so that later read would still get
        the facts cached from the rolled-back writes. Let such failures abort the command.
        """
        previous = self._facts, self._stamp, self._command, self._material_day
        self._facts, self._stamp, self._command = None, None, True
        self._material_day = None
        try:
            yield
        finally:
            self._facts, self._stamp, self._command, self._material_day = previous
            self._lookups = {}

    def _row(self, facts, table, key, value):
        """First row with this key, indexed once per snapshot rather than scanned per ref."""
        cached = self._lookups.get(table)
        if cached is None or cached[0] is not facts:
            index = {}
            for row in facts[table]:
                index.setdefault(row[key], row)
            cached = self._lookups[table] = (facts, index)
        return cached[1].get(value)

    def resolve(self, ref, kind="batch"):
        from core.models.workbench_batch import public_ref

        public_ref(ref)
        facts = self._pinned()
        if facts is None:
            identity = self.identities.get(ref)
        else:
            row = self._row(facts, "WorkbenchEntityRefs", "ref", ref)
            identity = WorkbenchEntityIdentity(row["ref"], row["kind"], row["entity_key"], int(row["revision"]), bool(row["active"])) if row else None
        if identity is None or not identity.active or identity.kind != kind:
            raise WorkbenchCommandRejected("entity_not_found", "这条记录已经不在了，请重新选择。请刷新后重新选择。", 404)
        return identity

    def batch(self, ref):
        identity = self.resolve(ref)
        facts = self._pinned()
        if facts is None:
            row = self.repo.batch_row(identity.entity_key)
        else:
            row = self._row(facts, "Batches", "batch_id", identity.entity_key)
        if row is None:
            raise WorkbenchCommandRejected("storage_failure", "批次和系统编号对不上，请联系维护人员核对资料。", 500)
        if identity.entity_key != identity.entity_key.strip():
            raise WorkbenchCommandRejected("constraint_conflict", "批次号存在首尾空格，请先核对原记录。")
        return row


def related(facts, batch):
    return index_relations(facts)[batch["batch_id"]]


def require_unreferenced(facts, batch, relations=None):
    """relations 是调用方已按同一份 facts 算好的这一批关联；逐批循环时先 index_relations 一次再传进来。"""
    relations = related(facts, batch) if relations is None else relations
    if relations["outsourcing_receipts"]:
        raise WorkbenchCommandRejected("constraint_conflict", "这个批次已有外协发出或回厂登记，不能删除、重建工序、改数量或更换工序供应商，以免原登记无法继续核对回厂。")
    if relations["protected"]:
        raise WorkbenchCommandRejected("constraint_conflict", "这个批次已经进了计划、试调或现场报工，不能删除、重建工序或改数量。")


def group_protected(group, batch):
    return bool(group["plans"] or group["events"] or group["execution_protected"] or group["outsourcing_receipts"]
                or batch["status"] in ("scheduled", "processing", "completed")
                or any(row["status"] != "pending" for row in group["operations"]))


def require_deletable(facts, batch, relations=None):
    relations = related(facts, batch) if relations is None else relations
    require_unreferenced(facts, batch, relations)
    if relations["quantity_splits"]:
        raise WorkbenchCommandRejected("constraint_conflict", "这个批次有数量拆分记录，需保留原批与子批以核对数量，不能删除。")
    if relations["materials"]:
        raise WorkbenchCommandRejected("constraint_conflict", "这个批次还挂着物料需求，不能直接删除。")


def _index_outsourcing_receipts(facts, result):
    batch_refs = {row["ref"]: row["entity_key"] for row in facts["WorkbenchEntityRefs"] if row["kind"] == "batch" and row["active"]}
    for receipt in facts["WorkbenchOutsourcingReceipts"]:
        owner = batch_refs.get(receipt["batch_ref"])
        if owner in result:
            result[owner]["outsourcing_receipts"].append(receipt)


def index_relations(facts):
    result = {row["batch_id"]: {"operations": [], "plans": [], "events": [], "reports": [], "materials": [],
                              "outsourcing_receipts": [], "quantity_splits": [], "execution_protected": False} for row in facts["Batches"]}
    _index_outsourcing_receipts(facts, result)
    for row in facts["BatchQuantitySplits"]:
        for owner in {row["source_batch_id"], row["child_batch_id"]}:
            if owner in result:
                result[owner]["quantity_splits"].append(row)
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
