"""ER: real SQLite/HTTP payloads plus opt-in full-workbench merged-cycle UI."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.workbench.merged_cycle_projection_support import merged_cycle_application

HERE = Path(__file__).resolve().parent


def contract(api, mutate=False):
    node = shutil.which("node")
    assert node, "Node is required to verify the production ProcessContract.js"
    before = api.snapshot()
    raw = api.detail()
    result = subprocess.run([node, str(HERE / "merged_cycle_ui_contract.cjs")],
                            input=json.dumps({"raw": raw, "mutate": mutate}), text=True,
                            capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert api.snapshot() == before
    return json.loads(result.stdout)


def test_merged_cycle_exact_frontend_contract(merged_cycle_api):
    result = contract(merged_cycle_api, mutate=True)
    assert len(result["rejected"]) == 26


@pytest.mark.parametrize("change", [
    "UPDATE ExternalGroups SET total_days=NULL WHERE group_id='PROC-G'",
    "UPDATE ExternalGroups SET total_days='bad' WHERE group_id='PROC-G'",
    "UPDATE ExternalGroups SET merge_mode='separate' WHERE group_id='PROC-G'",
    "UPDATE ExternalGroups SET merge_mode='unknown' WHERE group_id='PROC-G'",
    "UPDATE ExternalGroups SET part_no='PROC-002' WHERE group_id='PROC-G'",
    "UPDATE ExternalGroups SET start_seq=21 WHERE group_id='PROC-G'",
    "UPDATE ExternalGroups SET start_seq='bad' WHERE group_id='PROC-G'",
    "UPDATE PartOperations SET source='internal' WHERE part_no='PROC-001' AND seq=25",
    "UPDATE PartOperations SET part_no='PROC-002' WHERE part_no='PROC-001' AND seq=25",
    "UPDATE PartOperations SET ext_days=-1 WHERE part_no='PROC-001' AND seq=20",
    "UPDATE PartOperations SET ext_days=3.25 WHERE part_no='PROC-001' AND seq=20",
    "UPDATE PartOperations SET supplier_id=NULL WHERE part_no='PROC-001' AND seq=20",
    "UPDATE PartOperations SET setup_hours=-1 WHERE part_no='PROC-001' AND seq=20",
    "UPDATE PartOperations SET status='deleted',seq=99,source='internal' WHERE part_no='PROC-001' AND seq=25",
])
def test_real_damaged_facts_remain_displayable(merged_cycle_api, change):
    merged_cycle_api.execute(change)
    assert contract(merged_cycle_api)["accepted"]


@pytest.mark.skipif(os.environ.get("ER_RUN_BROWSER") != "1", reason="Opt-in isolated Chrome109 full workbench")
def test_merged_cycle_real_workbench_browser():
    from tests.workbench.merged_cycle_ui_runner import run_probe

    root, result = run_probe()
    assert not result.get("runner_error"), str(root) + str(result.get("runner_error", ""))
    assert "forced_kill" not in result, str(root)
    assert result["server_returncode"] == 0, str(root)
    assert result["probe_returncode"] == 0, str(root / "er-probe.log")
    assert result["isolation"]["stopped"] and result["isolation"]["assets_unchanged"]
    assert result["isolation"]["isolation_violations"] == []
    report = result["probe"]
    assert report["summary"]["cases"] == 40 and report["summary"]["failed"] == 0
    assert len(report["states"]) == 4
    assert report["pageerrors"] == report["external"] == report["http_errors"] == report["console"] == []
    assert all(not item["changes"] for item in report["oracles"] if item["policy"] == "read")
    for shot in report["screenshots"]:
        if shot["layout"]["scope"] != "no-active-dialog":
            assert shot["contrast"]["failures"] == [], shot["file"]
    for candidate in report["assets"]["candidates"]:
        assert hashlib.sha256((HERE.parents[1] / candidate["source"]).read_bytes()).hexdigest() == candidate["source_sha256"]
        assert hashlib.sha256(Path(candidate["static"]).read_bytes()).hexdigest() == candidate["candidate_sha256"]
    print("ER_VERIFIED " + str(root), flush=True)
