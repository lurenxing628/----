"""Replacement and legacy identities fail closed; pending writes only look up."""

import json
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode

import pytest

from core.infrastructure.backup import BackupManager
from tests.workbench.final_operations_seed import seed
from tests.workbench.final_operations_support import OperationsHost
from tests.workbench.test_final_operations_restore import _database_rows, _restart_audit_only
from tests.workbench.test_system_restore_entrypoint_support import wait_for


def _unchanged_except_config(before, after):
    allowed = {"SystemConfig", "WorkbenchCommandReceipts", "OperationLogs", "sqlite_sequence"}
    assert {key: value for key, value in before.items() if key not in allowed} == {key: value for key, value in after.items() if key not in allowed}
    assert len(after["WorkbenchCommandReceipts"]) == len(before["WorkbenchCommandReceipts"]) + 1
    assert after["WorkbenchCommandReceipts"][-1]["action"] == "system.config.save"
    assert after["OperationLogs"][:-1] == before["OperationLogs"]


def _old_tokens_rejected(host, report):
    row = report["original_file"]
    filtered = {**report["before_restart"]["context"]["records"]["backups"]["filters"], "page": 2, "page_size": 10,
                "snapshot_ref": report["before_restart"]["snapshots"]["backups"]}
    query = urlencode(filtered)
    read_status, old_read = host.request("/api/workbench/v1/system/backups?" + query)
    assert read_status == 409 and old_read["error"]["code"] == "snapshot_stale"
    download_status, old_download = host.request("/api/workbench/v1/system/backups/" + row["backup_ref"] + "/download?" + query)
    assert download_status == 409 and old_download["error"]["code"] == "stale_write"
    actions = []
    for action in ("delete", "restore"):
        status, value = host.request("/api/workbench/v1/system/backups/" + action, {
            "request_key": "final-operations-expired-file-" + action + "-000001",
            "write_token": row["write_context"]["write_token"], "input": {"backup_ref": row["backup_ref"]}}, "POST")
        assert status == 409 and value["error"]["code"] == "stale_write"
        actions.append({"action": action, "status": status, "result": value})
    return {"read": old_read, "download": old_download, "actions": actions}


@pytest.mark.parametrize("case", ["replaced_file", "legacy_selection", "pending_config"])
def test_final_operations_system_recovery_identity_and_pending_request(tmp_path, case):
    host = OperationsHost(tmp_path / "system-recovery-edges")
    seed(host.root)
    manager = BackupManager(str(host.path), str(host.backups))
    now = time.time_ns()
    for index in range(15):
        path = manager.backup(suffix=f"manual_F-SR{index:02d}")
        stamp = now - (30 - index) * 1000000000
        os.utime(path, ns=(stamp, stamp))
    try:
        host.start()
        wait_for(lambda: host.stored("SELECT state FROM WorkbenchRunJobs")[0]["state"] == "complete", timeout=60)
        original, before_rows = host.hashes(), _database_rows(host.path)
        first_pid, first_port = host.process.pid, host.port
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(host.probe, "system-restart", active_kind="backups", recovery_case=case, restart_dir=str(host.root))
            marker = host.root / "browser-restart-request.json"
            wait_for(lambda: marker.exists() or future.done(), timeout=80)
            if future.done():
                future.result()
            prepared = json.loads(marker.read_text(encoding="utf-8"))
            if case == "pending_config":
                _unchanged_except_config(before_rows, _database_rows(host.path))
                assert prepared["committed_config"]["result"] == "committed"
            else:
                assert host.hashes() == original
            before_stop = host.hashes()
            host.stop()
            assert host.hashes() == before_stop
            replacement = None
            if case == "replaced_file":
                target = host.backups / prepared["original_file"]["filename"]
                old = target.stat()
                fresh = Path(manager.backup(suffix="manual_replacement_fixture"))
                assert fresh.read_bytes() != target.read_bytes()
                os.replace(str(fresh), str(target))
                os.utime(str(target), ns=(old.st_atime_ns, old.st_mtime_ns))
                replacement = {"filename": target.name, "old_inode": old.st_ino, "new_inode": target.stat().st_ino}
                assert replacement["old_inode"] != replacement["new_inode"]
            shutil.copyfile(str(host.path), str(host.root / "stage-restored-before-restart.db"))
            host.start(reuse_port=True)
            shutil.copyfile(str(host.path), str(host.root / "stage-after-restart-before-read.db"))
            audit, after_start = _restart_audit_only(host.root), host.hashes()
            negatives = _old_tokens_rejected(host, prepared)
            assert host.hashes() == after_start
            pids = {"first_pid": first_pid, "second_pid": host.process.pid, "first_port": first_port, "second_port": host.port}
            (host.root / "browser-restart-resume.json").write_text(json.dumps(pids), encoding="utf-8")
            report = future.result(timeout=100)
        assert host.hashes() == after_start
        host.stop()
        assert host.hashes() == after_start
        assert all(not json.loads(path.read_text())["violations"] for path in host.root.glob("process-evidence-*.json"))
        (host.root / "system-recovery-boundary-proof.json").write_text(json.dumps({**pids, "case": case,
            "original": original, "before_stop": before_stop, "after_start": after_start, "startup_only": audit,
            "negative_expired_tokens": negatives, "declared_fixture_replacement": replacement,
            "browser_writes": report["browser_writes"], "before": report["before_restart"], "after": report["after_restart"],
            "pending_after": report.get("pending_after_restart"), "original_receipt_lookup": report.get("original_receipt_lookup")}, indent=2), encoding="utf-8")
    finally:
        host.close()
