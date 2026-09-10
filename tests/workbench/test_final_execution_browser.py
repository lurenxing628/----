"""Real full-main actions, local identity history and physical host restarts."""

import json

import pytest

from tests.workbench.final_execution_artifacts import verify_downloads
from tests.workbench.final_execution_cases import ADOPT_TABLES, CREATE_TABLES
from tests.workbench.final_execution_cases import final_e_runtime as final_e_runtime
from tests.workbench.final_execution_support import changes, old_rows_preserved, restart_preserved, serving
from tests.workbench.live_environment import write_json


@pytest.mark.parametrize("profile,kind", [("execution", "field"), ("calibration", "calibration")])
def test_complete_main_actions_and_real_restart(final_e_runtime, profile, kind):
    parent, built, runtime = final_e_runtime
    with serving(parent, built, runtime, profile) as host:
        print("FINAL_BROWSER_ROOT " + str(host.root), flush=True)
        before = host.state()
        script = "final_execution_" + kind + ".cjs"
        host.browser(script)
        report = json.loads((host.root / ("final-" + kind + "-initial.json")).read_text(encoding="utf-8"))
        assert all(row["passed"] for row in report["actions"])
        assert report["page_errors"] == report["external_requests"] == []
        expected_console = [] if kind == "field" else ["Failed to load resource: the server responded with a status of 409 (CONFLICT)"]
        assert report["console_errors"] == expected_console
        assert all(row["method"] == "GET" and row["failure"] == {"errorText": "net::ERR_ABORTED"} for row in report["failed_requests"])
        after = host.state()
        expected = CREATE_TABLES if profile == "execution" else ADOPT_TABLES
        assert changes(before, after) == expected
        old_rows_preserved(before, after, {"WorkbenchExecutionLedgerClock"} if profile == "execution" else {"PartOperations", "WorkbenchEntityRefs"})
        if profile == "execution":
            assert len(after["WorkbenchProductionReports"]) == len(before["WorkbenchProductionReports"]) + 4
            assert len(after["WorkbenchProductionReportRevisions"]) == len(before["WorkbenchProductionReportRevisions"]) + 6
        host.stop()
        artifact_proof = verify_downloads(host.root, report)
        host.start(reuse=True)
        restarted_state = host.state()
        restart_audit = restart_preserved(after, restarted_state)
        host.browser(script, "restart")
        restarted = json.loads((host.root / ("final-" + kind + "-restart.json")).read_text(encoding="utf-8"))
        assert all(row["passed"] for row in restarted["actions"])
        assert host.state() == restarted_state
        if kind == "calibration":
            assert restarted["saved"] == report["saved"]
            saved = report["saved"]
            receipt = host.json("/api/workbench/v1/calibration/" + saved["baseline"]["template_operation_ref"] + "/adopt/receipts/" + saved["request_key"])
            assert receipt["receipt_ref"] == report["receipt"]["receipt_ref"]
            assert receipt["data"] == report["receipt"]["data"]
        write_json(host.root / "final-browser-proof.json", {"profile": profile, "strict_changed_tables": sorted(expected),
            "old_rows_preserved": True, "restart_audit": restart_audit, "initial_actions": report["actions"],
            "restart_actions": restarted["actions"], "gaps": report["gaps"] + restarted["gaps"],
            "artifact_checks": artifact_proof,
            "screenshots": report["screenshots"] + restarted["screenshots"]})
        assert report["gaps"] == [], report["gaps"]
