"""Official-plan and adoption-baseline evidence reads: raw rows, history heads, source refs.

Raw reads keep SQLite storage classes (unary + and synthetic aliases bypass both
DECLTYPES and COLNAMES conversion) and are limited to a fixed table allowlist.
Only facts are returned; the service layer classifies every gap itself.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .base_repo import BaseRepository

_RAW_TABLES = {
    "Schedule": '"Schedule"',
    "WorkbenchPlanSourceRefs": '"WorkbenchPlanSourceRefs"',
    "WorkbenchTaskRefs": '"WorkbenchTaskRefs"',
}

_SOURCE_LOOKUPS = {
    ("WorkbenchRunJobs", "run_ref"): "SELECT 1 FROM WorkbenchRunJobs WHERE run_ref=?",
    ("WorkbenchRunCandidates", "candidate_ref"): "SELECT 1 FROM WorkbenchRunCandidates WHERE candidate_ref=?",
    ("WorkbenchTrialScenarios", "scenario_ref"): "SELECT 1 FROM WorkbenchTrialScenarios WHERE scenario_ref=?",
    ("WorkbenchTrialDrafts", "draft_ref"): "SELECT 1 FROM WorkbenchTrialDrafts WHERE draft_ref=?",
}


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class WorkbenchPlanBaselineRepository(BaseRepository):
    # ---- raw storage-class reads (allowlisted tables) ----
    def _raw_select(self, table: str) -> Optional[Tuple[List[str], str]]:
        """(columns, "SELECT +col AS raw_i,... FROM <table>") or None when the table has no columns."""
        source = _RAW_TABLES[table]
        columns = [row[0] for row in self.execute("SELECT name FROM pragma_table_info(?)", (table,))]
        if not columns:
            return None
        # Unary + and synthetic aliases bypass both DECLTYPES and COLNAMES conversion.
        fields = ",".join("+" + _quote(name) + " AS raw_" + str(i) for i, name in enumerate(columns))
        return columns, "SELECT " + fields + " FROM " + source

    def _raw_rows(self, columns: List[str], sql: str, params: Sequence[Any]) -> List[Dict[str, Any]]:
        return [dict(zip(columns, row)) for row in self.execute(sql, params)]

    def raw_schedule_rows_by_version(self, version: Any, *, limit: int) -> Optional[List[Dict[str, Any]]]:
        """Whole Schedule rows of one version in rowid order, at most ``limit`` rows; None if the table is absent."""
        selected = self._raw_select("Schedule")
        if selected is None:
            return None
        columns, select = selected
        return self._raw_rows(columns, select + " WHERE version=? ORDER BY rowid LIMIT ?", (version, limit))

    def raw_source_refs_by_refs(self, refs: Sequence[str]) -> Optional[List[Dict[str, Any]]]:
        """Whole WorkbenchPlanSourceRefs rows whose ref is in ``refs``; None if the table is absent."""
        selected = self._raw_select("WorkbenchPlanSourceRefs")
        if selected is None:
            return None
        columns, select = selected
        marks = ",".join("?" for _ in refs)
        return self._raw_rows(columns, select + " WHERE ref IN (" + marks + ") ORDER BY rowid", list(refs))

    def raw_task_refs_by_plan(self, plan_ref: str) -> Optional[List[Dict[str, Any]]]:
        """Whole WorkbenchTaskRefs rows of one plan in rowid order; None if the table is absent."""
        selected = self._raw_select("WorkbenchTaskRefs")
        if selected is None:
            return None
        columns, select = selected
        return self._raw_rows(columns, select + " WHERE plan_ref=? ORDER BY rowid", (plan_ref,))

    # ---- adoption source and lineage facts ----
    def source_exists(self, table: str, field: str, ref: Any) -> bool:
        """Whether an adoption source row exists; (table, field) must be in the fixed allowlist."""
        sql = _SOURCE_LOOKUPS.get((table, field))
        if sql is None:
            raise ValueError("Adoption source lookup is not allowed: " + str(table) + "." + str(field))
        return self.fetchone(sql, (ref,)) is not None

    def list_scenario_row_bindings(self, scenario_ref: str) -> List[Tuple[Any, Any, Any]]:
        """(row_ref, task_ref, source_row_ref) tuples of one saved trial scenario."""
        return [tuple(row) for row in self.execute(
            "SELECT row_ref,task_ref,source_row_ref FROM WorkbenchTrialScenarioRows WHERE scenario_ref=?",
            (scenario_ref,))]

    def history_version_exists(self, version: Any) -> bool:
        return self.fetchone("SELECT 1 FROM ScheduleHistory WHERE version=?", (version,)) is not None

    def get_history_result_summary(self, version: Any) -> Optional[Dict[str, Any]]:
        """{"result_summary": ...} of the first ScheduleHistory row of ``version``, or None."""
        return self.fetchone("SELECT result_summary FROM ScheduleHistory WHERE version=?", (version,))

    def list_task_refs_by_plan(self, plan_ref: str) -> List[Any]:
        return [row[0] for row in self.execute("SELECT ref FROM WorkbenchTaskRefs WHERE plan_ref=?", (plan_ref,))]

    def list_schedule_identity_rows(self, version: Any) -> List[Dict[str, Any]]:
        """(schedule_id, op_id, version) of every Schedule row of ``version`` in id order."""
        return self.fetchall("SELECT id AS schedule_id,op_id,version FROM Schedule WHERE version=? ORDER BY id", (version,))
