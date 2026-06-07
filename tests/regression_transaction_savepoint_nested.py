"""回归测试：TransactionManager 嵌套事务的 savepoint 语义——内层失败只回滚内层、外层失败整体回滚，且当 RELEASE/ROLLBACK TO SAVEPOINT 或 outer commit 失败、或连接缺失/读 in_transaction 抛错无法判断事务所有权时，必须抛错并整体回滚、绝不在不可信状态下静默写入。

并入自 test_transaction_boundary.py（P5.1 单文件挂靠）：事务边界的函数级失败闭合（in_transaction_context depth 查询抛错、外部已有事务时 savepoint-only 不夺取/不提交外部、外层 rollback 失败的不可信抛错与 caplog 文案、commit+rollback 双失败 combined error、嵌套 ROLLBACK TO SAVEPOINT 失败阻止外层提交且不留写入）。这些 case 与上面的 mega-test 同测 savepoint/事务边界契约、坏值边界互补，逐字保真搬入。
"""

import logging
import sqlite3
from typing import List
from unittest import mock

import pytest

from core.infrastructure.transaction import TransactionManager


def test_transaction_savepoint_nested(mem_conn) -> None:
    class _PatchableConn:
        def __init__(self, inner: sqlite3.Connection):
            self._inner = inner

        @property
        def in_transaction(self):
            return getattr(self._inner, "in_transaction", False)

        def execute(self, sql, params=()):
            return self._inner.execute(sql, params)

        def commit(self):
            return self._inner.commit()

        def rollback(self):
            return self._inner.rollback()

        def close(self):
            return self._inner.close()

    class _MissingStateConn:
        def __init__(self, inner: sqlite3.Connection):
            self._inner = inner

        def execute(self, sql, params=()):
            return self._inner.execute(sql, params)

        def commit(self):
            return self._inner.commit()

        def rollback(self):
            return self._inner.rollback()

        def close(self):
            return self._inner.close()

    class _BrokenStateConn(_PatchableConn):
        @property
        def in_transaction(self):
            raise RuntimeError("in_transaction boom")

    conn = mem_conn
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

        # Case 3：内层 RELEASE SAVEPOINT 失败时，应抛错并让外层整体回滚
        conn.execute("DELETE FROM t")
        conn.commit()
        pconn_release = _PatchableConn(conn)
        tm_release = TransactionManager(pconn_release)
        original_execute = pconn_release.execute
        release_state = {"remaining": 1}

        def _fail_inner_release(sql, params=()):
            stmt = " ".join(str(sql).split()).upper()
            if stmt.startswith("RELEASE SAVEPOINT APS_TX_") and release_state["remaining"] > 0:
                release_state["remaining"] -= 1
                raise sqlite3.OperationalError("injected release failure")
            return original_execute(sql, params)

        with mock.patch.object(pconn_release, "execute", side_effect=_fail_inner_release):
            try:
                with tm_release.transaction():
                    pconn_release.execute("INSERT INTO t (val) VALUES ('outer_release')")
                    with tm_release.transaction():
                        pconn_release.execute("INSERT INTO t (val) VALUES ('inner_release')")
                raise AssertionError("预期 inner RELEASE SAVEPOINT 失败时抛出异常")
            except sqlite3.OperationalError as e:
                assert "injected release failure" in str(e), f"异常信息不匹配：{e!r}"

        rows3 = [r[0] for r in conn.execute("SELECT val FROM t ORDER BY id").fetchall()]
        assert rows3 == [], f"inner RELEASE SAVEPOINT 失败后应整体回滚，rows={rows3!r}"

        # Case 4：内层 ROLLBACK TO SAVEPOINT 失败时，必须按连接状态不可信失败闭合，且外层整体回滚
        pconn_rb = _PatchableConn(conn)
        tm_rb = TransactionManager(pconn_rb)
        original_execute_rb = pconn_rb.execute
        rollback_state = {"remaining": 1}

        def _fail_inner_rollback(sql, params=()):
            stmt = " ".join(str(sql).split()).upper()
            if stmt.startswith("ROLLBACK TO SAVEPOINT APS_TX_") and rollback_state["remaining"] > 0:
                rollback_state["remaining"] -= 1
                raise sqlite3.OperationalError("injected rollback-to failure")
            return original_execute_rb(sql, params)

        with mock.patch.object(pconn_rb, "execute", side_effect=_fail_inner_rollback):
            try:
                with tm_rb.transaction():
                    pconn_rb.execute("INSERT INTO t (val) VALUES ('outer_rb')")
                    with tm_rb.transaction():
                        pconn_rb.execute("INSERT INTO t (val) VALUES ('inner_rb')")
                        raise RuntimeError("inner boom")
                raise AssertionError("预期 inner ROLLBACK TO SAVEPOINT 失败时抛出事务不可信异常")
            except RuntimeError as e:
                assert "事务回滚失败，连接状态不可信" in str(e), f"异常信息不匹配：{e!r}"

        rows4 = [r[0] for r in conn.execute("SELECT val FROM t ORDER BY id").fetchall()]
        assert rows4 == [], f"inner ROLLBACK TO SAVEPOINT 失败后应整体回滚，rows={rows4!r}"

        # Case 5：最外层 commit 失败时，应抛错并回滚整个事务
        pconn_commit = _PatchableConn(conn)
        tm_commit = TransactionManager(pconn_commit)
        with mock.patch.object(pconn_commit, "commit", side_effect=sqlite3.OperationalError("injected commit failure")):
            try:
                with tm_commit.transaction():
                    pconn_commit.execute("INSERT INTO t (val) VALUES ('outer_commit_fail')")
                raise AssertionError("预期 outer commit 失败时抛出异常")
            except sqlite3.OperationalError as e:
                assert "injected commit failure" in str(e), f"异常信息不匹配：{e!r}"

        rows5 = [r[0] for r in conn.execute("SELECT val FROM t ORDER BY id").fetchall()]
        assert rows5 == [], f"outer commit 失败后应整体回滚，rows={rows5!r}"

        # Case 6：事务归属判断失败时不能猜自己拥有事务，必须失败闭合。
        broken_conn = _BrokenStateConn(conn)
        tm_broken = TransactionManager(broken_conn)
        try:
            with tm_broken.transaction():
                broken_conn.execute("INSERT INTO t (val) VALUES ('should_not_write')")
            raise AssertionError("预期 in_transaction 读取失败时抛出异常")
        except RuntimeError as e:
            assert "无法安全判断事务所有权" in str(e), f"异常信息不匹配：{e!r}"

        rows6 = [r[0] for r in conn.execute("SELECT val FROM t ORDER BY id").fetchall()]
        assert rows6 == [], f"事务归属未知时不应写入数据，rows={rows6!r}"

        missing_conn = _MissingStateConn(conn)
        tm_missing = TransactionManager(missing_conn)
        try:
            with tm_missing.transaction():
                missing_conn.execute("INSERT INTO t (val) VALUES ('missing_state_should_not_write')")
            raise AssertionError("预期缺少 in_transaction 时抛出异常")
        except RuntimeError as e:
            assert "无法安全判断事务所有权" in str(e), f"异常信息不匹配：{e!r}"

        rows7 = [r[0] for r in conn.execute("SELECT val FROM t ORDER BY id").fetchall()]
        assert rows7 == [], f"事务状态属性缺失时不应写入数据，rows={rows7!r}"

    finally:
        try:
            conn.close()
        except Exception:
            pass


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
            with pytest.raises(RuntimeError, match="已阻止提交"):
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
