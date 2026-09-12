"""Narrow viewport details remain visible, keyboard reachable and source bound."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

from tests.workbench.dashboard_widgets_support import serve
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from tests.workbench.test_live_browser import runtime_tools

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def test_dashboard_detail_narrow_viewports(candidate_case, tmp_path, monkeypatch):
    output = Path(os.environ.get("DASHBOARD_DETAIL_UI_OUTPUT", str(tmp_path / "details"))).resolve()
    assert output != ROOT and ROOT not in output.parents
    output.mkdir(parents=True, exist_ok=True)
    node, browser, modules = runtime_tools()
    with serve(candidate_case, output, monkeypatch) as config:
        run = subprocess.run([node, str(HERE / "dashboard_widgets_probe.cjs"), str(output)],
                             input=json.dumps(config), text=True, capture_output=True, timeout=180,
                             env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser,
                                      WORKBENCH_DASHBOARD_DETAIL_ONLY="1"))
    assert run.returncode == 0, run.stdout + run.stderr + "\n" + str(output)
    report = json.loads((output / "dashboard-ui.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.")
    assert len(report["ui_refinement"]) == 4
    assert report["errors"] == report["external"] == []
    assert all(row["focus_returned"] for row in report["ui_refinement"])
    for source in report["sources"]:
        assert hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() == source["sha256"], source["path"]
    server = json.loads((output / "dashboard-server.json").read_text(encoding="utf-8"))
    assert all(row["method"] == "GET" and row["changed_tables"] == [] for row in server["journal"])
