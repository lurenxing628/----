"""批次事实读仓储：BatchFacts 的整表快照与单条批次原始行。

整表读取只展开本模块的白名单常量，不接受调用方传表名；不做任何裁决。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_repo import BaseRepository

BATCH_FACT_TABLES = ("Batches", "BatchOperations", "Parts", "PartOperations", "ExternalGroups", "BatchMaterials", "BatchMaterialReviews", "BatchMaterialStages", "BatchMaterialArrivals", "BatchQuantitySplits", "Materials",
                     "Machines", "MachineOpTypes", "Operators", "OperatorMachine", "OperatorSkill", "OpTypes", "Suppliers", "WorkbenchSupplierOpTypes",
                     "WorkbenchSupplierProfiles", "WorkbenchOperatorProfiles", "WorkbenchEntityRefs",
                     "WorkbenchOutsourcingReceipts", "BatchExternalContexts")
CHOICE_CATALOG_TABLES = ("Parts", "Machines", "Operators", "Suppliers", "OperatorMachine")


class WorkbenchBatchFactsRepository(BaseRepository):
    def plan_reference_counts(self):
        """Only live operation references affect batch maintenance, regardless of plan contents."""
        rows = self.fetchall("""SELECT p.op_id, COUNT(*) AS reference_count
            FROM Schedule p JOIN BatchOperations o ON o.id=p.op_id
            GROUP BY p.op_id ORDER BY p.op_id""")
        return {row["op_id"]: row["reference_count"] for row in rows}

    def whole_tables(self) -> Dict[str, List[Dict[str, Any]]]:
        """按 BATCH_FACT_TABLES 顺序整表读取（rowid 序），返回 {表名: [行 dict]}。"""
        return {table: self.fetchall('SELECT * FROM "' + table + '" ORDER BY rowid') for table in BATCH_FACT_TABLES}

    def choice_tables(self) -> Dict[str, List[Dict[str, Any]]]:
        """Creation choices need only base catalogs, authorizations and existing refs."""
        tables = {table: self.fetchall('SELECT * FROM "' + table + '" ORDER BY rowid') for table in CHOICE_CATALOG_TABLES}
        tables["WorkbenchEntityRefs"] = self.fetchall('''SELECT * FROM "WorkbenchEntityRefs"
            WHERE kind IN ('part', 'machine', 'operator', 'supplier') ORDER BY rowid''')
        return tables

    def batch_row(self, batch_id: str) -> Optional[Dict[str, Any]]:
        return self.fetchone("SELECT * FROM Batches WHERE batch_id=?", (batch_id,))
