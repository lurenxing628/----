"""Raw SQLite facts and a complete, streaming read-snapshot fingerprint."""

import hashlib
from contextlib import contextmanager

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected

TABLES = ("Batches", "BatchOperations", "Parts", "PartOperations", "ExternalGroups", "BatchMaterials",
          "Machines", "Operators", "OperatorMachine", "OperatorSkill", "OpTypes", "Suppliers",
          "WorkbenchSupplierOpTypes", "WorkbenchOperatorProfiles", "OperationExecutionEvents", "Schedule",
          "WorkbenchEntityRefs", "WorkbenchPlanSourceRefs", "ScheduleConfig")


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def full_facts_fingerprint(conn):
    # Includes unselected execution/resources/calendars and all ledger revisions.
    digest = hashlib.sha256()
    schema = list(conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"))
    digest.update(repr([tuple(row) for row in schema]).encode("utf-8"))
    for row in schema:
        if row[0] != "table":
            continue
        digest.update(row[1].encode("utf-8"))
        for fact in conn.execute("SELECT * FROM " + quote(row[1]) + " ORDER BY rowid"):
            encoded = repr(tuple(fact)).encode("utf-8")
            digest.update(str(len(encoded)).encode("ascii") + b":" + encoded)
    return digest.hexdigest()


class PreflightFacts:
    def __init__(self, conn):
        self.conn = conn
        self.tables = {}
        self.refs = {}
        self.operation_refs = {}

    @contextmanager
    def snapshot(self):
        with TransactionManager(self.conn).transaction():
            self.tables = {name: [dict(row) for row in self.conn.execute("SELECT * FROM " + quote(name) + " ORDER BY rowid")]
                           for name in TABLES}
            self.refs = {(row["kind"], row["entity_key"]): row["ref"] for row in self.tables["WorkbenchEntityRefs"] if row["active"]}
            self.operation_refs = {int(row["source_key"]): row["ref"] for row in self.tables["WorkbenchPlanSourceRefs"]
                                   if row["kind"] == "operation" and row["active"]}
            yield full_facts_fingerprint(self.conn)

    def selected(self, refs):
        identities = {ref: key for (kind, key), ref in self.refs.items() if kind == "batch"}
        batches = {row["batch_id"]: row for row in self.tables["Batches"]}
        result = []
        for ref in refs:
            key = identities.get(ref)
            if key is None:
                raise WorkbenchCommandRejected("entity_not_found", "选中批次已失效，请刷新列表后重新选择。", 404)
            if key not in batches:
                raise WorkbenchCommandRejected("storage_failure", "批次编号和原记录对不上，检查没有继续。请刷新重试；仍不行请联系维护人员。", 500)
            result.append({**batches[key], "ref": ref})
        return result

    def operation_ref(self, op):
        ref = self.operation_refs.get(op["id"])
        if ref is None:
            raise WorkbenchCommandRejected("storage_failure", "工序编号缺失，请联系维护人员。", 500)
        return ref
