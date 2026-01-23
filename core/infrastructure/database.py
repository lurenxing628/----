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
        # 对存量 DB 做轻量迁移：补齐缺失列（保持幂等）
        _ensure_columns(conn)
        conn.commit()
        if logger:
            logger.info("数据库结构检查完成（已确保所有表存在）。")
    finally:
        conn.close()


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        for r in rows:
            if (r["name"] if isinstance(r, sqlite3.Row) else r[1]) == column:
                return True
        return False
    except Exception:
        return False


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """
    轻量迁移（幂等）：为存量表补齐新增字段。

    说明：
    - SQLite 的 CREATE TABLE IF NOT EXISTS 不会修改既有表结构
    - 这里用 PRAGMA table_info + ALTER TABLE ADD COLUMN 做“缺列补齐”
    """
    # Batches.ready_date（齐套日期）
    if not _column_exists(conn, "Batches", "ready_date"):
        conn.execute("ALTER TABLE Batches ADD COLUMN ready_date DATE")

    # Machines.category（设备类别）
    if not _column_exists(conn, "Machines", "category"):
        conn.execute("ALTER TABLE Machines ADD COLUMN category TEXT")

    # MachineDowntimes.scope_type/scope_value（停机范围预留字段）
    if not _column_exists(conn, "MachineDowntimes", "scope_type"):
        conn.execute("ALTER TABLE MachineDowntimes ADD COLUMN scope_type TEXT DEFAULT 'machine'")
    if not _column_exists(conn, "MachineDowntimes", "scope_value"):
        conn.execute("ALTER TABLE MachineDowntimes ADD COLUMN scope_value TEXT")

    # WorkCalendar.shift_start/shift_end（班次起止时间）
    if not _column_exists(conn, "WorkCalendar", "shift_start"):
        conn.execute("ALTER TABLE WorkCalendar ADD COLUMN shift_start TEXT")
    if not _column_exists(conn, "WorkCalendar", "shift_end"):
        conn.execute("ALTER TABLE WorkCalendar ADD COLUMN shift_end TEXT")

