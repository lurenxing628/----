"""Request-local, SELECT-only catalog pages using existing indexes.

History seek order is version DESC (distinct versions); the head of each selected
version is schedule_time DESC, id DESC, matching the existing identity query.
Scenario seek order is scenario_id COLLATE BINARY ASC, deliberately independent
of the full catalog's chronological order. Neither page uses OFFSET or COUNT.
One lookahead header/key is read, but its details are never inspected.

Use a fresh instance per page under the caller's read snapshot. Header, role and
span caches are request-local; no database/global cache or schema changes. The
lean history projection intentionally omits schedule_row_count: identity only
needs version/status/summary, and counting rows would touch unnecessary details.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, Iterator, List, Optional, Tuple

from core.infrastructure.connection_guards import schema_contract_memo
from core.models.schedule_plan_role import (
    SOURCE_ADJUSTMENT_SCENARIO_ROWS,
    SOURCE_CANDIDATE_ROWS,
    SOURCE_SCHEDULE,
)

from .schedule_plan_query_repo import SCENARIO_HEADER_COLUMNS_SQL, SCENARIO_PLAN_ROWS_SQL, SchedulePlanQueryRepository
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


def validate_after_scenario_id(value: Optional[str]) -> None:
    if value is not None and (not isinstance(value, str) or not value or "\x00" in value):
        raise ValueError("场景页边界必须是非空且不含空字符的内部场景编号。")


class WorkbenchPlanCatalogRepository(SchedulePlanQueryRepository):
    """Strict-query repository restricted to one catalog page, not full history."""

    def __init__(self, conn: sqlite3.Connection, logger=None, *, role_reader=None):
        super().__init__(conn, logger=logger)
        self._role_reader = role_reader
        self._histories: Dict[int, Optional[Dict[str, Any]]] = {}
        self._history_rows: Dict[int, List[Dict[str, Any]]] = {}
        self._roles: Dict[int, List[Dict[str, Any]]] = {}
        self._scenarios: Dict[str, Optional[Dict[str, Any]]] = {}
        self._spans: Dict[Tuple[int, str, Optional[int], Optional[str]], Optional[ScheduleTimeSpanRow]] = {}
        self._storage_columns: Dict[str, List[str]] = {}
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

    def scenario_page(
        self, *, page_size: int, after_scenario_id: Optional[str],
    ) -> Tuple[List[Dict[str, Any]], bool]:
        validate_page_size(page_size)
        validate_after_scenario_id(after_scenario_id)
        where, params = ("", []) if after_scenario_id is None else (
            "WHERE scenario_id COLLATE BINARY > ?", [after_scenario_id],
        )
        rows = self.fetchall(
            "SELECT " + SCENARIO_HEADER_COLUMNS_SQL + " FROM ScheduleAdjustmentScenario "
            f"{where} ORDER BY scenario_id COLLATE BINARY ASC LIMIT ?",
            params + [page_size + 1],
        )
        selected = rows[:page_size]
        self._scenarios.update((str(row["scenario_id"]), row) for row in selected)
        return selected, len(rows) > page_size

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
        if "ScheduleHistory" not in self._storage_columns:
            self._storage_columns["ScheduleHistory"] = [str(row[1]) for row in schema_contract_memo(self.conn).structure.table_info("ScheduleHistory")]
        selected = ",".join('CASE WHEN 1 THEN "' + name.replace('"', '""') + '" END AS "' + name.replace('"', '""') + '"'
                            for name in self._storage_columns["ScheduleHistory"])
        for start in range(0, len(pending), 400):
            chunk = pending[start:start + 400]
            if len(chunk) == 1:
                self._history_rows[chunk[0]] = self.fetchall("SELECT " + selected +
                    " FROM ScheduleHistory WHERE version=? ORDER BY schedule_time DESC,id DESC LIMIT 2", chunk)
                continue
            self._history_rows.update((version, []) for version in chunk)
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall("SELECT " + selected + " FROM ScheduleHistory WHERE id IN (SELECT id FROM (SELECT id,"
                "ROW_NUMBER() OVER (PARTITION BY version ORDER BY schedule_time DESC,id DESC) AS history_position "
                "FROM ScheduleHistory WHERE version IN (" + marks + ")) WHERE history_position <= 2) "
                "ORDER BY version,schedule_time DESC,id DESC", chunk)
            for row in rows:
                self._history_rows[row["version"]].append(row)

    def list_plan_role_options(self, version: int) -> List[Dict[str, Any]]:
        if version not in self._roles:
            self._roles[version] = (self._role_reader(version) if self._role_reader is not None else
                                    super().list_plan_role_options(version))
        return self._roles[version]

    def get_scenario_context(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        if scenario_id not in self._scenarios:
            self._scenarios[scenario_id] = super().get_scenario_context(scenario_id)
        return self._scenarios[scenario_id]

    def _plan_rows_sql(self, *, source_table, candidate_id, scenario_id):
        if source_table == SOURCE_ADJUSTMENT_SCENARIO_ROWS:
            scenario_key = str(scenario_id or "")
            if not scenario_key:
                raise ValueError("scenario_id is required for adjustment_scenario_rows plan")
            return SCENARIO_PLAN_ROWS_SQL, [scenario_key]
        return super()._plan_rows_sql(
            source_table=source_table, candidate_id=candidate_id, scenario_id=scenario_id,
        )

    def get_plan_time_span(
        self, *, version: int, source_table: str, candidate_id: Optional[int], scenario_id: Optional[str] = None,
    ) -> Optional[ScheduleTimeSpanRow]:
        key = (version, source_table, None if source_table == SOURCE_SCHEDULE else candidate_id, scenario_id)
        if key not in self._spans:
            self._spans[key] = super().get_plan_time_span(
                version=version, source_table=source_table, candidate_id=candidate_id, scenario_id=scenario_id,
            )
        return self._spans[key]

    def first_raw_plan_identity_row(
        self, *, version: int, source_table: str, candidate_id: Optional[int], scenario_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        sql, extra = self._plan_rows_sql(source_table=source_table, candidate_id=candidate_id, scenario_id=scenario_id)
        return self.fetchone("SELECT id AS source_row_id, lock_status FROM (" + sql + ") raw ORDER BY id ASC LIMIT 1",
                             [version] + extra)

    def iter_raw_plan_rows(
        self, *, version: int, source_table: str, candidate_id: Optional[int], scenario_id: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Stream plan rows in id order without declared DATE/TIMESTAMP conversion."""
        sql, extra = self._plan_rows_sql(source_table=source_table, candidate_id=candidate_id, scenario_id=scenario_id)
        fields = ("id", "op_id", "machine_id", "operator_id", "start_time", "end_time", "lock_status", "version")
        selected = ", ".join("CASE WHEN 1 THEN raw." + field + " END AS " + field for field in fields)
        return self.iter_rows("SELECT " + selected + " FROM (" + sql + ") raw ORDER BY raw.id ASC", [version] + extra)

    def list_plan_storage_rows(
        self, *, version: Any, source_table: str, candidate_id: Optional[int], scenario_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Capture every persisted field without declared DATE/TIMESTAMP conversion."""
        _, extra = self._plan_rows_sql(
            source_table=source_table, candidate_id=candidate_id, scenario_id=scenario_id,
        )
        if source_table == SOURCE_SCHEDULE:
            table, joins, where = "Schedule", "", "r.version = ?"
        elif source_table == SOURCE_CANDIDATE_ROWS:
            table, joins, where = "ScheduleCandidateRows", "", "r.version = ? AND r.candidate_id = ?"
        else:
            table = "ScheduleAdjustmentScenarioRow"
            joins = " JOIN ScheduleAdjustmentScenario s ON s.scenario_id = r.scenario_id"
            where = "s.base_version = ? AND r.scenario_id = ? AND s.status = 'active'"
        if table not in self._storage_columns:
            self._storage_columns[table] = [str(row[1]) for row in schema_contract_memo(self.conn).structure.table_info(table)]
        expressions = []
        for name in self._storage_columns[table]:
            quoted = '"' + name.replace('"', '""') + '"'
            expressions.append(f"CASE WHEN 1 THEN r.{quoted} ELSE NULL END AS {quoted}")
        sql = "SELECT " + ", ".join(expressions) + f' FROM "{table}" r{joins} WHERE {where}'
        return self.fetchall(sql + " ORDER BY r.id ASC, r.rowid ASC", [version] + extra)

    def enrich_arrangements(self, arrangements, *, version, captured_machines=None):
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
                           ("op_id", "start_time", "end_time", "lock_status", "machine_id", "operator_id")})
            detail.update(schedule_id=row["id"], version=row.get("version", version),
                          machine_name=names["machine"].get(str(row["machine_id"])) if row["machine_id"] is not None else None,
                          operator_name=names["operator"].get(str(row["operator_id"])) if row["operator_id"] is not None else None)
            result.append(detail)
        return result
