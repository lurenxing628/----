"""基础资料只读事实：资料总览整表快照。

整表读取只展开本模块的白名单常量，不拼接调用方传入的表名或列名。
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from core.infrastructure.connection_guards import schema_contract_memo

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
    def overview_tables(self) -> Tuple[Dict[str, List[Dict[str, Any]]], Set[str]]:
        """按 MASTER_OVERVIEW_TABLES 顺序整表读取当前存在的表。

        返回 (表名 -> 行 dict 列表, sqlite_master 里实际存在的表名集合)；缺失的表不出现在结果里，
        由调用方按同一常量判断缺口。行 dict 按游标列名构造，不依赖连接的 row_factory。
        """
        present = {name for name, (kind, _table, _sql) in schema_contract_memo(self.conn).structure.objects.items() if kind == "table"}
        tables: Dict[str, List[Dict[str, Any]]] = {}
        for name in MASTER_OVERVIEW_TABLES:
            if name not in present:
                continue
            cursor = self.execute('SELECT * FROM "' + name + '" ORDER BY rowid')
            keys = [column[0] for column in cursor.description]
            tables[name] = [dict(zip(keys, row)) for row in cursor]
        return tables, present
