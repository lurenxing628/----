"""FG: current-source plan actions, real adoption DTOs, read-only Chrome 109."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.workbench.plan_adoption_baseline_support import adopt_candidate, two_versions
from tests.workbench.point_downstream_support import app_for, read, serve
from tests.workbench.run_candidate_support import corrupt_update, retained
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def invoke(script, value):
    node, browser, modules = runtime_tools()
    result = subprocess.run([node, str(HERE / script)], input=json.dumps(value),
        text=True, capture_output=True, timeout=180,
        env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser))
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture(scope="module")
def fg_assets(tmp_path_factory):
    output = tmp_path_factory.mktemp("fg-plan-actions-assets")
    invoke("point_downstream_browser_build_support.cjs", {"output": str(output)})
    return output


@pytest.mark.parametrize("source", ["candidate", "trial"])
def test_fg_plan_workspace_readonly_actions(trial_case, fg_assets, tmp_path, source):
    case = trial_case
    historical, missing = two_versions(case, source)
    current = adopt_candidate(case, "third")
    table, column = (("WorkbenchRunJobs", "run_ref") if source == "candidate"
                     else ("WorkbenchTrialScenarios", "scenario_ref"))
    case.conn.execute("PRAGMA foreign_keys=OFF")
    corrupt_update(case.conn, table, "DELETE FROM " + table + " WHERE " + column + "=?",
                   (missing["source_" + column],))
    app = app_for(case, fg_assets)
    client = app.test_client()
    cases = [{"name": "initial-no-plan"}]
    with retained(case.conn):
        for name, plan, identity in [("current", current, "当前正式"),
                                     ("historical", historical, "历史正式"),
                                     ("source-missing", missing, "历史正式")]:
            payload = read(client, "/api/workbench/v1/plans/" + plan["plan_ref"] + "/workspace")
            assert payload["data"]["plan"]["capabilities"]["adopt"] is False
            if name == "source-missing":
                assert payload["data"]["projections"]["baseline"]["reason_code"] == "adoption_source_archived"
            cases.append({"name": name, "plan_ref": plan["plan_ref"], "identity": identity,
                          "payload": payload})
        with serve(app) as base:
            assert not base.endswith(":53144")
            invoke("fg_plan_workspace_actions_probe.cjs", {"base": base, "entry": "/",
                "cases": cases, "output": str(tmp_path)})
    report = json.loads((tmp_path / "fg-plan-actions-result.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.")
    assert len(report["cases"]) == 32
    assert report["writes"] == report["errors"] == report["external"] == []
    assert report["global_build"] is False
    assert report["source_sha256"] == hashlib.sha256(
        (ROOT / "frontend/workbench/app/PlanWorkspace.jsx").read_bytes()).hexdigest()
    for filename in report["screenshots"]:
        assert Path(filename).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    print("FG_PLAN_ACTIONS_EVIDENCE " + str(tmp_path), flush=True)
