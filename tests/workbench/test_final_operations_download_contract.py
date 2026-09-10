"""The client rejects response mismatch before a browser download is triggered."""

import json
import os
import subprocess

from tests.workbench.final_operations_support import REPO
from tests.workbench.test_live_browser import runtime_tools


def test_final_operations_backup_client_rejects_wrong_payload():
    node, _browser, modules = runtime_tools()
    result = subprocess.run([node, str(REPO / "tests/workbench/final_operations_download_contract.cjs")],
                            cwd=str(REPO), env=dict(os.environ, NODE_PATH=modules),
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["passed"] == 1 and payload["browser_downloads"] == 1
    assert payload["invalidContexts"] == 5
    assert payload["event_rejections"] == 2
    assert payload["rejected"] == ["empty", "magic", "size", "mime", "filename", "reference", "bad-encoding", "json", "disguised-json"]
