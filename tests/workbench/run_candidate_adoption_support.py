"""BX-only helpers: temporary real v26 SQLite and actual admission/worker/engine."""

from flask import Blueprint, g

from core.services.workbench.run.candidate_adoption import WorkbenchRunCandidateAdoptionService
from tests.workbench.run_candidate_support import candidate_case as candidate_case  # noqa: F401
from tests.workbench.run_candidate_support import compute, connect
from tests.workbench.trial_adoption_support import assert_dashboard_task_appends
from web.routes.workbench.materials import command_receipt
from web.routes.workbench.run_candidate_adoption import register_run_candidate_adoption_routes
from web.routes.workbench.write_context import issue_write_context, validate_write_context

INTENT = {"confirm": True, "reason": "Approved production plan", "declared_operator": "Declared operator"}
KEY = "candidate-adoption-000001"
BASE = "/api/workbench/v1/scheduling/candidates/"


def service(conn, enabled=True):
    return WorkbenchRunCandidateAdoptionService(conn, integration_enabled=enabled,
        context_factory=issue_write_context, context_validator=validate_write_context)


def candidate(case, settings=None):
    return compute(case, settings)[1][0]


def preview(case, ref):
    data = service(case.conn).preview(ref)
    assert data["validation"]["can_adopt"] is True, data
    return data["write_context"]["write_token"]


def snapshot(conn):
    result = {}
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        quoted = '"' + name.replace('"', '""') + '"'
        rows = []
        for row in conn.execute("SELECT rowid,* FROM " + quoted + " ORDER BY rowid"):
            rows.append(tuple((type(value).__name__, value) for value in row))
        result[name] = rows
    return result


def assert_retained(before, after):
    append_only = {"Schedule", "ScheduleHistory", "ScheduleVersionSeq", "OperationLogs",
                   "WorkbenchCommandReceipts", "WorkbenchPlanSourceRefs", "WorkbenchTaskRefs"}
    mutable_clocks = {"sqlite_sequence", "WorkbenchPlanIdentityClock"}
    assert set(before) == set(after)
    for name, rows in before.items():
        if name == "WorkbenchDashboardItems":
            assert_dashboard_task_appends(before, after)
        elif name in append_only:
            current = {row[0]: row for row in after[name]}
            assert all(current.get(row[0]) == row for row in rows), name
        elif name not in mutable_clocks:
            assert after[name] == rows, name


def api(case, enabled=True, connection_factory=connect):
    case.app.config["WORKBENCH_CANDIDATE_ADOPTION_ENABLED"] = enabled
    bp = Blueprint("workbench", __name__)
    register_run_candidate_adoption_routes(bp)
    bp.add_url_rule("/api/workbench/v1/commands/<request_key>", view_func=command_receipt, methods=["GET"])
    case.app.register_blueprint(bp)

    @case.app.before_request
    def bind():
        g.db = connection_factory(case.path)

    @case.app.teardown_request
    def close(error):
        g.db.close()

    return case.app.test_client()
