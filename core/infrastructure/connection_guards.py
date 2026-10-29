"""SQLite 连接级守卫与元数据探针：query_only 开关、外键开关、data_version、库文件清单、表结构版本。

服务层不再自己拼 PRAGMA；这里只做执行与最小规范化，不做业务裁决。
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator, List, Optional, Tuple

from .schema_structure import SchemaStructure

SCHEMA_CONTRACTS: ContextVar[tuple] = ContextVar("aps_schema_contracts", default=())

_QUERY_ONLY: ContextVar[Tuple[sqlite3.Connection, ...]] = ContextVar("aps_query_only", default=())


def is_query_only(conn: sqlite3.Connection) -> bool:
    if any(current is conn for current in _QUERY_ONLY.get()):
        return True
    row = conn.execute("PRAGMA query_only").fetchone()
    return bool(row) and row[0] == 1


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


def foreign_keys_enabled(conn: sqlite3.Connection) -> bool:
    row = conn.execute("PRAGMA foreign_keys").fetchone()
    return bool(row) and row[0] == 1


def data_version(conn: sqlite3.Connection) -> Optional[int]:
    """PRAGMA data_version；取不到有效整数时返回 None，不吞 sqlite3.Error。"""
    row = conn.execute("PRAGMA data_version").fetchone()
    if row is None or type(row[0]) is not int:
        return None
    return row[0]


def main_database_path(conn: sqlite3.Connection) -> str:
    for row in conn.execute("PRAGMA database_list").fetchall():
        if row[1] == "main":
            return str(row[2])
    raise LookupError("connection has no main database")


_SCHEMA_CACHE: dict = {}


class SchemaContractMemo:
    """同一命令或读请求内，共享一次结构捕获及各合同检查的结果。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._results: dict = {}
        self._structure: Optional[SchemaStructure] = None

    def get(self, check):
        if check not in self._results:
            self._results[check] = check(self.conn)
        return self._results[check]

    @property
    def structure(self):
        if self._structure is None:
            self._structure = SchemaStructure(self.conn)
        return self._structure

    def get_schema(self, check):
        if check not in self._results:
            cached = _SCHEMA_CACHE.get(self.conn)
            is_local = "<locals>" in check.__qualname__
            if not is_local and cached is not None and check in cached["results"]:
                self._results[check] = cached["results"][check]
            else:
                structure = self._structure or (cached["structure"] if cached is not None else None) or self.structure
                result = check(self.conn, structure=structure)
                self._results[check] = result
                if not result and not is_local:
                    if cached is None:
                        if len(_SCHEMA_CACHE) >= 16:
                            _SCHEMA_CACHE.pop(next(iter(_SCHEMA_CACHE)))
                        cached = _SCHEMA_CACHE[self.conn] = {"structure": structure, "results": {}}
                    cached["results"][check] = result
        return self._results[check]


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


def schema_contract_memo(conn):
    """Use the current transaction/read owner; standalone callers get fresh facts."""
    return next((memo for memo in reversed(SCHEMA_CONTRACTS.get()) if memo.conn is conn), None) or SchemaContractMemo(conn)


@contextmanager
def schema_contract_scope(conn):
    """Share one lazy structure until the existing operation boundary exits."""
    existing = next((memo for memo in SCHEMA_CONTRACTS.get() if memo.conn is conn), None)
    if existing is not None:
        yield existing
        return
    memo = SchemaContractMemo(conn)
    token = SCHEMA_CONTRACTS.set(SCHEMA_CONTRACTS.get() + (memo,))
    try:
        yield memo
    finally:
        SCHEMA_CONTRACTS.reset(token)
