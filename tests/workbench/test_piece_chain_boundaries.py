"""Real admission freshness, missing work, protected points and transactional failure."""


import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.piece_chain_support import piece_candidate, piece_layout, saved_trial
from tests.workbench.piece_chain_support import trial_case as trial_case  # noqa: F401
from tests.workbench.round1_piece_point_support import point_case as point_case
from tests.workbench.run_candidate_adoption_support import INTENT
from tests.workbench.run_candidate_adoption_support import service as candidate_adoption
from tests.workbench.run_jobs_support import service as run_service
from tests.workbench.trial_adoption_support import service as trial_adoption
from tests.workbench.trial_support import connect, snapshot


@pytest.mark.parametrize("phase", ["worker"])
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


@pytest.mark.parametrize("phase", ["candidate"])
@pytest.mark.parametrize("table", ["WorkbenchCommandReceipts"])
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
