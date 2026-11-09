"""归档/备份库的只读连接与备份复制。"""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator

from core.infrastructure.sqlite_udf import register_schedule_time_sql_functions


@contextmanager
def open_readonly_immutable(path: str, *, detect_types: int = 0, row_factory=None) -> Iterator[sqlite3.Connection]:
    uri = Path(path).absolute().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True, detect_types=detect_types)) as conn:
        conn.row_factory = row_factory
        conn.execute("PRAGMA foreign_keys=ON")
        register_schedule_time_sql_functions(conn)
        yield conn


def backup_to_file(source: sqlite3.Connection, path: str) -> None:
    """Materialize a consistent caller-owned database copy and release its handles."""
    with closing(sqlite3.connect(path)) as destination:
        source.backup(destination)
