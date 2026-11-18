"""Run pure shared UI JavaScript contracts from the Python required gate."""

import json
import os
from pathlib import Path

import pytest

from tests._support.node_runtime_support import run_node
from web.routes.workbench.navigation_metadata import NAVIGATION_RULES

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("name", ("workbench-format.cjs", "workbench-terms-and-ids.cjs", "workbench-density.cjs", "workbench-guards.cjs",
                                  "workbench/analysis_ui_contract.cjs", "workbench/dashboard_analysis_pagination_contract.cjs",
                                  "workbench/ui_refinement_reports_review_contract.cjs",
                                  "workbench/batch_summary_contract.cjs",
                                  "workbench/runtime_reuse_contract.cjs", "workbench/quota_revision_contract.cjs", "workbench/resource_rail_presentation_contract.cjs",
                                  "workbench-calendar-zero-hours.cjs", "workbench/notice_ownership_contract.cjs",
                                  "workbench/scheduling_preferences_contract.cjs", "workbench/gantt_graph_contract.cjs",
                                  "workbench/decision_comparison_contract.cjs", "workbench/decision_resource_contract.cjs",
                                  "workbench/decision_preparation_contract.cjs", "workbench/decision_history_contract.cjs",
                                  "workbench/system_source_contract.cjs", "workbench/storage_write_contract.cjs"))
def test_shared_ui_node_contract(name):
    # 导航契约读后端唯一的受控导航声明，不在测试里另存一份。
    env = dict(os.environ, WORKBENCH_NAVIGATION_RULES=json.dumps(NAVIGATION_RULES))
    run_node([ROOT / "tests" / name], cwd=ROOT, env=env)
