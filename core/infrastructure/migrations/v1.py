from __future__ import annotations

import sqlite3
from typing import Optional

from .common import column_exists, fallback_log, table_exists


def run(conn: sqlite3.Connection, logger=None) -> None:
    """
    v1 迁移：
    - 补齐 V1.1 关键字段（缺列补齐）
    - 一次性清洗 Batches 的日期字段（due_date / ready_date）
    """
    _ensure_columns(conn, logger=logger)
    _sanitize_batch_dates(conn, logger=logger)


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, ddl: str, logger=None) -> None:
    if not table_exists(conn, table):
        if logger:
            fallback_log(logger, "warning", f"数据库迁移 v1：{table} 表不存在，已跳过 {column} 补列。")
        return
    if column_exists(conn, table, column):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _ensure_columns(conn: sqlite3.Connection, logger=None) -> None:
    """
    轻量迁移（幂等）：为存量表补齐新增字段。

    说明：
    - SQLite 的 CREATE TABLE IF NOT EXISTS 不会修改既有表结构
    - 这里用 PRAGMA table_info + ALTER TABLE ADD COLUMN 做“缺列补齐”
    """
    # Batches.ready_date（齐套日期）
    _add_column_if_missing(conn, "Batches", "ready_date", "ready_date DATE", logger=logger)

    # Machines.category（设备类别）
    _add_column_if_missing(conn, "Machines", "category", "category TEXT", logger=logger)

    # MachineDowntimes.scope_type/scope_value（停机范围预留字段）
    _add_column_if_missing(
        conn,
        "MachineDowntimes",
        "scope_type",
        "scope_type TEXT DEFAULT 'machine'",
        logger=logger,
    )
    _add_column_if_missing(conn, "MachineDowntimes", "scope_value", "scope_value TEXT", logger=logger)

    # WorkCalendar.shift_start/shift_end（班次起止时间）
    _add_column_if_missing(conn, "WorkCalendar", "shift_start", "shift_start TEXT", logger=logger)
    _add_column_if_missing(conn, "WorkCalendar", "shift_end", "shift_end TEXT", logger=logger)

    # OperatorMachine.skill_level/is_primary（人机关联：技能等级/主操设备）
    _add_column_if_missing(
        conn,
        "OperatorMachine",
        "skill_level",
        "skill_level TEXT DEFAULT 'normal'",
        logger=logger,
    )
    _add_column_if_missing(
        conn,
        "OperatorMachine",
        "is_primary",
        "is_primary TEXT DEFAULT 'no'",
        logger=logger,
    )

    # 旧数据回填：将 NULL/空串统一为默认值（避免导出/排序出现空值）
    try:
        conn.execute(
            "UPDATE OperatorMachine SET skill_level = 'normal' "
            "WHERE skill_level IS NULL OR TRIM(CAST(skill_level AS TEXT)) = ''"
        )
    except sqlite3.OperationalError as e:
        msg = str(e).lower()
        if "no such table" in msg or "no such column" in msg:
            if logger:
                fallback_log(logger, "warning", f"数据库迁移 v1：OperatorMachine.skill_level 默认值回填已跳过（{e}）。")
        else:
            raise
    try:
        conn.execute(
            "UPDATE OperatorMachine SET is_primary = 'no' "
            "WHERE is_primary IS NULL OR TRIM(CAST(is_primary AS TEXT)) = ''"
        )
    except sqlite3.OperationalError as e:
        msg = str(e).lower()
        if "no such table" in msg or "no such column" in msg:
            if logger:
                fallback_log(logger, "warning", f"数据库迁移 v1：OperatorMachine.is_primary 默认值回填已跳过（{e}）。")
        else:
            raise


def _sanitize_batch_dates(conn: sqlite3.Connection, logger=None) -> None:
    """
    清洗 Batches 的 DATE 字段（due_date / ready_date）。

    背景：
    - V1 业务约定 DATE 字段使用 `YYYY-MM-DD`（开发文档与 schema.sql）
    - 存量 DB 可能因为 Excel 导入/手工写入导致不合法值（如 `2026`）
    - 不合法值会导致页面/算法无法正确处理；这里做一次性“最佳努力”规范化：
      - 支持：YYYY-MM-DD / YYYY/M/D / YYYY/MM/DD / 带时间的 YYYY-MM-DD HH:MM(:SS) / YYYY-MM-DDTHH:MM(:SS)
      - 无法解析：置为 NULL（避免误判）
    """
    try:
        rows = conn.execute(
            """
            SELECT batch_id, due_date, ready_date
            FROM Batches
            WHERE (due_date IS NOT NULL AND TRIM(CAST(due_date AS TEXT)) <> '')
               OR (ready_date IS NOT NULL AND TRIM(CAST(ready_date AS TEXT)) <> '')
            """
        ).fetchall()
    except sqlite3.OperationalError as e:
        msg = str(e).lower()
        if "no such table" in msg or "no such column" in msg:
            if logger:
                fallback_log(logger, "warning", f"数据库迁移 v1：Batches 表/列不存在，已跳过日期清洗（{e}）。")
            return
        raise

    if not rows:
        return

    import re
    from datetime import date

    def norm(value) -> Optional[str]:
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        s = s.replace("：", ":").replace("/", "-")
        # 若误写入了时间：只取日期部分（DATE 字段不存时分秒）
        if "T" in s:
            s = s.split("T", 1)[0]
        if " " in s:
            s = s.split(" ", 1)[0]
        # 仅接受 YYYY-M-D / YYYY-MM-DD（显式组装，避免依赖 strptime 的宽松/严格差异）
        m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
        if not m:
            return None
        try:
            y = int(m.group(1))
            mo = int(m.group(2))
            d = int(m.group(3))
            return date(y, mo, d).isoformat()
        except Exception:
            return None

    changed = 0
    changed_samples = []
    failed = 0
    failed_samples = []
    for r in rows:
        bid = r["batch_id"]
        old_due = r["due_date"]
        old_ready = r["ready_date"]
        new_due = norm(old_due)
        new_ready = norm(old_ready)

        # 只在发生变化时写入（避免无谓更新 updated_at）
        if (str(old_due).strip() if old_due is not None else None) == new_due and (
            str(old_ready).strip() if old_ready is not None else None
        ) == new_ready:
            continue

        try:
            conn.execute(
                "UPDATE Batches SET due_date = ?, ready_date = ? WHERE batch_id = ?",
                (new_due, new_ready, bid),
            )
            changed += 1
            if len(changed_samples) < 10:
                changed_samples.append(str(bid))
        except sqlite3.OperationalError:
            # 迁移中不应吞掉数据库级错误；抛出以触发事务回滚与备份恢复
            raise
        except sqlite3.Error:
            failed += 1
            if len(failed_samples) < 10:
                failed_samples.append(str(bid))
            continue

    if changed and logger:
        sample_text = "，".join(changed_samples)
        fallback_log(
            logger,
            "warning",
            f"已清洗 Batches 的日期字段（due_date/ready_date）：受影响批次数={changed}，样例批次号（最多10个）={sample_text}。",
        )

    if failed and logger:
        sample_text = "，".join(failed_samples)
        fallback_log(
            logger,
            "warning",
            f"Batches 日期字段清洗更新失败：失败批次数={failed}，样例批次号（最多10个）={sample_text}。",
        )
