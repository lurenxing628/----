"""批次事实读仓储：BatchFacts 的整表快照与单条批次原始行。

整表读取只展开本模块的白名单常量，不接受调用方传表名；不做任何裁决。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_repo import BaseRepository

BATCH_FACT_TABLES = ("Batches", "BatchOperations", "Parts", "PartOperations", "ExternalGroups", "BatchMaterials", "Materials",
                     "Machines", "Operators", "OperatorMachine", "OperatorSkill", "OpTypes", "Suppliers", "WorkbenchSupplierOpTypes",
                     "WorkbenchSupplierProfiles", "WorkbenchOperatorProfiles", "Schedule", "ScheduleCandidateRows", "ScheduleAdjustmentChange",
                     "ScheduleAdjustmentScenarioRow", "OperationExecutionEvents", "WorkbenchEntityRefs", "WorkbenchPlanSourceRefs")


class WorkbenchBatchFactsRepository(BaseRepository):
    def whole_tables(self) -> Dict[str, List[Dict[str, Any]]]:
        """按 BATCH_FACT_TABLES 顺序整表读取（rowid 序），返回 {表名: [行 dict]}。"""
        return {table: self.fetchall('SELECT * FROM "' + table + '" ORDER BY rowid') for table in BATCH_FACT_TABLES}

    def batch_row(self, batch_id: str) -> Optional[Dict[str, Any]]:
        return self.fetchone("SELECT * FROM Batches WHERE batch_id=?", (batch_id,))
