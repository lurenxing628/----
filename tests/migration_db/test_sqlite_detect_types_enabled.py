"""回归测试：守护 get_connection() 开启 sqlite3 detect_types（PARSE_DECLTYPES|PARSE_COLNAMES）——DATE 列与列名标注 [date] 的查询结果须返回纯 datetime.date（非 str、非 datetime），否则隐式日期转换失效会引入细微行为差异。"""

import sqlite3
from datetime import date, datetime


def _assert_is_date(v, context: str) -> None:
    # datetime 是 date 的子类，这里显式排除 datetime，确保是纯 date（SQLite DATE 隐式转换）
    ok = isinstance(v, date) and (not isinstance(v, datetime))
    assert ok, f"{context}：预期返回 datetime.date，实际 type={type(v)} value={v!r}"


def test_sqlite_detect_types_enabled():
    """
    回归目标：
    - get_connection() 必须开启 sqlite3 的 detect_types（PARSE_DECLTYPES | PARSE_COLNAMES），
      否则 SQLite 的 DATE 隐式类型转换会失效（DATE 变回 str），产生潜在的细微行为差异。
    """

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



def test_unparseable_stored_date_reads_back_as_text():
    """库里 DATE 列存了非标准写法时，取数不能直接抛 ValueError；原文交给读取端判成"日期无效"。"""

    from core.infrastructure.database import get_connection

    conn = get_connection(":memory:")
    try:
        conn.execute("CREATE TABLE t_bad(d DATE)")
        stored = ("2026/10/01", "2026-02-30", "2026-10-01 00:00:00")
        conn.executemany("INSERT INTO t_bad(d) VALUES (?)", [(value,) for value in stored])
        assert [row["d"] for row in conn.execute("SELECT d FROM t_bad ORDER BY rowid")] == list(stored)

        # 默认转换器原来能读的写法（含不补零的旧值）继续返回日期。
        conn.execute("DELETE FROM t_bad")
        conn.executemany("INSERT INTO t_bad(d) VALUES (?)", [("2026-01-05",), ("2026-1-5",)])
        values = [row["d"] for row in conn.execute("SELECT d FROM t_bad ORDER BY rowid")]
        for value in values:
            _assert_is_date(value, "可解析的 DATE 值")
        assert values == [date(2026, 1, 5), date(2026, 1, 5)]
    finally:
        conn.close()
