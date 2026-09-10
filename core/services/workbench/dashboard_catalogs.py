"""Reuse bounded resource occupancy and run catalog without selecting a candidate."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_history import RunHistoryScope
from core.services.workbench.plan_calendar import project_plan_calendar
from core.services.workbench.plan_occupancy import project_plan_occupancy
from core.services.workbench.run_history import WorkbenchRunHistoryQueryService


def resource_pressure(conn, arguments):
    calendar, facts = project_plan_calendar(conn, **arguments)
    occupancy, private = project_plan_occupancy(conn, calendar_facts=facts, **arguments)
    return {"state": occupancy["state"], "plan_ref": occupancy["plan_ref"], "time_scope": occupancy["time_scope"],
            "basis": occupancy["basis"], "resources": occupancy["resources"], "issues": occupancy["issues"],
            "calendar_state": calendar["state"]}, private


def candidate_catalog(conn):
    try:
        data, fingerprint = WorkbenchRunHistoryQueryService(conn).catalog(RunHistoryScope(size=20))
    except WorkbenchCommandRejected as exc:
        if exc.code not in ("run_schema_unavailable", "run_result_inconsistent"):
            raise
        return {"state": "unavailable", "runs": [], "page": None, "run_count": None,
                "issues": [{"code": exc.code, "message": str(exc)}]}, {"unavailable": exc.code}
    return {**data, "state": "loaded" if data["run_count"] else "no_data", "issues": [],
            "basis": "saved_runs_not_current_official", "selection": None,
            "candidate_target_template": "/api/workbench/v1/scheduling/runs/{run_ref}/candidates"}, fingerprint
