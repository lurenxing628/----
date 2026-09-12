"""Every dense actual-Gantt mark remains operable by keyboard in Chrome 109."""
import os
import subprocess
import tempfile
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_wbui_actual_keyboard():
    node, browser, modules = runtime_tools()
    output = Path(tempfile.mkdtemp(prefix='aps-wbui-actual-keyboard-'))
    print('WBUI_ACTUAL_KEYBOARD ' + str(output), flush=True)
    result = subprocess.run(
        [node, str(Path(__file__).with_name('wbui_actual_keyboard_probe.cjs')), str(output)],
        env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
