from __future__ import annotations

import re
import sqlite3
import sys


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """
    判断指定表是否存在。

    说明：
    - 查询 sqlite_master，避免把“表不存在”和“列不存在”混为一谈
    - 仅接受安全标识符，避免 SQL 注入/语法注入
    """
    try:
        t = str(table or "").strip()
    except Exception:
        t = ""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", t or ""):
        return False
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (t,),
        ).fetchone()
        return row is not None
    except Exception:
        return False


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """
    判断指定表是否存在指定列。

    说明：
    - SQLite: PRAGMA table_info(table)
    - 防御：异常时返回 False
    """
    # 防御：PRAGMA 不支持参数化 table 名，必须做白名单校验，避免 SQL 注入/语法注入
    # 允许：字母/数字/下划线，且不能以数字开头（符合常见 SQLite 标识符约束）
    try:
        t = str(table or "").strip()
    except Exception:
        t = ""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", t or ""):
        return False
    try:
        rows = conn.execute(f"PRAGMA table_info({t})").fetchall()
        for r in rows:
            name = r["name"] if isinstance(r, sqlite3.Row) else r[1]
            if name == column:
                return True
        return False
    except Exception:
        return False


def fallback_log(logger, level: str, message: str) -> None:
    if not logger:
        return
    method = getattr(logger, str(level or "").strip(), None)
    if callable(method):
        try:
            method(str(message))
            return
        except Exception:
            pass
    try:
        print(str(message), file=sys.stderr)
    except Exception:
        pass

