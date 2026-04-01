import os
import sqlite3
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.migrations.common import column_exists, table_exists

    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE TestTable (id INTEGER PRIMARY KEY, name TEXT)")
        conn.commit()
        assert table_exists(conn, "TestTable") is True
        assert column_exists(conn, "TestTable", "name") is True
        assert table_exists(conn, "1-bad-table") is False
        assert column_exists(conn, "1-bad-table", "name") is False
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

    print("OK")


if __name__ == "__main__":
    main()
