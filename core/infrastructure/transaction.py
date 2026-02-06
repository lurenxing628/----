from contextlib import contextmanager
from functools import wraps
import logging
import threading
from typing import Dict


logger = logging.getLogger(__name__)

_TX_LOCAL = threading.local()


def _depth_map() -> Dict[int, int]:
    m = getattr(_TX_LOCAL, "depth_map", None)
    if m is None:
        m = {}
        _TX_LOCAL.depth_map = m
    return m


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
    try:
        return int(_depth_map().get(id(conn), 0) or 0) > 0
    except Exception:
        return False


class TransactionManager:
    """事务管理器（必须保留）。"""

    def __init__(self, db_connection):
        self.conn = db_connection

    @contextmanager
    def transaction(self):
        """事务上下文管理器：成功提交、异常回滚。"""
        _inc_depth(self.conn)
        try:
            yield self.conn
            self.conn.commit()
            logger.debug("事务提交成功")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"事务已回滚：{e}")
            raise
        finally:
            _dec_depth(self.conn)


def transactional(func):
    """事务装饰器：要求 self 上存在 tx_manager 字段。"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        with self.tx_manager.transaction():
            return func(self, *args, **kwargs)

    return wrapper

