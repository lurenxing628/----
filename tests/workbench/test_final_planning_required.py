"""Locked missing planning branches and original-object read-view recovery."""

import os

import pytest

from tests.workbench.final_planning_oracle import read
from tests.workbench.live_environment import create_root, environment, write_json
from tests.workbench.test_final_planning_browser import host_phase, invoke, verify_build_inputs
from tests.workbench.test_live_browser import runtime_tools


@pytest.mark.parametrize("width,theme", [(1920, "light"), (1920, "dark"), (1392, "light"), (1392, "dark")])
@pytest.mark.parametrize("case", ["readonly", "stale"])
def test_required_planning_branches_on_real_persistent_inputs(width, theme, case):
    node, browser, modules = runtime_tools()
    root = create_root(os.environ.get("FINAL_PLANNING_TEMP_PARENT"))
    env = environment(root)
    env.update(NODE_PATH=modules, WORKBENCH_BROWSER=browser, WORKBENCH_NODE=node,
               PYTHONPYCACHEPREFIX=str(root / "pycache"), FINAL_PLANNING_REQUIRED_CASE=case)
    print("FINAL_PLANNING_REQUIRED_ARTIFACTS " + str(root), flush=True)
    assert invoke(node, "final_planning_build.cjs", [str(root)], root, env, 180) == 0, str(root)
    mode = "required-" + case
    result = host_phase(root, env, node, width, theme, mode)
    verify_build_inputs(root)
    assert "forced_kill" not in result and result["server_returncode"] == 0
    proof = result["isolation"]
    assert proof["stopped"] and proof["assets_unchanged"]
    assert proof["isolation_violations"] == proof["python_sources"]["changed"] == []
    assert "runtime_shutdown_joined" in proof["events"]
    assert result["browser_returncode"] == 0, str(root / ("final_planning_" + mode + ".json"))
    report = read(root / ("final_planning_" + mode + ".json"))
    expected = ({"WBP-RUN-007.no-result", "WBP-GANTT-002.conflict-track", "WBP-TRIAL-011.export-failure"}
                if case == "readonly" else {"WBP-TRIAL-007.stale-conflict"})
    assert {item["action_id"] for item in report["actions"]} == expected
    assert all(item["status"] == "passed" for item in report["actions"])
    covered = set(expected)
    if case == "readonly":
        session = root / "sessions" / result["ready"]["session"]
        before, after = read(session / "business-before.json"), read(session / "business-after.json")
        assert before == after, "Read-only required cases changed a persistent table"
        l5_expected = {"WBP-DELAY-004.conflicts", "WBP-TRIAL-003.mode", "WBP-TRIAL-003.baseline",
                       "WBP-TRIAL-003.only-changed", "WBP-TRIAL-003.search",
                       "WBP-TRIAL-010.tabs", "WBP-TRIAL-010.keyboard"}
        l5_actions = report["required_l5_actions"]
        assert len(l5_actions) == len(l5_expected)
        assert {item["action_id"] for item in l5_actions} == l5_expected
        assert all(item["status"] == "passed" and item["gates"]["P"] == "passed" for item in l5_actions)
        assert next(item for item in l5_actions if item["action_id"] == "WBP-DELAY-004.conflicts")["gates"]["K"] == "passed"
        witness = report["l5_readonly_witness"]
        assert witness["only_get"] and witness["all_tables_and_schema_equal"]
        assert witness["before"]["sha256"] == witness["after"]["sha256"]
        assert witness["before"]["tables"] == witness["after"]["tables"]
        view = report["trial_view_recovery"]
        assert view["original_scenario_unchanged"]
        assert view["scenario_ref"] == report["native_export_failure"]["scenario_ref"]
        assert view["f5"]["controls"] == view["selected"]["controls"] == view["same_url_new_page"]["controls"]
        assert set(view["selected"]["controls"]) == {"mode", "baseline", "only_changed", "query", "result_tab"}
        assert report["delay_conflicts"]["f5_same_projection_and_rows"]
        covered.update(l5_expected)
    else:
        rejection = report["scenario_stale"]
        assert rejection["before"]["sha256"] == rejection["after"]["sha256"] == rejection["final"]["sha256"]
        assert rejection["f5_original_request_retained"] and not rejection["repreview_can_adopt"]
    write_json(root / "final_planning_required_result.json", {"root": str(root), "case": case,
        "width": width, "theme": theme, "covered_actions": sorted(covered), "errors": []})
