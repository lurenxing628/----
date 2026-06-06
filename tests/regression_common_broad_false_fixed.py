"""回归测试：迁移公共工具 common.table_exists / column_exists 对非法表名/列名（如 "1-bad-table"）须抛 ValueError 而非误判为不存在，且在连接已关闭时须抛 sqlite3.ProgrammingError 而非静默返回 False。"""

import sqlite3


def test_common_broad_false_fixed(mem_conn) -> None:
    from core.infrastructure.migrations.common import column_exists, table_exists

    conn = mem_conn
    try:
        conn.execute("CREATE TABLE TestTable (id INTEGER PRIMARY KEY, name TEXT)")
        conn.commit()
        assert table_exists(conn, "TestTable") is True
        assert column_exists(conn, "TestTable", "name") is True
        try:
            table_exists(conn, "1-bad-table")
        except ValueError:
            pass
        else:
            raise AssertionError("非法表名不应被当成表不存在")
        try:
            column_exists(conn, "TestTable", "1-bad-column")
        except ValueError:
            pass
        else:
            raise AssertionError("非法列名不应被当成列不存在")
    finally:
        conn.close()

    try:
        table_exists(conn, "TestTable")
    except sqlite3.ProgrammingError:
        pass
    else:
        raise AssertionError("预期 table_exists 在关闭连接时抛出 sqlite3.ProgrammingError，而不是静默返回 False")

    try:
        column_exists(conn, "TestTable", "name")
    except sqlite3.ProgrammingError:
        pass
    else:
        raise AssertionError("预期 column_exists 在关闭连接时抛出 sqlite3.ProgrammingError，而不是静默返回 False")
