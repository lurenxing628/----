"""Pending BZ hook: source-only Chromium109 matrix, isolated Flask and SQLite."""

import ast
import hashlib
import json
import os
import subprocess
import tempfile
import threading
from pathlib import Path

from werkzeug.serving import make_server

from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION
from tests.workbench.run_baseline_widgets_support import BaselineWidgetServer
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_run_candidate_support import candidate_case as _candidate_case  # noqa: F401


def test_run_baseline_widgets_real_browser(candidate_case):
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-run-baseline-widgets-"))
    print("RUN_BASELINE_WIDGET_ARTIFACTS " + str(output), flush=True)
    backend = BaselineWidgetServer(candidate_case, output)
    server = make_server("127.0.0.1", 0, backend.app, threaded=True)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        result = subprocess.run([node, str(root / "tests/workbench/run_baseline_widgets_probe.cjs"), str(output),
                                 f"http://127.0.0.1:{server.server_port:d}"], cwd=str(root),
                                env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                                capture_output=True, text=True, timeout=900)
    finally:
        server.shutdown()
        thread.join(timeout=15)
        server.server_close()
        proof = backend.proof()
        (output / "sqlite-proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "probe-output.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, (result.stdout + result.stderr)[-8000:] + "\n" + str(output)
    report = json.loads((output / "baseline-widgets.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.")
    assert not report["errors"] and not report["external"] and not report["dialogs"]
    assert len(report["variants"]) == 4 and all(r["passed"] for r in report["variants"])
    assert proof["source_data_retained"] and proof["all_connections_isolated"] and proof["read_only_http"]
    assert all(r["schema_version"] == CURRENT_SCHEMA_VERSION and r["schema_contract_issues"] == []
               for r in proof["databases"])
    for item in report["sources"]:
        assert hashlib.sha256((root / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    for name in ("test_run_baseline_widgets.py", "run_baseline_widgets_support.py"):
        ast.parse((root / "tests/workbench" / name).read_text(encoding="utf-8"), feature_version=(3, 8))
    print(result.stdout, flush=True)
