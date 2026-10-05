"""schema.sql 的定位与“声明结构”解析。

schema.sql 是生成物（python -m tools.generate_schema_sql --write），手写源是 DDL 模块与迁移链；
运行期需要“声明了哪些表、每张表有哪些列”时，把文本装进一个隔离的 :memory: 库再用 PRAGMA 读，
不再用正则猜 CREATE TABLE。解析结果按文本内容缓存，同一份 schema 只解析一次。
"""

from __future__ import annotations

import os
import sqlite3
import sys
from typing import Dict, List, Optional, Tuple

_DECLARED_CACHE: Dict[str, Tuple[List[str], Dict[str, List[str]]]] = {}
_TEXT_CACHE: Dict[str, Tuple[Tuple[int, int], str]] = {}


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
                schema_path = absolute
                break
    if not schema_path:
        raise FileNotFoundError("找不到数据库结构文件：schema.sql（请确认工作目录或打包参数包含该文件）")
    schema_path = os.path.abspath(schema_path)
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"找不到数据库结构文件：{schema_path}")
    return schema_path


def load_schema_sql(schema_path: Optional[str] = None) -> str:
    """读取 schema.sql 文本；按 (mtime_ns, size) 缓存，文件一变就重读。"""
    path = resolve_schema_path(schema_path)
    stat = os.stat(path)
    stamp = (int(stat.st_mtime_ns), int(stat.st_size))
    cached = _TEXT_CACHE.get(path)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    _TEXT_CACHE[path] = (stamp, text)
    return text


def _parse(schema_sql: str) -> Tuple[List[str], Dict[str, List[str]]]:
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(schema_sql)
        names = [
            str(row[0]) for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid"
            )
        ]
        columns = {
            name: [str(row[1]) for row in conn.execute('PRAGMA table_info("' + name.replace('"', '""') + '")')]
            for name in names
        }
    finally:
        conn.close()
    return names, columns


def _declared(schema_sql: str) -> Tuple[List[str], Dict[str, List[str]]]:
    key = str(schema_sql or "")
    cached = _DECLARED_CACHE.get(key)
    if cached is None:
        cached = _parse(str(schema_sql or ""))
        if len(_DECLARED_CACHE) >= 8:
            _DECLARED_CACHE.clear()
        _DECLARED_CACHE[key] = cached
    return cached


def declared_tables(schema_sql: str) -> List[str]:
    """schema 文本声明的业务表名（创建顺序，不含 SchemaVersion）。"""
    return [name for name in _declared(schema_sql)[0] if name != "SchemaVersion"]


def declared_columns(schema_sql: str) -> Dict[str, List[str]]:
    """schema 文本声明的 {表名: [列名...]}（含 SchemaVersion）。"""
    return {name: list(cols) for name, cols in _declared(schema_sql)[1].items()}
