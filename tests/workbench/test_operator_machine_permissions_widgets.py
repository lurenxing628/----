"""Current JSX controls in Chromium 109; independent from the SQL contract tests."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_permission_editor_preserves_legacy_values_and_submits_full_set():
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-permissions-controls-"))
    result = subprocess.run([node, str(root / "tests/workbench/operator_machine_permissions_probe.cjs"), str(output)],
                            cwd=str(root), env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                            capture_output=True, text=True, timeout=150)
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "permissions-result.json").read_text(encoding="utf-8"))
    assert len(report["cases"]) == 4 and not report["errors"]
    print("PERMISSION_WIDGET_ARTIFACTS " + str(output), flush=True)
