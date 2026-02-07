import gc
import os
import shutil
import sqlite3
import sys
import time
from typing import Optional


CURRENT_SCHEMA_VERSION = 4


def _is_windows_lock_error(e: Exception) -> bool:
    try:
        if isinstance(e, PermissionError):
            return True
        winerr = getattr(e, "winerror", None)
        if winerr in (32, 33, 5):
            return True
    except Exception:
        pass
    return False


def _cleanup_sqlite_sidecars(db_path: str, logger=None) -> None:
    # WAL/SHM/JOURNAL 残留可能导致“恢复后仍读到旧数据”或打开失败；最佳努力清理
    for suf in ("-wal", "-shm", "-journal"):
        p = f"{db_path}{suf}"
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception as e:
            if logger:
                try:
                    logger.warning(f"清理 SQLite sidecar 失败：{e}（path={p}）")
                except Exception:
                    pass


def _restore_db_file_from_backup(
    backup_path: str,
    db_path: str,
    logger=None,
    retries: int = 6,
    base_delay_s: float = 0.2,
) -> None:
    bp = os.path.abspath(backup_path)
    dp = os.path.abspath(db_path)
    tmp_path = f"{dp}.rollback_tmp"
    last = None
    r = int(retries) if retries is not None else 1
    if r < 1:
        r = 1
    for i in range(r):
        try:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            shutil.copy2(bp, tmp_path)
            os.replace(tmp_path, dp)
            _cleanup_sqlite_sidecars(dp, logger=logger)
            return
        except Exception as e:
            last = e
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            try:
                gc.collect()
            except Exception:
                pass
            if _is_windows_lock_error(e) and i < r - 1:
                if logger and i == 0:
                    try:
                        logger.warning(f"数据库文件回滚遇到文件锁，准备重试：{e}（db={dp}）")
                    except Exception:
                        pass
                time.sleep(base_delay_s * (i + 1))
                continue
            raise
    if last:
        raise last


def get_connection(db_path: str) -> sqlite3.Connection:
    """
    获取 SQLite 连接（每请求一个连接，避免跨线程问题）。
    """
    # 防御：db_path 可能仅是文件名（dirname 为空串时 makedirs 会报错）
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    # 恢复 sqlite3 的类型探测：保持 DATE/TIMESTAMP 等隐式转换行为一致。
    # 例如：声明为 DATE 的列在查询时会自动转换为 datetime.date（而不是 str）。
    conn = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
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
    # 防御：确保即使未来 try 内出现局部异常吞掉，也不会在迁移判断处引用未定义变量
    current_version: int = 0
    try:
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                sql = f.read()
            # sqlite3.executescript 默认不保证原子性：中途失败会留下“半初始化表结构”。
            # 这里用显式 BEGIN/COMMIT 包裹，让失败时可通过 rollback 回滚。
            script = sql
            try:
                import re

                if not re.search(r"(?im)^\s*BEGIN\b", str(sql or "")):
                    script = "BEGIN;\n" + str(sql or "") + "\nCOMMIT;\n"
            except Exception:
                script = "BEGIN;\n" + str(sql or "") + "\nCOMMIT;\n"
            conn.executescript(script)
            # SchemaVersion（用于后续迁移判断；若是新库且结构已满足当前版本，会自动提升版本号）
            _ensure_schema_version(conn, logger=logger)
            current_version = _get_schema_version(conn)
            conn.commit()
            if logger:
                logger.info("数据库结构检查完成（已确保所有表存在）。")
        except Exception:
            # 失败尽最大努力回滚，避免半初始化状态
            try:
                conn.rollback()
            except Exception:
                pass
            raise
    finally:
        try:
            conn.close()
        except Exception as e:
            if logger:
                try:
                    logger.warning(f"数据库连接关闭失败：{e}")
                except Exception:
                    pass

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
        ("OperatorCalendar", "operator_id"),
        ("OperatorMachine", "skill_level"),
        ("OperatorMachine", "is_primary"),
    ]
    # 复用 migrations 的通用工具（避免 database.py 继续膨胀）
    from .migrations.common import column_exists

    for table, col in needed:
        if not column_exists(conn, table, col):
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
    except sqlite3.OperationalError as e:
        msg = str(e).lower()
        # 仅在“表/列不存在”等可预期场景回落 0；其它错误必须可观测（向上抛出）
        if "no such table" in msg or "no such column" in msg:
            return 0
        raise


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute("UPDATE SchemaVersion SET version=?, updated_at=CURRENT_TIMESTAMP WHERE id=1", (int(version),))


