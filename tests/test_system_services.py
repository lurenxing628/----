from __future__ import annotations

import sqlite3

from core.services.system.operation_log_service import OperationLogService
from core.services.system.system_config_service import SystemConfigService
from core.services.system.system_job_state_query_service import SystemJobStateQueryService


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _create_operation_logs(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE OperationLogs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          log_time TEXT DEFAULT CURRENT_TIMESTAMP,
          log_level TEXT,
          module TEXT,
          action TEXT,
          target_type TEXT,
          target_id TEXT,
          operator TEXT,
          detail TEXT,
          error_code TEXT,
          error_message TEXT
        )
        """
    )
    conn.commit()


def _create_system_job_state(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE SystemJobState (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          job_key TEXT UNIQUE,
          last_run_time TEXT,
          last_run_detail TEXT,
          updated_at TEXT
        )
        """
    )
    conn.commit()


def _create_system_config(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE SystemConfig (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          config_key TEXT UNIQUE,
          config_value TEXT,
          description TEXT,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()


def test_operation_log_service_list_and_delete() -> None:
    conn = _mem_conn()
    _create_operation_logs(conn)

    conn.executemany(
        """
        INSERT INTO OperationLogs
        (log_level, module, action, target_type, target_id, operator, detail, error_code, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("INFO", "system", "a1", "t", "1", "u", "{}", None, None),
            ("WARN", "plugins", "a2", "t", "2", "u", "{}", None, None),
            ("INFO", "system", "a3", "t", "3", "u", "{}", None, None),
        ],
    )
    conn.commit()

    svc = OperationLogService(conn)

    all_logs = svc.list_recent(limit=10)
    assert len(all_logs) == 3

    sys_logs = svc.list_recent(limit=10, module="system")
    assert len(sys_logs) == 2
    assert all(l.module == "system" for l in sys_logs)

    lid = all_logs[0].id
    assert isinstance(lid, int) and lid > 0
    assert svc.delete_by_id(lid) == 1
    assert svc.delete_by_id(lid) == 0

    remaining = svc.list_recent(limit=10)
    assert len(remaining) == 2

    ids = [int(l.id) for l in remaining if isinstance(l.id, int)]
    assert svc.delete_by_ids(ids) == 2
    assert svc.list_recent(limit=10) == []


def test_system_job_state_query_service_get_and_map() -> None:
    conn = _mem_conn()
    _create_system_job_state(conn)

    conn.execute(
        "INSERT INTO SystemJobState(job_key, last_run_time, last_run_detail, updated_at) VALUES (?, ?, ?, ?)",
        ("auto_backup", "2026-03-01 10:00:00", '{"ok": 1}', "2026-03-01 10:00:00"),
    )
    conn.commit()

    q = SystemJobStateQueryService(conn)

    st = q.get("auto_backup")
    assert st is not None
    assert st.job_key == "auto_backup"
    assert st.last_run_time == "2026-03-01 10:00:00"

    keys = ["auto_backup", "auto_log_cleanup"]
    m = {k: q.get(k) for k in keys}
    assert set(m.keys()) == set(keys)
    assert m["auto_backup"] is not None
    assert m["auto_log_cleanup"] is None


def test_system_config_service_get_value() -> None:
    conn = _mem_conn()
    _create_system_config(conn)

    svc = SystemConfigService(conn)

    assert svc.get_value("ui_mode", default=None) is None
    assert svc.get_value("ui_mode", default="v2") == "v2"

    svc.set_value("ui_mode", "v1", description=None)

    assert svc.get_value("ui_mode", default="v2") == "v1"

