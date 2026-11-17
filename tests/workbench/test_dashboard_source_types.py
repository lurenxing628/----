"""Dashboard navigation contexts are accepted by each destination's real frontend protocol."""

import json
import subprocess
from pathlib import Path

from tests._support.node_runtime_support import node_runtime
from tests.workbench.dashboard_support import api
from tests.workbench.dashboard_support import dashboard_case as dashboard_case  # noqa: F401

ROOT = "/api/workbench/v1/dashboard"
FRONTEND_READ = r"""
const fs = require('node:fs'), vm = require('node:vm');
const { compile } = require('./scripts/workbench/compile.cjs');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
// 在 fetch 层打桩：真实后端响应经共享传输层和领域合约的同一条读取链校验。
const fetch = async () => ({
  ok: true, status: 200, headers: {get: () => 'application/json'}, json: async () => payload
});
const window = {}, context = vm.createContext({window, fetch, location: {origin: 'http://127.0.0.1'}, URL, DOMException,
  AbortController, URLSearchParams, setTimeout, clearTimeout});
const files = ['WorkbenchTerms.js', 'shared/network/transport.js', 'DashboardContract.js', 'RunCandidateAPI.js',
               'DashboardAnalysisAPI.js'];
for (const out of compile({ sources: files.map(name => ({ path: name, code: fs.readFileSync('frontend/workbench/app/' + name, 'utf8') })) }).outputs) {
  vm.runInContext(out.code, context, { filename: out.path });
}
const DashboardContract = context.__wbRuntime.getModule('DashboardContract.js');
DashboardContract.list({}).then(value => process.stdout.write(JSON.stringify(value.data)))
  .catch(error => { console.error(error); process.exitCode = 1; });
"""
PLAN_ACCEPT = r"""
const fs = require('node:fs'), vm = require('node:vm');
const { compile } = require('./scripts/workbench/compile.cjs');
const contexts = JSON.parse(fs.readFileSync(0, 'utf8')), window = {}, context = vm.createContext({window});
const files = ['resource-contract.js', 'PlanNavigation.js'];
for (const out of compile({ sources: files.map(name => ({ path: name, code: fs.readFileSync('frontend/workbench/app/' + name, 'utf8') })) }).outputs) {
  vm.runInContext(out.code, context, { filename: out.path });
}
const APSPlanNavigation = context.__wbRuntime.getModule('PlanNavigation.js');
contexts.forEach(value => APSPlanNavigation.accept(value));
"""


def frontend_data(response):
    assert response.status_code == 200, response.get_json()
    result = subprocess.run([node_runtime(), "-e", FRONTEND_READ], input=json.dumps(response.get_json()), text=True,
        encoding="utf-8", capture_output=True, cwd=str(Path(__file__).resolve().parents[2]), timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_risk_navigation_uses_destination_protocols(dashboard_case):
    from core.models.workbench_plan_scope import PlanReadScope
    from core.services.workbench.plan.queries import WorkbenchPlanQueryService

    # The real HTTP list is read through the real DashboardContract; each destination keeps its own focus keys.
    data = frontend_data(api(dashboard_case).get(ROOT))
    items, plan_ref = {row["category"]: row for row in data["items"]}, data["plan"]["plan_ref"]
    delivery, downtime, material = items["delivery"], items["downtime"], items["material"]
    assert delivery["navigation"] == [{"view": "gantt", "context": {"plan_ref": plan_ref, "selected_batch_ref": delivery["source"]["batch_ref"]},
                                       "enabled": True, "reason": None}]
    assert downtime["navigation"] == [{"view": "gantt", "context": {"plan_ref": plan_ref, "selected_task_ref": downtime["source"]["task_ref"]},
                                       "enabled": True, "reason": None}]
    assert material["navigation"] == [{"view": "batches", "context": {"batch_ref": material["source"]["batch_ref"]}, "enabled": True, "reason": None}]
    expected_actual_context = {key: items["actual"]["source"][key] for key in ("plan_ref", "task_ref", "operation_ref")}
    assert items["actual"]["navigation"] == [
        {"view": "fieldgantt", "context": expected_actual_context, "enabled": True, "reason": None},
        {"view": "field", "context": expected_actual_context, "enabled": True, "reason": None},
    ]
    # The formal plan gantt context has one receiver: every produced context is accepted by the real APSPlanNavigation.accept.
    contexts = [n["context"] for row in data["items"] for n in row["navigation"] if n["view"] == "gantt"]
    accepted = subprocess.run([node_runtime(), "-e", PLAN_ACCEPT], input=json.dumps(contexts), text=True, encoding="utf-8",
                              capture_output=True, cwd=str(Path(__file__).resolve().parents[2]), timeout=30)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    # The focus identities are the ones the formal plan workspace itself reads for the same plan.
    reader = WorkbenchPlanQueryService(dashboard_case.conn)
    with reader.read_snapshot() as context:
        plan, _ = reader.workspace(context, PlanReadScope(plan_ref))
    assert delivery["source"]["batch_ref"] in {row["batch_ref"] for row in plan["projections"]["delivery_risks"]["items"]}
    assert downtime["source"]["task_ref"] in {row["task_ref"] for row in plan["tasks"]}
