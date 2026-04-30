from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from functools import wraps
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_TX_LOCAL = threading.local()


def _depth_map() -> Dict[int, int]:
    m = getattr(_TX_LOCAL, "depth_map", None)
    if m is None:
        m = {}
        _TX_LOCAL.depth_map = m
    return m


def _poison_map() -> Dict[int, BaseException]:
    m = getattr(_TX_LOCAL, "poison_map", None)
    if m is None:
        m = {}
        _TX_LOCAL.poison_map = m
    return m


def _mark_poisoned(conn, exc: BaseException) -> None:
    _poison_map()[id(conn)] = exc


def _poison_reason(conn) -> Optional[BaseException]:
    return _poison_map().get(id(conn))


def _clear_poison(conn) -> None:
    _poison_map().pop(id(conn), None)


def _inc_depth(conn) -> None:
    m = _depth_map()
    key = id(conn)
    m[key] = int(m.get(key, 0) or 0) + 1


def _dec_depth(conn) -> None:
    m = _depth_map()
    key = id(conn)
    d = int(m.get(key, 0) or 0)
    if d <= 1:
        m.pop(key, None)
    else:
        m[key] = d - 1


def in_transaction_context(conn) -> bool:
    """
    判断当前线程是否处于该 conn 的 TransactionManager.transaction() 上下文中。

    用途：避免在事务内执行隐式 commit()（例如 OperationLogger）。
    """
    if conn is None:
        return False
    try:
        return _current_depth(conn) > 0
    except Exception as exc:
        logger.warning("读取事务上下文失败，按处于事务内处理：%s", exc)
        return True


def _current_depth(conn) -> int:
    return int(_depth_map().get(id(conn), 0) or 0)


def _owns_transaction(conn, depth: int) -> bool:
    if depth != 1:
        return False
    try:
        return not bool(conn.in_transaction)
    except AttributeError as exc:
        raise RuntimeError("事务连接缺少 in_transaction，无法安全判断事务所有权。") from exc
    except Exception as exc:
        raise RuntimeError("读取事务状态失败，无法安全判断事务所有权。") from exc


def _savepoint_name(conn, depth: int) -> str:
    return f"aps_tx_{id(conn)}_{depth}"


def _begin_scope(conn, depth: int, owns_tx: bool) -> Optional[str]:
    if depth == 1 and owns_tx:
        # 最外层且由我们负责事务边界：必须显式 BEGIN，避免最外层 SAVEPOINT 在 RELEASE 后已提交，
        # 导致后续 commit() 再失败时来不及回滚。
        conn.execute("BEGIN")
        return None

    sp_name = _savepoint_name(conn, depth)
    conn.execute(f"SAVEPOINT {sp_name}")
    return sp_name


def _rollback_savepoint(conn, sp_name: str) -> None:
    try:
        conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
    except Exception as e:
        logger.error(f"SAVEPOINT 回滚失败：{e}")
        raise RuntimeError(f"SAVEPOINT 回滚失败：{e}") from e
    try:
        conn.execute(f"RELEASE SAVEPOINT {sp_name}")
    except Exception as e:
        logger.error(f"SAVEPOINT 释放失败（回滚路径）：{e}")
        raise RuntimeError(f"SAVEPOINT 释放失败（回滚路径）：{e}") from e


def _rollback_outer_transaction(conn) -> None:
    try:
        conn.rollback()
    except Exception as exc:
        logger.error(f"事务回滚失败，连接状态不可信：{exc}")
        raise RuntimeError("事务回滚失败，连接状态不可信") from exc


def _rollback_scope(conn, depth: int, owns_tx: bool, sp_name: Optional[str]) -> None:
    if sp_name is not None:
        # 回滚到本层 savepoint（不影响外层）
        _rollback_savepoint(conn, sp_name)
    elif depth == 1 and owns_tx:
        # 最外层且由我们启动的事务：结束事务（避免悬挂在半事务状态）
        _rollback_outer_transaction(conn)


