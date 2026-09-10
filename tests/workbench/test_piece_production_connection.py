"""Production DATE conversion must not weaken complete raw-work equality."""

from dataclasses import replace
from datetime import date, datetime
from unittest.mock import patch

import pytest

from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.models.workbench_trial_adoption import TrialAdoptionBlocked
from core.services.workbench import piece_adoption
from core.services.workbench.piece_adoption import validate_piece_adoption
from core.services.workbench.trial_adoption_validation import validate_trial_adoption
from tests.workbench.piece_adoption_support import lower_input, slot_payload, split
from tests.workbench.piece_chain_support import adopt_candidate, saved_trial
from tests.workbench.piece_production_connection_support import (
    assert_all_old_rows_retained,
    assert_official_rows,
    assert_raw_date_differences,
    open_connection,
    reopen,
    seed_history,
    write_evidence,
)
from tests.workbench.piece_production_connection_support import production_case as production_case  # noqa: F401
from tests.workbench.piece_production_connection_support import stable_tmp_path as tmp_path  # noqa: F401
from tests.workbench.run_candidate_adoption_support import INTENT
from tests.workbench.run_candidate_adoption_support import service as candidate_adoption
from tests.workbench.run_candidate_support import compute
from tests.workbench.trial_adoption_support import service as trial_adoption
from tests.workbench.trial_support import service as trial_service
from tests.workbench.trial_support import snapshot
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401


def test_worker_new_connection_trial_adopts_under_begin_immediate(production_case):
    case = production_case
    ids, rival, old_receipt = seed_history(case)
    before = snapshot(case.conn)
    assert len(before) == 77
    for table in ("Batches", "BatchOperations", "WorkbenchProductionReports",
                  "WorkbenchProductionReportRevisions", "WorkbenchCommandReceipts", "ScheduleCandidate",
                  "ScheduleCandidateRows", "ScheduleAdjustmentScenario", "ScheduleAdjustmentScenarioRow"):
        assert before[table], table
    root = case.path.parent
    write_evidence(root, "before", before)
    run_ref, refs = compute(case, case.settings("B1", "B2"))
    adopted = adopt_candidate(case, refs[0])
    assert adopted["data"]["official_plan"]["version"] == 5
    case = reopen(case)
    try:
        draft, changed, saved = saved_trial(case, {"plan_ref": adopted["data"]["official_plan"]["plan_ref"]},
                                            op_id=ids[None, 40])
        assert draft["task_count"] == changed["task_count"] == saved["task_count"] == 9
        assert {row["quantity"] for row in draft["tasks"] if row["piece_id"] is not None} == {1}
        frozen = trial_service(case.conn).scenario(saved["scenario_ref"])
        evidence = validate_trial_adoption(case.conn, saved["scenario_ref"])
        assert_raw_date_differences(case, evidence.prepared)
        case = reopen(case)
        trace, checked_transactions = [], []
        case.conn.set_trace_callback(trace.append)
        real_scope = piece_adoption.current_piece_scope

        def checked(conn, prepared):
            assert conn is case.conn and conn.in_transaction
            checked_transactions.append([sql for sql in trace if sql.startswith("BEGIN")][-1])
            return real_scope(conn, prepared)

        svc = trial_adoption(case.conn)
        with patch.object(piece_adoption, "current_piece_scope", side_effect=checked):
            preview = svc.preview(saved["scenario_ref"])
            assert preview["validation"]["can_adopt"], preview
            result = svc.adopt(saved["scenario_ref"], preview["write_context"]["write_token"],
                               "et-trial-adopt-0001", INTENT)
        assert result["ok"], result
        assert "BEGIN IMMEDIATE" in checked_transactions and "BEGIN" in checked_transactions
        plan = result["data"]["official_plan"]
        assert plan["version"] == 6 and plan["source_scenario_ref"] == saved["scenario_ref"]
        assert trial_service(case.conn).scenario(saved["scenario_ref"]) == frozen
        after = snapshot(case.conn)
        assert_all_old_rows_retained(before, after)
        write_evidence(root, "after", after)
        replay = svc.adopt(saved["scenario_ref"], "expired", "et-trial-adopt-0001", INTENT)
        assert replay["replayed"] and replay["receipt_ref"] == result["receipt_ref"]
        replay = candidate_adoption(case.conn).adopt(refs[0], "expired", "ef-candidate-adopt-0001", INTENT)
        assert replay["replayed"] and replay["receipt_ref"] == adopted["receipt_ref"]
        assert snapshot(case.conn) == after
        assert_official_rows(case, ids, rival)
        write_evidence(root, "result", {"connection": case.connection_kind, "run_ref": run_ref,
            "candidate_ref": refs[0], "scenario_ref": saved["scenario_ref"], "plan": plan,
            "checked_transactions": checked_transactions, "old_receipt_ref": old_receipt["receipt_ref"],
            "tables": len(after), "all_old_rows_retained": True, "replays_retained": True})
    finally:
        case.conn.close()


