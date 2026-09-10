"""Real admission freshness, missing work, protected points and transactional failure."""

import sqlite3

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.piece_chain_support import piece_candidate, piece_layout, saved_trial
from tests.workbench.piece_chain_support import trial_case as trial_case  # noqa: F401
from tests.workbench.round1_piece_point_support import adopt, candidate, workspace
from tests.workbench.round1_piece_point_support import point_case as point_case
from tests.workbench.run_candidate_adoption_support import INTENT
from tests.workbench.run_candidate_adoption_support import service as candidate_adoption
from tests.workbench.run_candidate_support import compute
from tests.workbench.run_jobs_support import service as run_service
from tests.workbench.trial_adoption_support import service as trial_adoption
from tests.workbench.trial_support import connect, snapshot


@pytest.mark.parametrize("change,reason", [("missing_piece", "piece_scope_incomplete"),
    ("missing_stage", "piece_stage_incomplete")])
def test_admission_cannot_authorize_incomplete_or_unproven_piece_work(trial_case, change, reason):
    case = trial_case
    ids = piece_layout(case)
    if change == "missing_piece":
        case.conn.execute("DELETE FROM BatchOperations WHERE piece_id='item-C'")
    elif change == "missing_stage":
        case.conn.execute("DELETE FROM BatchOperations WHERE id=?", (ids["item-C", 30],))
    case.conn.commit()
    input_ref = case.preflight()
    before = snapshot(case.conn)
    preview = run_service(case.conn).preview(input_ref)
    assert preview["write_context"]["write_token"] is None
    assert reason in {row["code"] for row in preview["write_context"]["blocked_reasons"]}
    assert snapshot(case.conn) == before


def test_zero_piece_work_requires_managed_candidate_and_adopted_witness(point_case):
    case = point_case
    ids = piece_layout(case)
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0,setup_hours=0 WHERE piece_id IS NOT NULL")
    case.conn.commit()
    plan = adopt(case, candidate(case))["data"]["official_plan"]
    data = workspace(case.conn, plan["plan_ref"])
    points = [task for task in data["tasks"] if task["piece_id"] is not None]
    assert len(points) == 6 and all(task["event_kind"] == "point" for task in points)
    assert all(task["quantity"] == 1 and task["start"] == task["end"] for task in points)
    case.plan(2, [ids["item-A", 20]], start=points[0]["start"], end=points[0]["start"])
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected):
        workspace(case.conn, case.plan_ref(2))
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("phase", ["admission", "worker", "candidate", "scenario"])
def test_other_connection_drift_rejected_without_changing_old_work(trial_case, phase):
    case = trial_case
    if phase in ("admission", "worker"):
        piece_layout(case)
        if phase == "admission":
            ref, token = case.intent()
        else:
            accepted = case.accept()
    else:
        ids, _, refs = piece_candidate(case)
        if phase == "candidate":
            ref, svc = refs[0], candidate_adoption(case.conn)
        else:
            _, _, saved = saved_trial(case, {"candidate_ref": refs[0]}, op_id=ids[None, 40])
            ref, svc = saved["scenario_ref"], trial_adoption(case.conn)
        preview = svc.preview(ref)
        assert preview["validation"]["can_adopt"], preview
        token = preview["write_context"]["write_token"]
    other = connect(case.path)
    try:
        other.execute("UPDATE BatchOperations SET unit_hours=0.5 WHERE piece_id='item-A'")
        other.commit()
    finally:
        other.close()
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected):
        if phase == "admission":
            run_service(case.conn).accept(ref, token, "ef-stale-admission-0001")
        elif phase == "worker":
            WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
        else:
            svc.adopt(ref, token, "ef-stale-adopt-0001", INTENT)
    after = snapshot(case.conn)
    if phase == "worker":
        for table, rows in before.items():
            if table not in ("WorkbenchRunJobs", "WorkbenchRunReceipts"):
                assert after[table] == rows, table
        assert after["WorkbenchRunReceipts"][:-1] == before["WorkbenchRunReceipts"]
        assert len(after["WorkbenchRunReceipts"]) == len(before["WorkbenchRunReceipts"]) + 1
        assert case.conn.execute("SELECT state FROM WorkbenchRunJobs").fetchone()[0] == "failed"
        assert case.conn.execute("SELECT state FROM WorkbenchRunReceipts").fetchone()[0] == "failed"
    else:
        assert after == before


