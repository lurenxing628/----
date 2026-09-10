"""Deliberately corrupt isolated fixtures; never rewrite or bless bad evidence."""

import json

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from data.repositories import workbench_trial_adoption_history as limits
from tests.workbench.trial_adoption_history_support import raw_receipt, read, seeded
from tests.workbench.trial_adoption_history_support import trial_case as trial_case  # noqa: F401
from tests.workbench.trial_support import snapshot


@pytest.mark.parametrize("field", ["scenario_ref", "draft_ref", "source_scenario_ref", "source_draft_ref", "plan_ref", "version", "baseline_ref", "row_count"])
def test_bad_receipt_binding_rejected_without_repair(trial_case, field):
    saved, receipt = seeded(trial_case)
    row = trial_case.conn.execute("SELECT outcome_json FROM WorkbenchCommandReceipts WHERE receipt_ref=?", (receipt["receipt_ref"],)).fetchone()
    value = json.loads(row[0])
    target = value["data"] if field in ("scenario_ref", "draft_ref", "row_count") else value["data"]["official_plan"]
    target[field] = 800 if field in ("version", "row_count") else saved["draft_ref"] if field == "plan_ref" else "f" * 48
    trial_case.conn.execute("UPDATE WorkbenchCommandReceipts SET outcome_json=? WHERE receipt_ref=?", (json.dumps(value), receipt["receipt_ref"]))
    trial_case.conn.commit()
    before = snapshot(trial_case.conn)
    with pytest.raises(WorkbenchCommandRejected):
        read(trial_case, saved)
    assert snapshot(trial_case.conn) == before


def test_duplicate_plan_does_not_become_second_history(trial_case):
    saved, _ = seeded(trial_case)
    raw_receipt(trial_case.conn, saved, key="db-fault-duplicate-0001")
    with pytest.raises(WorkbenchCommandRejected) as error:
        read(trial_case, saved)
    assert error.value.code == "adoption_history_invalid"


def test_inactive_identity_preserves_receipt_with_explicit_gap(trial_case):
    saved, receipt = seeded(trial_case)
    ref = receipt["data"]["official_plan"]["plan_ref"]
    trial_case.conn.execute("UPDATE WorkbenchPlanSourceRefs SET active=0 WHERE ref=?", (ref,))
    trial_case.conn.commit()
    data, _ = read(trial_case, saved)
    item = data["items"][0]
    assert item["official_plan"] is None and item["current_state"] == "unavailable"
    assert item["receipt_ref"] == receipt["receipt_ref"] and item["evidence_gaps"]


@pytest.mark.parametrize("limit", ["MAX_SCAN_ROWS", "MAX_RECEIPTS", "MAX_DIRECTORY_BYTES", "MAX_RECEIPT_BYTES", "MAX_SCENARIO_BYTES"])
def test_all_directory_and_payload_bounds_are_explicit(trial_case, monkeypatch, limit):
    saved, _ = seeded(trial_case)
    monkeypatch.setattr(limits, limit, 0 if limit == "MAX_RECEIPTS" else 1)
    with pytest.raises(WorkbenchCommandRejected) as error:
        read(trial_case, saved)
    assert error.value.code == "query_too_large"


@pytest.mark.parametrize("field", ["scenario_ref", "draft_ref", "base", "baseline"])
def test_saved_snapshot_must_match_original_save_receipt(trial_case, field):
    saved, _ = seeded(trial_case)
    changed = dict(saved)
    changed[field] = {"plan_ref": "f" * 48} if field == "base" else {"version": 1, "plan_ref": "f" * 48} if field == "baseline" else "f" * 48
    key = trial_case.conn.execute("SELECT request_key FROM WorkbenchTrialScenarios WHERE scenario_ref=?", (saved["scenario_ref"],)).fetchone()[0]
    trial_case.conn.execute("UPDATE WorkbenchCommandReceipts SET outcome_json=? WHERE request_key=?", (json.dumps({"result": "committed", "data": changed, "warnings": []}), key))
    trial_case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected):
        read(trial_case, saved)


def test_multiple_directory_rows_are_paged_not_local_last_receipt(trial_case):
    # Extra receipts are intentionally identity-unavailable boundary fixtures;
    # successful CQ commands cannot adopt one immutable baseline twice.
    saved, _ = seeded(trial_case)
    for index in range(5):
        raw_receipt(trial_case.conn, saved, key=f"db-page-fault-{index:04d}",
                    plan={"plan_ref": f"{index + 1:048x}", "version": 30 + index})
    pages = [read(trial_case, saved, page=page, size=2) for page in (1, 2, 3)]
    assert len({digest for _data, digest in pages}) == 1
    items = [item for data, _ in pages for item in data["items"]]
    assert len(items) == 6 and len({item["receipt_ref"] for item in items}) == 6
    assert sum(item["current_state"] == "unavailable" for item in items) == 5
