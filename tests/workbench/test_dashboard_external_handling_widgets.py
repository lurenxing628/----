"""DX front-end contracts and actual Chromium109 input/click evidence."""

import ast
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from flask import Flask

from core.models.workbench_dashboard import DashboardQuery
from core.services.workbench.dashboard import WorkbenchDashboardService
from tests.workbench.dashboard_external_handling_widgets_support import database, serve
from tests.workbench.outsourcing_widgets_support import NOW, connect, tables
from tests.workbench.test_live_browser import runtime_tools

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def test_current30_external_contract(tmp_path):
    path = database(tmp_path / "dx-current30.sqlite")
    with connect(path) as conn, Flask("dx-contract").app_context():
        before = tables(conn)
        service = WorkbenchDashboardService(conn, clock=lambda: NOW)
        with service.read_snapshot():
            data = service.workspace(service.read(), DashboardQuery())
        assert tables(conn) == before
    summary = data["categories"]["external"]
    assert summary["handling_supported"] is False
    node, _, _ = runtime_tools()
    script = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert/strict');
global.window = {}; vm.runInThisContext(fs.readFileSync('frontend/workbench/app/DashboardContract.js', 'utf8'));
const actual = JSON.parse(fs.readFileSync(0, 'utf8')), C = window.DashboardContract;
assert.equal(C.external(actual), actual);
for (const state of ['not_connected', 'unavailable']) {
  const explicit = {...actual, handling_supported:false, handling_count:null, closed_count:null,
    handling_state:state, handling_issues:[{code:'dashboard_external_' + state,message:'明确未接入或不可读'}]};
  assert.equal(C.external(explicit).handling_count, null);
  for (const patch of [{handling_count:0}, {closed_count:0}, {handling_state:'loaded'}, {handling_issues:[]},
    {handling_supported:true}, {handling_issues:[{}]}, {handling_state:undefined}]) {
    assert.throws(() => C.external({...explicit,...patch}));
  }
}
assert.throws(() => C.external({...actual, receipt_count:-1}));
console.log(JSON.stringify({actual, explicit_states:2, rejected:15}));
"""
    result = subprocess.run([node, "-e", script], input=json.dumps(summary), text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    print("DX_CURRENT30_CONTRACT " + result.stdout, flush=True)


def test_dashboard_external_handling_widgets(tmp_path, monkeypatch):
    output = Path(os.environ.get("DASHBOARD_EXTERNAL_UI_OUTPUT", str(tmp_path / "dx-ui"))).resolve()
    assert output != ROOT and ROOT not in output.parents
    output.mkdir(parents=True, exist_ok=True)
    print("DX_UI_ARTIFACTS " + str(output), flush=True)
    node, browser, modules = runtime_tools()
    database_root = Path(tempfile.mkdtemp(prefix="databases-", dir=str(output)))
    with serve(database_root, output, monkeypatch) as config:
        run = subprocess.run([node, str(HERE / "dashboard_external_handling_widgets_probe.cjs"), str(output)],
            input=json.dumps(config), text=True, capture_output=True, timeout=600,
            env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser))
    assert run.returncode == 0, run.stdout + run.stderr + "\n" + str(output)
    report = json.loads((output / "dashboard-external-ui.json").read_text(encoding="utf-8"))
    server = json.loads((output / "dashboard-external-server.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.") and report["compile_global_build"] is False
    assert len(report["cases"]) == report["restarts"] == 4
    assert report["errors"] == report["external"] == []
    assert len(report["boundaries"]) >= 8 and all(report["boundaries"].values())
    assert report["contract_rejections"] == 20
    assert server["server_stopped"] and server["schema_version"] == 30
    assert hashlib.sha256(Path(server["baseline_database"]).read_bytes()).hexdigest() == server["baseline_sha256"]
    for source in report["sources"]:
        assert hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() == source["sha256"]
    for case in report["cases"]:
        proof = next(p for p in server["proofs"] if p["case"] == case["name"])
        assert len(proof["facts"]) == 2
        assert [r["confirmed_state"] for r in proof["facts"]] == ["in_transit", "returned"]
        assert len(proof["history"]) == 4 and len(proof["states"]) == 1
        assert [json.loads(h["after_json"])["status"] for h in proof["history"]] == ["following", "awaiting_verification", "closed", "following"]
        closed = json.loads(proof["history"][2]["after_json"])
        assert closed["completion_evidence"] == case["completion_evidence"] and closed["evidence_reference_text"] == case["evidence"]
        assert proof["history"][3]["reason"] == case["reopen_reason"]
        commands = [r for r in proof["receipts"] if r["action"].startswith("dashboard.")]
        assert len(commands) == 4 and sum(r["request_key"] == case["unknown_key"] for r in commands) == 1
        assert {"SchemaVersion", "Schedule", "ScheduleHistory", "BatchOperations", "Batches", "Parts", "OperationExecutionEvents",
                "WorkbenchProductionReports", "WorkbenchProductionReportRevisions", "WorkbenchDashboardItems", "WorkbenchDashboardStates",
                "WorkbenchDashboardHistory"} <= set(proof["preserved_tables"])
    for name in ("current30", "missing", "lost", "stale"):
        proof = next(p for p in server["proofs"] if p["case"] == name)
        assert proof["history"] == proof["states"] == []
    for row in server["journal"]:
        if row["method"] == "GET" or row["path"].endswith("/preview"):
            assert row["changed_tables"] == []
    print("DX_UI_VERIFIED " + str(output), flush=True)


def test_dashboard_external_widgets_python38_syntax():
    for name in ("test_dashboard_external_handling_widgets.py", "dashboard_external_handling_widgets_support.py"):
        ast.parse((HERE / name).read_text(encoding="utf-8"), feature_version=(3, 8))
