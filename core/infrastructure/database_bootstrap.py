from __future__ import annotations

import logging
import os
import re
import sqlite3
from typing import List

from .migration_state import list_user_tables
from .migrations.common import fallback_log

_CREATE_TABLE_RE = re.compile(
    r"(?ims)^\s*(CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(.*?\);)"
)
_CREATE_INDEX_RE = re.compile(
    r"(?im)^\s*(CREATE\s+(?:UNIQUE\s+)?INDEX\s+IF\s+NOT\s+EXISTS\s+[A-Za-z_][A-Za-z0-9_]*\s+ON\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(.*?\);)"
)
_LOGGER = logging.getLogger(__name__)


def load_schema_sql(schema_path: str) -> str:
    with open(schema_path, encoding="utf-8") as f:
        return f.read()


def build_schema_exec_script(sql: str) -> str:
    script = str(sql or "")
    try:
        # 只有在没有显式 BEGIN 时才包裹
        if not re.search(r"(?im)^\s*BEGIN\b", script):
            # 移除 PRAGMA foreign_keys = ON; 因为它不能在事务中执行
            clean_sql = re.sub(r"(?im)^\s*PRAGMA\s+foreign_keys\s*=\s*\w+;?", "", script)
            return "BEGIN;\n" + clean_sql + "\nCOMMIT;\n"
    except Exception:
        return script
    return script


def missing_schema_tables(conn: sqlite3.Connection, schema_sql: str) -> List[str]:
    existing = set(list_user_tables(conn))
    return [name for name in declared_schema_tables(schema_sql) if name not in existing]


def bootstrap_missing_tables_from_schema(conn: sqlite3.Connection, schema_sql: str, logger=None) -> List[str]:
    missing_tables = missing_schema_tables(conn, schema_sql)
    if not missing_tables:
        return []
    selected_statements = _create_missing_table_statements(schema_sql, missing_tables)
    script = _build_statement_script(selected_statements)
    if not script:
        return []
    conn.executescript(script)
    try:
        conn.commit()
    except Exception as exc:
        fallback_log(logger, "warning", f"缺失整表补齐后提交失败（已继续）：{exc}")
    if logger:
        fallback_log(
            logger, "warning", f"检测到非空数据库缺失整表，已按 schema.sql 补齐：{', '.join(missing_tables)}。"
        )
    return missing_tables


def cleanup_probe_db(db_path: str) -> None:
    for suffix in ("", "-wal", "-shm", "-journal"):
        path = f"{db_path}{suffix}"
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as exc:
            fallback_log(_LOGGER, "warning", f"迁移预检临时库清理失败（已继续）：{exc}（path={path}）")


def declared_schema_tables(schema_sql: str) -> List[str]:
    tables: List[str] = []
    for match in _CREATE_TABLE_RE.finditer(str(schema_sql or "")):
        name = str(match.group(2) or "").strip()
        if not name or name == "SchemaVersion" or name in tables:
            continue
        tables.append(name)
    return tables


def _create_missing_table_statements(schema_sql: str, missing_tables: List[str]) -> List[str]:
    table_statements = _schema_create_table_statements(schema_sql)
    index_statements = _schema_index_statements(schema_sql)
    selected_statements: List[str] = []
    for table in missing_tables:
        stmt = table_statements.get(table)
        if stmt:
            selected_statements.append(stmt)
    for table, stmt in index_statements:
        if table in missing_tables:
            selected_statements.append(stmt)
    return selected_statements


def _schema_create_table_statements(schema_sql: str) -> dict:
    statements = {}
    for match in _CREATE_TABLE_RE.finditer(str(schema_sql or "")):
        stmt = str(match.group(1) or "").strip()
        name = str(match.group(2) or "").strip()
        if stmt and name and name != "SchemaVersion":
            statements[name] = stmt
    return statements


def _schema_index_statements(schema_sql: str) -> List[tuple]:
    statements = []
    for match in _CREATE_INDEX_RE.finditer(str(schema_sql or "")):
        stmt = str(match.group(1) or "").strip()
        table = str(match.group(2) or "").strip()
        if stmt and table:
            statements.append((table, stmt))
    return statements


def _build_statement_script(statements: List[str]) -> str:
    clean = [str(stmt or "").strip() for stmt in statements if str(stmt or "").strip()]
    if not clean:
        return ""
    return "BEGIN;\n" + "\n".join(clean) + "\nCOMMIT;\n"
