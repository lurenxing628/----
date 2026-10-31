"""基础资料只读事实：资料总览整表快照。

整表读取只展开本模块的白名单常量，不拼接调用方传入的表名或列名。
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

from .base_repo import BaseRepository

MASTER_OVERVIEW_TABLES = (
    "Parts", "PartOperations", "ExternalGroups", "OpTypes", "Machines", "Operators", "Materials", "Suppliers", "WorkCalendar",
    "OperatorSkill", "OperatorMachine", "WorkbenchOperatorProfiles", "WorkbenchSupplierOpTypes",
    "WorkbenchSupplierProfiles", "WorkbenchMachineGroupMembers", "WorkbenchMachineGroups",
    "WorkbenchShiftProfiles", "WorkbenchOpTypePolicies",
    "Batches", "BatchMaterials", "BatchMaterialArrivals", "BatchMaterialReviews", "MachineOpTypes",
    "WorkbenchProcessWorkflow", "WorkbenchProcessOperationConfirmations",
    "WorkbenchEntityRefs",
)


class WorkbenchMasterQueryRepository(BaseRepository):
    def present_tables(self) -> Set[str]:
        """sqlite_master 里实际存在的表名集合。"""
        return {row[0] for row in self.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}

    def overview_tables(self, present: Set[str]) -> Dict[str, List[Dict[str, Any]]]:
        """按 MASTER_OVERVIEW_TABLES 顺序整表读取 present 里存在的表。

        present 由调用方在同一事务内用 present_tables() 读出；缺失的表不出现在结果里，
        由调用方按同一常量判断缺口。行 dict 按游标列名构造，不依赖连接的 row_factory。
        """
        tables: Dict[str, List[Dict[str, Any]]] = {}
        for name in MASTER_OVERVIEW_TABLES:
            if name not in present:
                continue
            cursor = self.execute('SELECT * FROM "' + name + '" ORDER BY rowid')
            keys = [column[0] for column in cursor.description]
            tables[name] = [dict(zip(keys, row)) for row in cursor]
        return tables
