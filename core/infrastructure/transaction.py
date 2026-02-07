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
        """
        事务上下文管理器：成功提交、异常回滚，并支持“嵌套事务”。

        说明：
        - SQLite 本身不支持真正的嵌套事务，这里使用 SAVEPOINT 来模拟。
        - 内层失败：仅回滚到内层 SAVEPOINT，不影响外层继续执行。
        - 外层失败：整体回滚。
        - 若进入本上下文前连接已处于事务中（conn.in_transaction=True），则不在外层自动 commit/rollback，
          仅负责本层 SAVEPOINT 的 release/rollback（由外层事务边界负责提交/回滚）。
        """
        conn = self.conn
        _inc_depth(conn)
        owns_tx = False
        sp_name = None
        try:
            depth = int(_depth_map().get(id(conn), 0) or 0)
            sp_name = f"aps_tx_{id(conn)}_{depth}"

            # 仅最外层需要判断“是否由本 TransactionManager 启动事务”
            if depth == 1:
                try:
                    owns_tx = not bool(getattr(conn, "in_transaction", False))
                except Exception:
                    # 防御：极少数连接实现可能没有该属性；此时按“自己负责提交”处理
                    owns_tx = True

            # SAVEPOINT 会在必要时隐式开启事务
            conn.execute(f"SAVEPOINT {sp_name}")

            try:
                yield conn
            except Exception as e:
                # 回滚到本层 savepoint（不影响外层）
                try:
                    conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                except Exception as e2:
                    logger.error(f"SAVEPOINT 回滚失败：{e2}")
                try:
                    conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                except Exception as e2:
                    logger.error(f"SAVEPOINT 释放失败（回滚路径）：{e2}")

                # 最外层且由我们启动的事务：结束事务（避免悬挂在半事务状态）
                if depth == 1 and owns_tx:
                    try:
                        conn.rollback()
                    except Exception:
                        pass

                logger.error(f"事务已回滚：{e}")
                raise
            else:
                # 正常路径：释放本层 savepoint
                try:
                    conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                except Exception as e:
                    # RELEASE 失败时事务状态可能不确定：尽最大努力回滚本层并结束事务（若由我们启动）
                    try:
                        conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                    except Exception as e2:
                        logger.error(f"SAVEPOINT 回滚失败（提交路径）：{e2}")
                    try:
                        conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                    except Exception as e2:
                        logger.error(f"SAVEPOINT 释放失败（提交路径-回滚后）：{e2}")
                    if depth == 1 and owns_tx:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                    logger.error(f"SAVEPOINT 释放失败（提交路径）：{e}")
                    raise

                if depth == 1 and owns_tx:
                    try:
                        conn.commit()
                    except Exception as e:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        logger.error(f"事务提交失败：{e}")
                        raise
                logger.debug("事务提交成功")
        finally:
            _dec_depth(conn)


def transactional(func):
    """事务装饰器：要求 self 上存在 tx_manager 字段。"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        with self.tx_manager.transaction():
            return func(self, *args, **kwargs)

    return wrapper

