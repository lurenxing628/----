"""SQLite 连接级守卫与元数据探针：query_only 开关、data_version、库文件清单、表结构版本。

服务层不再自己拼 PRAGMA；这里只做执行与最小规范化，不做业务裁决。
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Tuple

_QUERY_ONLY: ContextVar[Tuple[sqlite3.Connection, ...]] = ContextVar("aps_query_only", default=())


def is_query_only(conn: sqlite3.Connection) -> bool:
    if any(current is conn for current in _QUERY_ONLY.get()):
        return True
    return conn.execute("PRAGMA query_only").fetchone()[0] == 1


@contextmanager
def query_only(conn: sqlite3.Connection) -> Iterator[None]:
    """最外层拥有只读开关；同连接嵌套加入已有作用域，退出恢复原值。"""
    active = _QUERY_ONLY.get()
    if any(current is conn for current in active):
        yield
        return
    previous = is_query_only(conn)
    token = _QUERY_ONLY.set(active + (conn,))
    try:
        if not previous:
            conn.execute("PRAGMA query_only=ON")
        yield
    finally:
        _QUERY_ONLY.reset(token)
        if not previous:
            conn.execute("PRAGMA query_only=OFF")


def data_version(conn: sqlite3.Connection) -> int:
    """PRAGMA data_version，不吞 sqlite3.Error。"""
    return conn.execute("PRAGMA data_version").fetchone()[0]


def main_database_path(conn: sqlite3.Connection) -> str:
    for row in conn.execute("PRAGMA database_list").fetchall():
        if row[1] == "main":
            return str(row[2])
    raise LookupError("connection has no main database")


def connection_snapshot_metadata(conn: sqlite3.Connection) -> Tuple[int, int, int, int]:
    """(main.data_version, main.schema_version, temp.schema_version, query_only)。"""
    return (
        conn.execute("PRAGMA main.data_version").fetchone()[0],
        conn.execute("PRAGMA main.schema_version").fetchone()[0],
        conn.execute("PRAGMA temp.schema_version").fetchone()[0],
        conn.execute("PRAGMA query_only").fetchone()[0],
    )
