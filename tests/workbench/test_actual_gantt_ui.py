"""Chrome109 mouse/keyboard, screenshots and canvas pixels; no shared build."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.workbench.test_live_browser import runtime_tools

HERE = Path(__file__).resolve().parent


def test_actual_gantt_model():
    node, _, modules = runtime_tools()
    result = subprocess.run([node, str(HERE / "test_actual_gantt_model.cjs")], env=dict(os.environ, NODE_PATH=modules, TZ="America/New_York"), capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_actual_gantt_browser():
    root = Path(tempfile.mkdtemp(prefix="actual-gantt-ui-"))
    node, browser, modules = runtime_tools()
    print("ACTUAL_GANTT_ARTIFACTS " + str(root), flush=True)
    with (root / "server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen([sys.executable, "-B", str(HERE / "test_actual_gantt_live_server.py"), str(root)], stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 30
            while not (root / "ready.json").exists():
                assert server.poll() is None, (root / "server.log").read_text()
                assert time.monotonic() < deadline, "Temporary fixture server startup timed out"
                time.sleep(.05)
            run = subprocess.run([node, str(HERE / "test_actual_gantt_browser.cjs"), str(root)],
                                 env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser), capture_output=True, text=True, timeout=240)
            assert run.returncode == 0, run.stdout + run.stderr + "\n" + str(root)
        finally:
            server.terminate()
            server.wait(timeout=10)
    report = json.loads((root / "result.json").read_text())
    assert report["browser"].startswith("109.")
    assert report["errors"] == [] and report["external"] == []
    assert report["real_api_reads"] >= 4
    assert report["dense_count"] == 10000 and report["virtual_rows"] < 60
    assert report["canvas_pixels"] > 0 and report["screenshots"]
    for source in report["sources"]:
        assert hashlib.sha256((HERE.parents[1] / source["path"]).read_bytes()).hexdigest() == source["sha256"]
    assert hashlib.sha256((HERE / "test_actual_gantt_browser.cjs").read_bytes()).hexdigest() == report["probe_sha256"]
    assert json.loads((root / "db-evidence.json").read_text())["unchanged"]


if __name__ == "__main__":
    test_actual_gantt_model()
    test_actual_gantt_browser()
