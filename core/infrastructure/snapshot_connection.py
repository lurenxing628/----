"""归档/备份库的只读连接与备份复制。"""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator

from core.infrastructure.sqlite_udf import DETECT_TYPES, configure_connection


@contextmanager
def open_readonly_immutable(path: str) -> Iterator[sqlite3.Connection]:
    """只读、不可变方式打开调用方独占的库副本；打开后的配置与产品读写连接一致。"""
    uri = Path(path).absolute().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True, detect_types=DETECT_TYPES)) as conn:
        configure_connection(conn)
        yield conn


def backup_to_file(source: sqlite3.Connection, path: str) -> None:
    """Materialize a consistent caller-owned database copy and release its handles."""
    with closing(sqlite3.connect(path)) as destination:
        source.backup(destination)
