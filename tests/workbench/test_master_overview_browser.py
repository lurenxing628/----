"""Independent mock HTTP browser; fixture SQLite never serves live requests."""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from core.services.workbench.master_overview import MasterOverviewService
from tests.workbench.master_overview_support import ROOT, seed

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_live_browser import runtime_tools


def make_fixture(output):
    with sqlite3.connect(str(output / "fixture.sqlite")) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
        seed(conn)
        reader = MasterOverviewService(conn)
        with reader.read_snapshot():
            value = {"entities": reader.entities, "issues": reader.issues, "overview": reader.overview()}
    (output / "fixture.json").write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_master_overview_browser(output=None):
    node, browser, modules = runtime_tools()
    artifacts = Path(output or tempfile.mkdtemp(prefix="aps-master-overview-u-"))
    artifacts.mkdir(parents=True, exist_ok=True)
    print("MASTER_OVERVIEW_ARTIFACTS " + str(artifacts), flush=True)
    make_fixture(artifacts)
    result = subprocess.run([node, str(HERE / "test_master_overview_browser_probe.cjs"), str(artifacts)],
                            env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                            capture_output=True, text=True, timeout=360)
    path = artifacts / "master-overview-result.json"
    report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + report.get("error", "") + "\n" + str(artifacts)
    assert report["browser"].startswith("109.")
    assert report["summary"]["failed"] == 0
    assert report["summary"]["cases"] >= 28
    assert report["summary"]["screenshots"] >= 12
    assert report["global_build"] is False
    assert report["errors"] == [] and report["external"] == []
    for row in report["sources"]:
        assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"], row["path"]
    print("MASTER_OVERVIEW_UI_VERIFIED " + json.dumps(report["summary"]), flush=True)


if __name__ == "__main__":
    test_master_overview_browser(sys.argv[1] if len(sys.argv) > 1 else None)
