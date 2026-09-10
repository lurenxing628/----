"""A real worker's persisted candidate set remains separate from official risk."""

from core.infrastructure.workbench_dashboard_schema import install
from core.models.workbench_dashboard import DashboardQuery
from core.services.workbench.dashboard import WorkbenchDashboardService
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.dashboard_support import NOW
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401


def test_real_candidates_without_official_are_not_selected_as_official(candidate_case):
    case = candidate_case
    case.conn.commit()
    case.conn.execute("BEGIN")
    install(case.conn)
    case.conn.commit()
    accepted = case.accept()
    result = WorkbenchRunWorker(case.conn, clock=lambda: NOW).execute(accepted["run_ref"])
    run_ref, refs = result["run_ref"], [row["candidate_ref"] for row in result["candidates"]]
    reader = WorkbenchDashboardService(case.conn)
    changes = case.conn.total_changes
    with reader.read_snapshot():
        data = reader.workspace(reader.read(), DashboardQuery())
    assert len(refs) == 4
    assert data["plan"] is None
    assert data["categories"]["delivery"]["state"] == "no_official_plan"
    assert data["categories"]["delivery"]["risk_count"] is None
    assert data["candidate_catalog"]["state"] == "loaded"
    assert data["candidate_catalog"]["runs"][0]["run_ref"] == run_ref
    assert data["candidate_catalog"]["runs"][0]["candidate_count"] == 4
    assert data["candidate_catalog"]["selection"] is None
    assert not any(row["category"] == "candidate" for row in data["items"])
    assert case.conn.total_changes == changes
