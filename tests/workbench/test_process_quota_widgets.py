"""DG browser input -> real calibration lock -> file import -> original receipt."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from core.services.workbench.production_report import WorkbenchProductionReportService
from tests.workbench.process_quota_protection_support import quota_case as _quota_case  # noqa: F401
from tests.workbench.process_quota_widgets_support import serve
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.test_template_lineage_support import lineage_case as _lineage_case  # noqa: F401

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


@pytest.fixture(autouse=True)
def live_report_clock(lineage_case):
    # Run before quota_case creates reports; the reusable ledger defaults to noon.
    lineage_case.writer = WorkbenchProductionReportService(lineage_case.conn)


def test_process_quota_widgets(quota_case, tmp_path):
    output = Path(os.environ.get("PROCESS_QUOTA_UI_OUTPUT", str(tmp_path / "dg-browser-evidence"))).resolve()
    assert output != ROOT and ROOT not in output.parents
    output.mkdir(parents=True, exist_ok=True)
    node, browser, modules = runtime_tools()
    print("PROCESS_QUOTA_UI_ARTIFACTS " + str(output), flush=True)
    with serve(quota_case, output) as config:
        run = subprocess.run([node, str(HERE / "process_quota_widgets_probe.cjs"), str(output)],
            cwd=str(ROOT), input=json.dumps(config), text=True, capture_output=True, timeout=360,
            env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser))
    assert run.returncode == 0, run.stdout + run.stderr + "\n" + str(output)
    report = json.loads((output / "process-quota-ui.json").read_text(encoding="utf-8"))
    server = json.loads((output / "process-quota-server.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.") and report["global_build"] is False
    assert len(report["cases"]) == 8 and report["refreshes"] == 8
    assert report["errors"] == report["external"] == [] and report["contract_rejections"] >= 12
    assert report["setup_equal"] and report["setup_blank"] and report["noop"] and report["drift"]
    assert report["lost_response_recovered"] and server["server_stopped"]
    for row in report["sources"]:
        assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"], row["path"]
    for case in report["cases"]:
        proof = next(row for row in server["proofs"] if row["case"] == case["name"])
        assert len(proof["locks"]) == len(proof["audits"]) == 1
        assert proof["audits"][0]["reason"] == case["reason"]
        assert proof["templates"] == [{"seq": 1, "setup_hours": 0.0, "unit_hours": 3.0},
            {"seq": 2, "setup_hours": 0.5, "unit_hours": 8.0 if case["layout"] == "mixed" else 7.0}]
        receipts = [row for row in proof["receipts"] if row["request_key"] == case["request_key"]]
        assert len(receipts) == 1 and json.loads(receipts[0]["outcome_json"])["data"] == case["receipt"]["data"]
        requests = [row for row in server["journal"] if row["case"] == case["name"]]
        writes = [row for row in requests if row["path"].endswith("/hours/confirm")]
        sent = [row for row in report["responses"] if row["case"] == case["name"] and row["path"].endswith("/hours/confirm")]
        assert len(writes) == len(sent) and writes
        assert all(row["input"] == sent[0]["input"] for row in sent)
        assert sent[0]["input"]["request_key"] == case["request_key"]
        assert all(row["request_key"] == case["request_key"] for row in writes)
        assert sum(not row["payload"]["replayed"] for row in writes) == 1
        assert all(not row["changed_tables"] for row in writes if row["payload"]["replayed"])
        if case["layout"] == "allskip":
            assert writes[0]["changed_tables"] == ["WorkbenchCommandReceipts"]
        assert any(row["path"].endswith("/commands/" + case["request_key"]) and row["payload"]["replayed"] for row in requests)
        assert {"Batches", "BatchOperations", "Schedule", "ScheduleHistory", "WorkbenchProductionReports",
                "WorkbenchProductionReportRevisions", "WorkbenchProcessOperationConfirmations"} <= set(proof["preserved_tables"])
    setup = next(row for row in server["proofs"] if row["case"] == "setup")
    assert setup["templates"][0] == {"seq": 1, "setup_hours": 10.0, "unit_hours": 3.0}
    assert all(not row["changed_tables"] for row in server["journal"] if row["method"] == "GET" or row["status"] != 200 or row["path"].endswith("preview"))
    print("PROCESS_QUOTA_UI_VERIFIED " + str(output), flush=True)
