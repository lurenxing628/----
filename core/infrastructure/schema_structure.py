"""Structure facts shared only within one validation, before any DDL change."""

import sqlite3
import threading
from collections import OrderedDict
from typing import AbstractSet, Any, Dict, List, Mapping, Optional, Tuple

_INVALID_ARCHIVED_DDL = "Invalid archived table DDL"
_DECLARED_CACHE_LIMIT = 32
_DECLARED_CACHE_LOCK = threading.RLock()
_DECLARED_SCHEMA_CACHE: Dict[
    Tuple[Tuple[Tuple[str, str], ...], Tuple[str, ...]],
    Dict[str, Tuple[str, ...]],
] = OrderedDict()
_DECLARED_SINGLE_TABLE_CACHE: Dict[Tuple[str, str], Tuple[str, ...]] = OrderedDict()


def _cache_get(cache, key):
    with _DECLARED_CACHE_LOCK:
        value = cache.get(key)
        if value is not None:
            cache.move_to_end(key)
        return value


def _cache_put(cache, key, value):
    with _DECLARED_CACHE_LOCK:
        if key in cache:
            cache.move_to_end(key)
        elif len(cache) >= _DECLARED_CACHE_LIMIT:
            cache.popitem(last=False)
        cache[key] = value
        return value


def _reserved_table_columns(name: str, sql: str) -> Optional[Tuple[str, ...]]:
    if name == "sqlite_sequence":
        if " ".join(sql.split()) != "CREATE TABLE sqlite_sequence(name,seq)":
            raise ValueError(_INVALID_ARCHIVED_DDL)
        return ("name", "seq")
    if name.startswith("sqlite_"):
        raise ValueError(_INVALID_ARCHIVED_DDL)
    return None


def _extract_table_columns(mem: sqlite3.Connection, name: str, sql: str) -> Tuple[str, ...]:
    try:
        mem.execute(sql)
        exists = mem.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        escaped = name.replace('"', '""')
        cols = (
            tuple(row[1] for row in mem.execute(f'PRAGMA table_info("{escaped}")').fetchall())
            if exists is not None
            else ()
        )
    except (sqlite3.Error, sqlite3.Warning, ValueError, TypeError) as exc:
        raise ValueError(_INVALID_ARCHIVED_DDL) from exc
    if not cols:
        raise ValueError(_INVALID_ARCHIVED_DDL)
    return cols


def declared_table_columns(name: str, sql: str) -> Tuple[str, ...]:
    if type(name) is not str or not name or type(sql) is not str or not sql.strip():
        raise ValueError(_INVALID_ARCHIVED_DDL)
    reserved = _reserved_table_columns(name, sql)
    if reserved is not None:
        return reserved
    key = (name, sql)
    cached = _cache_get(_DECLARED_SINGLE_TABLE_CACHE, key)
    if cached is not None:
        return cached
    mem = sqlite3.connect(":memory:")
    try:
        cols = _extract_table_columns(mem, name, sql)
    finally:
        mem.close()
    return _cache_put(_DECLARED_SINGLE_TABLE_CACHE, key, cols)


def declared_schema_table_columns(
    schema: Any,
    *,
    excluded_tables: AbstractSet[str] = frozenset(),
) -> Mapping[str, Tuple[str, ...]]:
    if not isinstance(schema, list):
        raise ValueError(_INVALID_ARCHIVED_DDL)
    table_sqls: List[Tuple[str, str]] = []
    seen = set()
    for row in schema:
        if (
            type(row) is not list
            or len(row) != 4
            or type(row[0]) is not str
            or type(row[1]) is not str
            or type(row[2]) is not str
        ):
            raise ValueError(_INVALID_ARCHIVED_DDL)
        if row[0] != "table" or row[1] in excluded_tables:
            continue
        name, tbl_name, sql = row[1], row[2], row[3]
        if not name or tbl_name != name or type(sql) is not str or not sql.strip() or name in seen:
            raise ValueError(_INVALID_ARCHIVED_DDL)
        seen.add(name)
        table_sqls.append((name, sql))
    if not seen:
        raise ValueError(_INVALID_ARCHIVED_DDL)
    key = (tuple(table_sqls), tuple(sorted(excluded_tables)))
    cached = _cache_get(_DECLARED_SCHEMA_CACHE, key)
    if cached is not None:
        return cached
    mem = sqlite3.connect(":memory:")
    try:
        declared: Dict[str, Tuple[str, ...]] = {}
        for name, sql in table_sqls:
            reserved = _reserved_table_columns(name, sql)
            declared[name] = reserved if reserved is not None else _extract_table_columns(mem, name, sql)
    finally:
        mem.close()
    return _cache_put(_DECLARED_SCHEMA_CACHE, key, declared)


class SchemaStructure:
    def __init__(self, conn):
        self.conn = conn
        self.objects = {row[1]: (row[0], row[2], row[3]) for row in conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master")}
        self.sql = {name: value[2] for name, value in self.objects.items()}
        self._columns: Dict[str, tuple] = {}
        self._indexes: Dict[str, tuple] = {}
        self._index_columns: Dict[str, tuple] = {}

    def has_table(self, name):
        return name in self.objects and self.objects[name][0] == "table"

    def index_table(self, name):
        obj = self.objects.get(name)
        return obj[1] if obj is not None and obj[0] == "index" else ""

    def _pragma(self, cache, command, name):
        if name not in cache:
            quoted = '"' + name.replace('"', '""') + '"'
            cache[name] = tuple(self.conn.execute("PRAGMA " + command + "(" + quoted + ")"))
        return cache[name]

    def table_info(self, name):
        return self._pragma(self._columns, "table_info", name)

    def index_list(self, name):
        return self._pragma(self._indexes, "index_list", name)

    def index_info(self, name):
        return self._pragma(self._index_columns, "index_info", name)

    def has_unique_key(self, table, columns, *, index_name=None):
        expected = tuple(columns)
        return any(
            (index_name is None or row[1] == index_name)
            and row[2]
            and not row[4]
            and tuple(col[2] for col in self.index_info(row[1])) == expected
            for row in self.index_list(table)
        )