def _release_savepoint(conn, sp_name: str) -> None:
    try:
        conn.execute(f"RELEASE SAVEPOINT {sp_name}")
    except Exception as e:
        # RELEASE 失败时事务状态可能不确定：尽最大努力回滚本层并结束事务（若由我们启动）
        try:
            conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
        except Exception as e2:
            logger.error(f"SAVEPOINT 回滚失败（提交路径）：{e2}")
            raise RuntimeError(f"SAVEPOINT 释放失败且回滚失败：{e}; rollback={e2}") from e
        try:
            conn.execute(f"RELEASE SAVEPOINT {sp_name}")
        except Exception as e2:
            logger.error(f"SAVEPOINT 释放失败（提交路径-回滚后）：{e2}")
            raise RuntimeError(f"SAVEPOINT 释放失败且回滚后释放失败：{e}; release_after_rollback={e2}") from e
        logger.error(f"SAVEPOINT 释放失败（提交路径）：{e}")
        raise


def _commit_outer_transaction(conn) -> None:
    try:
        conn.commit()
    except Exception as e:
        try:
            _rollback_outer_transaction(conn)
        except Exception as rollback_exc:
            logger.error(f"事务提交失败，且回滚失败；连接状态不可信：commit={e}; rollback={rollback_exc}")
            raise RuntimeError("事务提交失败，且回滚失败；连接状态不可信") from e
        logger.error(f"事务提交失败：{e}")
        raise


def _commit_scope(conn, depth: int, owns_tx: bool, sp_name: Optional[str]) -> None:
    if sp_name is not None:
        # 正常路径：释放本层 savepoint
        _release_savepoint(conn, sp_name)
    elif depth == 1 and owns_tx:
        _commit_outer_transaction(conn)


def _block_commit_if_poisoned(conn, depth: int, owns_tx: bool, sp_name: Optional[str]) -> None:
    reason = _poison_reason(conn)
    if reason is None:
        return
    try:
        _rollback_scope(conn, depth, owns_tx, sp_name)
    except Exception as rollback_exc:
        logger.error(f"事务状态不可信后的回滚也失败：{rollback_exc}")
    raise RuntimeError(f"事务状态不可信，已阻止提交：{reason}") from reason


@contextmanager
def _transaction_scope(conn):
    _inc_depth(conn)
    sp_name = None
    depth = 0
    try:
        depth = _current_depth(conn)
        owns_tx = _owns_transaction(conn, depth)
        sp_name = _begin_scope(conn, depth, owns_tx)

        try:
            yield conn
        except Exception as e:
            try:
                _rollback_scope(conn, depth, owns_tx, sp_name)
            except Exception as rollback_exc:
                _mark_poisoned(conn, rollback_exc)
                logger.error(f"事务回滚失败，事务状态不可信：原始异常={e}; 回滚异常={rollback_exc}")
                raise RuntimeError("事务回滚失败，连接状态不可信") from rollback_exc
            logger.error(f"事务已回滚：{e}")
            raise
        else:
            _block_commit_if_poisoned(conn, depth, owns_tx, sp_name)
            try:
                _commit_scope(conn, depth, owns_tx, sp_name)
            except Exception as commit_exc:
                _mark_poisoned(conn, commit_exc)
                raise
            logger.debug("事务提交成功")
    finally:
        if depth <= 1:
            _clear_poison(conn)
        _dec_depth(conn)


class TransactionManager:
    """事务管理器（必须保留）。"""

    def __init__(self, db_connection):
        self.conn = db_connection

    def transaction(self):
        """
        事务上下文管理器：成功提交、异常回滚，并支持“嵌套事务”。

        说明：
        - SQLite 本身不支持真正的嵌套事务，这里对“最外层自有事务”使用 BEGIN/COMMIT，
          对嵌套层（或外部已开启事务时）使用 SAVEPOINT 来模拟。
        - 内层失败：仅回滚到内层 SAVEPOINT，不影响外层继续执行。
        - 外层失败：整体回滚。
        - 若进入本上下文前连接已处于事务中（conn.in_transaction=True），则不在外层自动 commit/rollback，
          仅负责本层 SAVEPOINT 的 release/rollback（由外层事务边界负责提交/回滚）。
        """
        return _transaction_scope(self.conn)


def transactional(func):
    """事务装饰器：要求 self 上存在 tx_manager 字段。"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        with self.tx_manager.transaction():
            return func(self, *args, **kwargs)

    return wrapper
