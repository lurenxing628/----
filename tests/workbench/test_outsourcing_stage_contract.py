"""Outsourcing query, member selection and paging callbacks; browser evidence is separate."""

import os
import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_outsourcing_stage_frontend_contract(tmp_path):
    node, _browser, modules = runtime_tools()
    script = Path(__file__).with_name("outsourcing_stage_contract.cjs")
    result = subprocess.run([node, str(script)], env=dict(os.environ, NODE_PATH=modules),
                            capture_output=True, text=True, timeout=90)
    (tmp_path / "outsourcing-stage-contract.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"failed":0' in result.stdout
