"""CZ: Chrome 109 downloads current source against real isolated trial services."""

import ast
import hashlib
import json
import os
import subprocess
import tempfile
import threading
from pathlib import Path

from werkzeug.serving import make_server

from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.trial_export_widgets_support import TrialExportServer, verify_download


def test_trial_export_widgets_real_browser():
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix='aps-cz-trial-export-'))
    print('TRIAL_EXPORT_ARTIFACTS ' + str(output), flush=True)
    backend = TrialExportServer(output)
    server = make_server('127.0.0.1', 0, backend.app, threaded=True)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        result = subprocess.run([node, str(root / 'tests/workbench/trial_export_widgets_probe.cjs'), str(output),
                                 'http://127.0.0.1:' + str(server.server_port)], cwd=str(root),
                                env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                                capture_output=True, text=True, timeout=360)
        (output / 'probe-output.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    finally:
        server.shutdown()
        thread.join(timeout=15)
        server.server_close()
        proof = backend.proof()
        (output / 'sqlite-proof.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf-8')
    assert result.returncode == 0, (result.stdout + result.stderr)[-10000:] + '\n' + str(output)
    report = json.loads((output / 'trial-export-widgets.json').read_text(encoding='utf-8'))
    assert report['browser'].startswith('109.')
    assert len(report['variants']) == 4 and all(row['passed'] for row in report['variants'])
    assert not report['errors'] and not report['external']
    decoded = [verify_download(item) for item in report['downloads'] if item['button'] == '导出对比']
    (output / 'csv-field-proof.json').write_text(json.dumps(decoded, ensure_ascii=False, indent=2), encoding='utf-8')
    assert any(item['rows'] == 24 for item in decoded)
    assert report['boundary_checks'] and all(item['passed'] for item in report['boundary_checks'])
    assert proof['all_connections_isolated'] and proof['all_database_rows_unchanged']
    assert all(row['method'] == 'GET' for row in proof['journal'])
    for item in report['sources']:
        assert hashlib.sha256((root / item['path']).read_bytes()).hexdigest() == item['sha256']
    for name in ('test_trial_export_widgets.py', 'trial_export_widgets_support.py'):
        ast.parse((root / 'tests/workbench' / name).read_text(encoding='utf-8'), feature_version=(3, 8))
    print(result.stdout, flush=True)
