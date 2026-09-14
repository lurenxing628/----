"""Task E full-factory HTTP: original rows, strict writes, files, rollback and restart."""

import csv
import io

from core.services.workbench.field_report_files_codec import decode_reports, encode_reports
from tests.workbench.final_execution_cases import (
    CORRECT_TABLES,
    CREATE_TABLES,
    EXECUTION,
    command,
    confirm_file,
    create,
    preview_file,
    revise,
    seed,
    sql,
    task,
    values,
)
from tests.workbench.final_execution_cases import final_e_runtime as final_e_runtime
from tests.workbench.final_execution_cases import final_execution_host as final_execution_host
from tests.workbench.final_execution_fileedit import selected_piece_file
from tests.workbench.final_execution_support import changes, old_rows_preserved, report_facts, restart_preserved
from tests.workbench.live_environment import write_json


def test_actual_quantities_correction_old_facts_and_receipts_survive_restart(final_execution_host):
    host = final_execution_host
    original = host.state()
    current = task(host)
    assert current["execution"]["target_quantity"] == 10
    first_body, first = create(host)
    record = first["data"]["rows"][0]
    assert changes(original, host.state()) == CREATE_TABLES
    partial = task(host)["execution"]
    assert partial["known_completed_quantity"] == 2 and partial["remaining_quantity"] == 8
    assert partial["confirmed_finish"] is None and partial["execution_state"] == "partial"
    before_correct = host.state()
    correction_body, correction = revise(host, record, {"completed_quantity": 3, "effective_processing_hours": 1.25})
    assert changes(before_correct, host.state()) == CORRECT_TABLES
    corrected = next(row for row in task(host)["execution"]["reports"] if row["report_ref"] == record["report_ref"])
    assert corrected["revision_ref"] == correction["data"]["rows"][0]["revision_ref"]
    assert corrected["recorded_against_task_ref"] == current["task_ref"]
    assert corrected["recorded_against_plan_ref"] == current["plan_ref"]
    assert corrected["operation_ref"] == current["operation_ref"]
    assert len(corrected["correction_history"]) == 2
    _, complete = create(host, values(host, 7, actual_start="2026-09-02T10:00:00", actual_end="2026-09-02T12:00:00"))
    done = task(host)["execution"]
    assert done["execution_state"] == "complete" and done["completion_basis"] == "complete_reports"
    assert done["known_completed_quantity"] == 10 and done["remaining_quantity"] == 0
    assert done["confirmed_finish"] == "2026-09-02T12:00:00"
    legacy = task(host, 3)["execution"]
    assert legacy["execution_state"] == "complete" and legacy["completion_basis"] == "legacy_finish_event"
    assert legacy["reports"] == [] and legacy["remaining_quantity"] is None
    paused = task(host, 5)["execution"]
    assert paused["execution_state"] == "paused" and len(paused["legacy_facts"]) == 2
    actual = host.json("/api/workbench/v1/actual-gantt", query={"plan_ref": current["plan_ref"]})
    actual_item = next(row for row in actual["data"]["items"] if row["task"]["task_ref"] == current["task_ref"])
    assert actual_item["execution"]["known_completed_quantity"] == 10
    before_restart = host.state()
    old_rows_preserved(original, before_restart, {"WorkbenchExecutionLedgerClock"})
    host.stop()
    host.start(reuse=True)
    restarted_state = host.state()
    restart_audit = restart_preserved(before_restart, restarted_state)
    for body, receipt, path in [
        (first_body, first, EXECUTION + "/tasks/" + current["task_ref"] + "/reports"),
        (correction_body, correction, EXECUTION + "/reports/" + record["report_ref"] + "/correct"),
    ]:
        replay = host.json(path, body={**body, "write_token": "expired-after-real-restart"})
        assert replay["replayed"] and replay["receipt_ref"] == receipt["receipt_ref"]
        assert replay["data"] == receipt["data"]
    assert list(map(report_facts, task(host)["execution"]["reports"])) == list(map(report_facts, done["reports"]))
    assert host.state() == restarted_state
    write_json(host.root / "backend-proof.json", {"current": current, "first": first, "correction": correction,
        "complete": complete, "strict_create_tables": sorted(CREATE_TABLES), "strict_correct_tables": sorted(CORRECT_TABLES),
        "actual_item": actual_item, "all_old_rows_preserved": True, "restarted": True, "restart_audit": restart_audit,
        "replayed_original_receipts": [first["receipt_ref"], correction["receipt_ref"]]})


