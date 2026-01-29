from __future__ import annotations

import sqlite3


def run(conn: sqlite3.Connection, logger=None) -> None:
    """
    v2 迁移：把历史 WorkCalendar.day_type='weekend' 统一写成 'holiday'。
    - 幂等：可重复执行
    - 不改表结构，仅做数据修正
    """
    cur = conn.execute("UPDATE WorkCalendar SET day_type='holiday' WHERE day_type='weekend'")
    changed = int(getattr(cur, "rowcount", 0) or 0)
    if changed and logger:
        try:
            logger.warning(f"数据库迁移 v2：已将 WorkCalendar.day_type 的 weekend 统一为 holiday（影响行数={changed}）。")
        except Exception:
            pass

