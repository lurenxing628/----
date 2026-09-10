"""BT history source-only Chromium 109 matrix, strict DTO and read-only proof."""

import ast
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
import threading
from pathlib import Path

from werkzeug.serving import make_server

from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION
from tests.workbench.run_history_widgets_support import HistoryWidgetServer
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_run_history_support import history_case as _history_case  # noqa: F401


def test_run_history_widgets_chromium109_four_combinations(history_case, monkeypatch):
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-run-history-widgets-")).resolve()
    print("RUN_HISTORY_WIDGET_ARTIFACTS " + str(output), flush=True)
    original, connections = sqlite3.connect, []

    def guard(path, *args, **kwargs):
        if str(path) == ":memory:":
            connections.append(":memory:")
            return original(path, *args, **kwargs)
        actual = Path(path).resolve()
        assert actual == history_case.path.resolve() or actual.parent == output, "Nonfixture SQLite access"
        connections.append(str(actual))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guard)
    backend = HistoryWidgetServer(history_case, output)
    server = make_server("127.0.0.1", 0, backend.app, threaded=True)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        result = subprocess.run([node, str(root / "tests/workbench/run_history_widgets_probe.cjs"), str(output),
                                 f"http://127.0.0.1:{server.server_port}"], cwd=str(root),
                                env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                                capture_output=True, text=True, timeout=600)
    finally:
        server.shutdown()
        thread.join(timeout=15)
        server.server_close()
        proof = backend.proof()
        proof["guarded_connections"] = connections
        (output / "sqlite-proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "probe-output.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, (result.stdout + result.stderr)[-9000:] + "\n" + str(output)
    report = json.loads((output / "history-widgets.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.")
    assert not report["errors"] and not report["external"] and not report["dialogs"] and not report["downloads"]
    assert len(report["directEntrypoints"]) == 4
    for entry in report["directEntrypoints"]:
        assert entry["host"] == "direct-component-without-renderers" and entry["requests_after_clicks"] == 0
        assert [row["name"] for row in entry["blocked"]] == ["采用方案", "试调"]
        assert all(row["disabled"] and "入口未接入" in row["reason"] for row in entry["blocked"])
    assert len(report["variants"]) == 4 and all(row["passed"] for row in report["variants"])
    assert {(r["width"], r["height"]) for r in report["variants"]} == {(1920, 1080), (1392, 924)}
    assert proof["schema_version"] == CURRENT_SCHEMA_VERSION and proof["source_data_retained"]
    assert proof["schema_contract_issues"] == []
    assert proof["read_only_http"] and proof["read_only_sql"] and proof["all_connections_isolated"]
    assert len([row for row in proof["journal"] if row["path"].endswith("/baseline") and row["status"] == 200]) == 4
    assert {"RunBaselineAPI.js", "RunBaselineModel.js", "RunBaselineControls.jsx"}.issubset(
        {Path(item["path"]).name for item in report["sources"]})
    for item in report["sources"]:
        assert hashlib.sha256((root / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    for name in ("test_run_history_widgets.py", "run_history_widgets_support.py"):
        ast.parse((root / "tests/workbench" / name).read_text(encoding="utf-8"), feature_version=8)
    print(result.stdout, flush=True)
