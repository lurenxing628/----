from __future__ import annotations

import re
import sqlite3
from typing import List, Optional, Tuple

_PK_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
_PK_CAST = rf"CAST\({_PK_IDENT} AS TEXT\)"
_PK_LIT = r"'[^']*'"
_PK_TERM = rf"(?:{_PK_CAST}|{_PK_LIT})"
_SAFE_PK_EXPR_RE = re.compile(rf"^{_PK_CAST}(?:\s*\|\|\s*{_PK_TERM})*$")


def _rows_to_list(rows) -> List[str]:
    out: List[str] = []
    for r in rows or []:
        try:
            if isinstance(r, sqlite3.Row):
                out.append(str(r[0]))
            else:
                out.append(str(r[0]))
        except Exception:
            continue
    return out


def _is_expected_missing_schema_error(e: Exception) -> bool:
    if not isinstance(e, sqlite3.OperationalError):
        return False
    msg = str(e).lower()
    return "no such table" in msg or "no such column" in msg


def _sanitize_field(
    conn: sqlite3.Connection,
    *,
    table: str,
    field: str,
    pk_expr: str,
    default: Optional[str],
    logger=None,
) -> Tuple[int, List[str]]:
    """
    把枚举/状态字段做一致性清洗：
    - 非空：LOWER(TRIM(x))
    - NULL/空串：写入 default（若提供）

    Returns:
        (changed_rows, sample_pk_list)
    """
    sample: List[str] = []
    changed = 0

    # 防御：table/field 会被拼接进 SQL（SQLite 标识符无法参数化），仅允许安全标识符
    t = str(table or "").strip()
    f = str(field or "").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", t or "") or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", f or ""):
        if logger:
            try:
                logger.error(f"数据库迁移 v4：非法标识符，已跳过清洗（table={table!r} field={field!r}）")
            except Exception:
                pass
        return 0, []

    # 防御：pk_expr 也会被拼接进 SQL（无法参数化），禁止可疑字符，避免语法注入
    pk = str(pk_expr or "").strip()
    if (
        not pk
        or len(pk) > 200
        or ";" in pk
        or "--" in pk
        or "/*" in pk
        or "*/" in pk
        or not _SAFE_PK_EXPR_RE.fullmatch(pk)
    ):
        if logger:
            try:
                logger.error(f"数据库迁移 v4：非法 pk_expr，已跳过清洗（table={table!r} field={field!r} pk_expr={pk_expr!r}）")
            except Exception:
                pass
        return 0, []

    # 1) 样例：找出需要被 lower/trim 的行（最多 10 条）
    try:
        rows = conn.execute(
            f"""
            SELECT {pk}
            FROM {t}
            WHERE {f} IS NOT NULL
              AND TRIM(CAST({f} AS TEXT)) <> ''
              AND LOWER(TRIM(CAST({f} AS TEXT))) <> TRIM(CAST({f} AS TEXT))
            LIMIT 10
            """
        ).fetchall()
        sample = _rows_to_list(rows)
    except Exception as e:
        if _is_expected_missing_schema_error(e):
            if logger:
                try:
                    logger.warning(f"数据库迁移 v4：{t}.{f} 清洗已跳过（{e}）。")
                except Exception:
                    pass
            return 0, []
        sample = []

    # 2) lower+trim（仅更新需要变更的行）
    try:
        cur = conn.execute(
            f"""
            UPDATE {t}
            SET {f} = LOWER(TRIM(CAST({f} AS TEXT)))
            WHERE {f} IS NOT NULL
              AND TRIM(CAST({f} AS TEXT)) <> ''
              AND LOWER(TRIM(CAST({f} AS TEXT))) <> TRIM(CAST({f} AS TEXT))
            """
        )
        changed += int(getattr(cur, "rowcount", 0) or 0)
    except Exception as e:
        if _is_expected_missing_schema_error(e):
            if logger:
                try:
                    logger.warning(f"数据库迁移 v4：{t}.{f} 清洗已跳过（{e}）。")
                except Exception:
                    pass
            return 0, []
        raise

    # 3) 空值兜底（可选）
    if default is not None:
        try:
            cur2 = conn.execute(
                f"""
                UPDATE {t}
                SET {f} = ?
                WHERE {f} IS NULL
                   OR TRIM(CAST({f} AS TEXT)) = ''
                """,
                (str(default),),
            )
            changed += int(getattr(cur2, "rowcount", 0) or 0)
        except Exception as e:
            if _is_expected_missing_schema_error(e):
                if logger:
                    try:
                        logger.warning(f"数据库迁移 v4：{t}.{f} 清洗已跳过（{e}）。")
                    except Exception:
                        pass
                return 0, []
            raise

    if changed and logger:
        try:
            sample_text = "，".join(sample[:10])
            logger.warning(
                f"数据库迁移 v4：已清洗 {table}.{field}（影响行数={changed}）"
                + (f"，样例（最多10个）={sample_text}" if sample_text else "")
                + (f"，default={default}" if default is not None else "")
            )
        except Exception:
            pass

    return changed, sample


