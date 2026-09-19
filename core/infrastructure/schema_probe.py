"""sqlite_master 自省探针：对象名、表名、对象 DDL、有序对象清单、表列名。

只读、无裁决；服务层要判断“表在不在 / DDL 里有没有 AUTOINCREMENT”时调用这里，不自己写 sqlite_master 查询。
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

SchemaObject = Tuple[str, str, str, Any]


def object_names(conn: sqlite3.Connection) -> Set[str]:
    """sqlite_master 里全部对象名（表、索引、触发器、视图）。"""
    return {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master")}


def table_names(conn: sqlite3.Connection) -> Set[str]:
    return {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def user_table_count(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND substr(name, 1, 7) != 'sqlite_'"
    ).fetchone()
    return int(row[0])


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def object_sql(conn: sqlite3.Connection, name: str, *, kind: str = "table") -> Optional[str]:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type=? AND name=?", (kind, name)).fetchone()
    if row is None:
        return None
    return None if row[0] is None else str(row[0])


def object_sql_map(conn: sqlite3.Connection, names: Iterable[str]) -> Dict[str, Any]:
    """名字在 names 里的对象及其 sql（任意类型；自动索引的 sql 为 None）。"""
    wanted = set(names)
    return {str(row[0]): row[1] for row in conn.execute("SELECT name,sql FROM sqlite_master") if row[0] in wanted}


def schema_objects(conn: sqlite3.Connection, *, exclude_tbl_names: Sequence[str] = ()) -> List[SchemaObject]:
    """按 (type, name) 排序的 (type, name, tbl_name, sql) 元组清单。"""
    excluded = set(exclude_tbl_names)
    return [
        (str(row[0]), str(row[1]), str(row[2]), row[3])
        for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")
        if row[2] not in excluded
    ]


def table_columns(conn: sqlite3.Connection, name: str) -> List[str]:
    quoted = '"' + str(name).replace('"', '""') + '"'
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({quoted})")]
