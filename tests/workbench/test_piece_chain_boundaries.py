"""Real admission freshness, missing work, protected points and transactional failure."""

import json
from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest

from core.models.content import same
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.run import piece_adoption
from core.services.workbench.run.candidate_adoption_validation import require_official_scope
from core.services.workbench.run.compute_validation import validate_candidate
from core.services.workbench.run.input import prepare_solver_input
from core.services.workbench.run.input_runtime import prepare_solver_resources
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.piece_adoption_support import START, checked_read_only, lower_input, slot_payload, split
from tests.workbench.piece_chain_support import piece_candidate, piece_layout
from tests.workbench.piece_chain_support import trial_case as trial_case  # noqa: F401
from tests.workbench.run_candidate_adoption_support import INTENT
from tests.workbench.run_candidate_adoption_support import service as candidate_adoption
from tests.workbench.run_compute_support import prepare_run_input
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
        WorkbenchRunWorker(case.conn, clock=datetime.now).execute(accepted["run_ref"])
    after = snapshot(case.conn)
    for table, rows in before.items():
        if table not in (
            "WorkbenchRunJobs",
            "WorkbenchRunReceipts",
            "WorkbenchRunDecisionReadModels",
            "WorkbenchHistoryEntries",
            "WorkbenchSourceRevisions",
        ):
            assert after[table] == rows, table
    assert [row for row in after["WorkbenchSourceRevisions"] if row[1] != ("str", "run_jobs")] == [
        row for row in before["WorkbenchSourceRevisions"] if row[1] != ("str", "run_jobs")
    ]
    models = after["WorkbenchRunDecisionReadModels"]
    assert models[:-1] == before["WorkbenchRunDecisionReadModels"]
    assert len(models) == len(before["WorkbenchRunDecisionReadModels"]) + 1
    model = dict(case.conn.execute("SELECT * FROM WorkbenchRunDecisionReadModels WHERE rowid=?",
                                   (models[-1][0][1],)).fetchone())
    assert model["run_ref"] == accepted["run_ref"]
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
    assert svc.commands.lookup("ef-piece-rollback-0001", action=svc._action, context_ref=ref) is None


def test_closed_partial_piece_publication_keeps_adoption_and_protection_boundaries(trial_case):
    case = trial_case
    from tests.workbench.execution_ledger_support import publish_official_plan

    ids: dict = split(case)
    common = ids[None, 10]
    case.batch("B2")
    outside = case.operation(batch="B2")
    publish_official_plan(
        case.conn,
        1,
        [
            {"op_id": common, "machine_id": "M1", "operator_id": "O1",
             "start_time": START.isoformat(), "end_time": (START + timedelta(minutes=45)).isoformat()},
            {"op_id": outside, "machine_id": "M2", "operator_id": "O2",
             "start_time": (START + timedelta(hours=1)).isoformat(),
             "end_time": (START + timedelta(hours=1, minutes=45)).isoformat()},
        ],
    )
    case.conn.commit()
    case.config(freeze_window_enabled="yes", freeze_window_days=1)
    prepared = lower_input(case)
    assert prepared.seeds.frozen_op_ids == {common}
    full = slot_payload(prepared)
    keep = {common, ids["item-A", 20], ids["item-A", 30], ids["item-B", 20]}
    rows = [row for row in full if row.op_id in keep]
    assert {row.op_id for row in rows} < prepared.allowed_op_ids

    with candidate_read_snapshot(case.conn):
        calendar = prepare_solver_resources(prepared, prepare_solver_input(prepared)).calendar_engine

    def published(value):
        # Publication form: compute prepares the shared proof once, then checks each candidate.
        return lambda: piece_adoption.validate_piece_candidate(
            case.conn,
            prepared=prepared,
            calendar=calendar,
            payload=value,
            context=piece_adoption.prepare_piece_validation_context(case.conn, prepared),
        )

    def publish(candidate_rows):
        return checked_read_only(case, published(candidate_rows))

    def reject(candidate_rows, reason):
        with pytest.raises(PieceAdoptionBlocked) as caught:
            publish(candidate_rows)
        assert caught.value.code == reason

    checked_read_only(case, published(rows))
    with pytest.raises(PieceAdoptionBlocked) as caught:
        checked_read_only(case, lambda: piece_adoption.validate_piece_adoption(
            case.conn, prepared=prepared, payload=rows))
    assert caught.value.code == "piece_scope_incomplete"
    checked_read_only(case, published(full))
    with pytest.raises(CandidateAdoptionBlocked) as caught:
        checked_read_only(case, lambda: require_official_scope(prepared.latest_plan_rows, {row.op_id for row in full}))
    assert caught.value.code == "official_scope_not_covered"

    with pytest.raises(CandidateRunInputError) as caught:
        validate_candidate(prepared, [row for row in rows if row.op_id != ids["item-A", 20]])
    assert caught.value.code == "candidate_predecessor_missing"
    with pytest.raises(CandidateRunInputError) as caught:
        validate_candidate(prepared, [row for row in rows if row.op_id != common])
    assert caught.value.code == "protected_seed_changed"
    late = [replace(row, start_time=row.start_time + timedelta(days=30),
                    end_time=row.end_time + timedelta(days=30)) if row.op_id == ids["item-A", 30] else row
            for row in rows]
    with pytest.raises(CandidateRunInputError) as caught:
        validate_candidate(prepared, late)
    assert caught.value.code == "candidate_outside_window"
    reject([replace(row, operator_id="O2") if row.op_id == ids["item-A", 20] else row
            for row in rows], "piece_resource_invalid")
    first = next(row for row in rows if row.op_id == ids["item-A", 20])
    reject([replace(row, start_time=first.start_time, end_time=first.end_time)
            if row.op_id == ids["item-B", 20] else row for row in rows], "candidate_resource_overlap")


