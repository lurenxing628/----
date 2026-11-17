"""schema.sql 的定位与“声明结构”解析。

schema.sql 是生成物（python -m tools.generate_schema_sql --write），手写源是 DDL 模块；
运行期需要“声明了哪些表、每张表有哪些列、哪些列组不许重复”时，把文本装进一个隔离的 :memory: 库再用
PRAGMA 读，不再用正则猜 CREATE TABLE / CREATE UNIQUE INDEX。schema.sql 随程序发布、运行中不变，同一路径进程内只读一次。
"""

from __future__ import annotations

import os
import sqlite3
import sys
from typing import Dict, NamedTuple, Optional, Tuple

_TEXT_CACHE: Dict[str, str] = {}


def resolve_schema_path(schema_path: Optional[str]) -> str:
    """纯路径解析：显式路径 → 仓库根 → frozen exe 同目录 → 当前目录；找不到抛 FileNotFoundError。"""
    if not schema_path:
        candidates = [os.path.join(os.path.dirname(__file__), "..", "..", "schema.sql")]
        if getattr(sys, "frozen", False):
            candidates.append(os.path.join(os.path.dirname(sys.executable), "schema.sql"))
        candidates.append(os.path.join(os.getcwd(), "schema.sql"))
        for candidate in candidates:
            absolute = os.path.abspath(candidate)
            if os.path.exists(absolute):
                return absolute
        raise FileNotFoundError("找不到数据库结构文件：schema.sql（请确认工作目录或打包参数包含该文件）")
    schema_path = os.path.abspath(schema_path)
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"找不到数据库结构文件：{schema_path}")
    return schema_path


def load_schema_sql(schema_path: Optional[str] = None) -> str:
    """读取 schema.sql 文本；同一路径进程内只读一次。"""
    path = resolve_schema_path(schema_path)
    if path not in _TEXT_CACHE:
        with open(path, encoding="utf-8") as handle:
            _TEXT_CACHE[path] = handle.read()
    return _TEXT_CACHE[path]


class DeclaredTable(NamedTuple):
    """一张表的声明：列名（声明顺序），以及主键与无条件唯一约束各自的列组。"""

    columns: Tuple[str, ...]
    unique_keys: Tuple[Tuple[str, ...], ...]


def _quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def declared_tables(schema_sql: str) -> Dict[str, DeclaredTable]:
    """schema 文本声明的每张表（含 SchemaVersion）；调用方按需缓存结果。

    ``unique_keys`` 是 PRIMARY KEY（含 INTEGER PRIMARY KEY）、列级与表级 UNIQUE、``CREATE UNIQUE INDEX`` 的列组，
    同一列组只记一次。带 WHERE 的部分唯一索引只约束满足条件的行，不在其中，由读这些行的地方自己核对。
    """
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(schema_sql)
        names = [
            str(row[0]) for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid"
            )
        ]
        tables = {}
        for name in names:
            info = conn.execute("PRAGMA table_info(" + _quoted(name) + ")").fetchall()
            keys = [tuple(str(row[1]) for row in sorted((row for row in info if row[5]), key=lambda row: row[5]))]
            for _seq, index, unique, _origin, partial in conn.execute("PRAGMA index_list(" + _quoted(name) + ")"):
                if unique and not partial:
                    keys.append(tuple(row[2] for row in conn.execute("PRAGMA index_info(" + _quoted(index) + ")")))
            tables[name] = DeclaredTable(tuple(str(row[1]) for row in info), tuple(dict.fromkeys(key for key in keys if key)))
    finally:
        conn.close()
    return tables
