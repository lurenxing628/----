"""Actual zero-duration DTO contracts/layout; no string-only assertions."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.workbench.point_frontend_support import app_for, seed, serve
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401

HERE = Path(__file__).resolve().parent
MODULES = "/Users/lurenxing/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"
BROWSER = "/tmp/aps-chromium109-assessment/runtime/chrome-mac/Chromium.app/Contents/MacOS/Chromium"


def invoke(script, value, timeout=90):
    result = subprocess.run([shutil.which("node"), str(HERE / script)], input=json.dumps(value),
                            text=True, capture_output=True, timeout=timeout,
                            env=dict(os.environ, NODE_PATH=MODULES, WORKBENCH_BROWSER=BROWSER))
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


@pytest.mark.parametrize("mixed", [False, True], ids=["all-points", "mixed-dense"])
def test_real_point_contracts_layout_and_chrome109(trial_case, tmp_path, mixed):
    identity = seed(trial_case, mixed)
    output = tmp_path / "ee-point-browser"
    invoke("point_browser_build.cjs", {"output": str(output)})
    app = app_for(trial_case, output)
    client = app.test_client()
    fixtures = {}
    paths = {"candidate": "/api/workbench/v1/scheduling/candidates/" + identity["candidate_ref"] + "/workspace",
             "initial": "/api/workbench/v1/plans/" + identity["initial_plan_ref"] + "/workspace",
             "plan": "/api/workbench/v1/plans/" + identity["plan_ref"] + "/workspace",
             "trial": "/api/workbench/v1/trial/drafts/" + identity["draft_ref"],
             "saved": "/api/workbench/v1/trial/scenarios/" + identity["scenario_ref"]}
    for key, path in paths.items():
        response = client.get(path)
        assert response.status_code == 200, response.get_data(as_text=True)
        fixtures[key] = response.get_json()
    assert all(row["start"] == row["end"] for row in fixtures["plan"]["data"]["tasks"] if row.get("event_kind") == "point")
    point = next(row for row in fixtures["plan"]["data"]["tasks"] if row.get("event_kind") == "point")
    for kind in ("plan", "candidate", "initial"):
        for label, low, high in [("left", point["start"], "2026-09-09T08:01:00"),
                                 ("right", "2026-09-09T07:00:00", point["start"])]:
            query = {"range_start": low, "range_end": high}
            response = client.get(paths[kind], query_string=query)
            assert response.status_code == 200, response.get_data(as_text=True)
            fixtures[kind + "_" + label] = {"payload": response.get_json(), "scope": query}
    end = fixtures["plan"]["data"]["plan_span"]["end"]
    query = {"range_start": "2026-09-09T07:00:00", "range_end": end}
    response = client.get(paths["plan"], query_string=query)
    assert response.status_code == 200, response.get_data(as_text=True)
    fixtures["plan_until_last"] = {"payload": response.get_json(), "scope": query}
    evidence = json.loads(json.dumps(fixtures))
    for kind in ("trial", "saved"):
        if evidence[kind]["data"].get("write_context"):
            evidence[kind]["data"]["write_context"]["write_token"] = "<redacted transient test token>"
    (output / "dto-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(invoke("point_frontend_probe.cjs", {"fixtures": fixtures, "identity": identity}), flush=True)
    with serve(app) as base:
        print(invoke("point_browser_probe.cjs", {"base": base, "paths": paths, "identity": identity, "output": str(output)}, timeout=180), flush=True)
    report = json.loads((output / "browser-result.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.") and report["errors"] == [] and report["external"] == []
    assert len(report["screenshots"]) == 12
    print("EE_POINT_EVIDENCE " + str(output), flush=True)
