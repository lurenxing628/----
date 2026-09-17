"""Original browser System records survive a real process change without tokens."""

import json
import shutil
from concurrent.futures import ThreadPoolExecutor

import pytest

from core.infrastructure.backup import BackupManager
from tests.workbench.final_operations_seed import seed
from tests.workbench.final_operations_support import OperationsHost
from tests.workbench.system_restore_entrypoint_support import wait_for
from tests.workbench.test_final_operations_restore import _restart_audit_only


@pytest.mark.parametrize("kind", ["backups", "logs"])
@pytest.mark.parametrize("width,theme", [(1920, "dark")])
def test_final_operations_system_records_after_actual_restart(tmp_path, kind, width, theme):
    host = OperationsHost(tmp_path / "system-new-process")
    seed(host.root)
    manager = BackupManager(str(host.path), str(host.backups))
    for index in range(15):
        manager.backup(suffix=f"manual_F-SR{index:02d}")
    try:
        host.start()
        wait_for(lambda: host.stored("SELECT state FROM WorkbenchRunJobs")[0]["state"] == "complete", timeout=60)
        first_pid, first_port, original = host.process.pid, host.port, host.hashes()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(host.probe, "system-restart", width, theme, active_kind=kind, restart_dir=str(host.root))
            wait_for(lambda: (host.root / "browser-restart-request.json").exists() or future.done(), timeout=80)
            if future.done():
                future.result()
            assert host.hashes() == original
            host.stop()
            assert host.hashes() == original
            shutil.copyfile(str(host.path), str(host.root / "stage-restored-before-restart.db"))
            host.start(reuse_port=True)
            shutil.copyfile(str(host.path), str(host.root / "stage-after-restart-before-read.db"))
            audit, after_start = _restart_audit_only(host.root), host.hashes()
            pids = {"first_pid": first_pid, "second_pid": host.process.pid, "first_port": first_port, "second_port": host.port}
            (host.root / "browser-restart-resume.json").write_text(json.dumps(pids), encoding="utf-8")
            report = future.result(timeout=100)
        assert host.hashes() == after_start
        host.stop()
        assert host.hashes() == after_start
        assert all(not json.loads(path.read_text())["violations"] for path in host.root.glob("process-evidence-*.json"))
        (host.root / "system-record-restart-proof.json").write_text(json.dumps({**pids, "original": original,
            "after_start": after_start, "startup_only": audit, "before": report["before_restart"],
            "after": report["after_restart"], "original_file": report["original_file"], "rebound_file": report["rebound_file"]}, indent=2), encoding="utf-8")
    finally:
        host.close()
