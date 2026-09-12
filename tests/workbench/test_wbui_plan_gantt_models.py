"""Display-only plan selection, viewport and hit-area contracts."""
import os
import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_wbui_plan_gantt_models():
    node, _, modules = runtime_tools()
    result = subprocess.run(
        [node, str(Path(__file__).with_suffix('.cjs'))],
        env=dict(os.environ, NODE_PATH=modules, TZ='America/New_York'),
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
