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
FRONTEND_LIST = r"""
const fs = require('node:fs'), vm = require('node:vm');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const window = {}, context = vm.createContext({window, AbortController, URLSearchParams, setTimeout, clearTimeout});
for (const name of ['DashboardContract.js', 'RunCandidateAPI.js', 'DashboardAnalysisAPI.js']) {
  vm.runInContext(fs.readFileSync('frontend/workbench/app/' + name, 'utf8'), context);
}
window.DashboardContract.create(async () => ({
  ok: true, status: 200, headers: {get: () => 'application/json'}, json: async () => payload
})).list({}).then(value => process.stdout.write(JSON.stringify(value.data)))
  .catch(error => { console.error(error); process.exitCode = 1; });
"""


def frontend_data(response):
    assert response.status_code == 200, response.get_json()
    result = subprocess.run([node_runtime(), "-e", FRONTEND_LIST],
        input=json.dumps(response.get_json()), text=True, encoding="utf-8", capture_output=True,
        cwd=str(Path(__file__).resolve().parents[2]), timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_legacy_internal_keeps_analysis_downtime_and_execution_readable(dashboard_case, monkeypatch):
    case = dashboard_case
    case.conn.execute("UPDATE BatchOperations SET source=' INTERNAL ' WHERE id=?", (case.op,))
    case.conn.commit()
    reader = WorkbenchDashboardService(case.conn, clock=lambda: NOW)
    with reader.read_snapshot():
        sources = reader.load()
        reader.project(sources)
    assert sources.facts.task_rows[0]["source"] == "internal"
    assert sources.facts.raw["plan_task_sources"][0][1] == " INTERNAL "
    assert list(sources.facts.raw["execution_operation_sources"].values()) == [" INTERNAL "]
    assert not source_gap_rows(case.conn, 1)

    data = frontend_data(api(case, monkeypatch).get(ROOT))
    assert data["analysis_error"] is None
    analysis = data["analysis"]
    task = analysis["tasks"][0]
    assert task["source"] == "internal"
    assert analysis["resources"][0]["task_refs"] == [task["task_ref"]]
    assert len(analysis["downtimes"]) == 1 and analysis["overlaps"][0]["source"]["known_overlap_hours"] == 1
    assert data["categories"]["downtime"]["unknown_count"] == 0
    assert analysis["execution"][0]["source"]["data_quality"] != "invalid"
    assert case.conn.execute("SELECT source FROM BatchOperations WHERE id=?", (case.op,)).fetchone()[0] == " INTERNAL "
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        case.report()
    assert rejected.value.code == "constraint_conflict"


def test_legacy_external_keeps_analysis_and_reports_unassessed_logistics(external_case, monkeypatch):
    case = external_case
    op = case.conn.execute("SELECT id FROM BatchOperations WHERE op_code='XO1'").fetchone()[0]
    case.conn.execute("UPDATE BatchOperations SET source=' EXTERNAL ' WHERE id=?", (op,))
    case.conn.execute("INSERT INTO Schedule(version,op_id,start_time,end_time) "
        "VALUES(1,?,'2026-09-09T08:00:00','2026-09-11T10:00:00')", (op,))
    case.conn.commit()

    data = frontend_data(api(case, monkeypatch).get(ROOT))
    assert data["analysis_error"] is None
    task = next(row for row in data["analysis"]["tasks"] if row["batch_id"] == "XB1")
    assert task["source"] == "external" and task["machine_ref"] is None
    actual = next(row for row in data["analysis"]["execution"] if row["source"]["batch_id"] == "XB1")
    assert actual["source"]["hours"]["basis"] == "not_currently_evaluated"
    assert actual["source"]["data_quality"] != "invalid"
    external = data["categories"]["external"]
    assert external["risk_count"] is None and external["source_gap_count"] == 1
    gap = next(row for row in external["evaluation_gaps"] if row["code"] == "external_source_noncanonical")
    assert gap["subject"] == "XO1" and "历史外协" in gap["message"] and "尚未评估" in gap["message"]
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        case.shipments.preview(case.shipments.payload())
    assert rejected.value.code == "constraint_conflict"


@pytest.mark.parametrize("stored_source", ["unknown", b"internal"])
def test_unknown_source_stays_unknown_and_preserves_readable_list(external_case, monkeypatch, stored_source):
    case = external_case
    case.conn.execute("UPDATE BatchOperations SET source=? WHERE id=?", (stored_source, case.op))
    case.conn.commit()

    data = frontend_data(api(case, monkeypatch).get(ROOT))
    assert data["plan"] is not None and data["items"]
    assert data["analysis"] is None and data["analysis_error"]
    assert data["categories"]["downtime"]["unknown_count"] == 1
    external = data["categories"]["external"]
    assert external["risk_count"] is None and external["source_gap_count"] == 1
    gap = next(row for row in external["evaluation_gaps"] if row["code"] == "external_source_unknown")
    assert gap["subject"] == "DOP1"
    assert case.conn.execute("SELECT source FROM BatchOperations WHERE id=?", (case.op,)).fetchone()[0] == stored_source


def test_source_gap_limit_counts_selected_rows_and_keeps_storage_types(external_case):
    case = external_case
    case.conn.execute("UPDATE BatchOperations SET source=' INTERNAL ' WHERE id=?", (case.op,))
    case.conn.execute("UPDATE BatchOperations SET source=? WHERE op_code='XO3'", (b"external",))
    case.conn.commit()

    # Canonical and recognized internal rows before XO3 do not exhaust the result limit.
    rows = source_gap_rows(case.conn, 1)
    assert len(rows) == 1 and rows[0]["business_code"] == "XO3"
    assert rows[0]["source"] == rows[0]["source_kind"] == b"external"
