from __future__ import annotations

import logging
import sqlite3
from typing import List


def test_in_transaction_context_fails_closed_when_depth_lookup_errors(monkeypatch, caplog):
    from core.infrastructure import transaction as tx_mod

    def _boom(conn):
        raise RuntimeError("depth boom")

    monkeypatch.setattr(tx_mod, "_current_depth", _boom)

    assert tx_mod.in_transaction_context(None) is False
    with caplog.at_level(logging.WARNING, logger=tx_mod.__name__):
        assert tx_mod.in_transaction_context(object()) is True
    assert "读取事务上下文失败" in caplog.text


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


def test_transaction_logs_rollback_failure_without_swallowing_original(caplog):
    from core.infrastructure.transaction import TransactionManager

    class RollbackFailConn:
        in_transaction = False

        def __init__(self) -> None:
            self.statements: List[str] = []

        def execute(self, sql):
            self.statements.append(str(sql))

        def commit(self):
            raise AssertionError("commit should not be called")

        def rollback(self):
            raise sqlite3.OperationalError("rollback fail")

    conn = RollbackFailConn()
    manager = TransactionManager(conn)

    with caplog.at_level(logging.ERROR, logger="core.infrastructure.transaction"):
        try:
            with manager.transaction():
                raise RuntimeError("original failure")
        except RuntimeError as exc:
            assert "original failure" in str(exc)
        else:
            raise AssertionError("原始异常必须继续向外抛出")

    assert "事务回滚失败" in caplog.text
    assert "事务已回滚：original failure" in caplog.text
