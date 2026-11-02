"""预检事实读仓储：从共享捕获读取业务行，并保留整表原始值和转换器输入。"""

from __future__ import annotations

import re
import sqlite3
from typing import Any, Dict, List

from core.infrastructure.schema_structure import SchemaStructure
from core.infrastructure.sqlite_udf import NON_INPUT_RECEIPT_ACTIONS, NON_INPUT_RECEIPT_PREFIXES

from .base_repo import BaseRepository
from .sqlite_rows import raw_projection

PREFLIGHT_TABLES = ("Batches", "BatchOperations", "BatchExternalContexts", "Parts", "PartOperations", "ExternalGroups", "BatchMaterials", "BatchMaterialReviews", "BatchMaterialStages", "BatchMaterialArrivals", "BatchQuantitySplits",
                    "Machines", "MachineOpTypes", "Operators", "OperatorMachine", "OperatorSkill", "OpTypes", "Suppliers",
                    "WorkbenchSupplierOpTypes", "WorkbenchOperatorProfiles", "Schedule",
                    "WorkbenchEntityRefs", "WorkbenchPlanSourceRefs", "ScheduleConfig")


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class WorkbenchPreflightFactsRepository(BaseRepository):
    def __init__(self, conn, logger=None, *, structure: SchemaStructure):
        super().__init__(conn, logger)
        self.structure = structure
        self.converters = {}

    def preflight_tables(self, capture) -> Dict[str, List[Dict[str, Any]]]:
        """按 PREFLIGHT_TABLES 顺序整表读取（rowid 序），返回 {表名: [行 dict]}。"""
        return {name: self._captured_business_rows(name, capture) for name in PREFLIGHT_TABLES}

    def _captured_business_rows(self, name, capture):
        rows = capture.business_table(name)
        return sorted(rows, key=lambda row: row["operation_id"]) if name == "BatchExternalContexts" else rows

    def table_converters(self, name):
        if name not in self.converters:
            info = self.structure.table_info(name)
            self.converters[name] = {
                str(row[1]): sqlite3.converters[kind]
                for row in info
                for kind in (re.split(r"[ (]", str(row[2]), maxsplit=1)[0].upper(),)
                if kind in sqlite3.converters
            }
        return self.converters[name]

    def capture_table(self, name):
        """Capture actual columns and original storage values once in rowid order."""
        if not self.structure.has_table(name):
            raise ValueError("unknown table: " + repr(name))
        info = self.structure.table_info(name)
        columns, projection = raw_projection(name, info)
        where, params = self._capture_predicate(name, columns)
        rows = [tuple(row) for row in self.execute(
            "SELECT " + projection + " FROM " + _quote(name) + where + " ORDER BY rowid", params)]
        return columns, rows

    def _capture_predicate(self, name, columns):
        if name != "WorkbenchCommandReceipts" or "action" not in columns:
            return "", ()
        checks = (
            '"action" COLLATE BINARY IN (' + ",".join("?" for _ in NON_INPUT_RECEIPT_ACTIONS) + ")",
            *('"action" GLOB ?' for _ in NON_INPUT_RECEIPT_PREFIXES),
        )
        params = (*NON_INPUT_RECEIPT_ACTIONS, *(prefix + "*" for prefix in NON_INPUT_RECEIPT_PREFIXES))
        return " WHERE NOT (typeof(\"action\")='text' AND (" + " OR ".join(checks) + "))", params
