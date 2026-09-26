"""Business identifiers remain readable when action buttons are hidden for printing."""

import json
import os
import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_business_values_survive_print_styles(tmp_path):
    node, browser, modules = runtime_tools()
    result = subprocess.run(
        [node, str(Path(__file__).with_name("workbench_print_values.cjs")), str(tmp_path)],
        env=dict(os.environ, WORKBENCH_BROWSER=browser, NODE_PATH=modules),
        text=True, capture_output=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["browser"].startswith("109.")
    assert report["themes"] == ["light", "dark"]
    assert report["errors"] == []
    for theme in report["themes"]:
        assert (tmp_path / (theme + ".pdf")).read_bytes().startswith(b"%PDF-")
