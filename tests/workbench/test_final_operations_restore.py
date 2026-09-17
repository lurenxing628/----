"""Current full-build restore, read-only failure and owned process restart."""

import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from core.infrastructure.database import get_connection
from core.services.workbench.system_journal import file_fingerprint
from tests.workbench.final_operations_seed import seed
from tests.workbench.final_operations_support import OperationsHost

KEY = "final-operations-pending-restore-000001"


def _database_rows(path):
    with closing(sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {table: [dict(row) for row in conn.execute('SELECT * FROM "' + table.replace('"', '""') + '" ORDER BY rowid')]
                for table in tables}


def _restart_audit_only(root):
    before = _database_rows(root / "stage-restored-before-restart.db")
    after = _database_rows(root / "stage-after-restart-before-read.db")
    assert set(before) == set(after)
    assert {key: rows for key, rows in before.items() if key not in ("OperationLogs", "sqlite_sequence")} == {
        key: rows for key, rows in after.items() if key not in ("OperationLogs", "sqlite_sequence")}
    old, new = before["OperationLogs"], after["OperationLogs"]
    assert len(new) == len(old) + 1 and new[:len(old)] == old
    audit = new[-1]
    assert (audit["log_level"], audit["module"], audit["action"], audit["target_type"]) == ("INFO", "plugins", "load", "runtime")
    previous, current = ({row["name"]: row["seq"] for row in data["sqlite_sequence"]} for data in (before, after))
    assert current == {**previous, "OperationLogs": previous["OperationLogs"] + 1}
    return {"unchanged_tables": sorted(set(before) - {"OperationLogs", "sqlite_sequence"}), "new_startup_audit": audit}


@pytest.mark.parametrize("width,theme", [(1920, "light")])
def test_final_operations_restore_fullbuild_and_real_restart(tmp_path, width, theme):
    host = OperationsHost(tmp_path / "restore-host")
    seed(host.root)
    try:
        host.start()
        report = host.probe("restore", width, theme)
        operation = report["operation"]
        assert operation["state"] == "succeeded" and operation["database_origin"] == "selected_backup"
        assert host.marker() == "selected"
        protection = host.backups / operation["protection_filename"]
        with closing(get_connection(str(protection))) as conn:
            assert conn.execute("SELECT config_value FROM SystemConfig WHERE config_key='FINAL_OPERATIONS'").fetchone()[0] == "current"
        before = host.hashes()
        host.locked()
        host.stop()
        assert host.hashes() == before, "Post-restore exit must preserve all backup/database/journal files, not run exit backup"
        shutil.copyfile(str(host.path), str(host.root / "stage-restored-before-restart.db"))
        host.start()
        assert host.ready["runtime_ready"]
        after_start = host.hashes()
        shutil.copyfile(str(host.path), str(host.root / "stage-after-restart-before-read.db"))
        restart_proof = _restart_audit_only(host.root)
        assert {path: value for path, value in after_start.items() if path != str(host.path)} == {
            path: value for path, value in before.items() if path != str(host.path)}
        status, value = host.request("/api/workbench/v1/system/results/" + operation["request_key"])
        assert status == 200 and value["data"]["operation"]["job_ref"] == operation["job_ref"]
        assert value["data"]["operation"]["replayed"] is True
        assert host.marker() == "selected"
        event_report = host.probe("read-controls", width, theme, restored_job_ref=operation["job_ref"])
        assert event_report["restored_event"]["event_ref"] == operation["job_ref"]
        after_read = host.hashes()
        shutil.copyfile(str(host.path), str(host.root / "stage-after-event-read.db"))
        (host.root / "restart-stage-hashes.json").write_text(json.dumps({"restored": before, "after_start": after_start,
            "after_read": after_read, "restart_proof": restart_proof}, indent=2), encoding="utf-8")
        assert after_read == after_start
        host.stop()
        assert host.hashes() == after_read
        assert not json.loads((host.root / "process-evidence.json").read_text())["violations"]
    finally:
        host.close()


@pytest.mark.parametrize("mode,state,marker", [("verify-failure", "rolled_back", "current"), ("rollback-failure", "rollback_failed", "selected")])
def test_final_operations_restore_failures_keep_readonly_without_exit_overwrite(tmp_path, mode, state, marker):
    host = OperationsHost(tmp_path / "restore-failure", mode)
    seed(host.root)
    try:
        host.start()
        report = host.probe("restore", 1392, "dark", expected=state)
        assert host.marker() == marker
        before = host.hashes()
        host.stop()
        assert host.hashes() == before
        assert report["operation"]["state"] == state
    finally:
        host.close()


@pytest.mark.parametrize("corrupt", [False, True])
def test_final_operations_pending_or_corrupt_cold_start_never_opens_database(tmp_path, corrupt):
    host = OperationsHost(tmp_path / "cold-restore", "no-database")
    seed(host.root)
    source = Path(json.loads((host.root / "seed.json").read_text())["source"])
    row, _ = host.journal().begin(KEY, "restore", {})
    host.journal().record(row, "verifying", target={"filename": source.name, "sha256": file_fingerprint(str(source))})
    if corrupt:
        next(host.journal_dir.glob("*.json")).write_text("{", encoding="utf-8")
    before = host.hashes()
    try:
        host.start()
        report = host.probe("cold", 1392, "light", reference=KEY, corrupt=corrupt)
        assert report["diagnostic"]["database_checked_by_page"] is False
        assert host.hashes() == before
        host.stop()
        assert host.hashes() == before
        evidence = json.loads((host.root / "process-evidence.json").read_text())
        assert evidence["sqlite_connections"] == [] and evidence["violations"] == []
    finally:
        host.close()
