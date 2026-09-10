"""Actual main.jsx, isolated build, persisted EA point and real report HTTP."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.workbench.point_downstream_support import adopted, app_for, report, serve
from tests.workbench.trial_support import snapshot
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401

HERE = Path(__file__).resolve().parent
MODULES = '/Users/lurenxing/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
BROWSER = '/tmp/aps-chromium109-assessment/runtime/chrome-mac/Chromium.app/Contents/MacOS/Chromium'


def invoke(script, value):
    result = subprocess.run([shutil.which('node'), str(HERE / script)], input=json.dumps(value),
        text=True, capture_output=True, timeout=180,
        env=dict(os.environ, NODE_PATH=MODULES, WORKBENCH_BROWSER=BROWSER))
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


@pytest.mark.parametrize('reports', [False, True], ids=['point-only', 'with-real-reports'])
def test_real_main_point_downstream_chrome109(trial_case, tmp_path, reports):
    identity = adopted(trial_case)
    output = tmp_path / 'ek-point-downstream-browser'
    invoke('point_downstream_browser_build_support.cjs', {'output': str(output)})
    app = app_for(trial_case, output)
    if reports:
        client = app.test_client()
        report(client, identity)
        report(client, identity, quantity=0, start='2026-09-09T09:40:00', end='2026-09-09T09:40:00', hours=None)
        report(client, identity, quantity=None, start='2026-09-09T09:50:00', end=None, hours=None)
    before = snapshot(trial_case.conn)
    with serve(app) as base:
        print(invoke('point_downstream_browser.cjs', {'base': base, 'output': str(output), 'identity': identity, 'reports': reports}), flush=True)
    assert snapshot(trial_case.conn) == before
    evidence = json.loads((output / 'browser-result.json').read_text(encoding='utf-8'))
    assert evidence['browser'].startswith('109.')
    assert evidence['errors'] == [] and evidence['external'] == []
    assert len(evidence['screenshots']) == 8
    assert evidence['main_source_used'] is True
    print('EK_POINT_EVIDENCE ' + str(output), flush=True)
