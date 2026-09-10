"""The shared navigation restores actual domain state without persisting commands."""

import json

import pytest

from tests.workbench.final_execution_cases import final_e_runtime as final_e_runtime
from tests.workbench.final_execution_support import serving
from tests.workbench.live_environment import write_json


@pytest.mark.parametrize("profile,view", [("execution", "field"), ("execution", "fieldgantt"),
                                         ("reports", "reports"), ("calibration", "calib")])
def test_full_main_sidebar_refresh_back_forward_readonly_context(final_e_runtime, profile, view):
    parent, built, runtime = final_e_runtime
    with serving(parent, built, runtime, profile) as host:
        print("FINAL_HISTORY_ROOT " + str(host.root), flush=True)
        before = host.state()
        host.browser("final_execution_history.cjs", view)
        report = json.loads((host.root / ("final-history-" + view + ".json")).read_text(encoding="utf-8"))
        assert len(report["actions"]) == len(report["restored"]) == 4
        assert all(row["passed"] for row in report["actions"])
        assert report["page_errors"] == report["external_requests"] == report["console_errors"] == report["gaps"] == []
        assert all(row["method"] == "GET" for row in report["requests"])
        assert host.state() == before
        write_json(host.root / "final-history-proof.json", {"view": view, "strict_changed_tables": [],
            "original_rows_preserved": True, "readonly_actions": report["actions"], "baseline": report["baseline"],
            "restored": report["restored"], "screenshots": report["screenshots"]})
