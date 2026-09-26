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
    assert 0 < server.server_port == server.socket.getsockname()[1]
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
    assert len(report["prints"]) == 1
    print_run = report["prints"][0]
    assert print_run["variant"] == "1392-dark"
    assert print_run["kind"] == "chunked-candidate-tables-and-default-zoom-canvas"
    before, after = print_run["events"]
    assert [(row["event"], row["trusted"], row["theme"]) for row in (before, after)] == [
        ("beforeprint", True, "dark"),
        ("afterprint", True, "dark"),
    ]
    assert before["rows"] == before["uniqueRowRefs"] == 500
    assert before["chunks"] == 42 and before["maxChunkRows"] == 12
    assert before["zoom"] == after["zoom"] == "1×"
    assert before["lanes"] == before["expectedLanes"] == 10
    assert after["rows"] <= 16 and after["chunks"] == 0 and after["lanes"] < before["lanes"]
    assert after["rows"] == after["uniqueRowRefs"]
    assert abs(after["spaceWidth"] - after["canvasWidth"]) < 2
    assert print_run["media"]["uniqueRowRefs"] == 500
    assert all(0 < chunk["rows"] <= 12 and chunk["headers"] == 4 for chunk in print_run["media"]["chunks"])
    pdf = Path(print_run["path"]).read_bytes()
    assert pdf.startswith(b"%PDF-")
    assert hashlib.sha256(pdf).hexdigest() == print_run["sha256"]
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
