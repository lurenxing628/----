"""Client identity boundaries against real adopted-plan and draft DTOs, not UI K."""

import json
import os
import subprocess
from pathlib import Path

from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.plan_queries import WorkbenchPlanQueryService
from tests.workbench.piece_chain_support import piece_layout
from tests.workbench.plan_adoption_baseline_support import adopt_candidate
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.trial_support import create, snapshot
from tests.workbench.trial_support import trial_case as trial_case


def test_real_task_origin_and_process_order_client_boundaries(trial_case):
    case = trial_case
    piece_layout(case)
    plan = adopt_candidate(case)
    draft = create(case, {"base": {"plan_ref": plan["plan_ref"]}})
    task = next(row for row in draft["tasks"] if row["piece_id"] == "item-B" and row["sequence"] == 20)
    before = snapshot(case.conn)
    service = WorkbenchPlanQueryService(case.conn)
    with service.read_snapshot():
        data, _ = service.workspace(PlanReadScope(plan["plan_ref"]))
    origin = {"plan_ref": plan["plan_ref"], "operation_ref": task["operation_ref"], "task_ref": task["source_task_ref"]}
    node, _, modules = runtime_tools()
    result = subprocess.run([node, str(Path(__file__).with_suffix(".cjs"))],
        input=json.dumps({"draft": draft, "plan": data, "origin": origin}), text=True, capture_output=True,
        env=dict(os.environ, NODE_PATH=modules), timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {"checks": 39, "actual_dto": True, "full_entry": False}
    assert snapshot(case.conn) == before
