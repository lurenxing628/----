from __future__ import annotations

import sqlite3
from typing import List, Optional, Tuple

from ..migration_common import MigrationOutcome, fallback_log


def _is_expected_missing_schema_error(e: Exception) -> bool:
    if not isinstance(e, sqlite3.OperationalError):
        return False
    msg = str(e).lower()
    return "no such table" in msg or "no such column" in msg


def _log_skipped_schema(logger, table: str, field: str, error: Exception) -> None:
    if logger:
        fallback_log(logger, "warning", f"数据库迁移 v4：{table}.{field} 清洗已跳过（{error}）。")


def _fetch_changed_sample(conn: sqlite3.Connection, *, table: str, field: str, pk_expr: str) -> List[str]:
    rows = conn.execute(
        f"""
        SELECT {pk_expr}
        FROM {table}
        WHERE {field} IS NOT NULL
          AND TRIM(CAST({field} AS TEXT)) <> ''
          AND LOWER(TRIM(CAST({field} AS TEXT))) <> CAST({field} AS TEXT)
        LIMIT 10
        """
    ).fetchall()
    return [str(row[0]) for row in rows]


def normalize_enum_text(conn: sqlite3.Connection, *, table: str, field: str, allowed_values=None) -> int:
    """Normalize enum text; forward repairs may restrict recognized lowercase values."""
    restriction, params = "", ()
    if allowed_values is not None:
        # Forward cleanup only repairs the known lowercase values missed by v4.
        restriction = " AND typeof(" + field + ")='text' AND TRIM(" + field + ") IN (" + ",".join("?" for _ in allowed_values) + ")"
        params = tuple(allowed_values)
        # Even a zero-row UPDATE can initialize sqlite_sequence through compiled
        # lineage triggers. A forward repair must leave unrelated history intact.
        needed = conn.execute(f"""SELECT 1 FROM {table}
            WHERE {field} IS NOT NULL AND TRIM(CAST({field} AS TEXT)) <> ''
              AND LOWER(TRIM(CAST({field} AS TEXT))) <> CAST({field} AS TEXT)
            """ + restriction + " LIMIT 1", params).fetchone()
        if needed is None:
            return 0
    cur = conn.execute(
        f"""
        UPDATE {table}
        SET {field} = LOWER(TRIM(CAST({field} AS TEXT)))
        WHERE {field} IS NOT NULL
          AND TRIM(CAST({field} AS TEXT)) <> ''
          AND LOWER(TRIM(CAST({field} AS TEXT))) <> CAST({field} AS TEXT)
        """ + restriction,
        params,
    )
    return cur.rowcount


def _apply_default(conn: sqlite3.Connection, *, table: str, field: str, default: str) -> int:
    cur = conn.execute(
        f"""
        UPDATE {table}
        SET {field} = ?
        WHERE {field} IS NULL
           OR TRIM(CAST({field} AS TEXT)) = ''
        """,
        (str(default),),
    )
    return cur.rowcount


def sanitize_field(
    conn: sqlite3.Connection,
    *,
    table: str,
    field: str,
    pk_expr: str,
    default: Optional[str],
    logger=None,
    collect_sample: bool = True,
) -> Tuple[MigrationOutcome, int, List[str]]:
    """
    把枚举/状态字段做一致性清洗：
    - 非空：LOWER(TRIM(x))
    - NULL/空串：写入 default（若提供）

    Returns:
        (outcome, changed_rows, sample_pk_list)
    """
    # table/field/pk_expr 是 v4 迁移任务表里的代码常量，直接拼进 SQL。
    try:
        if collect_sample:
            sample = _fetch_changed_sample(conn, table=table, field=field, pk_expr=pk_expr)
        else:
            # Keep the helper's missing-PK rejection without scanning for diagnostics.
            conn.execute(f"SELECT {pk_expr} FROM {table} WHERE 0")
            sample = []
        changed = normalize_enum_text(conn, table=table, field=field)
        if default is not None:
            changed += _apply_default(conn, table=table, field=field, default=str(default))
    except Exception as e:
        if _is_expected_missing_schema_error(e):
            _log_skipped_schema(logger, table, field, e)
            return MigrationOutcome.SKIPPED, 0, []
        raise

    if changed and logger:
        sample_text = "，".join(sample[:10])
        fallback_log(
            logger,
            "warning",
            f"数据库迁移 v4：已清洗 {table}.{field}（影响行数={changed}）"
            + (f"，样例（最多10个）={sample_text}" if sample_text else "")
            + (f"，default={default}" if default is not None else ""),
        )

    return MigrationOutcome.APPLIED, changed, sample
