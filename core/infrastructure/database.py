import os
import shutil
import sqlite3
import sys
from typing import Optional


CURRENT_SCHEMA_VERSION = 1


def get_connection(db_path: str) -> sqlite3.Connection:
    """
    获取 SQLite 连接（每请求一个连接，避免跨线程问题）。
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(
        db_path,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def ensure_schema(db_path: str, logger=None, schema_path: Optional[str] = None, backup_dir: Optional[str] = None) -> None:
    """
    确保数据库表结构存在。

    说明：使用 IF NOT EXISTS 方式建表，因此可重复执行。
    """
    if not schema_path:
        # 默认优先：仓库根目录（源码运行）
        candidates = [
            os.path.join(os.path.dirname(__file__), "..", "..", "schema.sql"),
        ]
        # PyInstaller onedir：schema.sql 与 exe 同目录（在 app.py 中也会显式传入，这里再做兜底）
        try:
            if getattr(sys, "frozen", False):
                candidates.append(os.path.join(os.path.dirname(sys.executable), "schema.sql"))
        except Exception:
            pass
        # 最后兜底：当前工作目录
        candidates.append(os.path.join(os.getcwd(), "schema.sql"))

        for p in candidates:
            ap = os.path.abspath(p)
            if os.path.exists(ap):
                schema_path = ap
                break

    if not schema_path:
        raise FileNotFoundError("找不到数据库结构文件：schema.sql（请确认工作目录或打包参数包含该文件）")

    schema_path = os.path.abspath(schema_path)
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"找不到数据库结构文件：{schema_path}")

    conn = get_connection(db_path)
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            sql = f.read()
        conn.executescript(sql)
        # SchemaVersion（用于后续迁移判断；若是新库且结构已满足当前版本，会自动提升版本号）
        _ensure_schema_version(conn, logger=logger)
        current_version = _get_schema_version(conn)
        conn.commit()
        if logger:
            logger.info("数据库结构检查完成（已确保所有表存在）。")
    finally:
        conn.close()

    # 需要迁移（ALTER TABLE / 数据清洗等）：迁移前先备份，失败可回滚
    if current_version < CURRENT_SCHEMA_VERSION:
        _migrate_with_backup(
            db_path,
            from_version=current_version,
            to_version=CURRENT_SCHEMA_VERSION,
            backup_dir=backup_dir,
            logger=logger,
        )


def _ensure_schema_version(conn: sqlite3.Connection, logger=None) -> None:
    """
    确保 SchemaVersion 表存在，并写入/修正版本号。

    兼容策略：
    - 老库可能没有 SchemaVersion：插入 version=0
    - 新库可能由 schema.sql 初始化为 version=0：若检测到结构已满足当前版本，则直接将版本提升到 CURRENT_SCHEMA_VERSION（避免无谓迁移/备份）
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS SchemaVersion (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("INSERT OR IGNORE INTO SchemaVersion (id, version) VALUES (1, 0)")

    v = _get_schema_version(conn)
    if v <= 0 and _detect_schema_is_current(conn):
        _set_schema_version(conn, CURRENT_SCHEMA_VERSION)
        if logger:
            try:
                logger.info(f"检测到新库结构已满足当前版本，SchemaVersion 已设为 {CURRENT_SCHEMA_VERSION}。")
            except Exception:
                pass


def _detect_schema_is_current(conn: sqlite3.Connection) -> bool:
    """
    用“结构特征”判断当前 DB 是否已经包含 V1.1 的关键字段（用于新库快速标定版本）。
    """
    # 这些字段/表是 V1.1 之后补齐的代表性特征
    needed = [
        ("Batches", "ready_date"),
        ("Machines", "category"),
        ("MachineDowntimes", "scope_type"),
        ("MachineDowntimes", "scope_value"),
        ("WorkCalendar", "shift_start"),
        ("WorkCalendar", "shift_end"),
    ]
    for table, col in needed:
        if not _column_exists(conn, table, col):
            return False
    # 系统管理表
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('SystemConfig','SystemJobState')"
        ).fetchall()
        names = {r[0] if not isinstance(r, sqlite3.Row) else r["name"] for r in row}
        return "SystemConfig" in names and "SystemJobState" in names
    except Exception:
        return False


def _get_schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        if not row:
            return 0
        return int(row["version"] if isinstance(row, sqlite3.Row) else row[0])
    except Exception:
        return 0


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute("UPDATE SchemaVersion SET version=?, updated_at=CURRENT_TIMESTAMP WHERE id=1", (int(version),))


