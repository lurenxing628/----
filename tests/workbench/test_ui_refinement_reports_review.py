"""Display contracts independent of report DTO and calibration write behavior."""

import os
import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools

ROOT = Path(__file__).resolve().parents[2]


def test_ui_refinement_reports_review_contract():
    node, _browser, modules = runtime_tools()
    result = subprocess.run(
        [node, str(ROOT / "tests/workbench/ui_refinement_reports_review_contract.cjs")],
        cwd=str(ROOT), env=dict(os.environ, NODE_PATH=modules),
        text=True, capture_output=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
