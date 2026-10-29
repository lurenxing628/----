"""Legacy dashboard reads share source semantics without relaxing command admission."""

import json
import subprocess
from pathlib import Path

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.dashboard.service import WorkbenchDashboardService
from data.repositories.workbench_dashboard_source_repo import source_gap_rows
from tests.workbench.dashboard_external_support import external_case as external_case  # noqa: F401
from tests.workbench.dashboard_support import NOW, api
from tests.workbench.dashboard_support import dashboard_case as dashboard_case  # noqa: F401
from tests.workbench.node_runtime_support import node_runtime

ROOT = "/api/workbench/v1/dashboard"
FRONTEND_READ = r"""
const fs = require('node:fs'), vm = require('node:vm');
const {payload, query} = JSON.parse(fs.readFileSync(0, 'utf8'));
// 在 fetch 层打桩：真实后端响应经共享传输层和领域合约的同一条读取链校验。
const fetch = async () => ({
  ok: true, status: 200, headers: {get: () => 'application/json'}, json: async () => payload
});
const window = {}, context = vm.createContext({window, fetch, location: {origin: 'http://127.0.0.1'}, URL, DOMException,
  AbortController, URLSearchParams, setTimeout, clearTimeout});
for (const name of ['WorkbenchTerms.js', 'transport.js', 'DashboardContract.js', 'RunCandidateAPI.js',
                    'ResourceProjectionContract.js', 'DashboardAnalysisAPI.js']) {
  vm.runInContext(fs.readFileSync('frontend/workbench/app/' + name, 'utf8'), context);
}
const reading = query === null ? window.DashboardContract.list({})
  : window.DashboardAnalysisAPI.read(payload.data.plan.plan_ref, undefined, query);
reading.then(value => process.stdout.write(JSON.stringify(value.data)))
  .catch(error => { console.error(error); process.exitCode = 1; });
"""


def frontend_result(response, query=None):
    assert response.status_code == 200, response.get_json()
    return subprocess.run([node_runtime(), "-e", FRONTEND_READ],
        input=json.dumps({"payload": response.get_json(), "query": query}), text=True, encoding="utf-8", capture_output=True,
        cwd=str(Path(__file__).resolve().parents[2]), timeout=30)


def frontend_data(response, query=None):
    result = frontend_result(response, query)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("stored_source", [" INTERNAL ", "\u2003InTeRnAl\u00a0"])
def test_legacy_internal_keeps_analysis_downtime_and_execution_readable(dashboard_case, monkeypatch, stored_source):
    case = dashboard_case
    case.conn.execute("UPDATE BatchOperations SET source=? WHERE id=?", (stored_source, case.op))
    case.conn.commit()
    reader = WorkbenchDashboardService(case.conn, clock=lambda: NOW)
    with reader.read_snapshot():
        sources = reader.load()
        reader.project(sources)
    assert sources.facts.task_rows[0]["source"] == "internal"
    assert sources.facts.raw["plan_task_sources"][0][1] == stored_source
    assert list(sources.facts.raw["execution_operation_sources"].values()) == [stored_source]
    assert not source_gap_rows(case.conn, 1)

    client = api(case, monkeypatch)
    data = frontend_data(client.get(ROOT))
    assert data["analysis_error"] is None
    assert data["analysis"]["pagination"]["section"] == "overview"
    assert data["analysis"]["tasks"] == data["analysis"]["resources"] == []
    actual = frontend_data(client.get(ROOT + "/analysis?section=actual"), {"section": "actual"})
    task = actual["tasks"][0]
    assert task["source"] == "internal"
    pressure = frontend_data(client.get(ROOT + "/analysis?section=pressure"), {"section": "pressure"})
    assert any(row["resource_ref"] == task["machine_ref"] for row in pressure["resources"])
    assert all(row["task_refs"] == row["days"] == [] for row in pressure["resources"])
    downtime = frontend_data(client.get(ROOT + "/analysis?section=downtime"), {"section": "downtime"})
    assert len(downtime["downtimes"]) == 1 and downtime["overlaps"][0]["source"]["known_overlap_hours"] == 1
    assert downtime["tasks"][0]["source"] == "internal"
    assert data["categories"]["downtime"]["unknown_count"] == 0
    assert actual["execution"][0]["source"]["data_quality"] != "invalid"
    assert case.conn.execute("SELECT source FROM BatchOperations WHERE id=?", (case.op,)).fetchone()[0] == stored_source
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        case.report()
    assert rejected.value.code == "constraint_conflict"


@pytest.mark.parametrize("stored_source", [" EXTERNAL ", "\u2003ExTeRnAl\u00a0"])
def test_legacy_external_keeps_analysis_and_reports_unassessed_logistics(external_case, monkeypatch, stored_source):
    case = external_case
    op = case.conn.execute("SELECT id FROM BatchOperations WHERE op_code='XO1'").fetchone()[0]
    case.conn.execute("UPDATE BatchOperations SET source=? WHERE id=?", (stored_source, op))
    case.conn.execute("INSERT INTO Schedule(version,op_id,start_time,end_time) "
        "VALUES(1,?,'2026-09-09T08:00:00','2026-09-11T10:00:00')", (op,))
    case.conn.commit()

    client = api(case, monkeypatch)
    data = frontend_data(client.get(ROOT))
    assert data["analysis_error"] is None
    analysis = frontend_data(client.get(ROOT + "/analysis?section=actual"), {"section": "actual"})
    task = next(row for row in analysis["tasks"] if row["batch_id"] == "XB1")
    assert task["source"] == "external" and task["machine_ref"] is None
    actual = next(row for row in analysis["execution"] if row["source"]["task_ref"] == task["task_ref"])
    assert actual["source"]["hours"]["basis"] == "not_currently_evaluated"
    assert actual["source"]["data_quality"] != "invalid"
    external = data["categories"]["external"]
    assert external["risk_count"] is None and external["source_gap_count"] == 1
    gap = next(row for row in external["evaluation_gaps"] if row["code"] == "external_source_noncanonical")
    assert gap["subject"] == "XO1" and "历史外协" in gap["message"] and "尚未评估" in gap["message"]
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        case.shipments.preview(case.shipments.payload())
    assert rejected.value.code == "constraint_conflict"
