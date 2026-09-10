"""Run current BK source against isolated real Flask/SQLite and actual Chromium 109."""

import hashlib
import json
import os
import subprocess
import tempfile
import threading
from pathlib import Path

from werkzeug.serving import make_server

from tests.workbench.run_job_widgets_support import WidgetServer
from tests.workbench.run_jobs_support import job_case as _job_case  # noqa: F401
from tests.workbench.test_live_browser import runtime_tools


def test_run_job_widgets(job_case):
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-run-job-widgets-"))
    backend = WidgetServer(job_case, output)
    server = make_server("127.0.0.1", 0, backend.app, threaded=True)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    print("RUN_JOB_WIDGET_ARTIFACTS " + str(output), flush=True)
    try:
        result = subprocess.run([node, str(root / "tests/workbench/run_job_widgets_probe.cjs"), str(output),
                                 f"http://127.0.0.1:{server.server_port}"], cwd=str(root),
                                env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                                capture_output=True, text=True, timeout=900)
    finally:
        backend.join()
        server.shutdown()
        thread.join(timeout=15)
        server.server_close()
        backend.proof()
        (output / "sqlite-proof.json").write_text(json.dumps({"databases": backend.databases, "proofs": backend.proofs,
            "worker_errors": backend.worker_errors, "journal": backend.journal}, ensure_ascii=False, indent=2), encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "run-job-widgets.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.")
    assert not report["errors"] and not report["external"] and not report["dialogs"]
    assert len(report["variants"]) == 4 and all(row["passed"] for row in report["variants"])
    assert report["capacity"]["task_count"] == 5000 and report["capacity"]["candidate_rows"] == 4
    assert all(proof["business_facts_unchanged"] for proof in backend.proofs)
    assert any(proof["candidate_tasks"] == 20000 for proof in backend.proofs)
    for item in report["sources"]:
        assert hashlib.sha256((root / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    print(result.stdout, flush=True)
