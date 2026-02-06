import os
import sqlite3
import sys
import tempfile


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.transaction import TransactionManager

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_tx_savepoint_")
    db_path = os.path.join(tmpdir, "tx_savepoint.db")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT NOT NULL)")
        tm = TransactionManager(conn)

        # Case 1：内层失败仅回滚内层，外层仍可提交
        with tm.transaction():
            conn.execute("INSERT INTO t (val) VALUES ('outer_ok')")
            try:
                with tm.transaction():
                    conn.execute("INSERT INTO t (val) VALUES ('inner_should_rollback')")
                    raise RuntimeError("inner boom")
            except RuntimeError:
                pass
            conn.execute("INSERT INTO t (val) VALUES ('outer_after_inner')")

        rows = [r[0] for r in conn.execute("SELECT val FROM t ORDER BY id").fetchall()]
        assert rows == ["outer_ok", "outer_after_inner"], f"内层回滚语义错误，rows={rows!r}"

        conn.execute("DELETE FROM t")
        conn.commit()

        # Case 2：外层失败应回滚全部（包括内层已“提交”的 savepoint）
        try:
            with tm.transaction():
                conn.execute("INSERT INTO t (val) VALUES ('outer_should_rollback')")
                with tm.transaction():
                    conn.execute("INSERT INTO t (val) VALUES ('inner_should_also_rollback')")
                raise RuntimeError("outer boom")
        except RuntimeError:
            pass

        rows2 = [r[0] for r in conn.execute("SELECT val FROM t ORDER BY id").fetchall()]
        assert rows2 == [], f"外层回滚语义错误，rows={rows2!r}"

        print("OK")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

