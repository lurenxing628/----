"""Real full-entry regression for the independently reproduced preflight return loss."""

import os

import pytest

from tests.workbench.final_planning_oracle import read
from tests.workbench.live_environment import create_root, environment, write_json
from tests.workbench.test_final_planning_browser import host_phase, invoke, verify_build_inputs
from tests.workbench.test_live_browser import runtime_tools


@pytest.mark.parametrize("width,theme", [(1920, "light"), (1920, "dark"), (1392, "light"), (1392, "dark")])
def test_full_entry_preflight_return_keeps_selection_and_dates(width, theme):
    node, browser, modules = runtime_tools()
    root = create_root(os.environ.get("FINAL_PLANNING_TEMP_PARENT"))
    env = environment(root)
    env.update(NODE_PATH=modules, WORKBENCH_BROWSER=browser, WORKBENCH_NODE=node,
               PYTHONPYCACHEPREFIX=str(root / "pycache"))
    print("FINAL_PLANNING_PREFLIGHT_ARTIFACTS " + str(root), flush=True)
    assert invoke(node, "final_planning_build.cjs", [str(root)], root, env, 180) == 0, str(root)
    result = host_phase(root, env, node, width, theme, "preflight")
    verify_build_inputs(root)
    assert "forced_kill" not in result and result["server_returncode"] == 0
    assert result["isolation"]["stopped"] and result["isolation"]["assets_unchanged"]
    assert result["isolation"]["isolation_violations"] == result["isolation"]["python_sources"]["changed"] == []
    session = root / "sessions" / result["ready"]["session"]
    before, after = read(session / "business-before.json"), read(session / "business-after.json")
    assert before == after, "Preflight navigation changed business data"
    assert result["browser_returncode"] == 0, str(root / "final_planning_preflight.json")
    write_json(root / "final_planning_preflight_result.json", {"root": str(root), "width": width, "theme": theme,
        "tables_unchanged": len(before), "source_build": read(root / "piece_main_build.json"), "errors": []})
