from __future__ import annotations

import logging
import os
import re
import sqlite3
from typing import List

from .migration_common import fallback_log
from .migration_state import list_user_tables
from .schema_declaration import declared_tables

_LOGGER = logging.getLogger(__name__)


def build_schema_exec_script(sql: str) -> str:
    if re.search(r"(?im)^\s*BEGIN(?:\s+(?:DEFERRED|IMMEDIATE|EXCLUSIVE))?(?:\s+TRANSACTION)?\s*;", sql):
        return sql
    # PRAGMA foreign_keys cannot be changed inside a transaction.
    clean_sql = re.sub(r"(?im)^\s*PRAGMA\s+foreign_keys\s*=\s*\w+;?", "", sql)
    return "BEGIN;\n" + clean_sql + "\nCOMMIT;\n"


def missing_schema_tables(conn: sqlite3.Connection, schema_sql: str) -> List[str]:
    """schema 文本声明了、当前库却没有的业务表；只用于迁移失败时的提示文案，绝不据此补表。"""
    existing = set(list_user_tables(conn))
    return [name for name in declared_tables(schema_sql) if name not in existing]


def cleanup_probe_db(db_path: str) -> None:
    for suffix in ("", "-wal", "-shm", "-journal"):
        path = f"{db_path}{suffix}"
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as exc:
            fallback_log(_LOGGER, "warning", f"迁移预检临时库清理失败（已继续）：{exc}（path={db_path}{suffix}）")
