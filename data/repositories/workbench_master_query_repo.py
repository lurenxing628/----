"""基础资料只读事实：资料总览整表快照、旧导航按业务键取单条实体。

整表读取只展开本模块的白名单常量；旧导航实体查询按 kind 选固定 SQL，不拼接调用方传入的表名或列名。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.infrastructure.schema_probe import table_names

from .base_repo import BaseRepository

MASTER_OVERVIEW_TABLES = (
    "Parts", "PartOperations", "ExternalGroups", "OpTypes", "Machines", "Operators", "Materials", "Suppliers", "WorkCalendar",
    "OperatorSkill", "OperatorMachine", "WorkbenchOperatorProfiles", "WorkbenchSupplierOpTypes",
    "WorkbenchSupplierProfiles", "WorkbenchMachineGroupMembers", "WorkbenchMachineGroups",
    "WorkbenchShiftProfiles", "WorkbenchShiftPatternDays", "WorkbenchOpTypePolicies",
    "Batches", "BatchMaterials", "OperatorCalendar",
    "WorkbenchProcessWorkflow", "WorkbenchProcessOperationConfirmations",
    "WorkbenchEntityRefs",
)

_LEGACY_ENTITY_SQL = {
    "machine": "SELECT * FROM Machines WHERE machine_id = ?",
    "operator": "SELECT * FROM Operators WHERE operator_id = ?",
    "op_type": "SELECT * FROM OpTypes WHERE op_type_id = ?",
    "part": "SELECT * FROM Parts WHERE part_no = ?",
    "supplier": "SELECT * FROM Suppliers WHERE supplier_id = ?",
    "batch": "SELECT * FROM Batches WHERE batch_id = ?",
}
LEGACY_ENTITY_KINDS = tuple(_LEGACY_ENTITY_SQL)


class WorkbenchMasterQueryRepository(BaseRepository):
    def overview_tables(self) -> Tuple[Dict[str, List[Dict[str, Any]]], Set[str]]:
        """按 MASTER_OVERVIEW_TABLES 顺序整表读取当前存在的表。

        返回 (表名 -> 行 dict 列表, sqlite_master 里实际存在的表名集合)；缺失的表不出现在结果里，
        由调用方按同一常量判断缺口。行 dict 按游标列名构造，不依赖连接的 row_factory。
        """
        present = table_names(self.conn)
        tables: Dict[str, List[Dict[str, Any]]] = {}
        for name in MASTER_OVERVIEW_TABLES:
            if name not in present:
                continue
            cursor = self.execute('SELECT * FROM "' + name + '" ORDER BY rowid')
            keys = [column[0] for column in cursor.description]
            tables[name] = [dict(zip(keys, row)) for row in cursor]
        return tables, present

    def legacy_entity_row(self, kind: str, business_key: str) -> Optional[Dict[str, Any]]:
        """按业务键取旧导航实体原始行；kind 只能是 LEGACY_ENTITY_KINDS 之一。"""
        if kind not in _LEGACY_ENTITY_SQL:
            raise ValueError("unsupported legacy entity kind: " + repr(kind))
        return self.fetchone(_LEGACY_ENTITY_SQL[kind], (business_key,))
