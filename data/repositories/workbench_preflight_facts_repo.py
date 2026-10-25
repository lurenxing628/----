"""预检事实读仓储：从共享捕获读取业务行，并保留整表原始值和转换器输入。"""

from __future__ import annotations

import re
import sqlite3
from typing import Any, Dict, List, Optional, Set

from core.infrastructure.connection_guards import schema_contract_memo

from .base_repo import BaseRepository
from .sqlite_rows import raw_projection

PREFLIGHT_TABLES = ("Batches", "BatchOperations", "BatchExternalContexts", "Parts", "PartOperations", "ExternalGroups", "BatchMaterials", "BatchMaterialReviews", "BatchMaterialStages", "BatchMaterialArrivals", "BatchQuantitySplits",
                    "Machines", "MachineOpTypes", "Operators", "OperatorMachine", "OperatorSkill", "OpTypes", "Suppliers",
                    "WorkbenchSupplierOpTypes", "WorkbenchOperatorProfiles", "OperationExecutionEvents", "Schedule",
                    "WorkbenchEntityRefs", "WorkbenchPlanSourceRefs", "ScheduleConfig")


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class WorkbenchPreflightFactsRepository(BaseRepository):
    def __init__(self, conn, logger=None, *, present_tables=None,
                 non_input_receipt_actions=(), non_input_receipt_prefixes=()):
        super().__init__(conn, logger)
        self._present: Optional[Set[str]] = set(present_tables) if present_tables is not None else None
        self.column_types, self.codec_inputs, self.converters = {}, {}, {}
        self._non_input_receipt_actions = tuple(non_input_receipt_actions)
        self._non_input_receipt_prefixes = tuple(non_input_receipt_prefixes)

    def _present_tables(self) -> Set[str]:
        if self._present is None:
            self._present = {name for name, (kind, _table, _sql) in schema_contract_memo(self.conn).structure.objects.items() if kind == "table"}
        return self._present

    def preflight_tables(self, capture) -> Dict[str, List[Dict[str, Any]]]:
        """按 PREFLIGHT_TABLES 顺序整表读取（rowid 序），返回 {表名: [行 dict]}。"""
        return {name: self._captured_business_rows(name, capture) for name in PREFLIGHT_TABLES}

    def _captured_business_rows(self, name, capture):
        introduced = {"BatchExternalContexts": 33, "MachineOpTypes": 35, "BatchMaterialReviews": 36,
                      "BatchMaterialStages": 36, "BatchMaterialArrivals": 36, "BatchQuantitySplits": 36}
        if name not in capture.table_names and name in introduced:
            versions = capture.table("SchemaVersion")
            version = versions[0].get("version") if len(versions) == 1 else None
            if type(version) is int and version < introduced[name]:
                return []
        rows = capture.business_table(name)
        return sorted(rows, key=lambda row: row["operation_id"]) if name == "BatchExternalContexts" else rows

    def capture_table(self, name):
        """Capture actual columns and original storage values once in rowid order."""
        if name not in self._present_tables():
            raise ValueError("unknown table: " + repr(name))
        info = schema_contract_memo(self.conn).structure.table_info(name)
        columns, projection = raw_projection(name, info)
        self.column_types[name] = {str(row[1]): str(row[2]) for row in info}
        codecs = {column: sqlite3.converters[kind] for column, declared in self.column_types[name].items()
                  for kind in (re.split(r"[ (]", declared, maxsplit=1)[0].upper(),) if kind in sqlite3.converters}
        encoded = ["CAST(+" + _quote(column) + ' AS BLOB) AS "wb_codec_' + str(index) + '"'
                   for index, column in enumerate(codecs)]
        if encoded:
            projection += "," + ",".join(encoded)
        where, params = self._capture_predicate(name, columns)
        values = [tuple(row) for row in self.execute(
            "SELECT " + projection + " FROM " + _quote(name) + where + " ORDER BY rowid", params)]
        rows = [row[:len(columns)] for row in values]
        self.codec_inputs[name] = [row[len(columns):] for row in values]
        self.converters[name] = codecs
        return columns, rows

    def _capture_predicate(self, name, columns):
        if name != "WorkbenchCommandReceipts" or "action" not in columns:
            return "", ()
        checks, params = [], []
        if self._non_input_receipt_actions:
            checks.append('"action" COLLATE BINARY IN (' + ",".join(
                "?" for _ in self._non_input_receipt_actions) + ")")
            params.extend(self._non_input_receipt_actions)
        for prefix in self._non_input_receipt_prefixes:
            checks.append('"action" GLOB ?')
            params.append(prefix + "*")
        if not checks:
            return "", ()
        return " WHERE NOT (typeof(\"action\")='text' AND (" + " OR ".join(checks) + "))", tuple(params)
