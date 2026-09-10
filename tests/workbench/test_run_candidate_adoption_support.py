"""BX-only helpers: temporary real v26 SQLite and actual admission/worker/engine."""

import json
import sqlite3

from flask import Blueprint, g

from core.models.workbench_command import canonical_json
from core.services.workbench.run_candidate_adoption import WorkbenchRunCandidateAdoptionService
from tests.workbench.test_run_candidate_support import candidate_case as candidate_case  # noqa: F401
from tests.workbench.test_run_candidate_support import compute, connect, corrupt_update
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


def rewrite_candidate(case, ref, change):
    row = case.conn.execute("SELECT artifact_json FROM WorkbenchRunCandidates WHERE candidate_ref=?", (ref,)).fetchone()
    artifact = json.loads(row[0])
    tasks = [(row[0], json.loads(row[1])) for row in case.conn.execute(
        "SELECT row_ref,payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=? ORDER BY ordinal", (ref,))]
    for row_ref, payload in tasks:
        change(payload)
        corrupt_update(case.conn, "WorkbenchRunCandidateTasks", "UPDATE WorkbenchRunCandidateTasks SET payload_json=? WHERE row_ref=?",
                       (canonical_json(payload), row_ref))
    artifact["validated_payload"]["schedule_rows"] = [{k: v for k, v in payload.items() if k != "locked"} for _, payload in tasks]
    by_id = {payload["op_id"]: payload for _, payload in tasks}
    for row in artifact["results"]:
        row.update({k: v for k, v in by_id[row["op_id"]].items() if k != "locked"})
    artifact["validated_payload"]["assigned_by_op_id"] = {
        str(payload["op_id"]): {key: payload[key] for key in ("machine_id", "operator_id")}
        for _, payload in tasks if payload["source"] == "internal"}
    corrupt_update(case.conn, "WorkbenchRunCandidates", "UPDATE WorkbenchRunCandidates SET artifact_json=? WHERE candidate_ref=?",
                   (canonical_json(artifact), ref))


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


class CommitFailureConnection(sqlite3.Connection):
    fail_commit = False
    acknowledge_only = False

    def commit(self):
        if self.fail_commit:
            self.fail_commit = False
            if self.acknowledge_only:
                super().commit()
            raise sqlite3.OperationalError("injected COMMIT acknowledgement failure")
        return super().commit()
