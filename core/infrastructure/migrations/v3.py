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
    except sqlite3.OperationalError as e:
        msg = str(e).lower()
        # 仅在“表/列不存在”等可预期场景跳过；其它错误必须向上抛出（触发事务回滚与备份恢复）
        if "no such table" in msg or "no such column" in msg:
            if logger:
                try:
                    logger.warning(f"数据库迁移 v3：OperatorCalendar 不存在，已跳过（{e}）。")
                except Exception:
                    pass
            return
        raise

