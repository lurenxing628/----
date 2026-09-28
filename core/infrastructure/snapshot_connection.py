"""归档/备份库的只读连接与“在隔离内存库里解析已知 DDL”两类特殊 SQLite 访问。

- open_readonly_immutable：以 mode=ro&immutable=1 打开备份文件，只做证据核对，绝不迁移、绝不写。
- ddl_columns：把一条 CREATE TABLE 语句放进空的 :memory: 库执行，取回列名；restricted=True 时挂授权器，
  只允许建这张表、读 sqlite_master 与该表的 table_info，拒绝一切其它动作。解析失败抛 ValueError。
"""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator, List

from .schema_probe import table_columns


@contextmanager
def open_readonly_immutable(path: str) -> Iterator[sqlite3.Connection]:
    uri = Path(path).absolute().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        yield conn


def backup_to_file(source: sqlite3.Connection, path: str) -> None:
    """Materialize a consistent caller-owned database copy and release its handles."""
    with closing(sqlite3.connect(path)) as destination:
        source.backup(destination)


def _restricted_authorizer(name: str):
    def authorize(action, first, second, database, source):
        if action == sqlite3.SQLITE_CREATE_TABLE and first in (name, "sqlite_sequence") and database == "main":
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_CREATE_INDEX and second == name and first.startswith("sqlite_autoindex_"):
            return sqlite3.SQLITE_OK
        if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_READ) and first == "sqlite_master":
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ and first == name:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_REINDEX and first.startswith("sqlite_autoindex_"):
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION and second in ("length", "typeof", "glob"):
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_PRAGMA and first == "table_info" and second == name:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    return authorize


def ddl_columns(create_table_sql: str, name: str, *, restricted: bool = False) -> List[str]:
    if type(create_table_sql) is not str:
        raise ValueError("DDL must be text")
    conn = sqlite3.connect(":memory:")
    try:
        if restricted:
            conn.set_authorizer(_restricted_authorizer(name))
        conn.execute(create_table_sql)
        return table_columns(conn, name)
    except (sqlite3.Error, sqlite3.Warning) as exc:
        raise ValueError(f"cannot parse archived DDL for {name}: {exc}") from exc
    finally:
        conn.close()
