"""归档/备份库的只读连接与“在隔离内存库里解析已知 DDL”两类特殊 SQLite 访问。"""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Iterator, List, Tuple

from .schema_probe import table_columns


@contextmanager
def open_readonly_immutable(path: str, *, detect_types: int = 0, row_factory=None) -> Iterator[sqlite3.Connection]:
    uri = Path(path).absolute().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True, detect_types=detect_types)) as conn:
        conn.row_factory = row_factory
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn


def backup_to_file(source: sqlite3.Connection, path: str) -> None:
    """Materialize a consistent caller-owned database copy and release its handles."""
    with closing(sqlite3.connect(path)) as destination:
        source.backup(destination)


@lru_cache(maxsize=128)
def _ddl_columns(create_table_sql: str, name: str) -> Tuple[str, ...]:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(create_table_sql)
        return tuple(table_columns(conn, name))
    except (sqlite3.Error, sqlite3.Warning) as exc:
        raise ValueError(f"cannot parse archived DDL for {name}: {exc}") from exc
    finally:
        conn.close()


def ddl_columns(create_table_sql: str, name: str, *, restricted: bool = False) -> List[str]:
    if type(create_table_sql) is not str:
        raise ValueError("DDL must be text")
    return list(_ddl_columns(create_table_sql, name))
