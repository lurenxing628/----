"""Real candidate workspace source, Chromium109 matrix, downloaded payload verification."""

import hashlib
import json
import os
import subprocess
import tempfile
import threading
from pathlib import Path

from werkzeug.serving import make_server

from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from tests.workbench.run_candidate_widgets_support import CandidateWidgetServer
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_run_candidate_exports import decode


def test_run_candidate_widgets_real_browser_and_downloads(candidate_case):
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-run-candidate-widgets-"))
    print("RUN_CANDIDATE_WIDGET_ARTIFACTS " + str(output), flush=True)
    backend = CandidateWidgetServer(candidate_case, output)
    server = make_server("127.0.0.1", 0, backend.app, threaded=True)
    assert server.server_port not in {63938, 51093, 56264, 52155, 51733}
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        backend.verify_baseline_route()
        with (output / "probe-output.log").open("w", encoding="utf-8") as log:
            result = subprocess.run([node, str(root / "tests/workbench/test_run_candidate_widgets.cjs"), str(output),
                                     f"http://127.0.0.1:{server.server_port}"], cwd=str(root),
                                    env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                                    stdout=log, stderr=subprocess.STDOUT, text=True, timeout=900)
    finally:
        server.shutdown()
        thread.join(timeout=15)
        server.server_close()
        proof = backend.proof()
        (output / "sqlite-proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    probe_output = (output / "probe-output.log").read_text(encoding="utf-8")
    assert result.returncode == 0, probe_output[-8000:] + "\n" + str(output)
    report = json.loads((output / "candidate-widgets.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.")
    assert not report["errors"] and not report["external"] and not report["dialogs"]
    assert len(report["variants"]) == 4 and all(row["passed"] for row in report["variants"])
    assert len(report["downloads"]) == 24
    assert len(report["capacity"]) == 12 and all(row["tasks"] == 5000 for row in report["capacity"])
    assert not any(row["path"].endswith("/baseline") for row in report["requests"])
    assert proof["source_data_retained"] and proof["read_only_http"] and proof["all_connections_isolated"]
    assert proof["schema_version"] == CURRENT_SCHEMA_VERSION
    assert proof["schema_contract_issues"] == []
    for item in report["sources"]:
        assert hashlib.sha256((root / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    for item in report["downloads"]:
        class Response:
            data = Path(item["path"]).read_bytes()
        headers, rows = decode(Response(), item["format"])
        assert len(rows) == item["row_count"]
        assert [row[headers.index("行编号")] for row in rows[:item["task_count"]]] == item["row_refs"]
        assert [row[headers.index("工序编号")] for row in rows[:item["task_count"]]] == item["operation_refs"]
        assert all(row[headers.index("候选方案编号")] == item["candidate_ref"] for row in rows)
        assert all(row[headers.index("排产编号")] == item["run_ref"] for row in rows)
        assert [row[headers.index("安排开始")] for row in rows[:item["task_count"]]] == item["starts"]
    print(probe_output, flush=True)
