"""BY presentation: current full shell and schema, real fixture routes, Chrome109."""

import ast
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
import threading
from pathlib import Path

from flask import Blueprint
from werkzeug.serving import make_server

from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_run_candidate_exports import decode
from tests.workbench.test_run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from tests.workbench.test_run_candidate_widgets_support import CandidateWidgetServer
from web.routes.workbench.pages import VIEW_TITLES
from web.routes.workbench.scheduling_jobs import register_scheduling_job_routes


def test_run_presentation_chrome109_real_fixture(candidate_case, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-run-presentation-by-")).resolve()
    print("RUN_PRESENTATION_ARTIFACTS " + str(output), flush=True)
    (output / "boot-fixture.json").write_text(json.dumps({
        "schema_version": 1, "view": "analysis", "entry_url": "/workbench",
        "trial_url": "/workbench/trial", "titles": VIEW_TITLES,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    node, browser, modules = runtime_tools()
    original, connections = sqlite3.connect, []

    def guard(path, *args, **kwargs):
        if str(path) != ":memory:":
            actual = Path(path).resolve()
            assert actual == candidate_case.path.resolve() or actual.parent == output, "Nonfixture SQLite access"
        connections.append(str(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guard)
    backend = CandidateWidgetServer(candidate_case, output)
    bp = Blueprint("by_run_records", __name__)
    register_scheduling_job_routes(bp)
    backend.app.register_blueprint(bp)
    server = make_server("127.0.0.1", 0, backend.app, threaded=True)
    assert server.server_port not in {63938, 51093, 56264, 52155, 51733}
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        backend.verify_baseline_route()
        with (output / "probe-output.log").open("w", encoding="utf-8") as log:
            result = subprocess.run([node, str(root / "tests/workbench/run_presentation_probe.cjs"), str(output),
                                     f"http://127.0.0.1:{server.server_port}"], cwd=str(root),
                                    env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                                    stdout=log, stderr=subprocess.STDOUT, text=True, timeout=900)
    finally:
        server.shutdown()
        thread.join(timeout=15)
        server.server_close()
        proof = backend.proof()
        proof["guarded_connections"] = connections
        (output / "sqlite-proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    probe_output = (output / "probe-output.log").read_text(encoding="utf-8")
    assert result.returncode == 0, probe_output[-9000:] + "\n" + str(output)
    report = json.loads((output / "presentation.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.")
    assert len(report["variants"]) == 4 and all(row["passed"] for row in report["variants"])
    assert {(r["width"], r["height"]) for r in report["variants"]} == {(1920, 1080), (1392, 924)}
    assert len(report["downloads"]) == 20
    assert sum(row["task_count"] == 5000 for row in report["downloads"]) == 8
    assert not any(row["path"].endswith("/baseline") for row in report["requests"])
    assert not report["errors"] and not report["external"] and not report["dialogs"]
    assert not [row for row in report["console"] if row["type"] == "error"]
    assert not [row for row in report["responses"] if row["status"] >= 400]
    assert len(report["hostEntrypoints"]) == 4
    assert all(row["host"] == "full-current-shell" and row["enabled"] and not row["writes_exercised"]
               and row["adoption"] == "正式采用" and row["trial"] == "试调" for row in report["hostEntrypoints"])
    assert proof["source_data_retained"] and proof["read_only_http"] and proof["all_connections_isolated"]
    assert proof["schema_version"] == CURRENT_SCHEMA_VERSION
    assert proof["schema_contract_issues"] == []
    assert report["compile"]["global_build"] is False and report["compile"]["full_current_shell"] is True
    for item in report["sources"]:
        if item["path"].endswith(("RunCandidateControls.jsx", "RunCandidateWorkspace.jsx", "RunJobControls.jsx", "RunHistoryControls.jsx")):
            assert hashlib.sha256((root / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    for item in report["downloads"]:
        class Response:
            data = Path(item["path"]).read_bytes()
        headers, rows = decode(Response(), item["format"])
        assert len(rows) == item["row_count"]
        assert [r[headers.index("行引用")] for r in rows[:item["task_count"]]] == item["row_refs"]
        assert [r[headers.index("工序引用")] for r in rows] == item["operation_refs"]
        assert all(r[headers.index("候选引用")] == item["candidate_ref"] for r in rows)
        assert all(r[headers.index("运行引用")] == item["run_ref"] for r in rows)
        assert [r[headers.index("安排开始")] for r in rows[:item["task_count"]]] == item["starts"]
    ast.parse(Path(__file__).read_text(encoding="utf-8"), feature_version=8)
    print(probe_output, flush=True)
