"""SELECT-only raw collections; unavailable sources never become empty domains."""

import math
from contextlib import contextmanager
from datetime import date, datetime

from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_metadata_schema import RESOURCE_TABLES
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_master_overview import public_ref
from core.services.process.workflow_state import workflow_snapshot

SOURCES = {
    "part": ("Parts",), "route": ("Parts", "PartOperations", "ExternalGroups"),
    "opType": ("OpTypes",), "equipment": ("Machines",), "personnel": ("Operators",),
    "material": ("Materials",), "supplier": ("Suppliers",), "calendar": ("WorkCalendar",),
}
RELATIONS = ("OperatorSkill", "OperatorMachine", "WorkbenchOperatorProfiles", "WorkbenchSupplierOpTypes",
             "WorkbenchSupplierProfiles", "WorkbenchMachineGroupMembers", "WorkbenchMachineGroups",
             "WorkbenchShiftProfiles", "WorkbenchShiftPatternDays", "WorkbenchOpTypePolicies",
             "Batches", "BatchMaterials", "OperatorCalendar")
WORKFLOW = ("WorkbenchProcessWorkflow", "WorkbenchProcessOperationConfirmations")
TABLES = tuple(dict.fromkeys(table for values in SOURCES.values() for table in values)) + RELATIONS + WORKFLOW + ("WorkbenchEntityRefs",)


def plain(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [plain(item) for item in value]
    if isinstance(value, bytes):
        return {"storage_type": "blob", "hex": value.hex()}
    if isinstance(value, float) and not math.isfinite(value):
        return {"storage_type": "float", "value": str(value)}
    return value


class MasterOverviewFacts:
    def __init__(self, conn):
        self.conn = conn
        self.tables = {}
        self.workflow = None
        self.gaps = []
        self.identities = {}
        self._indexes = {}
        self._groups = {}

    def available(self, *tables):
        return all(table in self.tables for table in tables)

    def rows(self, table):
        return self.tables.get(table, [])

    def index(self, table, key):
        cache_key = (table, key)
        if cache_key not in self._indexes:
            self._indexes[cache_key] = {row[key]: row for row in self.rows(table)}
        return self._indexes[cache_key]

    def grouped(self, table, key):
        cache_key = (table, key)
        if cache_key not in self._groups:
            groups = {}
            for row in self.rows(table):
                groups.setdefault(row[key], []).append(row)
            self._groups[cache_key] = groups
        return self._groups[cache_key]

    def ref(self, kind, key):
        row = self.identities.get((kind, str(plain(key))))
        if row is None or not public_ref(row["ref"]):
            raise WorkbenchCommandRejected("storage_failure", "基础资料缺少有效的系统编号，请联系维护人员核对资料。", 500)
        return row["ref"]

    def _load(self):
        self.tables, self.identities, self._indexes, self._groups = {}, {}, {}, {}
        self.gaps, self.workflow = [], None
        present = {row[0] for row in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for name in TABLES:
            if name not in present:
                self.gaps.append({"code": "source_unavailable", "source": name,
                                  "message": "数据来源 " + name + " 未读取，相关数量和检查结果都算不出来。"})
                continue
            cursor = self.conn.execute('SELECT * FROM "' + name + '" ORDER BY rowid')
            keys = [column[0] for column in cursor.description]
            self.tables[name] = [dict(zip(keys, row)) for row in cursor]
        for row in self.rows("WorkbenchEntityRefs"):
            if row["active"] == 1:
                key = (row["kind"], row["entity_key"])
                if key in self.identities:
                    raise WorkbenchCommandRejected("storage_failure", "基础资料存在重复关联，请联系维护人员核对。", 500)
                self.identities[key] = row
        required = ("Parts", "PartOperations", "ExternalGroups", "OpTypes", "Suppliers", "WorkbenchEntityRefs") + WORKFLOW
        metadata_sources = {table for table, _ in RESOURCE_TABLES.values()}
        if self.available(*required) and self.available(*RELATIONS[:10]) and metadata_sources <= present:
            try:
                self.workflow = workflow_snapshot(self.conn)
            except RuntimeError as exc:
                raise WorkbenchCommandRejected("storage_failure", "工艺确认的数据读得不完整，请联系维护人员核对资料。", 500) from exc
        else:
            self.gaps.append({"code": "workflow_unavailable", "source": "process.workflow_snapshot",
                              "message": "工艺确认的来源读不完整，已有路线、归属或 0 工时都不能当成人工确认过。"})

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            self._load()
            yield input_fingerprint(plain({"tables": self.tables, "workflow": self.workflow, "gaps": self.gaps}))
