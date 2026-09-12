"""Run pure shared UI JavaScript contracts from the Python required gate."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("name", ("workbench-format.cjs", "workbench-terms-and-ids.cjs", "workbench-density.cjs", "workbench-guards.cjs",
                                  "workbench/analysis_ui_contract.cjs", "workbench/ui_refinement_reports_review_contract.cjs"))
def test_shared_ui_node_contract(name):
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    node = os.environ.get("WORKBENCH_NODE") or shutil.which("node") or (str(bundled) if bundled.is_file() else None)
    assert node, "Node is required for pure UI contracts; browser tooling is not needed"
    result = subprocess.run([node, str(ROOT / "tests" / name)], cwd=str(ROOT), capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
