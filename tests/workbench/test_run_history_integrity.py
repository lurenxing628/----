"""Damaged terminal/receipt/manifest directories fail closed, including off-page rows."""

import pytest

from tests.workbench.run_history_support import BASE, api, corrupt, dump, edit_receipt, seed
from tests.workbench.run_history_support import history_case as _history_case


@pytest.mark.parametrize("damage", ["missing_receipt", "receipt_state", "manifest_state", "missing_candidate", "duplicate_candidate",
    "manifest_count", "boolean_count", "manifest_status", "result_persisted", "task_missing", "task_ordinal", "admission_missing",
    "admission_binding", "invalid_json", "duplicate_json", "nonfinite_json", "overflow_json", "running_with_receipt", "accepted_clock", "finished_clock"])
def test_directory_corruption_is_explicit_error_even_off_page(history_case, damage):
    case = history_case
    ref = seed(case, "complete", accepted="2026-09-08T00:00:00")
    seed(case, "queued", accepted="2026-09-10T00:00:00")
    if damage == "missing_receipt":
        corrupt(case.conn, "WorkbenchRunReceipts", "DELETE FROM WorkbenchRunReceipts")
    elif damage == "receipt_state":
        corrupt(case.conn, "WorkbenchRunReceipts", "UPDATE WorkbenchRunReceipts SET state='partial'")
    elif damage in ("manifest_state", "result_persisted"):
        edit_receipt(case, ref, lambda value: value.update({"state": "partial"} if damage == "manifest_state" else {"result_persisted": False}))
    elif damage in ("missing_candidate", "duplicate_candidate"):
        edit_receipt(case, ref, lambda value: value["candidates"].pop() if damage == "missing_candidate" else value["candidates"].append(value["candidates"][0]))
    elif damage in ("manifest_count", "boolean_count", "manifest_status"):
        patch = {"task_count": 2 if damage == "manifest_count" else True} if damage != "manifest_status" else {"status": "failed"}
        edit_receipt(case, ref, lambda value: value["candidates"][0].update(patch))
    elif damage == "task_missing":
        corrupt(case.conn, "WorkbenchRunCandidateTasks", "DELETE FROM WorkbenchRunCandidateTasks")
    elif damage == "task_ordinal":
        corrupt(case.conn, "WorkbenchRunCandidateTasks", "UPDATE WorkbenchRunCandidateTasks SET ordinal=2")
    elif damage == "admission_missing":
        case.conn.execute("PRAGMA foreign_keys=OFF")
        corrupt(case.conn, "WorkbenchCommandReceipts", "DELETE FROM WorkbenchCommandReceipts WHERE request_key=(SELECT request_key FROM WorkbenchRunJobs WHERE run_ref=?)", (ref,))
        case.conn.execute("PRAGMA foreign_keys=ON")
    elif damage == "admission_binding":
        corrupt(case.conn, "WorkbenchCommandReceipts", "UPDATE WorkbenchCommandReceipts SET context_ref='wrong'")
    elif damage in ("invalid_json", "duplicate_json", "nonfinite_json", "overflow_json"):
        values = {"invalid_json": "{", "duplicate_json": '{"state":"complete","state":"complete"}',
                  "nonfinite_json": '{"x":NaN}', "overflow_json": '{"x":1e999}'}
        corrupt(case.conn, "WorkbenchRunReceipts", "UPDATE WorkbenchRunReceipts SET result_json=?", (values[damage],))
    elif damage == "running_with_receipt":
        corrupt(case.conn, "WorkbenchRunJobs", "UPDATE WorkbenchRunJobs SET state='running',stage='computing',finished_at=NULL WHERE run_ref=?", (ref,))
    else:
        field = "accepted_at" if damage == "accepted_clock" else "finished_at"
        corrupt(case.conn, "WorkbenchRunJobs", "UPDATE WorkbenchRunJobs SET " + field + "='invalid' WHERE run_ref=?", (ref,))
    client, _ = api(case)
    before = dump(case.conn)
    response = client.get(BASE, query_string={"page": 1, "size": 1, "state": "queued"})
    assert response.status_code == 500 and response.get_json()["error"]["code"] == "run_result_inconsistent"
    assert response.get_json()["committed"] is False and "data" not in response.get_json()
    assert dump(case.conn) == before


def test_unknown_snapshot_is_not_treated_as_a_fresh_read(history_case):
    client, _ = api(history_case)
    response = client.get(BASE, query_string={"snapshot_ref": "unknown"})
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"


def test_equal_length_duplicate_manifest_cannot_hide_another_candidate(history_case):
    case = history_case
    ref = seed(case, "complete", counts=(1, 1))
    edit_receipt(case, ref, lambda value: value["candidates"].__setitem__(1, value["candidates"][0]))
    client, _ = api(case)
    response = client.get(BASE)
    assert response.status_code == 500 and response.get_json()["error"]["code"] == "run_result_inconsistent"


@pytest.mark.parametrize("table", ["WorkbenchRunReceipts", "WorkbenchRunCandidates", "WorkbenchRunCandidateTasks", "WorkbenchCommandReceipts"])
def test_orphan_records_fail_closed_without_writing_recovery(history_case, table):
    case = history_case
    seed(case, "complete")
    case.conn.execute("PRAGMA foreign_keys=OFF")
    if table == "WorkbenchCommandReceipts":
        corrupt(case.conn, "WorkbenchRunCandidateTasks", "DELETE FROM WorkbenchRunCandidateTasks")
        corrupt(case.conn, "WorkbenchRunCandidates", "DELETE FROM WorkbenchRunCandidates")
        corrupt(case.conn, "WorkbenchRunReceipts", "DELETE FROM WorkbenchRunReceipts")
        corrupt(case.conn, "WorkbenchRunJobs", "DELETE FROM WorkbenchRunJobs")
    else:
        field = "candidate_ref" if table == "WorkbenchRunCandidateTasks" else "run_ref"
        corrupt(case.conn, table, "UPDATE " + table + " SET " + field + "=?", ("f" * 48,))
    case.conn.execute("PRAGMA foreign_keys=ON")
    client, _ = api(case)
    before = dump(case.conn)
    response = client.get(BASE)
    assert response.status_code == 500 and response.get_json()["error"]["code"] == "run_result_inconsistent"
    assert dump(case.conn) == before
