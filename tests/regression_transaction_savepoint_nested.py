import os
import sqlite3
import sys
import tempfile
from unittest import mock


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

        # Case 4：内层 ROLLBACK TO SAVEPOINT 失败时，异常仍应向外传播，且外层整体回滚
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
                raise AssertionError("预期 inner ROLLBACK TO SAVEPOINT 失败时抛出原始 inner 异常")
            except RuntimeError as e:
                assert "inner boom" in str(e), f"异常信息不匹配：{e!r}"

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

        print("OK")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
