"""预检事实读仓储：固定白名单整表快照，以及按 sqlite_master 校验后的整表原始元组读取（指纹用）。

read_whole_table 只接受当前库 sqlite_master 里实际存在的表，表名在本模块内引号化；不做任何裁决。
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from core.infrastructure.schema_probe import table_names

from .base_repo import BaseRepository
from .batch_external_context_repo import BatchExternalContextRepository
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

    def preflight_tables(self, *, capture=None) -> Dict[str, List[Dict[str, Any]]]:
        """按 PREFLIGHT_TABLES 顺序整表读取（rowid 序），返回 {表名: [行 dict]}。"""
        if capture is not None:
            return {name: self._captured_business_rows(name, capture) for name in PREFLIGHT_TABLES}
        return {name: (BatchExternalContextRepository(self.conn).rows_for_readonly_preflight()
                       if name == "BatchExternalContexts" else self._optional_legacy_rows(name))
                for name in PREFLIGHT_TABLES}

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
        info = list(self.execute("PRAGMA table_info(" + _quote(name) + ")"))
        columns, projection = raw_projection(self.conn, name, column_info=info)
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

    def read_whole_table(self, name: str) -> Iterator[Tuple[Any, ...]]:
        """整表按 rowid 序流式产出原始值元组；表名必须真实存在于 sqlite_master（本实例内缓存一次）。

        表名校验与语句执行在调用时完成（未知表立即 ValueError），行只在迭代时物化，指纹计算不整表装内存。"""
        if name not in self._present_tables():
            raise ValueError("unknown table: " + repr(name))
        quoted = _quote(name)
        _, projection = raw_projection(self.conn, name)
        cursor = self.execute("SELECT " + projection + " FROM " + quoted + " ORDER BY rowid")
        return (tuple(row) for row in cursor)
