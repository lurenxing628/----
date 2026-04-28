from __future__ import annotations

import sqlite3

from data.repositories.machine_downtime_repo import MachineDowntimeRepository


def test_list_active_after_returns_only_active_rows_ending_after_start_ordered() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE MachineDowntimes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            scope_type TEXT DEFAULT 'machine',
            scope_value TEXT,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            reason_code TEXT,
            reason_detail TEXT,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    rows = [
        ("MC_1", "2026-01-01 07:30:00", "2026-01-01 08:30:00", "active"),
        ("MC_1", "2026-01-01 12:00:00", "2026-01-01 13:00:00", "active"),
        ("MC_1", "2026-01-01 09:00:00", "2026-01-01 10:00:00", "active"),
        ("MC_1", "2026-01-01 07:00:00", "2026-01-01 08:00:00", "active"),
        ("MC_1", "2026-01-01 14:00:00", "2026-01-01 15:00:00", "cancelled"),
        ("MC_2", "2026-01-01 09:00:00", "2026-01-01 10:00:00", "active"),
    ]
    conn.executemany(
        """
        INSERT INTO MachineDowntimes(machine_id, start_time, end_time, status)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )

    try:
        found = MachineDowntimeRepository(conn).list_active_after("MC_1", "2026-01-01 08:00:00")
    finally:
        conn.close()

    assert [(item.start_time, item.end_time, item.status) for item in found] == [
        ("2026-01-01 07:30:00", "2026-01-01 08:30:00", "active"),
        ("2026-01-01 09:00:00", "2026-01-01 10:00:00", "active"),
        ("2026-01-01 12:00:00", "2026-01-01 13:00:00", "active"),
    ]
