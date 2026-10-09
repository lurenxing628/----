"""Run pure shared UI JavaScript contracts from the Python required gate."""

import subprocess
from pathlib import Path

import pytest

from tests.workbench.node_runtime_support import node_runtime

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("name", ("workbench-format.cjs", "workbench-terms-and-ids.cjs", "workbench-density.cjs", "workbench-guards.cjs",
                                  "workbench/analysis_ui_contract.cjs", "workbench/ui_refinement_reports_review_contract.cjs",
                                  "workbench/runtime_reuse_contract.cjs", "workbench/quota_revision_contract.cjs", "workbench/resource_rail_presentation_contract.cjs",
                                  "workbench-calendar-zero-hours.cjs", "workbench/notice_ownership_contract.cjs"))
def test_shared_ui_node_contract(name):
    result = subprocess.run([node_runtime(), str(ROOT / "tests" / name)], cwd=str(ROOT), capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
