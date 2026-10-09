"""Real HTTP admission must agree with the worker's global execution scope."""

import json
import threading
import uuid
from datetime import datetime, timedelta
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from flask import Blueprint, g

from core.services.scheduler.operation_execution_feedback_service import (
    ExecutionFeedbackContext,
    OperationExecutionFeedbackService,
)
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.run_candidate_adoption_support import INTENT, preview, service
from tests.workbench.run_candidate_support import candidate_case as candidate_fixture  # noqa: F401
from tests.workbench.run_candidate_support import compute, connect
from web.bootstrap.runtime_server import create_runtime_server
from web.routes.workbench.execution import register_execution_routes
from web.routes.workbench.preflight import register_preflight_routes
from web.routes.workbench.scheduling_jobs import register_scheduling_job_routes

BASE = "/api/workbench/v1"


def request(base_url, path, payload=None):
    content = None if payload is None else json.dumps(payload).encode("utf-8")
    try:
        response = urlopen(Request(base_url + BASE + path, data=content,
                           headers={"Content-Type": "application/json"}), timeout=30)
    except HTTPError as exc:
        response = exc
    with response:
        return response.getcode(), json.loads(response.read().decode("utf-8"))


def success(base_url, path, payload=None):
    status, body = request(base_url, path, payload)
    assert status == 200 and body["ok"] is True, body
    return body["data"]


@pytest.fixture
def scope_server(candidate_case):
    case = candidate_case
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    _, candidates = compute(case, case.settings("B1", "B2"))
    adopted = service(case.conn).adopt(candidates[0], preview(case, candidates[0]), "scope-baseline-adopt-001", INTENT)
    case.version = adopted["data"]["official_plan"]["version"]
    bp = Blueprint("scope_execution_admission", __name__)
    register_preflight_routes(bp)
    register_scheduling_job_routes(bp)
    register_execution_routes(bp)
    case.app.register_blueprint(bp)
    dispatched = []
    case.app.config["WORKBENCH_RUN_JOBS_ENABLED"] = True
    case.app.extensions["workbench_run_dispatcher"] = dispatched.append

    @case.app.before_request
    def bind_database():
        g.db = connect(case.path)

    @case.app.teardown_request
    def close_database(error):
        g.db.close()

    server = create_runtime_server(case.app, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield case, "http://127.0.0.1:" + str(server.server_port), dispatched
    finally:
        server.shutdown()
        thread.join(timeout=10)
        server.server_close()


def intent(base_url, settings):
    checked = success(base_url, "/scheduling/preflight", settings)
    authorization = success(base_url, "/scheduling/runs/preview", {"input_ref": checked["input_ref"]})
    return checked, authorization


def report_partial(case, base_url):
    task = next(row for row in success(base_url, "/execution/tasks")["tasks"] if row["batch_id"] == "B1")
    start, end = case.conn.execute("SELECT start_time,end_time FROM Schedule WHERE version=? AND op_id=?",
                                  (case.version, case.op_id)).fetchone()
    start, end = datetime.fromisoformat(start), datetime.fromisoformat(end)
    middle = start + timedelta(seconds=(end - start).total_seconds() // 3)
    body = {"request_key": "scope-partial-report-" + uuid.uuid4().hex,
            "write_token": task["execution"]["write_context"]["write_token"],
            "input": case.values(1, actual_start=start.isoformat(timespec="seconds"),
                                  actual_end=middle.isoformat(timespec="seconds"),
                                  effective_processing_hours=(middle - start).total_seconds() / 3600)}
    status, result = request(base_url, "/execution/tasks/" + task["task_ref"] + "/reports", body)
    assert status == 200 and result["result"] == "committed", result
    refreshed = next(row for row in success(base_url, "/execution/tasks")["tasks"] if row["task_ref"] == task["task_ref"])
    assert refreshed["execution"]["execution_state"] == "partial"
    return task, middle, end


def assert_rejected_without_writes(case, base_url, dispatched, settings, expected, token="current-non-authorizing-token"):
    before = all_rows(case.conn)
    checked, authorization = intent(base_url, settings)
    context = authorization["write_context"]
    assert context["capabilities"]["scheduling.run"] is False
    assert context["write_token"] is None
    assert expected in {row["code"] for row in context["blocked_reasons"]}
    status, outcome = request(base_url, "/scheduling/runs", {"input_ref": checked["input_ref"],
        "write_token": token, "request_key": "scope-blocked-accept-" + uuid.uuid4().hex})
    assert status == 409 and outcome["committed"] is False, outcome
    assert outcome["error"]["code"] == "constraint_conflict"
    assert all_rows(case.conn) == before
    assert dispatched == []


def test_outside_partial_blocks_preview_and_fresh_and_stale_admission(scope_server):
    case, base_url, dispatched = scope_server
    stale_check, stale_authorization = intent(base_url, case.settings("B2"))
    assert stale_authorization["write_context"]["capabilities"]["scheduling.run"] is True
    task, middle, end = report_partial(case, base_url)
    assert_rejected_without_writes(case, base_url, dispatched, case.settings("B2"),
                                   "execution_ledger_requires_reconciliation")
    assert_rejected_without_writes(case, base_url, dispatched, case.settings("B1", "B2"),
                                   "execution_review_required")
    before = all_rows(case.conn)
    status, outcome = request(base_url, "/scheduling/runs", {"input_ref": stale_check["input_ref"],
        "write_token": stale_authorization["write_context"]["write_token"],
        "request_key": "scope-stale-accept-" + uuid.uuid4().hex})
    assert status == 409 and outcome["committed"] is False, outcome
    assert outcome["error"]["code"] == "snapshot_stale"
    assert all_rows(case.conn) == before and dispatched == []
    current = next(row for row in success(base_url, "/execution/tasks")["tasks"] if row["task_ref"] == task["task_ref"])
    status, completed = request(base_url, "/execution/tasks/" + task["task_ref"] + "/reports", {
        "request_key": "scope-complete-report-" + uuid.uuid4().hex,
        "write_token": current["execution"]["write_context"]["write_token"],
        "input": case.values(2, actual_start=middle.isoformat(timespec="seconds"),
            actual_end=end.isoformat(timespec="seconds"), effective_processing_hours=(end - middle).total_seconds() / 3600)})
    assert status == 200 and completed["result"] == "committed", completed
    checked, authorization = intent(base_url, case.settings("B2"))
    assert authorization["write_context"]["capabilities"]["scheduling.run"] is True
    status, accepted = request(base_url, "/scheduling/runs", {"input_ref": checked["input_ref"],
        "write_token": authorization["write_context"]["write_token"], "request_key": "scope-valid-accept-" + uuid.uuid4().hex})
    assert status == 202 and dispatched == [accepted["run_ref"]], accepted
    assert WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])["state"] == "complete"


def test_outside_legacy_release_unknown_is_blocked_before_worker(scope_server):
    case, base_url, dispatched = scope_server
    schedule = case.conn.execute("SELECT id FROM Schedule WHERE version=? AND op_id=?",
                                  (case.version, case.op_id)).fetchone()[0]
    context = ExecutionFeedbackContext(case.version, schedule, case.op_id, "B1", f"{case.op_id}:0:0",
        "legacy-operator", "scope-legacy-start-001", "adopted", "schedule", "adopted")
    OperationExecutionFeedbackService(case.conn).start_operation(
        context, event_time="2026-09-09 08:00", machine_id="M1", operator_id="O1")
    assert_rejected_without_writes(case, base_url, dispatched,
        case.settings("B2", start_date="2026-09-10"), "execution_resource_release_unknown")