def run(conn: sqlite3.Connection, logger=None) -> None:
    """
    v4 迁移：统一清洗“枚举/状态类文本字段”的大小写/空格（TRIM+LOWER），并对 NULL/空串写默认值。

    目标：
    - 避免历史数据出现 INTERNAL/External/ YES 等大小写混用导致业务误判
    - 幂等：可重复执行
    - 不改表结构，仅做数据修正
    """
    tasks = [
        # Scheduler
        ("Batches", "priority", "CAST(batch_id AS TEXT)", "normal"),
        ("Batches", "ready_status", "CAST(batch_id AS TEXT)", "yes"),
        ("Batches", "status", "CAST(batch_id AS TEXT)", "pending"),
        ("BatchOperations", "source", "CAST(id AS TEXT)", "internal"),
        ("BatchOperations", "status", "CAST(id AS TEXT)", "pending"),
        ("Schedule", "lock_status", "CAST(id AS TEXT)", "unlocked"),
        ("BatchMaterials", "ready_status", "CAST(id AS TEXT)", "no"),
        # Process
        ("Parts", "route_parsed", "CAST(part_no AS TEXT)", "no"),
        ("OpTypes", "category", "CAST(op_type_id AS TEXT)", "internal"),
        ("PartOperations", "source", "CAST(id AS TEXT)", "internal"),
        ("PartOperations", "status", "CAST(id AS TEXT)", "active"),
        ("ExternalGroups", "merge_mode", "CAST(group_id AS TEXT)", "separate"),
        ("OperatorMachine", "skill_level", "CAST(id AS TEXT)", "normal"),
        ("OperatorMachine", "is_primary", "CAST(id AS TEXT)", "no"),
        # Calendar
        ("WorkCalendar", "day_type", "CAST(date AS TEXT)", "workday"),
        ("WorkCalendar", "allow_normal", "CAST(date AS TEXT)", "yes"),
        ("WorkCalendar", "allow_urgent", "CAST(date AS TEXT)", "yes"),
        (
            "OperatorCalendar",
            "day_type",
            "CAST(operator_id AS TEXT) || '@' || CAST(date AS TEXT)",
            "workday",
        ),
        (
            "OperatorCalendar",
            "allow_normal",
            "CAST(operator_id AS TEXT) || '@' || CAST(date AS TEXT)",
            "yes",
        ),
        (
            "OperatorCalendar",
            "allow_urgent",
            "CAST(operator_id AS TEXT) || '@' || CAST(date AS TEXT)",
            "yes",
        ),
        # Master data / resources
        ("Machines", "status", "CAST(machine_id AS TEXT)", "active"),
        ("Operators", "status", "CAST(operator_id AS TEXT)", "active"),
        ("Suppliers", "status", "CAST(supplier_id AS TEXT)", "active"),
        ("Materials", "status", "CAST(material_id AS TEXT)", "active"),
        ("MachineDowntimes", "scope_type", "CAST(id AS TEXT)", "machine"),
        ("MachineDowntimes", "status", "CAST(id AS TEXT)", "active"),
    ]

    for table, field, pk_expr, default in tasks:
        _sanitize_field(conn, table=table, field=field, pk_expr=pk_expr, default=default, logger=logger)

