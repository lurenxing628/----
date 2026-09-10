"""Actual in-flight process work and new-data retention after an old restore retry."""

import json
from contextlib import closing

from core.infrastructure.backup import BackupManager
from core.infrastructure.database import ensure_schema, get_connection
from tests.workbench.final_operations_support import REPO, OperationsHost
from tests.workbench.test_system_restore_entrypoint_support import wait_for


def test_final_operations_restore_waits_for_real_work_and_retains_later_data(tmp_path):
    host = OperationsHost(tmp_path / "restore-inflight", "pause-worker")
    ensure_schema(str(host.path), None, schema_path=str(REPO / "schema.sql"))
    with closing(get_connection(str(host.path))) as conn:
        conn.execute("INSERT INTO SystemConfig(config_key,config_value) VALUES ('FINAL_OPERATIONS','selected')")
        for key in ("auto_backup_enabled", "auto_backup_cleanup_enabled", "auto_log_cleanup_enabled"):
            conn.execute("INSERT INTO SystemConfig(config_key,config_value) VALUES (?,'no')", (key,))
        conn.commit()
    BackupManager(str(host.path), str(host.backups)).backup(suffix="F_selected_source")
    with closing(get_connection(str(host.path))) as conn:
        conn.execute("UPDATE SystemConfig SET config_value='current' WHERE config_key='FINAL_OPERATIONS'")
        conn.commit()
    try:
        host.start()
        wait_for(lambda: (host.root / "worker-entered").exists(), timeout=10)
        report = host.probe("restore", inflight=True)
        assert (host.root / "worker-computed").exists() and (host.root / "http-finalized").exists()
        operation = report["operation"]
        assert operation["state"] == "succeeded" and host.marker() == "selected"
        with closing(get_connection(str(host.backups / operation["protection_filename"]))) as conn:
            assert conn.execute("SELECT state FROM WorkbenchRunJobs").fetchone()[0] == "complete"
            assert conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidates").fetchone()[0] == 4
        first_pid = host.process.pid
        host.stop()
        host.mode = "normal"
        host.start()
        assert host.process.pid != first_pid
        status, config = host.request("/api/workbench/v1/system/config")
        assert status == 200
        new_values = {**config["data"]["values"], "auto_backup_interval_minutes": 73}
        body = {"request_key": "final-operations-after-restore-config-0001",
                "write_token": config["data"]["write_context"]["write_token"], "input": new_values}
        status, saved = host.request("/api/workbench/v1/system/config/save", body, "POST")
        assert status == 200 and saved["result"] == "committed"
        before_retry = host.hashes()
        status, replay = host.request("/api/workbench/v1/system/backups/restore", report["restore_request"], "POST")
        assert status == 200 and replay["data"]["operation"]["replayed"] is True
        assert replay["data"]["operation"]["job_ref"] == operation["job_ref"]
        assert replay["data"]["host"]["state"] == "ready"
        assert host.hashes() == before_retry
        expected = {key: str(value) for key, value in new_values.items()}
        readback = host.probe("config-readback", expected_config_fields=expected, new_data_after_restore=True)
        assert readback["config_restart_values"] == expected
        assert host.hashes() == before_retry
        host.stop()
        assert host.hashes() == before_retry
        evidence = json.loads((host.root / "process-evidence.json").read_text())
        assert not evidence["violations"]
        (host.root / "inflight-retention-proof.json").write_text(json.dumps({"inflight_order": report["inflight_order"],
            "first_pid": first_pid, "second_pid": evidence["pid"], "new_config_receipt": saved["receipt_ref"],
            "restore_retry": replay, "new_data_files_unchanged": before_retry}), encoding="utf-8")
    finally:
        host.close()
