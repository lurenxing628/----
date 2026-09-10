"""CY real input/click workflows against isolated SQLite and mainline receipts."""

import ast
import hashlib
import json
import os
import subprocess
from pathlib import Path

from tests.workbench.dashboard_widgets_support import serve
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from tests.workbench.test_live_browser import runtime_tools

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def test_dashboard_widgets(candidate_case, tmp_path, monkeypatch):
    output = Path(os.environ.get("DASHBOARD_UI_OUTPUT", str(tmp_path / "dashboard-ui"))).resolve()
    assert output != ROOT and ROOT not in output.parents
    output.mkdir(parents=True, exist_ok=True)
    print("DASHBOARD_UI_ARTIFACTS " + str(output), flush=True)
    node, browser, modules = runtime_tools()
    with serve(candidate_case, output, monkeypatch) as config:
        run = subprocess.run([node, str(HERE / "dashboard_widgets_probe.cjs"), str(output)], input=json.dumps(config), text=True,
            capture_output=True, timeout=500, env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser))
    assert run.returncode == 0, run.stdout + run.stderr + "\n" + str(output)
    report = json.loads((output / "dashboard-ui.json").read_text(encoding="utf-8"))
    verify_report(report)
    server = json.loads((output / "dashboard-server.json").read_text(encoding="utf-8"))
    verify_server(report, server)
    print("DASHBOARD_UI_VERIFIED " + str(output), flush=True)


def verify_report(report):
    assert report["browser"].startswith("109.") and report["compile_global_build"] is False
    assert len(report["cases"]) == 4 and report["errors"] == report["external"] == []
    assert report["contract_rejections"] >= 8 and report["restarts"] == 4
    assert all(report["boundaries"].values()) and len(report["boundaries"]) >= 6
    for source in report["sources"]:
        assert hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() == source["sha256"]


def verify_server(report, server):
    assert server["server_stopped"] and set(server["mutations"]) == {"drift", "rollback"}
    for case in report["cases"]:
        proof = next(p for p in server["proofs"] if p["case"] == case["name"])
        verify_history(case, proof)
    for name in ("drift", "rollback", "lost", "missing"):
        proof = next(p for p in server["proofs"] if p["case"] == name)
        assert proof["history"] == proof["states"] == proof["receipts"] == []
    for row in server["journal"]:
        if row["method"] == "GET":
            assert row["changed_tables"] == []


def verify_history(case, proof):
    assert len(proof["history"]) == 5 and len(proof["receipts"]) == 6
    assert sum(json.loads(r["outcome_json"])["result"] == "unchanged" for r in proof["receipts"]) == 1
    states = [json.loads(h["after_json"])["status"] for h in proof["history"]]
    assert states == ["following", "awaiting_verification", "following", "closed", "following"]
    closed, reopened = [json.loads(h["after_json"]) for h in proof["history"][-2:]]
    assert closed["completion_evidence"] == case["completion_evidence"] and closed["evidence_reference_text"] == case["evidence"]
    assert reopened["completed_at"] is None and reopened["completion_evidence"] is None
    assert proof["history"][-1]["reason"] == case["reopen_reason"]
    assert {"Schedule", "ScheduleHistory", "BatchOperations", "Batches", "BatchMaterials", "OperationExecutionEvents", "WorkbenchProductionReports"} <= set(proof["preserved_tables"])
    assert case["unknown_key"] in {r["request_key"] for r in proof["receipts"]}


def test_dashboard_test_support_python38_syntax():
    for name in ("test_dashboard_widgets.py", "dashboard_widgets_support.py"):
        ast.parse((HERE / name).read_text(encoding="utf-8"), feature_version=(3, 8))
