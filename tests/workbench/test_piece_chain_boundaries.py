"""Real admission freshness, missing work, protected points and transactional failure."""

import json
from dataclasses import replace
from datetime import timedelta

import pytest

from core.models.content import same
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.workbench.run import piece_adoption
from core.services.workbench.run.compute_validation import validate_candidate
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.piece_adoption_support import START, checked_read_only, lower_input, payload, slot_payload, split
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
    if phase == "worker":
        admission = json.loads(case.conn.execute(
            "SELECT decision_json FROM WorkbenchRunAdmissionReadModels WHERE run_ref=?",
            (accepted["run_ref"],)).fetchone()[0])
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
            if table not in ("WorkbenchRunJobs", "WorkbenchRunReceipts", "WorkbenchRunDecisionReadModels"):
                assert after[table] == rows, table
        models = after["WorkbenchRunDecisionReadModels"]
        assert models[:-1] == before["WorkbenchRunDecisionReadModels"]
        assert len(models) == len(before["WorkbenchRunDecisionReadModels"]) + 1
        model = dict(case.conn.execute("SELECT * FROM WorkbenchRunDecisionReadModels WHERE rowid=?",
                                       (models[-1][0][1],)).fetchone())
        assert model["run_ref"] == accepted["run_ref"]
        assert model["projection_version"] == "decision-read-v1"
        header = json.loads(model["header_json"])
        assert header["state"] == "failed"
        assert header["result_persisted"] is False and header["candidates"] == []
        assert header["error"]["code"] == "snapshot_stale"
        for field in ("context", "memberships", "calendar", "official"):
            assert same(json.loads(model[field + "_json"]), admission[field]), field
        assert model["process_json"] is None
        assert after["WorkbenchRunReceipts"][:-1] == before["WorkbenchRunReceipts"]
        assert len(after["WorkbenchRunReceipts"]) == len(before["WorkbenchRunReceipts"]) + 1
        assert case.conn.execute("SELECT state FROM WorkbenchRunJobs").fetchone()[0] == "failed"
        assert case.conn.execute("SELECT state FROM WorkbenchRunReceipts").fetchone()[0] == "failed"
        assert not case.conn.in_transaction
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


def test_closed_partial_piece_publication_keeps_adoption_and_protection_boundaries(trial_case):
    case = trial_case
    ids = split(case)
    common = ids[None, 10]
    case.batch("B2")
    outside = case.operation(batch="B2")
    case.plan(1, [common], start=START.isoformat(), end=(START + timedelta(minutes=45)).isoformat())
    case.conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) "
        "VALUES (1,?,'M2','O2',?,?)", (outside, (START + timedelta(hours=1)).isoformat(),
                                     (START + timedelta(hours=1, minutes=45)).isoformat()))
    case.conn.commit()
    case.config(freeze_window_enabled="yes", freeze_window_days=1)
    prepared = lower_input(case)
    assert prepared.frozen_op_ids == {common}
    full = slot_payload(prepared)
    keep = {common, ids["item-A", 20], ids["item-A", 30], ids["item-B", 20]}
    rows = [row for row in full.schedule_rows if row.op_id in keep]
    known = payload(prepared, rows)
    assert known.scheduled_op_ids < prepared.schedule_output_allowed_op_ids

    def published(value):
        # Publication form: compute prepares the shared proof once, then checks each candidate.
        return lambda: piece_adoption.validate_piece_candidate(
            case.conn, prepared=prepared, payload=value,
            context=piece_adoption.prepare_piece_validation_context(case.conn, prepared))

    def publish(candidate_rows):
        return checked_read_only(case, published(payload(prepared, candidate_rows)))

    def reject(candidate_rows, reason):
        with pytest.raises(PieceAdoptionBlocked) as caught:
            publish(candidate_rows)
        assert caught.value.code == reason

    checked_read_only(case, published(known))
    with pytest.raises(PieceAdoptionBlocked) as caught:
        checked_read_only(case, lambda: piece_adoption.validate_piece_adoption(
            case.conn, prepared=prepared, payload=known))
    assert caught.value.code == "piece_scope_incomplete"
    checked_read_only(case, published(full))
    with pytest.raises(PieceAdoptionBlocked) as caught:
        checked_read_only(case, lambda: piece_adoption.validate_piece_adoption(
            case.conn, prepared=prepared, payload=full))
    assert caught.value.code == "official_scope_not_covered"

    with pytest.raises(CandidateRunInputError) as caught:
        validate_candidate(prepared, [row for row in rows if row.op_id != ids["item-A", 20]], [],
                           prepared_payload=payload(prepared, [row for row in rows if row.op_id != ids["item-A", 20]]))
    assert caught.value.code == "candidate_predecessor_missing"
    reject([row for row in rows if row.op_id != common], "piece_protected_seed_missing")
    late = [replace(row, start_time=row.start_time + timedelta(days=30),
                    end_time=row.end_time + timedelta(days=30)) if row.op_id == ids["item-A", 30] else row
            for row in rows]
    with pytest.raises(CandidateRunInputError) as caught:
        validate_candidate(prepared, late, [], prepared_payload=payload(prepared, late))
    assert caught.value.code == "candidate_outside_window"
    reject([replace(row, operator_id="O2") if row.op_id == ids["item-A", 20] else row
            for row in rows], "piece_resource_invalid")
    first = next(row for row in rows if row.op_id == ids["item-A", 20])
    reject([replace(row, start_time=first.start_time, end_time=first.end_time)
            if row.op_id == ids["item-B", 20] else row for row in rows], "candidate_resource_overlap")
