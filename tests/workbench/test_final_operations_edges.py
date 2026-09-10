"""Actual history receipts, malformed stored config and filesystem failure UI."""

import json
from contextlib import closing

from core.infrastructure.database import get_connection
from tests.workbench.dashboard_support import follow
from tests.workbench.final_operations_seed import seed
from tests.workbench.final_operations_support import OperationsHost
from tests.workbench.system_restore_entrypoint_support import wait_for


def test_final_operations_history_and_real_storage_failure(tmp_path):
    host = OperationsHost(tmp_path / "operation-edges")
    seed(host.root)
    with closing(get_connection(str(host.path))) as conn:
        conn.execute("INSERT INTO SystemConfig(config_key,config_value) VALUES ('auto_backup_interval_minutes','invalid-F-stored')")
        conn.commit()
    try:
        host.start()
        wait_for(lambda: host.stored("SELECT state FROM WorkbenchRunJobs")[0]["state"] == "complete", timeout=60)
        history_receipts = []
        for index in range(26):
            status, listed = host.request("/api/workbench/v1/dashboard?category=delivery")
            assert status == 200
            item = listed["data"]["items"][0]
            status, result = host.request("/api/workbench/v1/dashboard/items/" + item["item_ref"] + "/transition",
                {"request_key": f"final-operations-history-{index:04d}", "write_token": item["write_context"]["write_token"],
                 "input": follow(remark=f"F actual receipt {index:04d}")}, "POST")
            assert status == 200 and result["result"] == "committed"
            history_receipts.append(result["receipt_ref"])
        original = {table: host.stored('SELECT * FROM "' + table + '" ORDER BY rowid') for table in (
            "SystemConfig", "Batches", "BatchOperations", "Schedule", "ScheduleHistory", "WorkbenchDashboardHistory", "WorkbenchCommandReceipts")}
        backups = {path.name: path.read_bytes() for path in host.backups.glob("*.db")}
        report = host.probe("edges")
        assert report["failed_create"]["data"]["operation"]["state"] == "recovery_required"
        for table, rows in original.items():
            assert host.stored('SELECT * FROM "' + table + '" ORDER BY rowid') == rows
        assert {path.name: path.read_bytes() for path in host.backups.glob("*.db")} == backups
        assert len(host.stored("SELECT * FROM WorkbenchDashboardHistory")) == 26
        host.stop()
        evidence = json.loads((host.root / "process-evidence.json").read_text())
        assert not evidence["violations"]
        (host.root / "edge-proof.json").write_text(json.dumps({"history_receipts": history_receipts,
            "unchanged_tables": list(original), "backup_files_unchanged": list(backups), "failed_create": report["failed_create"]}), encoding="utf-8")
    finally:
        host.close()
