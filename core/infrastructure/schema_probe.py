"""sqlite_master 自省探针：对象名、表名、对象 DDL、表列名。

只读、无裁决；服务层要判断“表在不在 / DDL 里有没有 AUTOINCREMENT”时调用这里，不自己写 sqlite_master 查询。
"""

from __future__ import annotations

import sqlite3
from typing import List, Optional

from .connection_guards import SCHEMA_CONTRACTS
from .schema_structure import SchemaStructure


def cached_structure(conn: sqlite3.Connection) -> Optional[SchemaStructure]:
    memo = next((item for item in reversed(SCHEMA_CONTRACTS.get()) if item.conn is conn), None)
    return memo._structure if memo is not None else None


def user_table_count(conn: sqlite3.Connection) -> int:
    structure = cached_structure(conn)
    if structure is not None:
        return sum(1 for name, (kind, _tbl, _sql) in structure.objects.items()
                   if kind == "table" and not name.startswith("sqlite_"))
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND substr(name, 1, 7) != 'sqlite_'"
    ).fetchone()
    return int(row[0])


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    structure = cached_structure(conn)
    if structure is not None:
        return structure.has_table(name)
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def table_columns(conn: sqlite3.Connection, name: str) -> List[str]:
    structure = cached_structure(conn)
    if structure is not None:
        return [str(row[1]) for row in structure.table_info(name)]
    quoted = '"' + str(name).replace('"', '""') + '"'
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({quoted})")]
