"""Request-local, SELECT-only catalog pages using existing indexes.

History seek order is version DESC (distinct versions); the head of each selected
version is schedule_time DESC, id DESC, matching the existing identity query.
No page uses OFFSET or COUNT. One lookahead header/key is read, but its details
are never inspected.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .schedule_plan_query_repo import SCHEDULE_PLAN_ROWS_SQL, SchedulePlanQueryRepository
from .schedule_rows import ScheduleTimeSpanRow

DEFAULT_PLAN_PAGE_SIZE = 20
MAX_PLAN_PAGE_SIZE = 50
MAX_PLAN_VERSION = (1 << 63) - 1
_OPERATION_DETAIL_FIELDS = (
    "op_code", "batch_id", "piece_id", "seq", "op_type_name", "source", "op_status", "supplier_id",
    "part_no", "part_name", "due_date", "priority", "supplier_name",
)


def validate_page_size(value: int) -> None:
    if type(value) is not int or not 1 <= value <= MAX_PLAN_PAGE_SIZE:
        raise ValueError("目录每页数量必须是 1 到 50 的整数。")


def validate_before_version(value: Optional[int]) -> None:
    if value is not None and (type(value) is not int or not 1 <= value <= MAX_PLAN_VERSION):
        raise ValueError("历史页版本边界必须是 SQLite 范围内的正整数。")


class WorkbenchPlanCatalogRepository(SchedulePlanQueryRepository):
    """Strict-query repository restricted to one catalog page, not full history."""

    def __init__(self, conn: sqlite3.Connection, logger=None):
        super().__init__(conn, logger=logger)
        self._histories: Dict[int, Optional[Dict[str, Any]]] = {}
        self._history_rows: Dict[int, List[Dict[str, Any]]] = {}
        self._spans: Dict[int, Optional[ScheduleTimeSpanRow]] = {}
        self._latest_version: Optional[int] = None
        self._latest_version_loaded = False

    def latest_version(self) -> Optional[int]:
        if not self._latest_version_loaded:
            row = self.fetchone("SELECT version FROM ScheduleHistory WHERE version > 0 ORDER BY version DESC LIMIT 1")
            self._latest_version = int(row["version"]) if row else None
            self._latest_version_loaded = True
        return self._latest_version

    def history_page(
        self, *, page_size: int, before_version: Optional[int],
    ) -> Tuple[List[Dict[str, Any]], bool]:
        validate_page_size(page_size)
        validate_before_version(before_version)
        where, params = ("", []) if before_version is None else ("WHERE version < ?", [before_version])
        keys = self.fetchall(
            f"SELECT DISTINCT version FROM ScheduleHistory {where} ORDER BY version DESC LIMIT ?",
            params + [page_size + 1],
        )
        page_versions = [int(key["version"]) for key in keys[:page_size]]
        self.prefetch_history_rows(page_versions)
        rows = []
        for version in page_versions:
            row = self.get_history_identity_row(version)
            if row is None:
                raise RuntimeError("目录读取期间排产历史消失；调用方必须提供一致读快照。")
            rows.append(row)
        return rows, len(keys) > page_size

    def get_history_identity_row(self, version: int) -> Optional[Dict[str, Any]]:
        if version not in self._histories:
            rows = self.history_rows(version)
            self._histories[version] = {key: rows[0][key] for key in ("version", "result_status", "result_summary")} if rows else None
        return self._histories[version]

    def history_rows(self, version: int) -> List[Dict[str, Any]]:
        if version not in self._history_rows:
            self.prefetch_history_rows([version])
        return self._history_rows[version]

    def prefetch_history_rows(self, versions):
        pending = [version for version in dict.fromkeys(versions) if version not in self._history_rows]
        if not pending:
            return
        selected = "id, +schedule_time AS schedule_time, version, strategy, batch_count, op_count, result_status, result_summary, created_by"
        for start in range(0, len(pending), 400):
            chunk = pending[start:start + 400]
            if len(chunk) == 1:
                self._history_rows[chunk[0]] = self.fetchall(
                    f"SELECT {selected} FROM ScheduleHistory WHERE version=? ORDER BY schedule_time DESC,id DESC LIMIT 2", chunk)
                continue
            self._history_rows.update((version, []) for version in chunk)
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall(
                f"SELECT {selected} FROM ScheduleHistory WHERE version IN ({marks}) ORDER BY version,schedule_time DESC,id DESC", chunk)
            for row in rows:
                self._history_rows[row["version"]].append(row)

    def get_plan_time_span(
        self, *, version: int,
    ) -> Optional[ScheduleTimeSpanRow]:
        if version not in self._spans:
            self._spans[version] = super().get_plan_time_span(version=version)
        return self._spans[version]

    def first_raw_plan_identity_row(
        self, *, version: int,
    ) -> Optional[Dict[str, Any]]:
        return self.fetchone(
            "SELECT id AS source_row_id, lock_status FROM (" + SCHEDULE_PLAN_ROWS_SQL + ") raw ORDER BY id ASC LIMIT 1",
            (version,),
        )

    def iter_raw_plan_rows(self, *, version: int) -> Iterator[Dict[str, Any]]:
        """Stream plan rows in id order without declared DATE/TIMESTAMP conversion."""
        return self.iter_rows(
            "SELECT id, op_id, machine_id, operator_id, +start_time AS start_time, "
            "+end_time AS end_time, lock_status, version FROM Schedule WHERE version = ? ORDER BY id ASC", (version,))

    def list_plan_storage_rows(self, *, version: Any) -> List[Dict[str, Any]]:
        """Capture every persisted field without declared DATE/TIMESTAMP conversion."""
        return self.fetchall(
            "SELECT r.id, r.op_id, r.machine_id, r.operator_id, +r.start_time AS start_time, "
            '+r.end_time AS end_time, r.lock_status, r.version, +r.created_at AS created_at FROM "Schedule" r '
            "WHERE r.version = ? ORDER BY r.id ASC, r.rowid ASC", (version,))

    def enrich_arrangements(self, arrangements, *, captured_machines=None):
        """Enrich captured arrangements; supplied machines are complete, including missing keys."""
        operation_ids = list(dict.fromkeys(row["op_id"] for row in arrangements))
        operations = {}
        for start in range(0, len(operation_ids), 400):
            chunk = operation_ids[start:start + 400]
            rows = self.fetchall("""SELECT bo.id AS op_id, bo.op_code, bo.batch_id, bo.piece_id, bo.seq,
                bo.op_type_name, bo.source, bo.status AS op_status, bo.supplier_id,
                b.part_no, b.part_name, CAST(b.due_date AS TEXT) AS due_date, b.priority,
                sup.name AS supplier_name
                FROM BatchOperations bo LEFT JOIN Batches b ON b.batch_id=bo.batch_id
                LEFT JOIN Suppliers sup ON sup.supplier_id=bo.supplier_id
                WHERE bo.id IN (""" + ",".join("?" for _ in chunk) + ")", chunk)
            operations.update((row["op_id"], row) for row in rows)
        names = {}
        for kind, table, column in (("machine", "Machines", "machine_id"), ("operator", "Operators", "operator_id")):
            if kind == "machine" and captured_machines is not None:
                names[kind] = {str(row[column]): row["name"] for row in captured_machines}
                continue
            keys = list(dict.fromkeys(row[column] for row in arrangements if row[column] not in (None, "")))
            names[kind] = {}
            for start in range(0, len(keys), 400):
                chunk = keys[start:start + 400]
                rows = self.fetchall("SELECT " + column + ",name FROM " + table + " WHERE " + column +
                                     " IN (" + ",".join("?" for _ in chunk) + ")", chunk)
                names[kind].update((str(row[column]), row["name"]) for row in rows)
        result = []
        for row in arrangements:
            operation = operations.get(row["op_id"], {})
            detail = {key: operation.get(key) for key in _OPERATION_DETAIL_FIELDS}
            detail.update({key: row[key] for key in
                           ("op_id", "start_time", "end_time", "lock_status", "machine_id", "operator_id", "version")})
            detail.update(schedule_id=row["id"],
                          machine_name=names["machine"].get(str(row["machine_id"])) if row["machine_id"] is not None else None,
                          operator_name=names["operator"].get(str(row["operator_id"])) if row["operator_id"] is not None else None)
            result.append(detail)
        return result
