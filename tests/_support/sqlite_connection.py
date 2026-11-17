"""测试用 SQLite 连接：打开参数（锁等待、连接类）由测试决定，打开后的配置与产品连接走同一条路。"""

import sqlite3

from core.infrastructure.sqlite_udf import DETECT_TYPES, configure_connection


def open_test_connection(target, *, timeout=5.0, factory=sqlite3.Connection):
    """按产品口径（DATE 转换、行映射、外键、SQL 函数）打开测试库；`target` 可以是文件路径或 ``":memory:"``。"""
    conn = sqlite3.connect(str(target), detect_types=DETECT_TYPES, timeout=timeout, factory=factory,
                           check_same_thread=False)
    configure_connection(conn)
    return conn
