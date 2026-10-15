"""Trial evidence reads: whole-table raw snapshots and permanent source-ref lookups.

Raw snapshots read SQLite storage values, not connection DATE converters: unary +
keeps the storage class and suppresses DECLTYPES, and synthetic aliases prevent a
legacy column named "x [DATE]" from invoking COLNAMES. Explicit per-table methods
serve the trial base; ``read_whole_table`` serves the production-facts capture and
only accepts tables that exist in sqlite_master and are not trial/run bookkeeping.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from core.infrastructure.connection_guards import schema_contract_memo
from core.infrastructure.workbench_run_schema import RUN_TABLES
from core.infrastructure.workbench_trial_schema import TRIAL_TABLES

from .base_repo import BaseRepository
from .sqlite_rows import raw_projection

BOOKKEEPING_TABLES = frozenset(TRIAL_TABLES + RUN_TABLES) | {
    "WorkbenchCommandReceipts", "OperationLogs", "SystemJobState", "sqlite_sequence"}
BOOKKEEPING_TABLES |= {"WorkbenchDashboardStates", "WorkbenchDashboardHistory",
                       "WorkbenchDashboardExternalStates", "WorkbenchDashboardExternalHistory"}


def _quote(name: Any) -> str:
    if type(name) is not str or not name or "\x00" in name:
        raise ValueError("Raw SQLite column/table name is invalid")
    return '"' + name.replace('"', '""') + '"'


class WorkbenchTrialQueryRepository(BaseRepository):
    def __init__(self, conn, logger=None):
        super().__init__(conn, logger=logger)
        self._existing_tables: Optional[Set[str]] = None

    def _read_table(self, name: str) -> Tuple[List[str], List[Dict[str, Any]]]:
        quoted = _quote(name)
        names, columns = raw_projection(self.conn, name)
        cursor = self.execute("SELECT " + columns + " FROM " + quoted + " ORDER BY rowid")
        return names, [dict(zip(names, tuple(row))) for row in cursor]

    def read_whole_table(self, name: str) -> Tuple[List[str], List[Dict[str, Any]]]:
        """(columns, rows) of one existing non-bookkeeping table; any other name is refused."""
        if self._existing_tables is None:
            self._existing_tables = {name for name, (kind, _table, _sql) in schema_contract_memo(self.conn).structure.objects.items() if kind == "table"}
        if name not in self._existing_tables or name in BOOKKEEPING_TABLES:
            raise ValueError("Raw table read is not allowed: " + str(name))
        return self._read_table(name)

    def raw_rows_by_ids(self, name: str, ids) -> List[Dict[str, Any]]:
        """Selected legacy source rows retain all raw storage columns, in bounded ID chunks."""
        if name not in ("Schedule", "ScheduleCandidateRows", "ScheduleAdjustmentScenarioRow"):
            raise ValueError("Raw selected trial source is not allowed: " + str(name))
        names, columns = raw_projection(self.conn, name)
        wanted, result = sorted(set(ids)), []
        for offset in range(0, len(wanted), 400):
            chunk = wanted[offset:offset + 400]
            cursor = self.execute("SELECT " + columns + " FROM " + _quote(name)
                                  + " WHERE id IN (" + ",".join("?" for _ in chunk) + ") ORDER BY rowid", chunk)
            result.extend(dict(zip(names, tuple(row))) for row in cursor)
        return result

    # ---- explicit whole-table reads used by the trial base ----
    def raw_batch_operations(self) -> List[Dict[str, Any]]:
        return self._read_table("BatchOperations")[1]

    def raw_batches(self) -> List[Dict[str, Any]]:
        return self._read_table("Batches")[1]

    def raw_parts(self) -> List[Dict[str, Any]]:
        return self._read_table("Parts")[1]

    def raw_entity_refs(self) -> List[Dict[str, Any]]:
        return self._read_table("WorkbenchEntityRefs")[1]

    def raw_schedule(self) -> List[Dict[str, Any]]:
        return self._read_table("Schedule")[1]

    def raw_candidate_rows(self) -> List[Dict[str, Any]]:
        return self._read_table("ScheduleCandidateRows")[1]

    def raw_scenario_rows(self) -> List[Dict[str, Any]]:
        return self._read_table("ScheduleAdjustmentScenarioRow")[1]

    # ---- permanent identity and official history facts ----
    def active_operation_source_refs(self) -> List[Dict[str, Any]]:
        return self.fetchall("SELECT source_key,ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1")

    def active_source_refs_by_kind(self, kind: str) -> List[Dict[str, Any]]:
        return self.fetchall("SELECT source_key,ref FROM WorkbenchPlanSourceRefs WHERE kind=? AND active=1", (kind,))
