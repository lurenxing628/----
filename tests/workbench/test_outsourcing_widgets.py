"""DN actual Chromium109 input/click and database preservation evidence."""

import ast
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.workbench.outsourcing_widgets_support import serve
from tests.workbench.test_live_browser import runtime_tools

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


@pytest.mark.parametrize("legacy_source", [False, True])
def test_outsourcing_widgets(tmp_path, monkeypatch, legacy_source):
    output = Path(os.environ.get("OUTSOURCING_UI_OUTPUT", str(tmp_path / "outsourcing-ui"))).resolve()
    assert output != ROOT and ROOT not in output.parents
    output.mkdir(parents=True, exist_ok=True)
    print("OUTSOURCING_UI_ARTIFACTS " + str(output), flush=True)
    node, browser, modules = runtime_tools()
    with serve(tmp_path, output, monkeypatch, legacy_source=legacy_source) as config:
        run = subprocess.run([node, str(HERE / "outsourcing_widgets_probe.cjs"), str(output)], input=json.dumps(config),
                             text=True, capture_output=True, timeout=500,
                             env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser))
    assert run.returncode == 0, run.stdout + run.stderr + "\n" + str(output)
    report = json.loads((output / "outsourcing-ui.json").read_text(encoding="utf-8"))
    server = json.loads((output / "outsourcing-server.json").read_text(encoding="utf-8"))
    verify(report, server)
    print("OUTSOURCING_UI_VERIFIED " + str(output), flush=True)


def verify(report, server):
    assert report["browser"].startswith("109.") and report["compile_global_build"] is False
    assert len(report["cases"]) == 4 and report["errors"] == report["external"] == []
    assert report["restarts"] == 4 and report["contract_rejections"] >= 10
    assert len(report["boundaries"]) >= 10 and all(report["boundaries"].values())
    assert server["server_stopped"]
    assert hashlib.sha256(Path(server["baseline_database"]).read_bytes()).hexdigest() == server["baseline_sha256"]
    for source in report["sources"]:
        assert hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() == source["sha256"]
    for case in report["cases"]:
        proof = next(p for p in server["proofs"] if p["case"] == case["name"])
        assert len(proof["headers"]) == 3 and len(proof["facts"]) == len(proof["receipts"]) == 8
        expected = sum(len(json.loads(h["origin_json"])["operation_refs"]) for h in proof["headers"]) if report["legacy_source"] else 0
        assert len(proof["source_confirmations"]) == expected
        assert "WorkbenchOutsourcingOperationOrigins" in proof["preserved_tables"]
        assert "WorkbenchTemplateLineageEvents" in proof["preserved_tables"]
        facts = [r for r in proof["facts"] if r["outsourcing_ref"] == case["merged_ref"]]
        assert [r["confirmed_state"] for r in facts] == ["in_transit", "returned", "returned", "returned", "awaiting_confirmation", "returned"]
        assert facts[-1]["request_key"] == case["unknown_key"]
        assert facts[3]["planned"] == "2026-09-11T12:00:00" and facts[4]["returned"] is None
        assert {"Schedule", "ScheduleHistory", "BatchOperations", "Batches", "OperationExecutionEvents", "WorkbenchProductionReports", "WorkbenchProductionReportRevisions"} <= set(proof["preserved_tables"])
        assert proof["plan_rows"] == proof["execution_rows"] == 1
        for name in proof["preserved_tables"]:
            assert proof["table_proofs"][name]["before_sha256"] == proof["table_proofs"][name]["after_sha256"]
    for name in ("lost", "drift", "rollback", "missing"):
        proof = next(p for p in server["proofs"] if p["case"] == name)
        assert proof["facts"] == proof["headers"] == proof["receipts"] == []
    assert all(row["changed_tables"] == [] for row in server["journal"] if row["method"] == "GET" or row["path"].endswith("/preview"))


def test_outsourcing_widgets_python38_syntax():
    for name in ("test_outsourcing_widgets.py", "outsourcing_widgets_support.py"):
        ast.parse((HERE / name).read_text(encoding="utf-8"), feature_version=(3, 8))
