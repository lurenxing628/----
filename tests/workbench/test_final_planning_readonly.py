"""Real main-entry invalid identities and incomplete original-plan delivery risk."""

import os

import pytest

from tests.workbench.final_planning_oracle import read
from tests.workbench.live_environment import create_root, environment, write_json
from tests.workbench.test_final_planning_browser import host_phase, invoke, verify_build_inputs
from tests.workbench.test_live_browser import runtime_tools


@pytest.mark.parametrize("width,theme", [(1920, "dark")])
def test_full_entry_invalid_plan_and_incomplete_batch_are_readonly(width, theme):
    node, browser, modules = runtime_tools()
    root = create_root(os.environ.get("FINAL_PLANNING_TEMP_PARENT"))
    env = environment(root)
    env.update(NODE_PATH=modules, WORKBENCH_BROWSER=browser, WORKBENCH_NODE=node,
               PYTHONPYCACHEPREFIX=str(root / "pycache"))
    print("FINAL_PLANNING_READONLY_ARTIFACTS " + str(root), flush=True)
    assert invoke(node, "final_planning_build.cjs", [str(root)], root, env, 180) == 0, str(root)
    result = host_phase(root, env, node, width, theme, "readonly")
    verify_build_inputs(root)
    assert "forced_kill" not in result and result["server_returncode"] == 0
    proof = result["isolation"]
    assert proof["stopped"] and proof["assets_unchanged"]
    assert proof["isolation_violations"] == proof["python_sources"]["changed"] == []
    session = root / "sessions" / result["ready"]["session"]
    before, after = read(session / "business-before.json"), read(session / "business-after.json")
    assert before == after, "Read-only edge cases changed business data"
    assert result["browser_returncode"] == 0, str(root / "final_planning_readonly.json")
    write_json(root / "final_planning_readonly_result.json", {"root": str(root), "width": width, "theme": theme,
        "tables_unchanged": len(before), "source_build": read(root / "piece_main_build.json"), "errors": []})
