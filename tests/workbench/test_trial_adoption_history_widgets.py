"""Actual main.jsx, CQ/SQLite and browser navigation at both desktop sizes."""

import hashlib
import json
import os
import subprocess
import tempfile
import threading
from pathlib import Path

from werkzeug.serving import make_server

from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.trial_adoption_history_widgets_support import TrialAdoptionHistoryWidgetServer
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401
from web.routes.workbench.pages import VIEW_TITLES


def test_trial_adoption_history_real_main_browser(trial_case):
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-db-adoption-history-"))
    print("DB_ADOPTION_HISTORY_ARTIFACTS " + str(output), flush=True)
    (output / "boot-fixture.json").write_text(json.dumps({
        "schema_version": 1, "view": "trial", "entry_url": "/",
        "trial_url": "/trial", "titles": VIEW_TITLES,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    backend = TrialAdoptionHistoryWidgetServer(trial_case, output)
    server = make_server("127.0.0.1", 0, backend.app, threaded=True)
    assert server.server_port not in (50852, 57734)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        result = subprocess.run([node, str(root / "tests/workbench/trial_adoption_history_widgets_probe.cjs"), str(output),
                                 "http://127.0.0.1:" + str(server.server_port)], cwd=str(root),
                                env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                                capture_output=True, text=True, timeout=360)
    finally:
        backend.release.set()
        server.shutdown()
        thread.join(timeout=15)
        server.server_close()
        backend.close()
        proof = backend.proof()
        (output / "sqlite-proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "probe-output.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, (result.stdout + result.stderr)[-10000:] + "\n" + str(output)
    report = json.loads((output / "history-widgets.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.")
    assert len(report["variants"]) == 4
    assert not report["errors"] and not report["external"]
    assert proof["all_connections_isolated"] and not proof["business_results_mocked"]
    assert all(row["old_rows_and_types_retained"] and row["old_execution_exactly_retained"] for row in proof["databases"])
    history_requests = [row for row in proof["journal"] if row["path"].endswith("/adoption-history")]
    assert history_requests and all(row["method"] == "GET" for row in history_requests)
    for item in report["sources"]:
        assert hashlib.sha256((root / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    print(json.dumps({"artifacts": str(output), "checks": report["checks"], "variants": report["variants"]}), flush=True)