@pytest.mark.parametrize("field", ("due_date", "ready_date"))
@pytest.mark.parametrize("value", (None, "2026-09-09"))
def test_only_known_date_representations_are_equivalent(production_case, field, value):
    case = production_case
    split(case)
    case.conn.execute("UPDATE Batches SET " + field + "=? WHERE batch_id='B1'", (value,))
    case.conn.commit()
    prepared = lower_input(case)
    payload = slot_payload(prepared)
    before = snapshot(case.conn)
    for representation in ((None,) if value is None else (value, date.fromisoformat(value))):
        prepared.batches["B1"] = replace(prepared.batches["B1"], **{field: representation})
        validate_piece_adoption(case.conn, prepared=prepared, payload=payload)
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("field", ("due_date", "ready_date"))
@pytest.mark.parametrize("value", ("unknown", "2026-02-30", "2026-9-09", "2026-09-09T00:00:00",
                                  b"2026-09-09", 20260909, True, datetime(2026, 9, 9)))
def test_invalid_prepared_dates_fail_closed(production_case, field, value):
    case = production_case
    split(case)
    prepared = lower_input(case)
    payload = slot_payload(prepared)
    prepared.batches["B1"] = replace(prepared.batches["B1"], **{field: value})
    before = snapshot(case.conn)
    with pytest.raises(PieceAdoptionBlocked) as caught:
        validate_piece_adoption(case.conn, prepared=prepared, payload=payload)
    assert caught.value.code == "invalid_batch_date"
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("field,value", (("due_date", "2026-09-26"), ("due_date", None),
                                        ("ready_date", "2026-09-09"), ("quantity", 4)))
def test_semantic_raw_drift_still_rejected(production_case, field, value):
    case = production_case
    split(case)
    prepared = lower_input(case)
    payload = slot_payload(prepared)
    case.conn.execute("UPDATE Batches SET " + field + "=? WHERE batch_id='B1'", (value,))
    case.conn.commit()
    before = snapshot(case.conn)
    with pytest.raises(PieceAdoptionBlocked) as caught:
        validate_piece_adoption(case.conn, prepared=prepared, payload=payload)
    assert caught.value.code == ("piece_scope_incomplete" if field == "quantity" else "piece_raw_changed")
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("field,value", (("due_date", "2026-09-26"), ("quantity", 4),
    ("due_date", "unknown"), ("ready_date", "2026-02-30"), ("due_date", b"2026-09-25"),
    ("due_date", 20260925), ("baseline", None)))
def test_saved_snapshot_drift_after_preview_rejected_in_write_transaction(production_case, field, value):
    case = production_case
    ids = split(case)
    _, refs = compute(case)
    adopted = adopt_candidate(case, refs[0])
    _, _, saved = saved_trial(case, {"plan_ref": adopted["data"]["official_plan"]["plan_ref"]}, op_id=ids[None, 40])
    svc = trial_adoption(case.conn)
    preview = svc.preview(saved["scenario_ref"])
    assert preview["validation"]["can_adopt"], preview
    other = open_connection(case.path, case.connection_kind)
    try:
        if field == "baseline":
            from tests.workbench.run_jobs_support import JobCase
            JobCase(other).plan(2, list(ids.values()))
        else:
            other.execute("UPDATE Batches SET " + field + "=? WHERE batch_id='B1'", (value,))
        other.commit()
    finally:
        other.close()
    # Raw storage capture must preserve even malformed DATE/BLOB fixtures.
    from core.services.workbench.trial_facts import capture_facts
    before = capture_facts(case.conn)
    receipts = case.conn.execute("SELECT count(*) FROM WorkbenchCommandReceipts").fetchone()[0]
    blocked = svc.preview(saved["scenario_ref"])
    assert not blocked["validation"]["can_adopt"] and blocked["write_context"]["write_token"] is None
    trace = []
    case.conn.set_trace_callback(trace.append)
    with pytest.raises(TrialAdoptionBlocked) as caught:
        svc.adopt(saved["scenario_ref"], preview["write_context"]["write_token"], "et-stale-adopt-0001", INTENT)
    assert caught.value.code == ("snapshot_stale" if field in ("quantity", "baseline") else "scenario_work_changed")
    assert "BEGIN IMMEDIATE" in trace
    assert capture_facts(case.conn) == before
    assert case.conn.execute("SELECT count(*) FROM WorkbenchCommandReceipts").fetchone()[0] == receipts


@pytest.mark.parametrize("field,value,code", (("quantity", "3", "quantity_unknown"),
    ("quantity", 3.0, "quantity_unknown"), ("quantity", True, "quantity_unknown"),
    ("quantity", None, "quantity_unknown"), ("unit_hours", .5, "piece_raw_changed")))
def test_non_date_fields_keep_strict_validation_and_equality(production_case, field, value, code):
    case = production_case
    split(case)
    prepared = lower_input(case)
    payload = slot_payload(prepared)
    if field == "quantity":
        prepared.batches["B1"] = replace(prepared.batches["B1"], quantity=value)
    else:
        prepared.operations[0] = replace(prepared.operations[0], unit_hours=value)
    before = snapshot(case.conn)
    with pytest.raises(PieceAdoptionBlocked) as caught:
        validate_piece_adoption(case.conn, prepared=prepared, payload=payload)
    assert caught.value.code == code
    assert snapshot(case.conn) == before
