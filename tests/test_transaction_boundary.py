from __future__ import annotations

import logging
import sqlite3
from typing import List

import pytest


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


def test_transaction_raises_untrusted_when_outer_rollback_fails(caplog):
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
        with pytest.raises(RuntimeError, match="事务回滚失败，连接状态不可信"):
            with manager.transaction():
                raise RuntimeError("original failure")

    assert "rollback fail" in caplog.text
    assert "原始异常=original failure" in caplog.text
    assert "回滚异常=事务回滚失败，连接状态不可信" in caplog.text


def test_transaction_commit_failure_with_rollback_failure_raises_combined_error():
    from core.infrastructure.transaction import TransactionManager

    class CommitAndRollbackFailConn:
        in_transaction = False

        def execute(self, sql):
            return None

        def commit(self):
            raise sqlite3.OperationalError("commit fail")

        def rollback(self):
            raise sqlite3.OperationalError("rollback fail")

    manager = TransactionManager(CommitAndRollbackFailConn())

    with pytest.raises(RuntimeError, match="事务提交失败，且回滚失败；连接状态不可信") as exc_info:
        with manager.transaction():
            pass

    assert "commit fail" in str(exc_info.value.__cause__)


def test_nested_savepoint_rollback_failure_blocks_outer_commit(tmp_path, caplog):
    from core.infrastructure.transaction import TransactionManager

    class RollbackToFailConn:
        def __init__(self, inner):
            self.inner = inner
            self.remaining_failures = 1

        @property
        def in_transaction(self):
            return self.inner.in_transaction

        def execute(self, sql):
            stmt = " ".join(str(sql).split()).upper()
            if stmt.startswith("ROLLBACK TO SAVEPOINT APS_TX_") and self.remaining_failures > 0:
                self.remaining_failures -= 1
                raise sqlite3.OperationalError("rollback-to savepoint failed")
            return self.inner.execute(sql)

        def commit(self):
            return self.inner.commit()

        def rollback(self):
            return self.inner.rollback()

    db_path = tmp_path / "tx_poison.db"
    raw_conn = sqlite3.connect(str(db_path))
    try:
        raw_conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT NOT NULL)")
        raw_conn.commit()

        conn = RollbackToFailConn(raw_conn)
        manager = TransactionManager(conn)

        with caplog.at_level(logging.DEBUG, logger="core.infrastructure.transaction"):
            with pytest.raises(RuntimeError, match="事务状态不可信"):
                with manager.transaction():
                    conn.execute("INSERT INTO t (val) VALUES ('outer_before')")
                    try:
                        with manager.transaction():
                            conn.execute("INSERT INTO t (val) VALUES ('inner_should_not_commit')")
                            raise RuntimeError("inner boom")
                    except RuntimeError as exc:
                        assert "事务回滚失败，连接状态不可信" in str(exc)
                    conn.execute("INSERT INTO t (val) VALUES ('outer_after')")

        rows = [row[0] for row in raw_conn.execute("SELECT val FROM t ORDER BY id").fetchall()]
        assert rows == []
        assert "事务提交成功" not in caplog.text
    finally:
        raw_conn.close()
