"""Real CU adoption UI, Chrome 109 input and durable SQLite preservation evidence."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from tests.workbench.calibration_adoption_widgets_support import serve
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.test_template_lineage_support import lineage_case as _lineage_case  # noqa: F401

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def test_calibration_adoption_widgets(lineage_case, tmp_path):
    output = Path(os.environ.get("CALIBRATION_ADOPTION_UI_OUTPUT", str(tmp_path / "browser-evidence"))).resolve()
    assert output != ROOT and ROOT not in output.parents
    output.mkdir(parents=True, exist_ok=True)
    node, browser, modules = runtime_tools()
    print("CALIBRATION_ADOPTION_UI_ARTIFACTS " + str(output), flush=True)
    with serve(lineage_case, output) as config:
        result = subprocess.run([node, str(HERE / "calibration_adoption_widgets_probe.cjs"), str(output)],
            input=json.dumps(config), text=True, capture_output=True, timeout=360,
            env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser))
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "calibration-adoption-ui.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.") and report["compile_global_build"] is False
    assert len(report["cases"]) == 4 and report["errors"] == report["external"] == []
    assert report["contract_rejections"] >= 10 and report["drift_blocked"] and report["cross_template_blocked"]
    assert report["disabled_reason"] and report["insufficient_reason"] and report["not_found_retained"]
    assert report["browser_restarts"] == 4 and len(report["downloads"]) == 4 and report["navigation_retained"]
    for source in report["sources"]:
        assert hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() == source["sha256"]
    server = json.loads((output / "calibration-adoption-server.json").read_text(encoding="utf-8"))
    assert server["server_stopped"] and len(server["mutations"]) == 1
    for case in report["cases"]:
        proof = next(row for row in server["proofs"] if row["case"] == case["name"])
        assert len(proof["audits"]) == len(proof["locks"]) == 1
        audit = proof["audits"][0]
        assert audit["request_key"] == case["request_key"] and audit["old_unit_hours"] == 2 and audit["new_unit_hours"] == 3
        assert audit["declared_operator"] == case["declared_operator"] and audit["confirmed"] == 1
        assert audit["reason"] == case["reason"] and audit["sample_count"] == 5
        assert {"Batches", "BatchOperations", "Schedule", "ScheduleHistory", "WorkbenchProductionReports", "WorkbenchProductionReportRevisions"} <= set(proof["preserved_tables"])
        assert case["geometry"]["width"] <= case["viewport"]["width"]
        # A fresh Python process has no preview-token registry; it must still resolve the original durable key.
        code = ("import json,sqlite3; from core.services.workbench.calibration_adoption import WorkbenchCalibrationAdoptionService; "
                "c=sqlite3.connect(" + repr(proof["database"]) + "); c.row_factory=sqlite3.Row; "
                "print(json.dumps(WorkbenchCalibrationAdoptionService(c).receipt(" + repr(audit["template_operation_ref"]) + "," + repr(audit["request_key"]) + "))); c.close()")
        restarted = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), text=True, capture_output=True, check=True)
        receipt = json.loads(restarted.stdout)
        assert receipt["replayed"] and receipt["data"]["request_key"] == audit["request_key"] and receipt["data"]["locked"]
    assert all(not row["changed"] for row in server["journal"] if not row["path"].endswith("/adopt"))
    print("CALIBRATION_ADOPTION_UI_VERIFIED " + str(output), flush=True)