def test_real_sql_failure_rolls_back_and_invalid_or_duplicate_request_never_writes(final_execution_host):
    host = final_execution_host
    current = task(host)
    body = command(current["execution"]["write_context"], values(host))
    path = EXECUTION + "/tasks/" + current["task_ref"] + "/reports"
    before = host.state()
    sql(host, "CREATE TRIGGER final_e_fail_receipt BEFORE INSERT ON WorkbenchCommandReceipts "
              "BEGIN SELECT RAISE(ABORT,'final-e-owned-rollback'); END")
    failed = host.json(path, body=body, status=500)
    assert failed["committed"] == "unknown"
    assert host.state() == before
    sql(host, "DROP TRIGGER final_e_fail_receipt")
    accepted = host.json(path, body=body)
    committed = host.state()
    assert changes(before, committed) == CREATE_TABLES
    replay = host.json(path, body=body)
    assert replay["replayed"] and replay["receipt_ref"] == accepted["receipt_ref"]
    conflict = host.json(path, body={**body, "input": values(host, 4)}, status=409)
    assert conflict["error"]["code"] == "request_key_conflict" and conflict["committed"] is False
    assert host.state() == committed
    fresh = task(host)
    invalid = command(fresh["execution"]["write_context"], values(host, 11))
    rejection = host.json(path, body=invalid, status=409)
    assert rejection["committed"] is False and host.state() == committed
    write_json(host.root / "rollback-proof.json", {"failed": failed, "accepted": accepted, "replay": replay,
        "conflict": conflict, "invalid": rejection, "strict_tables": sorted(CREATE_TABLES), "rollback_all_tables": True})


def test_full_factory_13_column_identity_old10_unique_csv_and_atomic_import(final_execution_host):
    host = final_execution_host
    original = host.state()
    reading = host.json(EXECUTION + "/tasks")
    status, _, downloaded = host.request(EXECUTION + "/files/template", query={**reading["data"]["scope"],
                                               "snapshot_ref": reading["meta"]["snapshot_ref"]})
    assert status == 200
    decoded = decode_reports(downloaded)
    expected_tasks = set(seed(host)["task_refs"].values()) - {seed(host)["task_refs"]["3"]}
    assert len(decoded) == 32 and {row["values"]["task_ref"] for row in decoded} == expected_tasks
    selected = [row for row in decoded if row["values"]["piece_id"] in ("分件甲", "0")]
    content = selected_piece_file(downloaded)
    preview = preview_file(host, content, reading)
    assert host.state() == original
    assert preview["data"]["summary"]["changed"] == 2 and preview["data"]["can_confirm"]
    body, result = confirm_file(host, preview)
    assert changes(original, host.state()) == CREATE_TABLES
    for row in selected:
        current = host.json(EXECUTION + "/tasks/" + row["values"]["task_ref"])["data"]["task"]
        projection = current["execution"]
        assert projection["target_quantity"] == 1
        assert current["quantity"] is None and current["batch_quantity"] is None
        assert current["quantity_reason"] == "plan_target_not_recorded"
        assert sql(host, "SELECT quantity FROM Batches WHERE batch_id='B1'") == [{"quantity": 10}]
        report = projection["reports"][0]
        assert report["completed_quantity"] == report["effective_processing_hours"] == 0
        assert report["recorded_against_task_ref"] == row["values"]["task_ref"]
        assert projection["execution_state"] != "complete"
    replay_state = host.state()
    replay = host.json(EXECUTION + "/files/confirm", body=body)
    assert replay["replayed"] and replay["receipt_ref"] == result["receipt_ref"]
    assert host.state() == replay_state
    legacy = {"report_no": "FINAL-E-OLD-10", "batch_id": "B1", "operation_label": "30 Turning",
              "actual_start": "2026-09-01T08:00:00", "completed_quantity": 0, "effective_processing_hours": None}
    old = preview_file(host, encode_reports([legacy]))
    assert old["data"]["can_confirm"]
    confirm_file(host, old)
    unknown = task(host, 30)["execution"]["reports"][0]
    assert unknown["completed_quantity"] == 0 and unknown["effective_processing_hours"] is None
    ambiguous = preview_file(host, encode_reports([{**legacy, "operation_label": "1 Turning"}]))
    assert not ambiguous["data"]["can_confirm"]
    preserved = host.state()
    confirm_file(host, ambiguous, status=409)
    assert host.state() == preserved
    actual = host.json("/api/workbench/v1/actual-gantt", query={"plan_ref": seed(host)["plan_ref"]})
    code, _, raw = host.request("/api/workbench/v1/actual-gantt/export", query={"plan_ref": seed(host)["plan_ref"],
                          "snapshot_ref": actual["meta"]["snapshot_ref"], "format": "csv"})
    assert code == 200
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    columns = list(rows[0])
    assert columns[:10] == ["计划编号", "任务编号", "工序编号", "批次", "工序", "计划开工", "计划完工", "计划设备", "计划人员", "目标数量"]
    assert columns[42:] == ["单件编号", "计划应做数量", "计划批次数量", "计划数量依据", "计划数量缺失原因"]
    old_row = next(row for row in rows if row["报工单号"] == "FINAL-E-OLD-10")
    assert old_row["本次数量"] == "0" and old_row["有效加工工时（小时）"] == ""
    assert host.state() == preserved
    old_rows_preserved(original, preserved, {"WorkbenchExecutionLedgerClock"})
    write_json(host.root / "files-proof.json", {"template_columns": 13, "template_tasks": len(decoded),
        "explicit_identities": selected, "import": result, "replay": replay,
        "old10_unique": unknown, "old10_ambiguous": ambiguous, "csv_columns": list(rows[0]),
        "old_csv_row": old_row, "old_rows_preserved": True})
