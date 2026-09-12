"""Chrome 109 plan selection and first-screen geometry with current sources."""
import json
import os
import subprocess
import tempfile
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_wbui_plan_first_screen():
    node, browser, modules = runtime_tools()
    output = Path(tempfile.mkdtemp(prefix='aps-wbui-plan-first-screen-'))
    print('WBUI_PLAN_FIRST_SCREEN ' + str(output), flush=True)
    result = subprocess.run(
        [node, str(Path(__file__).with_name('wbui_plan_first_screen_probe.cjs')), str(output)],
        env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((output / 'result.json').read_text(encoding='utf-8'))
    assert report['passed'] and report['errors'] == []
    assert len(report['cases']) == 6
    assert len(report['selection_lifecycle']) == 6
    assert all(case['passed'] for case in report['selection_lifecycle'])