def _migrate_with_backup(db_path: str, from_version: int, to_version: int, backup_dir: Optional[str] = None, logger=None) -> None:
    backup_path = None
    if backup_dir:
        try:
            os.makedirs(backup_dir, exist_ok=True)
        except Exception:
            backup_dir = None

    # 迁移前备份（若可写）
    if backup_dir:
        try:
            from core.infrastructure.backup import BackupManager

            bm = BackupManager(db_path=db_path, backup_dir=backup_dir, keep_days=365, logger=logger)
            backup_path = bm.backup(suffix=f"before_migrate_v{from_version}_to_v{to_version}")
        except Exception as e:
            # 迁移前无法备份：直接阻断（避免带风险升级）
            if logger:
                logger.error(f"数据库迁移前备份失败，已阻断迁移：{e}")
            raise

    try:
        conn = get_connection(db_path)
        try:
            # 再次确认 version（避免并发/重复调用导致读到旧值）
            _ensure_schema_version(conn, logger=logger)
            current = _get_schema_version(conn)
            if current >= to_version:
                conn.commit()
                return

            for v in range(current + 1, to_version + 1):
                _run_migration(conn, target_version=v, logger=logger)
                _set_schema_version(conn, v)

            conn.commit()
            if logger:
                logger.info(f"数据库迁移完成：SchemaVersion {current} -> {to_version}")
        finally:
            conn.close()
    except Exception:
        # 回滚：用备份文件恢复 db_path
        if backup_path and os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, db_path)
                if logger:
                    logger.error(f"数据库迁移失败，已从备份回滚：{backup_path}")
            except Exception as e:
                if logger:
                    logger.error(f"数据库迁移失败且回滚失败：{e}（backup={backup_path}）")
        raise


def _run_migration(conn: sqlite3.Connection, target_version: int, logger=None) -> None:
    if target_version == 1:
        # v1：补齐 V1.1 关键字段 + 一次性日期清洗
        _ensure_columns(conn)
        _sanitize_batch_dates(conn, logger=logger)
        return
    raise RuntimeError(f"未知的迁移版本：{target_version}")


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


def _sanitize_batch_dates(conn: sqlite3.Connection, logger=None) -> None:
    """
    清洗 Batches 的 DATE 字段（due_date / ready_date）。

    背景：
    - V1 业务约定 DATE 字段使用 `YYYY-MM-DD`（开发文档与 schema.sql）
    - 存量 DB 可能因为 Excel 导入/手工写入导致不合法值（如 `2026`）
    - 不合法值会导致页面/算法无法正确处理；这里做一次性“最佳努力”规范化：
      - 支持：YYYY-MM-DD / YYYY/M/D / YYYY/MM/DD / 带时间的 YYYY-MM-DD HH:MM(:SS) / YYYY-MM-DDTHH:MM(:SS)
      - 无法解析：置为 NULL（避免误判）
    """
    try:
        rows = conn.execute(
            """
            SELECT batch_id, due_date, ready_date
            FROM Batches
            WHERE (due_date IS NOT NULL AND TRIM(CAST(due_date AS TEXT)) <> '')
               OR (ready_date IS NOT NULL AND TRIM(CAST(ready_date AS TEXT)) <> '')
            """
        ).fetchall()
    except Exception:
        return

    if not rows:
        return

    from datetime import datetime
    import re

    def norm(value) -> Optional[str]:
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        s = s.replace("：", ":").replace("/", "-")
        # 若误写入了时间：只取日期部分（DATE 字段不存时分秒）
        if "T" in s:
            s = s.split("T", 1)[0]
        if " " in s:
            s = s.split(" ", 1)[0]
        # 仅接受 YYYY-M-D / YYYY-MM-DD
        if not re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", s):
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d").date().isoformat()
        except Exception:
            return None

    changed = 0
    changed_samples = []
    for r in rows:
        bid = r["batch_id"]
        old_due = r["due_date"]
        old_ready = r["ready_date"]
        new_due = norm(old_due)
        new_ready = norm(old_ready)

        # 只在发生变化时写入（避免无谓更新 updated_at）
        if (str(old_due).strip() if old_due is not None else None) == new_due and (str(old_ready).strip() if old_ready is not None else None) == new_ready:
            continue

        try:
            conn.execute(
                "UPDATE Batches SET due_date = ?, ready_date = ? WHERE batch_id = ?",
                (new_due, new_ready, bid),
            )
            changed += 1
            if len(changed_samples) < 10:
                changed_samples.append(str(bid))
        except Exception:
            continue

    if changed and logger:
        try:
            sample_text = "，".join(changed_samples)
            logger.warning(
                f"已清洗 Batches 的日期字段（due_date/ready_date）：受影响批次数={changed}，样例批次号（最多10个）={sample_text}。"
            )
        except Exception:
            pass
