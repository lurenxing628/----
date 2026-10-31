"""Official-plan and adoption-baseline evidence reads: rows, history heads, source refs.

Only facts are returned; the service layer classifies every gap itself.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .base_repo import BaseRepository


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
    def list_scenario_row_bindings(self, scenario_ref: str) -> List[Tuple[Any, Any, Any]]:
        """(row_ref, task_ref, source_row_ref) tuples of one saved trial scenario."""
        return [tuple(row) for row in self.execute(
            "SELECT row_ref,task_ref,source_row_ref FROM WorkbenchTrialScenarioRows WHERE scenario_ref=?",
            (scenario_ref,))]

    def get_history_result_summary(self, version: Any) -> Optional[Dict[str, Any]]:
        """{"result_summary": ...} of the first ScheduleHistory row of ``version``, or None."""
        return self.fetchone("SELECT result_summary FROM ScheduleHistory WHERE version=?", (version,))
