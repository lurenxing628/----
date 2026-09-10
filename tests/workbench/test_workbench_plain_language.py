"""Current JSX and real Chrome109 with isolated adapters; no production DB writes."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_live_browser import runtime_tools


def test_workbench_plain_language(output=None):
    node, browser, modules = runtime_tools()
    artifacts = Path(output or tempfile.mkdtemp(prefix="aps-plain-language-"))
    print("PLAIN_LANGUAGE_ARTIFACTS " + str(artifacts), flush=True)
    completed = subprocess.run(
        [node, str(HERE / "workbench_plain_language_probe.cjs"), str(artifacts)],
        env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=300,
    )
    report_path = artifacts / "plain-language-result.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    diagnostic = completed.stdout + completed.stderr + str(artifacts)
    diagnostic += "\n" + report.get("runner_error", "")
    diagnostic += "\n".join(row.get("error", "") for row in report.get("cases", []) if not row["passed"])
    assert completed.returncode == 0, diagnostic
    assert report["browser"].startswith("109.")
    assert report["compile"]["global_build"] is False
    assert report["production_persistence_tested"] is False
    assert report["pending_storage_tested"] is True
    assert report["summary"]["failed"] == 0
    assert report["summary"]["cases"] >= 32
    for key in ("errors", "external", "unexpected_requests"):
        assert report[key] == [], (key, report[key])
    for row in report["sources"] + report["probes"]:
        assert hashlib.sha256((HERE.parent.parent / row["path"]).read_bytes()).hexdigest() == row["sha256"], row["path"]
    for screenshot in report["screenshots"]:
        assert Path(screenshot).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    print("PLAIN_LANGUAGE_VERIFIED " + json.dumps({"browser": report["browser"], **report["summary"]}), flush=True)


if __name__ == "__main__":
    test_workbench_plain_language(sys.argv[1] if len(sys.argv) > 1 else None)
