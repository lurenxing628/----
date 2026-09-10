"""Current source + Chrome109 + real temporary Flask/SQLite, no global build."""

import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
import threading
from pathlib import Path

from werkzeug.serving import make_server

from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_preflight_support import create_app, seed, snapshot


def test_preflight_real_browser():
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-preflight-browser-"))
    conn = sqlite3.connect(str(output / "preflight.sqlite"), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript((root / "schema.sql").read_text(encoding="utf-8"))
    seed(conn, count=45)
    before = snapshot(conn)
    changes = conn.total_changes
    app = create_app(conn)
    server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run([node, str(root / "tests/workbench/preflight_browser_probe.cjs"), str(output),
                                 f"http://127.0.0.1:{server.server_port}"], cwd=str(root),
                                env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                                capture_output=True, text=True, timeout=240)
    finally:
        server.shutdown()
        thread.join(timeout=10)
        server.server_close()
        unchanged = snapshot(conn) == before and conn.total_changes == changes
        (output / "sqlite-proof.json").write_text(json.dumps({"all_tables_unchanged": unchanged,
            "tables": sorted(before), "before_total_changes": changes, "after_total_changes": conn.total_changes,
            "database": str(output / "preflight.sqlite")}), encoding="utf-8")
        conn.close()
    assert unchanged, str(output)
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "preflight-browser.json").read_text(encoding="utf-8"))
    assert report["errors"] == [] and report["external"] == []
    assert len(report["variants"]) == 4 and all(row["passed"] for row in report["variants"])
    assert report["browser"].startswith("109.")
    for source in report["sources"]:
        assert hashlib.sha256((root / source["path"]).read_bytes()).hexdigest() == source["sha256"]
    print("PREFLIGHT_BROWSER_ARTIFACTS " + str(output))
