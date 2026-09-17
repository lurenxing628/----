"""An unadopted candidate creates a full draft; old admission then stays stale."""

import os

import pytest

from tests.workbench.final_planning_source_oracle import verify_source_only
from tests.workbench.live_environment import create_root, environment, write_json
from tests.workbench.test_final_planning_browser import host_phase, invoke, verify_build_inputs
from tests.workbench.test_live_browser import runtime_tools


@pytest.mark.parametrize("width,theme", [(1392, "light")])
def test_unadopted_candidate_source_and_stale_preview_preserve_formal(width, theme):
    node, browser, modules = runtime_tools()
    root = create_root(os.environ.get("FINAL_PLANNING_TEMP_PARENT"))
    env = environment(root)
    env.update(NODE_PATH=modules, WORKBENCH_BROWSER=browser, WORKBENCH_NODE=node,
               PYTHONPYCACHEPREFIX=str(root / "pycache"))
    print("FINAL_PLANNING_CANDIDATE_SOURCE " + str(root), flush=True)
    assert invoke(node, "final_planning_build.cjs", [str(root)], root, env, 180) == 0, str(root)
    host = host_phase(root, env, node, width, theme, "candidate-source")
    verify_build_inputs(root)
    assert "forced_kill" not in host and host["server_returncode"] == 0
    proof = host["isolation"]
    assert proof["stopped"] and proof["assets_unchanged"]
    assert proof["isolation_violations"] == proof["python_sources"]["changed"] == []
    assert host["browser_returncode"] == 0, str(root / "final_planning_candidate-source.json")
    result = verify_source_only(root, host)
    write_json(root / "final_planning_candidate-source_result.json", result)
    assert result["errors"] == [], result