def test_piece_scope_supports_full_positive_int64_identities_and_quantities():
    from types import SimpleNamespace

    from core.services.workbench.facts.piece_scope import build_piece_adoption_scope

    int64_max = (1 << 63) - 1
    js_safe_max = (1 << 53) - 1
    above_js = (1 << 53) + 17
    split_ops = [
        SimpleNamespace(id=above_js, batch_id="B-SPLIT", piece_id=None, seq=above_js + 1),
        SimpleNamespace(id=int64_max - 1, batch_id="B-SPLIT", piece_id="piece-1", seq=int64_max),
        SimpleNamespace(id=int64_max, batch_id="B-SPLIT", piece_id="piece-2", seq=int64_max),
    ]
    scope = build_piece_adoption_scope(split_ops, {"B-SPLIT": 2})
    assert [(item.op_id, item.sequence, item.target_quantity, item.predecessor_op_ids) for item in scope.operations] == [
        (above_js, above_js + 1, 2, ()),
        (int64_max - 1, int64_max, 1, (above_js,)),
        (int64_max, int64_max, 1, (above_js,)),
    ]

    common_scope = build_piece_adoption_scope(
        [SimpleNamespace(id=int64_max, batch_id="B-MAX", piece_id=None, seq=int64_max)],
        {"B-MAX": js_safe_max},
    )
    assert common_scope.operations[0].target_quantity == js_safe_max

    zero_scope = build_piece_adoption_scope(
        [SimpleNamespace(id=above_js, batch_id="B-ZERO", piece_id=None, seq=above_js)],
        {"B-ZERO": 0},
    )
    assert zero_scope.operations[0].target_quantity == 0

    for bad_id, bad_seq in ((0, 1), (-1, 1), (int64_max + 1, 1), (True, 1), (1, int64_max + 1), (1, 1.0)):
        with pytest.raises(PieceAdoptionBlocked) as exc_info:
            build_piece_adoption_scope(
                [SimpleNamespace(id=bad_id, batch_id="B", piece_id=None, seq=bad_seq)],
                {"B": 1},
            )
        assert exc_info.value.code == "piece_identity_invalid"

    for bad_qty in (-1, js_safe_max + 1, int64_max, True, 1.0, "1"):
        with pytest.raises(PieceAdoptionBlocked) as exc_info:
            build_piece_adoption_scope(
                [SimpleNamespace(id=1, batch_id="B", piece_id=None, seq=1)],
                {"B": bad_qty},
            )
        assert exc_info.value.code == "piece_quantity_unknown"


