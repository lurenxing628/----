"""BU fixtures reuse BL's real v26 database and worker, without global registration."""

from flask import Blueprint, g

from core.models.workbench_run_baseline import RunCandidateBaselineScope
from core.services.workbench.run_candidate_baseline import WorkbenchRunCandidateBaselineQueryService
from tests.workbench.run_candidate_support import connect, public
from web.routes.workbench.run_candidate_baseline import register_run_candidate_baseline_routes
from web.routes.workbench.run_candidates import register_run_candidate_routes


def api(case):
    bp = Blueprint("bu_baselines", __name__)
    register_run_candidate_baseline_routes(bp)
    register_run_candidate_routes(bp)
    case.app.register_blueprint(bp)
    statements = []

    @case.app.before_request
    def bind():
        g.db = connect(case.path)
        g.db.execute("PRAGMA query_only=ON")
        g.db.set_trace_callback(statements.append)

    @case.app.teardown_request
    def close(error):
        g.db.close()

    return case.app.test_client(), statements


def baseline(case, ref, **values):
    result = WorkbenchRunCandidateBaselineQueryService(case.conn).baseline(RunCandidateBaselineScope(ref, **values))
    public(result[0])
    return result


def original_plan(case, ids=None, **values):
    case.plan(7, ids if ids is not None else [case.op_id], **values)
    return case.plan_ref(7)


def legacy_blob_events(case):
    schedule_id = case.conn.execute("SELECT id FROM Schedule WHERE version=7 AND op_id=?", (case.op_id,)).fetchone()[0]
    previous = 0
    for index, kind in enumerate(("start", "finish")):
        cursor = case.conn.execute("""INSERT INTO OperationExecutionEvents
            (schedule_version,schedule_id,op_id,batch_id,source_table,effective_plan_role,event_type,reported_status,event_time,
             actual_machine_id,actual_operator_id,quantity_done,created_by,idempotency_key,request_fingerprint,previous_state_revision,
             remark,created_at)
            VALUES (7,?,?,'B1','schedule','adopted',?,?,?,'M1','O1',NULL,'old-operator',?,'old-fingerprint',?,?,?)""",
            (schedule_id, case.op_id, kind, "processing" if kind == "start" else "completed",
             "2026-09-09T08:00:00" if kind == "start" else "2026-09-09T10:00:00", "bu-old-" + kind,
             f"{case.op_id}:{index}:{previous}", b"old-note", b"old-time"))
        previous = cursor.lastrowid
    case.conn.commit()
