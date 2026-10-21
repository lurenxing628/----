"""Capture current calendar constraints and saved runs without selecting a candidate."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_history import RunHistoryScope
from core.services.workbench.run.history import WorkbenchRunHistoryQueryService


def candidate_catalog(conn):
    try:
        data, source_contents = WorkbenchRunHistoryQueryService(conn).catalog(RunHistoryScope(size=20))
    except WorkbenchCommandRejected as exc:
        if exc.code not in ("run_schema_unavailable", "run_result_inconsistent"):
            raise
        return {"state": "unavailable", "runs": [], "page": None, "run_count": None,
                "issues": [{"code": exc.code, "message": str(exc)}]}, {"unavailable": exc.code}
    return {**data, "state": "loaded" if data["run_count"] else "no_data", "issues": [],
            "basis": "saved_runs_not_current_official", "selection": None,
            "candidate_target_template": "/api/workbench/v1/scheduling/runs/{run_ref}/candidates"}, source_contents
