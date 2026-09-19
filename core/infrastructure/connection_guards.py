"""SQLite 连接级守卫与元数据探针：query_only 开关、外键开关、data_version、库文件清单。

服务层不再自己拼 PRAGMA；这里只做执行与最小规范化，不做业务裁决。
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator, List, Optional, Tuple


def is_query_only(conn: sqlite3.Connection) -> bool:
    row = conn.execute("PRAGMA query_only").fetchone()
    return bool(row) and row[0] == 1


@contextmanager
def query_only(conn: sqlite3.Connection) -> Iterator[None]:
    """进入时置 PRAGMA query_only=ON，退出时恢复进入前的值。"""
    previous = is_query_only(conn)
    try:
        conn.execute("PRAGMA query_only=ON")
        yield
    finally:
        conn.execute("PRAGMA query_only=" + ("ON" if previous else "OFF"))


def foreign_keys_enabled(conn: sqlite3.Connection) -> bool:
    row = conn.execute("PRAGMA foreign_keys").fetchone()
    return bool(row) and row[0] == 1


def data_version(conn: sqlite3.Connection) -> Optional[int]:
    """PRAGMA data_version；取不到有效整数时返回 None，不吞 sqlite3.Error。"""
    row = conn.execute("PRAGMA data_version").fetchone()
    if row is None or type(row[0]) is not int:
        return None
    return row[0]


def database_list(conn: sqlite3.Connection) -> List[Any]:
    """PRAGMA database_list 的原始行（seq, name, file），保留连接的行工厂形态。"""
    return list(conn.execute("PRAGMA database_list").fetchall() or [])


def main_database_path(conn: sqlite3.Connection) -> str:
    for row in database_list(conn):
        if row[1] == "main":
            return str(row[2])
    raise LookupError("connection has no main database")


def connection_snapshot_metadata(conn: sqlite3.Connection) -> Tuple[int, int, int, int]:
    """(main.data_version, main.schema_version, temp.schema_version, query_only)；任一值非整数抛 ValueError。"""
    values: List[int] = []
    for statement in ("PRAGMA main.data_version", "PRAGMA main.schema_version",
                      "PRAGMA temp.schema_version", "PRAGMA query_only"):
        row = conn.execute(statement).fetchone()
        if row is None or len(row) != 1 or type(row[0]) is not int:
            raise ValueError(f"connection metadata unavailable: {statement}")
        values.append(row[0])
    return values[0], values[1], values[2], values[3]
