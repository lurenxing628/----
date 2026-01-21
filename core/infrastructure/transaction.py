from contextlib import contextmanager
from functools import wraps
import logging


logger = logging.getLogger(__name__)


class TransactionManager:
    """事务管理器（必须保留）。"""

    def __init__(self, db_connection):
        self.conn = db_connection

    @contextmanager
    def transaction(self):
        """事务上下文管理器：成功提交、异常回滚。"""
        try:
            yield self.conn
            self.conn.commit()
            logger.debug("事务提交成功")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"事务已回滚：{e}")
            raise


def transactional(func):
    """事务装饰器：要求 self 上存在 tx_manager 字段。"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        with self.tx_manager.transaction():
            return func(self, *args, **kwargs)

    return wrapper

