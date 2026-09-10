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
            raise WorkbenchCommandRejected("storage_failure", "主数据永久引用缺失或无效，未分配身份或按编号代替。", 500)
        return row["ref"]

    def _load(self):
        self.tables, self.identities, self._indexes, self._groups = {}, {}, {}, {}
        self.gaps, self.workflow = [], None
        present = {row[0] for row in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for name in TABLES:
            if name not in present:
                self.gaps.append({"code": "source_unavailable", "source": name, "message": name + "来源未加载，相关数量或检查结果未知。"})
                continue
            cursor = self.conn.execute('SELECT * FROM "' + name + '" ORDER BY rowid')
            keys = [column[0] for column in cursor.description]
            self.tables[name] = [dict(zip(keys, row)) for row in cursor]
        for row in self.rows("WorkbenchEntityRefs"):
            if row["active"] == 1:
                key = (row["kind"], row["entity_key"])
                if key in self.identities:
                    raise WorkbenchCommandRejected("storage_failure", "同一主数据有多个有效永久引用，未猜测选择。", 500)
                self.identities[key] = row
        required = ("Parts", "PartOperations", "ExternalGroups", "OpTypes", "Suppliers", "WorkbenchEntityRefs") + WORKFLOW
        metadata_sources = {table for table, _ in RESOURCE_TABLES.values()}
        if self.available(*required) and self.available(*RELATIONS[:10]) and metadata_sources <= present:
            try:
                self.workflow = workflow_snapshot(self.conn)
            except RuntimeError as exc:
                raise WorkbenchCommandRejected("storage_failure", "工艺确认或身份存储契约不完整，未自动修补。", 500) from exc
        else:
            self.gaps.append({"code": "workflow_unavailable", "source": "process.workflow_snapshot",
                              "message": "工艺确认来源不完整，不能将现存路线、归属或0工时当作人工确认。"})

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            self._load()
            yield input_fingerprint(plain({"tables": self.tables, "workflow": self.workflow, "gaps": self.gaps}))