def test_prepare_run_input_supports_int64_piece_and_zero_duration_identities(trial_case):
    from core.services.workbench.execution.ledger import ExecutionLedgerService
    from core.services.workbench.execution.production_report_dependencies import ReportDependencies
    from core.services.workbench.run.preflight import PreflightService

    case = trial_case
    large_id = (1 << 53) + 17
    large_seq = (1 << 53) + 19
    case.conn.execute("UPDATE Batches SET quantity=2 WHERE batch_id='B1'")
    case.conn.execute("UPDATE BatchOperations SET seq=10,unit_hours=0.25 WHERE id=?", (case.op_id,))
    point_op_id = case.operation(
        id=large_id,
        seq=large_seq,
        piece_id="item-A",
        op_code="B1-item-A-point",
        setup_hours=0,
        unit_hours=0,
    )
    sibling_op_id = case.operation(
        id=large_id + 1,
        seq=large_seq,
        piece_id="item-B",
        op_code="B1-item-B-work",
        setup_hours=0,
        unit_hours=0.25,
    )
    case.conn.commit()

    prepared = prepare_run_input(case.conn, case.settings(), case.projections())
    assert prepared.piece_scope is not None
    assert [(item.op_id, item.sequence, item.target_quantity, item.predecessor_op_ids)
            for item in prepared.piece_scope.operations] == [
        (case.op_id, 10, 2, ()),
        (point_op_id, large_seq, 1, (case.op_id,)),
        (sibling_op_id, large_seq, 1, (case.op_id,)),
    ]

    payload = slot_payload(prepared)
    point_row = next(row for row in payload if row.op_id == point_op_id)
    assert point_row.start_time == point_row.end_time
    checked_read_only(
        case,
        lambda: piece_adoption.validate_piece_adoption(case.conn, prepared=prepared, payload=payload),
    )

    case.batch("B2", quantity=1)
    first_single = case.operation(batch="B2", seq=10, op_code="B2-10")
    second_single = case.operation(batch="B2", id=large_id + 5, seq=large_seq + 2, op_code="B2-large")
    case.conn.commit()

    single_prepared = prepare_run_input(case.conn, case.settings("B2"), case.projections("B2"))
    assert single_prepared.piece_scope is None
    by_op = {row["op_id"]: row for row in single_prepared.dispositions}
    assert by_op[second_single]["sequence"] == large_seq + 2
    assert by_op[second_single]["predecessor_refs"] == [by_op[first_single]["operation_ref"]]

    preflight_data, _ = PreflightService(case.conn).evaluate(case.settings("B1", "B2"), material_day=date.today().isoformat())
    assert preflight_data["counts"]["blocked_tasks"] == 0
    assert preflight_data["counts"]["ready_tasks"] == 5
    tasks_by_ref = {row["operation_ref"]: row for row in preflight_data["tasks"]}
    tasks_by_piece = {(row["batch_id"], row["piece_id"]): row for row in preflight_data["tasks"] if row["batch_id"] == "B1"}
    assert tasks_by_piece[("B1", None)]["sequence"] == 10 and type(tasks_by_piece[("B1", None)]["sequence"]) is int
    assert tasks_by_piece[("B1", "item-A")]["sequence"] == str(large_seq)
    assert tasks_by_piece[("B1", "item-B")]["sequence"] == str(large_seq)
    assert tasks_by_ref[by_op[first_single]["operation_ref"]]["sequence"] == 10
    assert tasks_by_ref[by_op[second_single]["operation_ref"]]["sequence"] == str(large_seq + 2)

    ledger = ExecutionLedgerService(case.conn)
    with ledger.read_snapshot() as scope:
        deps = ReportDependencies(scope, case.projections("B2"))
        assert deps.relatives(
            {"batch_id": "B2", "operation_ref": by_op[first_single]["operation_ref"]}
        ) == [by_op[second_single]["operation_ref"]]

    case.batch("B3", quantity=1)
    case.operation(batch="B3", id=large_id + 10, seq=large_seq, op_code="B3-skip", status="skipped")
    case.operation(batch="B3", id=large_id + 11, seq=large_seq + 4, op_code="B3-after")
    case.conn.commit()
    skipped_preflight, _ = PreflightService(case.conn).evaluate(case.settings("B3"), material_day=date.today().isoformat())
    assert [row["sequence"] for row in skipped_preflight["tasks"]] == [str(large_seq), str(large_seq + 4)]
    pred_issues = [item for item in skipped_preflight["tasks"][1]["issues"] if item["code"] == "predecessor_excluded"]
    assert len(pred_issues) == 1 and pred_issues[0]["predecessor_sequence"] == str(large_seq)
