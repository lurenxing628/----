"""嵌套事务不提交外部事务，内层回滚不影响外层。"""

import sqlite3


def test_transaction_inside_external_transaction_uses_savepoint_only(tmp_path):
    from core.infrastructure.transaction import TransactionManager

    db_path = tmp_path / "tx_external.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT NOT NULL)")
        conn.commit()
        conn.execute("BEGIN")
        with TransactionManager(conn).transaction():
            conn.execute("INSERT INTO t (val) VALUES ('inside_savepoint')")
        assert conn.in_transaction is True
        conn.rollback()
        rows = conn.execute("SELECT val FROM t").fetchall()
        assert rows == []
    finally:
        conn.close()


def test_transaction_rolls_back_nested_savepoint_without_affecting_outer(tmp_path):
    from core.infrastructure.transaction import TransactionManager

    db_path = tmp_path / "tx_nested.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT NOT NULL)")
        conn.commit()
        manager = TransactionManager(conn)
        with manager.transaction():
            conn.execute("INSERT INTO t (val) VALUES ('outer_ok')")
            try:
                with manager.transaction():
                    conn.execute("INSERT INTO t (val) VALUES ('inner_rollback')")
                    raise RuntimeError("inner boom")
            except RuntimeError:
                pass
            conn.execute("INSERT INTO t (val) VALUES ('outer_after')")

        rows = [row[0] for row in conn.execute("SELECT val FROM t ORDER BY id").fetchall()]
        assert rows == ["outer_ok", "outer_after"]
    finally:
        conn.close()
