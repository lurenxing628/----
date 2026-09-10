"""Current Plan UI sources + actual Chrome109; API adapter mocks, not live DB proof."""
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


def test_plan_ui_model():
    node, _, modules = runtime_tools()
    result = subprocess.run([node, str(HERE / "plan_ui_model_probe.cjs")],
                            env=dict(os.environ, NODE_PATH=modules), capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["assertions"] == 15


def test_plan_ui_browser(output=None):
    node, browser, modules = runtime_tools()
    artifacts = Path(output or tempfile.mkdtemp(prefix="aps-plan-ui-"))
    print("PLAN_UI_ARTIFACTS " + str(artifacts), flush=True)
    result = subprocess.run([node, str(HERE / "plan_ui_browser_probe.cjs"), str(artifacts)],
                            env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                            capture_output=True, text=True, timeout=360)
    path = artifacts / "plan-ui-result.json"
    report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    diagnostic = result.stdout + result.stderr + str(artifacts) + "\n" + report.get("runner_error", "")
    diagnostic += "\n".join(row.get("error", "") for row in report.get("cases", []) if not row["passed"])
    assert result.returncode == 0, diagnostic
    assert report["browser"].startswith("109.")
    assert report["compile"]["global_build"] is False
    assert report["production_persistence_tested"] is False
    assert report["summary"]["cases"] == 51
    assert report["summary"]["failed"] == 0
    assert report["summary"]["screenshots"] == 31
    for key in ("errors", "external", "unexpected_requests"):
        assert report[key] == []
    for row in report["sources"] + report["probes"]:
        source = HERE.parent.parent / row["path"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row["sha256"], row["path"]
    for image in report["screenshots"]:
        assert Path(image).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    print("PLAN_UI_VERIFIED " + json.dumps({"browser": report["browser"], **report["summary"]}), flush=True)


if __name__ == "__main__":
    test_plan_ui_model()
    test_plan_ui_browser(sys.argv[1] if len(sys.argv) > 1 else None)
