import os
import sqlite3
from typing import Optional


def get_connection(db_path: str) -> sqlite3.Connection:
    """
    获取 SQLite 连接（每请求一个连接，避免跨线程问题）。
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def ensure_schema(db_path: str, logger=None, schema_path: Optional[str] = None) -> None:
    """
    确保数据库表结构存在。

    说明：使用 IF NOT EXISTS 方式建表，因此可重复执行。
    """
    schema_path = schema_path or os.path.join(os.path.dirname(__file__), "..", "..", "schema.sql")
    schema_path = os.path.abspath(schema_path)

    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"找不到数据库结构文件：{schema_path}")

    conn = get_connection(db_path)
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            sql = f.read()
        conn.executescript(sql)
        conn.commit()
        if logger:
            logger.info("数据库结构检查完成（已确保所有表存在）。")
    finally:
        conn.close()

