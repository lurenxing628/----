"""SELECT-only raw collections; unavailable sources never become empty domains."""

import math
from contextlib import contextmanager
from datetime import date, datetime

from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_metadata_schema import RESOURCE_TABLES
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_master_overview import public_ref
from core.services.process.template_source import TemplateSourceFacts
from core.services.process.workflow_state import workflow_snapshot
from core.services.workbench.facts.source_revisions import (
    MASTER_OVERVIEW_SOURCE_KEYS,
    read_source_revisions,
)
from data.repositories.workbench_master_query_repo import MASTER_OVERVIEW_TABLES, WorkbenchMasterQueryRepository

SOURCES = {
    "part": ("Parts",), "route": ("Parts", "PartOperations", "ExternalGroups"),
    "opType": ("OpTypes",), "equipment": ("Machines",), "personnel": ("Operators",),
    "material": ("Materials",), "supplier": ("Suppliers",), "calendar": ("WorkCalendar",),
}
RELATIONS = ("OperatorSkill", "OperatorMachine", "WorkbenchOperatorProfiles", "WorkbenchSupplierOpTypes",
             "WorkbenchSupplierProfiles", "WorkbenchMachineGroupMembers", "WorkbenchMachineGroups",
             "WorkbenchShiftProfiles", "WorkbenchOpTypePolicies",
             "Batches", "BatchMaterials", "BatchMaterialArrivals", "BatchMaterialReviews", "MachineOpTypes")
WORKFLOW = ("WorkbenchProcessWorkflow", "WorkbenchProcessOperationConfirmations")
# 整表白名单归仓储所有；合同测试锁定它等于 SOURCES/RELATIONS/WORKFLOW 的展开顺序。
TABLES = MASTER_OVERVIEW_TABLES


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
        self.repo = WorkbenchMasterQueryRepository(conn)
        self.tables = {}
        self.workflow = None
        self.gaps = []
        self.identities = {}
        self._indexes = {}
        self._groups = {}
        self.material_day = None
        self.present = set()
        self.snapshot_state = None
        self.template_source_facts = None

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

    def read_snapshot_state(self):
        self.material_day = date.today().isoformat()
        self.present = self.repo.present_tables()
        revisions = (
            read_source_revisions(self.conn, MASTER_OVERVIEW_SOURCE_KEYS)
            if "WorkbenchSourceRevisions" in self.present
            else {}
        )
        self.snapshot_state = {
            "revisions": revisions,
            "material_day": self.material_day,
            "present": sorted(self.present),
        }
        return self.snapshot_state

    def _load(self):
        self.identities, self._indexes, self._groups = {}, {}, {}
        self.gaps, self.workflow, self.template_source_facts = [], None, None
        self.tables = self.repo.overview_tables(self.present)
        for name in TABLES:
            if name not in self.present:
                self.gaps.append({"code": "source_unavailable", "source": name,
                                  "message": "数据来源 " + name + " 未读取，相关数量和检查结果都算不出来。"})
        for row in self.rows("WorkbenchEntityRefs"):
            if row["active"] == 1:
                key = (row["kind"], row["entity_key"])
                if key in self.identities:
                    raise WorkbenchCommandRejected("storage_failure", "基础资料存在重复关联，请联系维护人员核对。", 500)
                self.identities[key] = row
        if self.available("PartOperations", "ExternalGroups", "OpTypes", "Suppliers",
                          "WorkbenchSupplierOpTypes", "WorkbenchSupplierProfiles"):
            suppliers = [
                dict(row, ref=self.identities.get(("supplier", str(plain(row["supplier_id"]))), {}).get("ref"))
                for row in self.rows("Suppliers")
            ]
            self.template_source_facts = TemplateSourceFacts(
                self.rows("PartOperations"),
                self.rows("ExternalGroups"),
                suppliers,
                self.rows("WorkbenchSupplierOpTypes"),
                self.rows("WorkbenchSupplierProfiles"),
            )
        required = ("Parts", "PartOperations", "ExternalGroups", "OpTypes", "Suppliers", "WorkbenchEntityRefs") + WORKFLOW
        metadata_sources = {table for table, _ in RESOURCE_TABLES.values()} | {"WorkbenchShiftPatternDays"}
        if self.available(*required) and self.available(*RELATIONS[:9]) and metadata_sources <= self.present:
            try:
                self.workflow = workflow_snapshot(
                    self.conn,
                    tables=self.tables,
                    identities=self.identities,
                    source_facts=self.template_source_facts,
                )
            except RuntimeError as exc:
                raise WorkbenchCommandRejected("storage_failure", "工艺确认的数据读得不完整，请联系维护人员核对资料。", 500) from exc
        else:
            self.gaps.append({"code": "workflow_unavailable", "source": "process.workflow_snapshot",
                              "message": "工艺确认的来源读不完整，已有路线、归属或 0 工时都不能当成人工确认过。"})

    @contextmanager
    def read_snapshot(self, *, bind_snapshot=None):
        with TransactionManager(self.conn).transaction():
            as_of = datetime.now().isoformat(timespec="seconds")
            state = self.read_snapshot_state()
            if bind_snapshot is not None:
                bind_snapshot(state, as_of)
            self._load()
            yield as_of
