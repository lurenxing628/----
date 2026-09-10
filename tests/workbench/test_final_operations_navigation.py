"""Same browser page and origin across an actual main-process replacement."""

import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest

from core.infrastructure.database import get_connection
from tests.workbench.dashboard_support import follow
from tests.workbench.final_operations_seed import seed
from tests.workbench.final_operations_support import OperationsHost
from tests.workbench.run_jobs_support import JobCase
from tests.workbench.system_restore_entrypoint_support import wait_for
from tests.workbench.test_final_operations_restore import _restart_audit_only


def _prepare(host):
    seed(host.root)
    with closing(get_connection(str(host.path))) as conn:
        case = JobCase(conn)
        for number in range(25):
            case.batch(f"F-R2{number:02d}", part_name="F restart exact scope", ready_status="no")
        conn.commit()
    host.start()
    wait_for(lambda: host.stored("SELECT state FROM WorkbenchRunJobs")[0]["state"] == "complete", timeout=60)
    status, listed = host.request("/api/workbench/v1/dashboard?category=material&query=F-R2&sort=subject&direction=desc&size=100")
    assert status == 200 and listed["data"]["page"]["total"] == 25
    selected = listed["data"]["items"][10]
    ref = selected["item_ref"]
    receipts = []
    for number in range(26):
        status, current = host.request("/api/workbench/v1/dashboard?category=material&query=F-R2&size=100")
        assert status == 200
        item = next(row for row in current["data"]["items"] if row["item_ref"] == ref)
        status, result = host.request("/api/workbench/v1/dashboard/items/" + ref + "/transition", {
            "request_key": f"final-operations-navigation-history-{number:04d}",
            "write_token": item["write_context"]["write_token"],
            "input": follow(remark=f"F navigation actual history {number:04d}")}, "POST")
        assert status == 200 and result["result"] == "committed"
        receipts.append(result["receipt_ref"])
    return ref, receipts


@pytest.mark.parametrize("width,theme", [(1392, "light"), (1392, "dark"), (1920, "light"), (1920, "dark")])
def test_final_operations_dashboard_page_two_after_actual_restart(tmp_path, width, theme):
    host = OperationsHost(tmp_path / "dashboard-new-process")
    try:
        ref, receipts = _prepare(host)
        first_pid, first_port, original = host.process.pid, host.port, host.hashes()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(host.probe, "dashboard-restart", width, theme, item_ref=ref, restart_dir=str(host.root))
            wait_for(lambda: (host.root / "browser-restart-request.json").exists() or future.done(), timeout=80)
            if future.done():
                future.result()
            assert host.hashes() == original
            host.stop()
            assert host.hashes() == original
            shutil.copyfile(str(host.path), str(host.root / "stage-restored-before-restart.db"))
            host.start(reuse_port=True)
            shutil.copyfile(str(host.path), str(host.root / "stage-after-restart-before-read.db"))
            audit = _restart_audit_only(host.root)
            after_start = host.hashes()
            pids = {"first_pid": first_pid, "second_pid": host.process.pid, "first_port": first_port, "second_port": host.port}
            (host.root / "browser-restart-resume.json").write_text(json.dumps(pids), encoding="utf-8")
            report = future.result(timeout=100)
        assert host.hashes() == after_start
        host.stop()
        assert host.hashes() == after_start
        assert all(not json.loads(path.read_text())["violations"] for path in host.root.glob("process-evidence-*.json"))
        (host.root / "dashboard-restart-proof.json").write_text(json.dumps({**pids, "history_receipts": receipts,
            "original": original, "after_start": after_start, "startup_only": audit,
            "before": report["before_restart"], "after": report["after_restart"]}, indent=2), encoding="utf-8")
    finally:
        host.close()


@pytest.mark.parametrize("width,theme", [(1392, "light"), (1392, "dark"), (1920, "light"), (1920, "dark")])
def test_final_operations_unlocatable_confirmation_and_original_return(tmp_path, width, theme):
    host = OperationsHost(tmp_path / "dashboard-original-object")
    seed(host.root)
    try:
        host.start()
        wait_for(lambda: host.stored("SELECT state FROM WorkbenchRunJobs")[0]["state"] == "complete", timeout=60)
        ref, original_plan, receipts = None, None, []
        for number in range(26):
            status, listed = host.request("/api/workbench/v1/dashboard?category=delivery")
            assert status == 200
            item = listed["data"]["items"][0]
            ref, original_plan = item["item_ref"], item["source"]["plan_ref"]
            status, result = host.request("/api/workbench/v1/dashboard/items/" + ref + "/transition", {
                "request_key": f"final-operations-unlocatable-history-{number:04d}",
                "write_token": item["write_context"]["write_token"],
                "input": follow(remark=f"F original source retained {number:04d}")}, "POST")
            assert status == 200 and result["result"] == "committed"
            receipts.append(result["receipt_ref"])
        host.stop()
        with closing(get_connection(str(host.path))) as conn:
            op = conn.execute("SELECT id FROM BatchOperations WHERE batch_id='FQ1'").fetchone()[0]
            conn.execute("INSERT INTO ScheduleHistory(version,strategy,result_status,result_summary,schedule_time) "
                         "VALUES (2,'F-replacement-formal','success',?,'2026-09-10T12:00:00')", (json.dumps({"scheduled_ops": 1}),))
            conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) "
                         "VALUES (2,?,'M1','O1','2026-09-09T12:00:00','2026-09-09T12:45:00')", (op,))
            conn.commit()
        host.start()
        before = host.hashes()
        report = host.probe("dashboard-unlocatable", width, theme, item_ref=ref, original_plan_ref=original_plan)
        assert host.hashes() == before
        host.stop()
        assert host.hashes() == before
        assert all(not json.loads(path.read_text())["violations"] for path in host.root.glob("process-evidence-*.json"))
        (host.root / "unlocatable-readonly-proof.json").write_text(json.dumps({"unchanged_database_backups_journal": before,
            "original_history_receipts": receipts, "dismissals": report["dismissals"], "item": report["unlocatable"],
            "exact_navigation": report["exact_navigation"], "overview_navigation": report["overview_navigation"]}, indent=2), encoding="utf-8")
    finally:
        host.close()
