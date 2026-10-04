"""A real worker's persisted candidate set remains separate from official risk."""

from core.infrastructure.workbench_dashboard_schema import install
from core.models.workbench_dashboard import DashboardQuery
from core.services.workbench.dashboard.service import WorkbenchDashboardService
from core.services.workbench.run.worker import WorkbenchRunWorker
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


def test_dashboard_handling_during_run_does_not_make_it_stale(candidate_case):
    # 看板处置只记处理进度，排产不读：排产开始后在看板上跟进一条风险，这次排产照常保存结果。
    from core.services.workbench.dashboard.commands import WorkbenchDashboardCommandService
    from tests.workbench.dashboard_support import follow
    from tests.workbench.run_candidate_adoption_support import INTENT, preview, service
    from tests.workbench.run_candidate_support import compute
    from web.routes.workbench.write_context import issue_write_context, validate_write_context

    case = candidate_case
    case.conn.commit()
    case.conn.execute("BEGIN")
    install(case.conn)
    case.conn.commit()
    _run, refs = compute(case)
    service(case.conn).adopt(refs[0], preview(case, refs[0]), "candidate-adoption-000009", INTENT)
    case.conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,reason_detail) "
                      "VALUES ('M1','2026-09-10T09:00:00','2026-09-10T11:00:00','Maintenance')")
    case.conn.commit()
    accepted = case.accept(key="run-request-00000002")
    reader = WorkbenchDashboardService(case.conn, clock=lambda: NOW, context_factory=issue_write_context)
    with reader.read_snapshot():
        item = reader.workspace(reader.read(), DashboardQuery(size=100))["items"][0]
    handled = WorkbenchDashboardCommandService(case.conn, clock=lambda: NOW, actor_provider=lambda: "local-test-operator").execute(
        "transition", item["item_ref"], follow(), request_key="dashboard-test-00000001",
        validate_context=lambda ref, verb, facts: validate_write_context(item["write_context"]["write_token"], ref, verb, facts))
    assert handled["result"] == "committed"
    result = WorkbenchRunWorker(case.conn, clock=lambda: NOW).execute(accepted["run_ref"])
    assert result["state"] == "complete" and result["result_persisted"] is True
