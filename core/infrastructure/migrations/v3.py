from __future__ import annotations

import sqlite3


def run(conn: sqlite3.Connection, logger=None) -> None:
    """
    v3 迁移：把历史 OperatorCalendar.day_type='weekend' 统一写成 'holiday'。
    - 幂等：可重复执行
    - 若表不存在（极端场景）：静默跳过（由 schema.sql 后续创建）
    """
    try:
        # 表不存在时 sqlite 会抛错；这里不阻断迁移版本推进
        cur = conn.execute("UPDATE OperatorCalendar SET day_type='holiday' WHERE day_type='weekend'")
        changed = int(getattr(cur, "rowcount", 0) or 0)
        if changed and logger:
            try:
                logger.warning(f"数据库迁移 v3：已将 OperatorCalendar.day_type 的 weekend 统一为 holiday（影响行数={changed}）。")
            except Exception:
                pass
    except Exception:
        # 不阻断：OperatorCalendar 由 schema.sql 创建；若不存在则跳过
        return