@pytest.mark.parametrize("phase", ["candidate", "scenario"])
@pytest.mark.parametrize("table", ["Schedule", "ScheduleHistory", "OperationLogs", "WorkbenchCommandReceipts"])
def test_actual_insert_failure_rolls_back_whole_piece_adoption(trial_case, phase, table):
    case = trial_case
    action = "scheduling.candidate.adopt" if phase == "candidate" else "trial.scenario.adopt"
    condition = "(SELECT count(*) FROM Schedule)>0" if table == "Schedule" else (
        "NEW.action='" + action + "'" if table == "WorkbenchCommandReceipts" else "1")
    case.conn.execute('CREATE TRIGGER ef_piece_failure BEFORE INSERT ON "' + table + '" WHEN ' + condition
                     + " BEGIN SELECT RAISE(ABORT,'EF partial-write failure'); END")
    case.conn.commit()
    ids, _, refs = piece_candidate(case)
    if phase == "candidate":
        ref, svc = refs[0], candidate_adoption(case.conn)
    else:
        _, _, saved = saved_trial(case, {"candidate_ref": refs[0]}, op_id=ids[None, 40])
        ref, svc = saved["scenario_ref"], trial_adoption(case.conn)
    preview = svc.preview(ref)
    assert preview["validation"]["can_adopt"], preview
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandUncertain):
        svc.adopt(ref, preview["write_context"]["write_token"], "ef-piece-rollback-0001", INTENT)
    assert snapshot(case.conn) == before
    assert not case.conn.in_transaction
    assert svc.lookup(ref, "ef-piece-rollback-0001") is None


@pytest.mark.parametrize("phase", ["candidate", "scenario"])
def test_full_piece_revalidation_is_inside_the_real_sqlite_writer_lock(trial_case, phase):
    case = trial_case
    ids, _, refs = piece_candidate(case)
    if phase == "candidate":
        ref, svc = refs[0], candidate_adoption(case.conn)
    else:
        _, _, saved = saved_trial(case, {"candidate_ref": refs[0]}, op_id=ids[None, 40])
        ref, svc = saved["scenario_ref"], trial_adoption(case.conn)
    preview = svc.preview(ref)
    assert preview["validation"]["can_adopt"], preview
    observations = []

    def trace(sql):
        if not observations and sql.startswith("SELECT * FROM BatchOperations WHERE batch_id="):
            other = sqlite3.connect(str(case.path), timeout=0.01)
            try:
                other.execute("UPDATE Batches SET quantity=4")
            except sqlite3.OperationalError as exc:
                observations.append((case.conn.in_transaction, str(exc)))
            finally:
                other.close()

    case.conn.set_trace_callback(trace)
    try:
        svc.adopt(ref, preview["write_context"]["write_token"], "ef-piece-lock-0001", INTENT)
    finally:
        case.conn.set_trace_callback(None)
    assert observations == [(True, "database is locked")]


def test_common_point_keeps_ea_evidence_and_default_public_switch_closed(trial_case):
    case = trial_case
    ids = piece_layout(case)
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0,setup_hours=0 WHERE id=?", (ids[None, 10],))
    case.conn.commit()
    _, refs = compute(case)
    preview = candidate_adoption(case.conn).preview(refs[0])
    assert preview["validation"]["can_adopt"] is False
    assert preview["validation"]["issues"][0]["code"] == "point_rendering_not_connected"
