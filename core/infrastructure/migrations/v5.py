from __future__ import annotations

import sqlite3

from .common import fallback_log


def _run_update(conn: sqlite3.Connection, sql: str, *, label: str, logger=None) -> None:
    try:
        cur = conn.execute(sql)
    except sqlite3.OperationalError as e:
        msg = str(e).lower()
        if "no such table" in msg or "no such column" in msg:
            if logger:
                fallback_log(logger, "warning", f"数据库迁移 v5：{label} 已跳过（{e}）。")
            return
        raise
    changed = int(getattr(cur, "rowcount", 0) or 0)
    if changed and logger:
        fallback_log(logger, "warning", f"数据库迁移 v5：已修正 {label}（影响行数={changed}）。")


def run(conn: sqlite3.Connection, logger=None) -> None:
    _run_update(
        conn,
        """
        UPDATE OperatorMachine
        SET skill_level = CASE
            WHEN skill_level IS NULL OR TRIM(CAST(skill_level AS TEXT)) = '' THEN 'normal'
            WHEN LOWER(TRIM(CAST(skill_level AS TEXT))) IN ('expert', 'high', 'skilled') THEN 'expert'
            WHEN TRIM(CAST(skill_level AS TEXT)) IN ('熟练', '高级', '专家') THEN 'expert'
            WHEN LOWER(TRIM(CAST(skill_level AS TEXT))) = 'normal' THEN 'normal'
            WHEN TRIM(CAST(skill_level AS TEXT)) IN ('普通', '一般', '中级') THEN 'normal'
            WHEN LOWER(TRIM(CAST(skill_level AS TEXT))) IN ('beginner', 'low') THEN 'beginner'
            WHEN TRIM(CAST(skill_level AS TEXT)) IN ('初级', '新手') THEN 'beginner'
            ELSE 'normal'
        END
        WHERE COALESCE(CAST(skill_level AS TEXT), '') <> CASE
            WHEN skill_level IS NULL OR TRIM(CAST(skill_level AS TEXT)) = '' THEN 'normal'
            WHEN LOWER(TRIM(CAST(skill_level AS TEXT))) IN ('expert', 'high', 'skilled') THEN 'expert'
            WHEN TRIM(CAST(skill_level AS TEXT)) IN ('熟练', '高级', '专家') THEN 'expert'
            WHEN LOWER(TRIM(CAST(skill_level AS TEXT))) = 'normal' THEN 'normal'
            WHEN TRIM(CAST(skill_level AS TEXT)) IN ('普通', '一般', '中级') THEN 'normal'
            WHEN LOWER(TRIM(CAST(skill_level AS TEXT))) IN ('beginner', 'low') THEN 'beginner'
            WHEN TRIM(CAST(skill_level AS TEXT)) IN ('初级', '新手') THEN 'beginner'
            ELSE 'normal'
        END
        """,
        label="OperatorMachine.skill_level",
        logger=logger,
    )
    _run_update(
        conn,
        """
        UPDATE OperatorMachine
        SET is_primary = CASE
            WHEN is_primary IS NULL OR TRIM(CAST(is_primary AS TEXT)) = '' THEN 'no'
            WHEN LOWER(TRIM(CAST(is_primary AS TEXT))) IN ('yes', 'y', 'true', '1', 'on') THEN 'yes'
            WHEN TRIM(CAST(is_primary AS TEXT)) IN ('是', '主操', '主') THEN 'yes'
            WHEN LOWER(TRIM(CAST(is_primary AS TEXT))) IN ('no', 'n', 'false', '0', 'off') THEN 'no'
            WHEN TRIM(CAST(is_primary AS TEXT)) IN ('否', '非主操', '非主') THEN 'no'
            ELSE 'no'
        END
        WHERE COALESCE(CAST(is_primary AS TEXT), '') <> CASE
            WHEN is_primary IS NULL OR TRIM(CAST(is_primary AS TEXT)) = '' THEN 'no'
            WHEN LOWER(TRIM(CAST(is_primary AS TEXT))) IN ('yes', 'y', 'true', '1', 'on') THEN 'yes'
            WHEN TRIM(CAST(is_primary AS TEXT)) IN ('是', '主操', '主') THEN 'yes'
            WHEN LOWER(TRIM(CAST(is_primary AS TEXT))) IN ('no', 'n', 'false', '0', 'off') THEN 'no'
            WHEN TRIM(CAST(is_primary AS TEXT)) IN ('否', '非主操', '非主') THEN 'no'
            ELSE 'no'
        END
        """,
        label="OperatorMachine.is_primary",
        logger=logger,
    )
