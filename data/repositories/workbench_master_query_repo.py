"""基础资料只读事实：资料总览整表快照。

整表读取只展开本模块的白名单常量，不拼接调用方传入的表名或列名。
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base_repo import BaseRepository
from .sqlite_rows import raw_table_select_sql

MASTER_OVERVIEW_TABLES = (
    "Parts", "PartOperations", "ExternalGroups", "OpTypes", "Machines", "Operators", "Materials", "Suppliers", "WorkCalendar",
    "OperatorSkill", "OperatorMachine", "WorkbenchOperatorProfiles", "WorkbenchSupplierOpTypes",
    "WorkbenchSupplierProfiles", "WorkbenchMachineGroupMembers", "WorkbenchMachineGroups",
    "WorkbenchShiftProfiles", "WorkbenchOpTypePolicies",
    "Batches", "BatchMaterials", "BatchMaterialArrivals", "BatchMaterialReviews", "MachineOpTypes",
    "WorkbenchEntityRefs",
)


class WorkbenchMasterQueryRepository(BaseRepository):
    def overview_tables(self) -> Dict[str, List[Dict[str, Any]]]:
        """按 MASTER_OVERVIEW_TABLES 顺序整表读取，行 dict 按游标列名构造，不依赖连接的 row_factory。"""
        tables: Dict[str, List[Dict[str, Any]]] = {}
        for name in MASTER_OVERVIEW_TABLES:
            cursor = self.execute(raw_table_select_sql(name) + " ORDER BY rowid")
            keys = [column[0] for column in cursor.description]
            tables[name] = [dict(zip(keys, row)) for row in cursor]
        return tables
