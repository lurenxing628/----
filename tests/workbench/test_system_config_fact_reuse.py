"""One raw configuration read and writes only for actual stored changes."""

import sqlite3

from core.services.system.system_config_service import SystemConfigService
from data.repositories.system_config_repo import SystemConfigRepository


def test_snapshot_preserves_presence_and_null_from_one_raw_read():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("CREATE TABLE SystemConfig(id INTEGER PRIMARY KEY,config_key TEXT UNIQUE,config_value TEXT,description TEXT,updated_at TEXT)")
        conn.execute("INSERT INTO SystemConfig(config_key,config_value) VALUES ('auto_backup_keep_days',NULL)")
        statements = []
        conn.set_trace_callback(statements.append)
        snapshot, stored = SystemConfigService(conn).snapshot_with_storage(7)
        assert stored == {"auto_backup_keep_days": None} and snapshot.auto_backup_keep_days == 7
        assert len([sql for sql in statements if sql.upper().startswith("SELECT")]) == 1
    finally:
        conn.close()


def test_unchanged_upsert_keeps_timestamp_and_does_not_write():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE SystemConfig(id INTEGER PRIMARY KEY,config_key TEXT UNIQUE,config_value TEXT,description TEXT,updated_at TEXT)")
        conn.execute("INSERT INTO SystemConfig(config_key,config_value,description,updated_at) VALUES ('key','value','note','2001-01-01')")
        repo, changes = SystemConfigRepository(conn), conn.total_changes
        repo.set("key", "value")
        assert conn.total_changes == changes
        assert conn.execute("SELECT updated_at FROM SystemConfig").fetchone()[0] == "2001-01-01"
        repo.set("key", "changed")
        assert conn.total_changes == changes + 1
    finally:
        conn.close()
