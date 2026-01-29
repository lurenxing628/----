from __future__ import annotations

import sqlite3


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """
    判断指定表是否存在指定列。

    说明：
    - SQLite: PRAGMA table_info(table)
    - 防御：异常时返回 False
    """
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        for r in rows:
            name = r["name"] if isinstance(r, sqlite3.Row) else r[1]
            if name == column:
                return True
        return False
    except Exception:
        return False

