"""Real cleanup audit and complete read-only maintenance controls in the full app."""

import json
import os
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from core.infrastructure.backup import BackupManager
from core.infrastructure.database import get_connection
from core.infrastructure.logging import OperationLogger
from core.services.system.maintenance.cleanup_task import maybe_run_auto_backup_cleanup
from core.services.system.system_maintenance_service import SystemMaintenanceService
from data.repositories.system_job_state_repo import SystemJobStateRepository
from tests.workbench.final_operations_seed import seed
from tests.workbench.final_operations_support import OperationsHost
from tests.workbench.system_restore_entrypoint_support import wait_for


def test_final_operations_real_cleanup_and_maintenance_read_controls(tmp_path):
    host = OperationsHost(tmp_path / "maintenance-read-controls")
    seed(host.root)
    manager = BackupManager(str(host.path), str(host.backups))
    files = [Path(manager.backup(suffix=("manual", "auto", "before_restore")[index % 3] + f"_F_{index:02d}")) for index in range(15)]
    old = (datetime.now() - timedelta(days=40)).timestamp()
    os.utime(str(files[0]), (old, old))
    with closing(get_connection(str(host.path))) as conn:
        ran, result = maybe_run_auto_backup_cleanup(conn, job_repo=SystemJobStateRepository(conn), now=datetime.now(),
            interval_minutes=5, backup_dir=str(host.backups), keep_days=7, max_backup_delete_per_run=2,
            job_key="auto_backup_cleanup", op_logger=OperationLogger(conn), is_due_fn=SystemMaintenanceService._is_due,
            fmt_db_dt_fn=lambda value: value.strftime("%Y-%m-%d %H:%M:%S"), min_keep_backups=2)
        assert ran and result["removed_count"] == 1 and result["oplog_persisted"] and result["job_state_persisted"]
        conn.commit()
    assert not files[0].exists() and all(path.exists() for path in files[1:])
    try:
        host.start()
        wait_for(lambda: host.stored("SELECT state FROM WorkbenchRunJobs")[0]["state"] == "complete", timeout=60)
        before = host.hashes()
        report = host.probe("read-controls")
        assert report["cleanup_event"]["file_capabilities"] == {"download": False, "restore": False, "delete": False}
        assert not [row for row in report["responses"] if row["method"] not in ("GET", "HEAD")]
        assert host.hashes() == before
        host.stop()
        assert host.hashes() == before
        evidence = json.loads((host.root / "process-evidence.json").read_text())
        assert not evidence["violations"]
        (host.root / "read-only-proof.json").write_text(json.dumps({"cleanup": result, "retained": before,
            "http_writes": [], "source_binding": evidence["source_binding"]}), encoding="utf-8")
    finally:
        host.close()