def _migrate_with_backup(db_path: str, from_version: int, to_version: int, backup_dir: Optional[str] = None, logger=None) -> None:
    """
    迁移入口（带强制备份）。

    安全约束：只要进入迁移流程，就必须在迁移前获得一个可用备份；否则直接阻断迁移。
    原因：SQLite 的 DDL/DML 在异常时可能导致“半迁移”，没有备份将无法回滚到一致状态。
    """

    # 1) 计算有效备份目录：未提供则回退到 db 同目录下的 backups/
    effective_backup_dir = ""
    if backup_dir:
        try:
            effective_backup_dir = str(os.fspath(backup_dir)).strip()  # type: ignore[arg-type]
        except Exception:
            effective_backup_dir = str(backup_dir).strip()

    if not effective_backup_dir:
        effective_backup_dir = os.path.join(os.path.dirname(os.path.abspath(db_path)), "backups")
        if logger:
            try:
                logger.warning(f"未提供 backup_dir，迁移将使用默认备份目录：{effective_backup_dir}")
            except Exception:
                pass

    # 2) 确保备份目录可用（不可创建则阻断迁移）
    try:
        os.makedirs(effective_backup_dir, exist_ok=True)
    except Exception as e:
        if logger:
            try:
                logger.error(f"数据库迁移前无法创建备份目录，已阻断迁移：{e}（dir={effective_backup_dir}）")
            except Exception:
                pass
        raise

    # 3) 迁移前强制备份（失败则阻断迁移）
    backup_path = None
    try:
        from core.infrastructure.backup import BackupManager

        bm = BackupManager(db_path=db_path, backup_dir=effective_backup_dir, keep_days=365, logger=logger)
        backup_path = bm.backup(suffix=f"before_migrate_v{from_version}_to_v{to_version}")
    except Exception as e:
        if logger:
            try:
                logger.error(f"数据库迁移前备份失败，已阻断迁移：{e}（dir={effective_backup_dir}）")
            except Exception:
                pass
        raise

    # 4) 执行迁移：使用事务包裹，失败后再用备份做文件级回滚兜底
    try:
        conn = get_connection(db_path)
        try:
            # sqlite3.Connection 的上下文管理器：异常自动 rollback，正常自动 commit
            # 统一事务边界：版本确认 / 迁移 / SchemaVersion 更新都在同一事务中完成
            with conn:
                # 再次确认 version（避免并发/重复调用导致读到旧值）
                _ensure_schema_version(conn, logger=logger)
                current = _get_schema_version(conn)
                if current >= to_version:
                    return

                for v in range(current + 1, to_version + 1):
                    _run_migration(conn, target_version=v, logger=logger)
                    _set_schema_version(conn, v)

            if logger:
                try:
                    logger.info(f"数据库迁移完成：SchemaVersion {current} -> {to_version}")
                except Exception:
                    pass
        finally:
            try:
                conn.close()
            except Exception as e:
                if logger:
                    try:
                        logger.warning(f"数据库连接关闭失败（可能导致文件锁未释放）：{e}")
                    except Exception:
                        pass
            finally:
                # 最佳努力释放 Windows 文件句柄
                try:
                    del conn
                except Exception:
                    pass
                try:
                    gc.collect()
                except Exception:
                    pass
    except Exception:
        # 回滚：用备份文件恢复 db_path
        if backup_path and os.path.exists(backup_path):
            try:
                _restore_db_file_from_backup(backup_path, db_path, logger=logger)
                if logger:
                    try:
                        logger.error(f"数据库迁移失败，已从备份回滚：{backup_path}")
                    except Exception:
                        pass
            except Exception as e:
                if logger:
                    try:
                        logger.error(f"数据库迁移失败且回滚失败：{e}（backup={backup_path}）")
                    except Exception:
                        pass
        raise


def _run_migration(conn: sqlite3.Connection, target_version: int, logger=None) -> None:
    # 迁移实现按版本拆到 core/infrastructure/migrations/*
    from .migrations import run_migration

    run_migration(conn, target_version=int(target_version), logger=logger)
