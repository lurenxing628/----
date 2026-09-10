"""R1-B private component build and real Chrome 109 file workflow, not site acceptance."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.workbench.point_downstream_support import serve
from tests.workbench.test_execution_ledger_support import ledger_case as ledger_case
from tests.workbench.test_field_workspace_support import field_api as field_api
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_round1_field_piece_files_support import (
    PIECES,
    by_piece,
)
from tests.workbench.test_round1_field_piece_files_support import (
    piece_file_api as piece_file_api,
)


@pytest.mark.parametrize('width,height', [(1920, 1080), (1392, 924)])
@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_real_file_browser(piece_file_api, tmp_path, width, height, theme):
    api = piece_file_api
    node, browser, modules = runtime_tools()
    script = Path(__file__).with_name('test_round1_field_piece_files_browser.cjs')
    env = dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser, WORKBENCH_PYTHON=sys.executable)
    with serve(api.app) as upstream:
        result = subprocess.run([node, str(script), upstream, str(tmp_path), str(width), str(height), theme],
            env=env, capture_output=True, text=True, timeout=150)
    assert result.returncode == 0, result.stdout + result.stderr + '\n' + str(tmp_path)
    report = json.loads((tmp_path / 'round1-field-browser.json').read_text(encoding='utf-8'))
    assert report['browser'].startswith('109.') and report['compile']['global_build'] is False
    assert report['errors'] == [] and report['completed'] is True
    rows = by_piece(api)
    assert all(len(rows[piece]['execution']['reports']) == 1 for piece in (None, PIECES[0], '0'))
    assert rows[PIECES[1]]['execution']['reports'] == []
    assert all(row['execution']['execution_state'] != 'complete' for row in rows.values())
    assert api.case.conn.execute('SELECT count(*) FROM WorkbenchProductionReportRevisions').fetchone()[0] == 3
    print('R1_B_BROWSER ' + str(tmp_path / 'round1-field-browser.json'))
