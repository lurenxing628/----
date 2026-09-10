"""Actual Chrome109 consumes DTOs from real temporary adoptions, without a live preview."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.workbench.plan_read_support import make_api
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_plan_adoption_baseline_support import read, two_versions
from tests.workbench.test_plan_adoption_baseline_support import trial_case as trial_case  # noqa: F401
from tests.workbench.test_plan_transport import workspace_fixture

HERE = Path(__file__).resolve().parent


@pytest.mark.parametrize("source", ["candidate", "trial"])
def test_real_adoption_dto_in_chrome109(trial_case, tmp_path, source):
    _, second = two_versions(trial_case, source)
    api = make_api(trial_case.path)
    full = workspace_fixture(api, source + " full", second["plan_ref"])
    fixtures = [full]
    if source == "trial":
        before = read(trial_case, second)[0]["items"][0]["before"]
        fixtures.append(workspace_fixture(api, "before-only range", second["plan_ref"],
                        range_start=before["start"], range_end=before["end"]))
    node, browser, modules = runtime_tools()
    directory = tmp_path / "da-browser"
    result = subprocess.run([node, str(HERE / "test_plan_adoption_baseline_probe.cjs"), str(directory)],
        input=json.dumps({"fixtures": fixtures}), capture_output=True, text=True, timeout=90,
        env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser))
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.") and report["errors"] == [] and report["external"] == []
    assert report["fixtures"] == len(fixtures) and report["production"] is False
    for row in report["sources"]:
        assert hashlib.sha256((HERE.parents[1] / row["path"]).read_bytes()).hexdigest() == row["sha256"]
    assert len(report["screenshots"]) == len(fixtures) * 2
    print("DA_BROWSER_EVIDENCE " + str(directory))
