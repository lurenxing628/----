"""预检事实读仓储：固定白名单整表快照，以及按 sqlite_master 校验后的整表原始元组读取（指纹用）。

read_whole_table 只接受当前库 sqlite_master 里实际存在的表，表名在本模块内引号化；不做任何裁决。
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from core.infrastructure.schema_probe import table_names

from .base_repo import BaseRepository
from .batch_external_context_repo import BatchExternalContextRepository

PREFLIGHT_TABLES = ("Batches", "BatchOperations", "BatchExternalContexts", "Parts", "PartOperations", "ExternalGroups", "BatchMaterials", "BatchMaterialReviews", "BatchMaterialStages", "BatchMaterialArrivals", "BatchQuantitySplits",
                    "Machines", "MachineOpTypes", "Operators", "OperatorMachine", "OperatorSkill", "OpTypes", "Suppliers",
                    "WorkbenchSupplierOpTypes", "WorkbenchOperatorProfiles", "OperationExecutionEvents", "Schedule",
                    "WorkbenchEntityRefs", "WorkbenchPlanSourceRefs", "ScheduleConfig")


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class WorkbenchPreflightFactsRepository(BaseRepository):
    def __init__(self, conn, logger=None):
        super().__init__(conn, logger)
        self._present: Optional[Set[str]] = None

    def _present_tables(self) -> Set[str]:
        if self._present is None:
            self._present = table_names(self.conn)
        return self._present

    def _optional_legacy_rows(self, name):
        introduced = {"MachineOpTypes": 35, "BatchMaterialReviews": 36, "BatchMaterialStages": 36,
                      "BatchMaterialArrivals": 36, "BatchQuantitySplits": 36}
        if name in introduced and name not in self._present_tables():
            version = self.fetchvalue("SELECT version FROM SchemaVersion WHERE id=1")
            if type(version) is int and version < introduced[name]:
                return []
        return self.fetchall("SELECT * FROM " + _quote(name) + " ORDER BY rowid")

    def preflight_tables(self) -> Dict[str, List[Dict[str, Any]]]:
        """按 PREFLIGHT_TABLES 顺序整表读取（rowid 序），返回 {表名: [行 dict]}。"""
        return {name: (BatchExternalContextRepository(self.conn).rows_for_readonly_preflight()
                       if name == "BatchExternalContexts" else self._optional_legacy_rows(name))
                for name in PREFLIGHT_TABLES}

    def read_whole_table(self, name: str) -> Iterator[Tuple[Any, ...]]:
        """整表按 rowid 序流式产出原始值元组；表名必须真实存在于 sqlite_master（本实例内缓存一次）。

        表名校验与语句执行在调用时完成（未知表立即 ValueError），行只在迭代时物化，指纹计算不整表装内存。"""
        if name not in self._present_tables():
            raise ValueError("unknown table: " + repr(name))
        quoted = _quote(name)
        cursor = self.execute("SELECT * FROM " + quoted + " ORDER BY rowid")
        return (tuple(row) for row in cursor)
