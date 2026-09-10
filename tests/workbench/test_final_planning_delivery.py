"""Candidate delivery service contracts; full UI proof is a separate browser test."""

import json
import subprocess
from pathlib import Path

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_candidate import RunCandidateReadScope
from core.services.workbench.run_candidates import WorkbenchRunCandidateQueryService
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_piece_chain_support import piece_layout
from tests.workbench.test_run_candidate_support import (
    api,
    compute,
    connect,
    edit_artifact,
    edit_capture,
    public,
    read,
    retained,
)
from tests.workbench.test_run_candidate_support import candidate_case as candidate_case


def workspace(case, ref, **scope):
    with retained(case.conn):
        data, fingerprint = WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(ref, **scope))
    public(data)
    return data, fingerprint


def labelled(case):
    case.conn.execute("UPDATE Batches SET part_name='Frozen batch label' WHERE batch_id='B1'")
    case.conn.commit()


def test_complete_delivery_uses_full_persisted_tasks_and_survives_reopen(candidate_case):
    case = candidate_case
    labelled(case)
    case.operation(seq=2, unit_hours=.5)
    case.conn.commit()
    _, refs = compute(case)
    for ref in refs:
        data, fingerprint = workspace(case, ref)
        delivery = data["delivery_risks"]
        assert delivery["state"] == "available" and delivery["items_complete"]
        assert delivery["basis"]["current_entities_consulted"] is False
        assert delivery["basis"]["operation_scope"] == "captured_batch_operations"
        item, = delivery["items"]
        assert item["schedule_complete"] and item["operation_count"] == item["scheduled_operation_count"] == 2
        assert item["planned_finish"] == max(row["end"] for row in data["tasks"])
        assert item["part_label"] == "Frozen batch label" and item["quantity"] == 3
        assert item["risk"] == "on_time" and item["delay_hours"] == 0
        assert {row["row_ref"] for row in item["last_operations"]} == {
            row["row_ref"] for row in data["tasks"] if row["end"] == item["planned_finish"]}
        with connect(case.path) as conn:
            recovered = WorkbenchRunCandidateQueryService(conn).workspace(RunCandidateReadScope(ref))
            assert recovered == (data, fingerprint)


def test_early_slice_keeps_later_full_batch_completion(candidate_case):
    case = candidate_case
    labelled(case)
    case.operation(seq=2, unit_hours=.5)
    case.conn.commit()
    _, refs = compute(case)
    full, _ = workspace(case, refs[0])
    first = min(full["tasks"], key=lambda row: row["start"])
    partial, _ = workspace(case, refs[0], range_start=first["start"], range_end=first["end"])
    assert partial["task_count"] == 1 < full["task_count"]
    assert partial["delivery_risks"]["items"] == full["delivery_risks"]["items"]
    assert partial["delivery_risks"]["items"][0]["planned_finish"] > partial["tasks"][0]["end"]


def test_skipped_batch_stays_unknown_instead_of_disappearing(candidate_case):
    case = candidate_case
    labelled(case)
    case.batch("B2", ready_status="no")
    case.operation("B2")
    case.conn.commit()
    _, refs = compute(case, case.settings("B1", "B2"))
    data, _ = workspace(case, refs[0])
    items = {row["batch_id"]: row for row in data["delivery_risks"]["items"]}
    assert set(items) == {"B1", "B2"}
    assert items["B1"]["risk"] == "on_time"
    assert items["B2"]["risk"] == "unknown" and items["B2"]["unscheduled_operation_count"] == 1
    assert items["B2"]["planned_finish"] is None and not items["B2"]["last_operations"]
    assert data["delivery_risks"]["summary"]["unknown_count"] == 1
    assert data["delivery_risks"]["summary"]["total_tardiness_hours"] is None


def test_current_business_edits_cannot_rewrite_admission_delivery(candidate_case):
    case = candidate_case
    labelled(case)
    _, refs = compute(case)
    before = workspace(case, refs[0])
    case.conn.execute("UPDATE Batches SET due_date='2000-01-01',quantity=99,part_name='Changed current name'")
    case.conn.execute("UPDATE BatchOperations SET seq=90,unit_hours=99")
    case.conn.execute("UPDATE Machines SET name='Changed current machine'")
    case.conn.commit()
    assert workspace(case, refs[0]) == before


def test_missing_admission_batch_is_visible_unavailable(candidate_case):
    case = candidate_case
    _, refs = compute(case)
    edit_capture(case, "facts_json", lambda facts: facts["tables"].pop("Batches"))
    data, _ = workspace(case, refs[0])
    delivery = data["delivery_risks"]
    assert delivery["state"] == "unavailable" and delivery["items_complete"] is False
    assert delivery["summary"]["unknown_count"] == 1 and delivery["summary"]["total_tardiness_hours"] is None
    assert {row["code"] for row in delivery["issues"]} == {"captured_batch_missing"}


@pytest.mark.parametrize("value,reason", [(None, "due_date_missing"), ("bad-date", "due_date_invalid"), ("9999-12-31", "due_date_unspecified")])
def test_missing_invalid_or_unspecified_admission_due_never_becomes_zero_risk(candidate_case, value, reason):
    case = candidate_case
    _, refs = compute(case)
    columns = [row[1] for row in case.conn.execute('PRAGMA table_info("Batches")')]

    def edit(facts):
        facts["tables"]["Batches"][0][columns.index("due_date")] = value

    edit_capture(case, "facts_json", edit)
    data, _ = workspace(case, refs[0])
    item, = data["delivery_risks"]["items"]
    assert item["risk"] == "unknown" and item["delay_hours"] is None
    assert reason in item["issues"]


def test_common_and_piece_points_preserve_all_tied_terminal_refs(candidate_case):
    case = candidate_case
    labelled(case)
    ids = piece_layout(case, parallel=False, unit=0)
    _, refs = compute(case)
    data, _ = workspace(case, refs[0])
    item, = data["delivery_risks"]["items"]
    assert item["schedule_complete"] and item["operation_count"] == len(ids)
    assert all(row["event_kind"] == "point" and not row["occupies_resources"] for row in data["tasks"])
    expected = {row["row_ref"] for row in data["tasks"] if row["end"] == max(task["end"] for task in data["tasks"])}
    assert len(expected) > 1
    assert {row["row_ref"] for row in item["last_operations"]} == expected
    assert {row["piece_id"] for row in item["last_operations"]} == {None, "item-A", "item-B", "item-C"}


def test_payload_mismatch_is_rejected_not_rebuilt_from_summary(candidate_case):
    case = candidate_case
    _, refs = compute(case)
    edit_artifact(case, refs[0], lambda value: value["validated_payload"]["schedule_rows"][0].update(op_id=999999))
    with pytest.raises(WorkbenchCommandRejected):
        workspace(case, refs[0])


def test_browser_contract_rejects_wrong_source_scope_summary_and_terminal_identity(candidate_case, tmp_path):
    case = candidate_case
    labelled(case)
    _, refs = compute(case)
    client, _ = api(case)
    payload = read(client, "/candidates/" + refs[0] + "/workspace")
    source = tmp_path / "candidate-response.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    node, _, _ = runtime_tools()
    result = subprocess.run([node, str(Path(__file__).with_name("final_planning_delivery_contract.cjs")), str(source)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"valid": 1, "rejected": 10}
