"""FB real factory/main.jsx/worker, isolated four-way Chromium 109 acceptance."""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.workbench.live_environment import create_root, environment, write_json
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_piece_main_browser import invoke

HERE = Path(__file__).resolve().parent


def retention(root):
    before = json.loads((root / 'business-before.json').read_text(encoding='utf-8'))
    after = json.loads((root / 'business-after.json').read_text(encoding='utf-8'))
    exact = ('Batches', 'BatchOperations', 'OperationExecutionEvents', 'ScheduleCandidateRows', 'ScheduleAdjustmentScenarioRow')
    for table in exact:
        assert after[table] == before[table], table
    appended = ('Schedule', 'WorkbenchTaskRefs', 'WorkbenchPlanSourceRefs', 'WorkbenchEntityRefs',
                'WorkbenchProductionReports', 'WorkbenchProductionReportRevisions', 'WorkbenchCommandReceipts')
    for table in appended:
        for row in before[table]:
            assert row in after[table], table
    assert len(after['WorkbenchProductionReports']) == len(before['WorkbenchProductionReports']) + 1
    return {'original_tables_unchanged': list(exact), 'original_rows_retained': list(appended),
            'original_reports': len(before['WorkbenchProductionReports']), 'new_reports': 1}


@pytest.mark.parametrize('width,theme', [(1920, 'light'), (1920, 'dark'), (1392, 'light'), (1392, 'dark')])
def test_piece_downstream_factory_browser(width, theme):
    node, browser, modules = runtime_tools()
    root = create_root()
    env = environment(root)
    env.update(NODE_PATH=modules, WORKBENCH_BROWSER=browser, WORKBENCH_NODE=node, PIECE_MAIN_LONG_IDS='0')
    print('FB_PIECE_DOWNSTREAM_ARTIFACTS ' + str(root), flush=True)
    assert invoke(node, 'piece_main_build.cjs', [str(root)], root, env, 180) == 0, str(root)
    server = None
    with (root / 'fb-server.out.log').open('w', encoding='utf-8') as out, (root / 'fb-server.err.log').open('w', encoding='utf-8') as err:
        try:
            server = subprocess.Popen([sys.executable, '-B', str(HERE / 'piece_main_server.py'), str(root)],
                cwd=str(root), env=env, stdout=out, stderr=err)
            ready = root / 'server-ready.json'
            deadline = time.monotonic() + 90
            while not ready.exists():
                assert server.poll() is None, str(root / 'fb-server.err.log')
                assert time.monotonic() < deadline, str(root)
                time.sleep(.1)
            assert json.loads(ready.read_text())['url'].split(':')[-1] != '53144'
            code = invoke(node, 'piece_downstream_browser.cjs', [str(ready), str(width), theme], root, env, 300)
        finally:
            if server is not None and server.poll() is None:
                server.terminate()
                server.wait(timeout=60)
    result = json.loads((root / 'piece_downstream_browser.json').read_text(encoding='utf-8'))
    assert code == 0, result.get('error', '') + '\n' + str(root)
    assert server.returncode == 0, str(root)
    isolation = json.loads((root / 'server-final.json').read_text())
    assert isolation['stopped'] and isolation['assets_unchanged'] and isolation['isolation_violations'] == []
    for path in isolation['sqlite_connections']:
        if path != ':memory:':
            Path(path).resolve().relative_to(root)
    assert result['browser_version'].startswith('109.')
    assert result['page_errors'] == result['console_errors'] == result['external_requests'] == []
    assert result['served_main'] and len(result['pieces_verified']) == 3
    retained = retention(root)
    write_json(root / 'fb-retention.json', retained)
    print('FB_VERIFIED ' + json.dumps({'root': str(root), 'matrix': [width, theme], 'retention': retained}), flush=True)
