"""Real HTTP rejection boundaries and pending-command preservation in the full UI."""

import json
import time
from concurrent.futures import ThreadPoolExecutor

from tests.workbench.final_execution_cases import (
    CREATE_TABLES,
    EXECUTION,
    command,
    create,
    sql,
    task,
    values,
)
from tests.workbench.final_execution_cases import final_e_runtime as runtime_fixture
from tests.workbench.final_execution_cases import final_execution_host as host_fixture
from tests.workbench.final_execution_support import changes, old_rows_preserved, restart_preserved
from tests.workbench.live_environment import write_json

final_e_runtime = runtime_fixture
final_execution_host = host_fixture


def test_real_http_rejections_and_current_zero_overlap_contract(final_execution_host):
    host = final_execution_host
    before = host.state()
    observations = []
    for label, patch, status, code in (
        ("unknown_machine", {"actual_machine_ref": "0" * 48}, 409, "constraint_conflict"),
        ("unknown_operator", {"actual_operator_ref": "0" * 48}, 409, "constraint_conflict"),
        ("future", {"actual_start": "2099-01-01T08:00:00", "actual_end": "2099-01-01T09:00:00"}, 422, "invalid_input"),
        ("reversed", {"actual_end": "2026-09-02T07:00:00"}, 422, "invalid_input"),
        ("hours_exceed_span", {"effective_processing_hours": 3}, 422, "invalid_input"),
        ("overreport", {"completed_quantity": 11}, 409, "constraint_conflict"),
    ):
        current = task(host)
        body = command(current["execution"]["write_context"], {**values(host), **patch})
        result = host.json(EXECUTION + "/tasks/" + current["task_ref"] + "/reports", body=body, status=status)
        assert result["committed"] is False and result["error"]["code"] == code
        assert host.state() == before
        observations.append({"case": label, "request": body, "response": result, "all_tables_unchanged": True})

    # These are observed ledger semantics, not acceptance of the conflicting prototype rejection labels.
    zero = values(host, 0, actual_end="2026-09-02T08:00:00", effective_processing_hours=0)
    _, zero_result = create(host, zero)
    _, positive_zero = create(host, values(host, 1, effective_processing_hours=0))
    _, overlapping = create(host, values(host, 1, effective_processing_hours=0.5))
    reports = task(host)["execution"]["reports"]
    assert len(reports) == 3
    assert reports[0]["completed_quantity"] == reports[0]["effective_processing_hours"] == 0
    assert reports[0]["actual_start"] == reports[0]["actual_end"]
    assert reports[1]["completed_quantity"] == 1 and reports[1]["effective_processing_hours"] == 0
    assert reports[1]["actual_start"] == reports[2]["actual_start"]
    assert reports[1]["actual_end"] == reports[2]["actual_end"]
    after = host.state()
    assert changes(before, after) == CREATE_TABLES
    old_rows_preserved(before, after, {"WorkbenchExecutionLedgerClock"})
    clock = before["WorkbenchExecutionLedgerClock"][0]
    assert after["WorkbenchExecutionLedgerClock"] == [{**clock, "revision": clock["revision"] + 6,
                                                       "next_report_no": clock["next_report_no"] + 3}]
    write_json(host.root / "rejection-contract-proof.json", {"rejections": observations,
        "observed_current_contract": {"zero_span_zero_values": zero_result, "positive_quantity_zero_hours": positive_zero,
            "overlapping_actual_intervals": overlapping}, "original_reports": reports,
        "prototype_rejection_equivalence": "requires_Main_contract_decision", "old_rows_preserved": True})


def test_full_main_failed_write_draft_pending_request_and_restart(final_execution_host):
    host = final_execution_host
    before = host.state()
    sql(host, "CREATE TRIGGER final_e_browser_fail BEFORE INSERT ON WorkbenchCommandReceipts "
              "BEGIN SELECT RAISE(ABORT,'final-e-real-ui-rollback'); END")
    with ThreadPoolExecutor(max_workers=1) as pool:
        browser = pool.submit(host.browser, "final_execution_rejections.cjs")
        deadline = time.monotonic() + 100
        while not (host.root / "rejection-restart-request.json").exists():
            if browser.done():
                browser.result()
                raise AssertionError("Browser ended before the real restart checkpoint")
            assert time.monotonic() < deadline, "Browser did not reach the restart checkpoint"
            time.sleep(.05)
        assert host.state() == before
        sql(host, "DROP TRIGGER final_e_browser_fail")
        host.stop()
        host.start(reuse=True)
        audit = restart_preserved(before, host.state())
        restarted = host.state()
        write_json(host.root / "rejection-restart-complete.json", {"url": host.ready["url"], "session": host.ready["session"]})
        browser.result(timeout=120)
    initial = json.loads((host.root / "final-rejections-initial.json").read_text(encoding="utf-8"))
    assert all(action["passed"] for action in initial["actions"]) and initial["gaps"] == []
    assert all(request["method"] == "GET" for request in initial["after_restart_requests"])
    assert host.state() == restarted
    write_json(host.root / "rejection-browser-proof.json", {"full_main": True, "initial": initial,
        "restart_audit": audit, "zero_business_writes": True,
        "original_request_preserved_without_resubmit": True})
