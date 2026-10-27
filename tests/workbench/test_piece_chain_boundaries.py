"""Real admission freshness, missing work, protected points and transactional failure."""

import json
from dataclasses import replace
from datetime import timedelta

import pytest

from core.models.content import same
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.workbench.run import piece_adoption
from core.services.workbench.run.candidate_adoption_validation import _require_official_scope
from core.services.workbench.run.compute_validation import validate_candidate
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.piece_adoption_support import START, checked_read_only, lower_input, payload, slot_payload, split
from tests.workbench.piece_chain_support import piece_candidate, piece_layout
from tests.workbench.piece_chain_support import trial_case as trial_case  # noqa: F401
from tests.workbench.run_candidate_adoption_support import INTENT
from tests.workbench.run_candidate_adoption_support import service as candidate_adoption
from tests.workbench.trial_support import connect, snapshot


def test_other_connection_drift_rejected_without_changing_old_work(trial_case):
    case = trial_case
    piece_layout(case)
    accepted = case.accept()
    other = connect(case.path)
    try:
        other.execute("UPDATE BatchOperations SET unit_hours=0.5 WHERE piece_id='item-A'")
        other.commit()
    finally:
        other.close()
    before = snapshot(case.conn)
    admission = json.loads(case.conn.execute(
        "SELECT decision_json FROM WorkbenchRunAdmissionReadModels WHERE run_ref=?",
        (accepted["run_ref"],)).fetchone()[0])
    with pytest.raises(WorkbenchCommandRejected):
        WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    after = snapshot(case.conn)
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


def test_actual_insert_failure_rolls_back_whole_piece_adoption(trial_case):
    case = trial_case
    case.conn.execute(
        'CREATE TRIGGER ef_piece_failure BEFORE INSERT ON "WorkbenchCommandReceipts" '
        "WHEN NEW.action='scheduling.candidate.adopt' "
        "BEGIN SELECT RAISE(ABORT,'EF partial-write failure'); END"
    )
    case.conn.commit()
    _, _, refs = piece_candidate(case)
    ref, svc = refs[0], candidate_adoption(case.conn)
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
    with pytest.raises(CandidateAdoptionBlocked) as caught:
        checked_read_only(case, lambda: _require_official_scope(prepared.latest_plan_rows, full.scheduled_op_ids))
    assert caught.value.code == "official_scope_not_covered"

    with pytest.raises(CandidateRunInputError) as caught:
        validate_candidate(prepared, [row for row in rows if row.op_id != ids["item-A", 20]], [],
                           prepared_payload=payload(prepared, [row for row in rows if row.op_id != ids["item-A", 20]]))
    assert caught.value.code == "candidate_predecessor_missing"
    with pytest.raises(CandidateRunInputError) as caught:
        validate_candidate(prepared, [row for row in rows if row.op_id != common], [],
                           prepared_payload=payload(prepared, [row for row in rows if row.op_id != common]))
    assert caught.value.code == "protected_seed_changed"
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
