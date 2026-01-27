import os
import sqlite3
import sys
from datetime import date, datetime


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _assert_is_date(v, context: str) -> None:
    # datetime 是 date 的子类，这里显式排除 datetime，确保是纯 date（SQLite DATE 隐式转换）
    ok = isinstance(v, date) and (not isinstance(v, datetime))
    assert ok, f"{context}：预期返回 datetime.date，实际 type={type(v)} value={v!r}"


def main():
    """
    回归目标：
    - get_connection() 必须开启 sqlite3 的 detect_types（PARSE_DECLTYPES | PARSE_COLNAMES），
      否则 SQLite 的 DATE 隐式类型转换会失效（DATE 变回 str），产生潜在的细微行为差异。
    """

    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import get_connection

    conn = get_connection(":memory:")
    try:
        # 1) PARSE_DECLTYPES：按“列声明类型”解析
        conn.execute("CREATE TABLE t_decl(d DATE)")
        conn.execute("INSERT INTO t_decl(d) VALUES (?)", ("2026-01-01",))
        row1 = conn.execute("SELECT d FROM t_decl").fetchone()
        assert row1 is not None, "t_decl 查询未返回结果"
        v1 = row1["d"] if isinstance(row1, sqlite3.Row) else row1[0]
        _assert_is_date(v1, "PARSE_DECLTYPES（DATE 列）")

        # 2) PARSE_COLNAMES：按“列名标注类型”解析（即使列声明为 TEXT，也应能转换）
        conn.execute("CREATE TABLE t_col(d TEXT)")
        conn.execute("INSERT INTO t_col(d) VALUES (?)", ("2026-01-02",))
        row2 = conn.execute("SELECT d as 'd [date]' FROM t_col").fetchone()
        assert row2 is not None, "t_col 查询未返回结果"
        v2 = row2[0]  # sqlite3.Row/tuple 都支持 [0]
        _assert_is_date(v2, "PARSE_COLNAMES（列名标注 [date]）")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    print("OK")


if __name__ == "__main__":
    main()

