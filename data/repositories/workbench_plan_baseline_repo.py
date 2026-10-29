"""Official-plan and adoption-baseline evidence reads: rows, history heads, source refs.

Only facts are returned; the service layer classifies every gap itself.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .base_repo import BaseRepository

_SOURCE_LOOKUPS = {
    ("WorkbenchRunJobs", "run_ref"): "SELECT 1 FROM WorkbenchRunJobs WHERE run_ref=?",
    ("WorkbenchRunCandidates", "candidate_ref"): "SELECT 1 FROM WorkbenchRunCandidates WHERE candidate_ref=?",
    ("WorkbenchTrialScenarios", "scenario_ref"): "SELECT 1 FROM WorkbenchTrialScenarios WHERE scenario_ref=?",
    ("WorkbenchTrialDrafts", "draft_ref"): "SELECT 1 FROM WorkbenchTrialDrafts WHERE draft_ref=?",
}


class WorkbenchPlanBaselineRepository(BaseRepository):
    def schedule_rows_by_version(self, version: Any) -> List[Dict[str, Any]]:
        """Whole Schedule rows of one version in rowid order."""
        return self.fetchall("SELECT * FROM Schedule WHERE version = ? ORDER BY rowid", (version,))

    def task_refs_by_plan(self, plan_ref: str) -> List[Dict[str, Any]]:
        """Whole WorkbenchTaskRefs rows of one plan in rowid order."""
        return self.fetchall("SELECT * FROM WorkbenchTaskRefs WHERE plan_ref = ? ORDER BY rowid", (plan_ref,))

    def source_refs_by_refs(self, refs: Sequence[str]) -> List[Dict[str, Any]]:
        """Whole WorkbenchPlanSourceRefs rows whose ref is in ``refs`` in rowid order."""
        if not refs:
            return []
        marks = ",".join("?" for _ in refs)
        return self.fetchall("SELECT * FROM WorkbenchPlanSourceRefs WHERE ref IN (" + marks + ") ORDER BY rowid", list(refs))

    # ---- adoption source and lineage facts ----
    def source_exists(self, table: str, field: str, ref: Any) -> bool:
        """Whether an adoption source row exists; (table, field) must be in the fixed allowlist."""
        return self.fetchone(_SOURCE_LOOKUPS[table, field], (ref,)) is not None

    def list_scenario_row_bindings(self, scenario_ref: str) -> List[Tuple[Any, Any, Any]]:
        """(row_ref, task_ref, source_row_ref) tuples of one saved trial scenario."""
        return [tuple(row) for row in self.execute(
            "SELECT row_ref,task_ref,source_row_ref FROM WorkbenchTrialScenarioRows WHERE scenario_ref=?",
            (scenario_ref,))]

    def get_history_result_summary(self, version: Any) -> Optional[Dict[str, Any]]:
        """{"result_summary": ...} of the first ScheduleHistory row of ``version``, or None."""
        return self.fetchone("SELECT result_summary FROM ScheduleHistory WHERE version=?", (version,))

    def list_schedule_identity_rows(self, version: Any) -> List[Dict[str, Any]]:
        """(schedule_id, op_id, version) of every Schedule row of ``version`` in id order."""
        return self.fetchall("SELECT id AS schedule_id,op_id,version FROM Schedule WHERE version=? ORDER BY id", (version,))
