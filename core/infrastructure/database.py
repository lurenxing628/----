from __future__ import annotations

import gc
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from typing import List, Optional

from .database_bootstrap import (
    bootstrap_missing_tables_from_schema as _bootstrap_missing_tables_from_schema_impl,
)
from .database_bootstrap import (
    build_schema_exec_script as _build_schema_exec_script,
)
from .database_bootstrap import (
    cleanup_probe_db as _cleanup_probe_db_impl,
)
from .database_bootstrap import (
    load_schema_sql as _load_schema_sql,
)
from .database_bootstrap import (
    missing_schema_tables as _missing_schema_tables,
)
from .migration_backup import cleanup_sqlite_sidecars as _cleanup_sqlite_sidecars
from .migration_state import (
    CURRENT_SCHEMA_VERSION,
    MigrationContractError,
)
from .migration_state import (
    build_contract_error as _build_contract_error,
)
from .migration_state import (
    detect_schema_is_current as _detect_schema_is_current,
)
from .migration_state import (
    ensure_schema_version as _ensure_schema_version,
)
from .migration_state import (
    get_schema_version as _get_schema_version,
)
from .migration_state import (
    has_no_user_tables as _has_no_user_tables,
)
from .migration_state import (
    is_truly_empty_db as _is_truly_empty_db,
)
from .migration_state import (
    list_user_tables as _list_user_tables,
)
from .migration_state import (
    set_schema_version as _set_schema_version,
)
from .migrations.common import MigrationOutcome, fallback_log

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "MigrationContractError",
    "get_connection",
    "ensure_schema",
]


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
                    fallback_log(logger, "warning", f"数据库文件回滚遇到文件锁，准备重试：{e}（db={dp}）")
                time.sleep(base_delay_s * (i + 1))
                continue
            raise
    if last:
        raise last


def _bootstrap_missing_tables_from_schema(conn: sqlite3.Connection, schema_sql: str, logger=None) -> List[str]:
    missing_tables = _bootstrap_missing_tables_from_schema_impl(conn, schema_sql, logger=logger)
    try:
        conn.commit()
    except Exception:
        pass
    return missing_tables


def _cleanup_probe_db(db_path: str) -> None:
    _cleanup_probe_db_impl(db_path)
    for suf in ("", "-wal", "-shm", "-journal"):
        path = f"{db_path}{suf}"
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


def ensure_schema(
    db_path: str, logger=None, schema_path: Optional[str] = None, backup_dir: Optional[str] = None
) -> None:
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
            sql = _load_schema_sql(schema_path)
            script = _build_schema_exec_script(sql)

            # 仅在库中不存在任何业务表时才执行 schema.sql 建表。
            # 旧 schema 的空表库不能走这里，否则 CREATE TABLE IF NOT EXISTS
            # 不会修正既有表结构，后续索引/新列依赖会直接失败。
            if _has_no_user_tables(conn):
                conn.executescript(script)

            # 确保 SchemaVersion 表存在，并获取当前版本
            _ensure_schema_version(conn, logger=logger)
            current_version = _get_schema_version(conn)
            conn.commit()
            if logger:
                fallback_log(logger, "info", "数据库结构检查完成（已确保所有表存在）。")
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
                fallback_log(logger, "warning", f"数据库连接关闭失败：{e}")

    # 需要迁移（ALTER TABLE / 数据清洗等）：迁移前先备份，失败可回滚
    if current_version < CURRENT_SCHEMA_VERSION:
        try:
            _preflight_migration_contract(
                db_path,
                to_version=CURRENT_SCHEMA_VERSION,
                schema_sql=sql,
            )
        except MigrationContractError as e:
            if logger:
                fallback_log(logger, "error", str(e))
            raise
        _migrate_with_backup(
            db_path,
            from_version=current_version,
            to_version=CURRENT_SCHEMA_VERSION,
            backup_dir=backup_dir,
            schema_sql=sql,
            logger=logger,
        )


def _preflight_migration_contract(
    db_path: str,
    *,
    to_version: int,
    schema_sql: str,
) -> None:
    fd, probe_path = tempfile.mkstemp(prefix="aps_migration_probe_", suffix=".db")
    os.close(fd)
    try:
        src = None
        probe = None
        try:
            src = get_connection(db_path)
            probe = get_connection(probe_path)
            src.backup(probe)
        finally:
            if probe is not None:
                try:
                    probe.close()
                except Exception:
                    pass
            if src is not None:
                try:
                    src.close()
                except Exception:
                    pass

        conn = None
        try:
            conn = get_connection(probe_path)
            missing_tables = _missing_schema_tables(conn, schema_sql)
            if missing_tables:
                try:
                    _bootstrap_missing_tables_from_schema(conn, schema_sql, logger=None)
                except Exception as e:
                    raise _build_contract_error(missing_tables=missing_tables, bootstrap_error=e) from e
            _ensure_schema_version(conn, logger=None)
            current = _get_schema_version(conn)
            if current >= to_version:
                return
            with conn:
                for v in range(current + 1, to_version + 1):
                    outcome = _run_migration(conn, target_version=v, logger=None)
                    if outcome != MigrationOutcome.APPLIED:
                        raise _build_contract_error(
                            missing_tables=missing_tables,
                            blocked_version=v,
                            blocked_outcome=outcome,
                        )
                    _set_schema_version(conn, v)
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass
    finally:
        _cleanup_probe_db(probe_path)


def _migrate_with_backup(
    db_path: str,
    from_version: int,
    to_version: int,
    backup_dir: Optional[str] = None,
    *,
    schema_sql: Optional[str] = None,
    logger=None,
) -> None:
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
            fallback_log(logger, "warning", f"未提供 backup_dir，迁移将使用默认备份目录：{effective_backup_dir}")

    # 2) 确保备份目录可用（不可创建则阻断迁移）
    try:
        os.makedirs(effective_backup_dir, exist_ok=True)
    except Exception as e:
        if logger:
            fallback_log(
                logger, "error", f"数据库迁移前无法创建备份目录，已阻断迁移：{e}（dir={effective_backup_dir}）"
            )
        raise

    from core.infrastructure.backup import BackupManager, maintenance_window

    with maintenance_window(db_path, logger=logger, action="migrate"):
        # 3) 迁移前强制备份（失败则阻断迁移）
        backup_path = None
        try:
            bm = BackupManager(db_path=db_path, backup_dir=effective_backup_dir, keep_days=365, logger=logger)
            backup_path = bm.backup(suffix=f"before_migrate_v{from_version}_to_v{to_version}")
        except Exception as e:
            if logger:
                fallback_log(logger, "error", f"数据库迁移前备份失败，已阻断迁移：{e}（dir={effective_backup_dir}）")
            raise

        # 4) 执行迁移：使用事务包裹，失败后再用备份做文件级回滚兜底
        try:
            conn = None
            try:
                conn = get_connection(db_path)
                if schema_sql:
                    _bootstrap_missing_tables_from_schema(conn, schema_sql, logger=logger)
                # sqlite3.Connection 的上下文管理器：异常自动 rollback，正常自动 commit
                # 统一事务边界：版本确认 / 迁移 / SchemaVersion 更新都在同一事务中完成
                with conn:
                    # 再次确认 version（避免并发/重复调用导致读到旧值）
                    _ensure_schema_version(conn, logger=logger)
                    current = _get_schema_version(conn)
                    if current >= to_version:
                        return

                    applied_upto = current
                    for v in range(current + 1, to_version + 1):
                        outcome = _run_migration(conn, target_version=v, logger=logger)
                        if outcome == MigrationOutcome.APPLIED:
                            _set_schema_version(conn, v)
                            applied_upto = v
                            continue
                        level = "warning" if outcome == MigrationOutcome.SKIPPED else "error"
                        if logger:
                            fallback_log(
                                logger,
                                level,
                                f"数据库迁移 v{v} 未完整完成（outcome={outcome.value}），SchemaVersion 保持在 {applied_upto}。",
                            )
                        raise _build_contract_error(blocked_version=v, blocked_outcome=outcome)

                if logger:
                    fallback_log(logger, "info", f"数据库迁移完成：SchemaVersion {current} -> {to_version}")
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception as e:
                        if logger:
                            fallback_log(logger, "warning", f"数据库连接关闭失败（可能导致文件锁未释放）：{e}")
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
                        fallback_log(logger, "error", f"数据库迁移失败，已从备份回滚：{backup_path}")
                except Exception as e:
                    if logger:
                        fallback_log(logger, "error", f"数据库迁移失败且回滚失败：{e}（backup={backup_path}）")
            raise


def _run_migration(conn: sqlite3.Connection, target_version: int, logger=None):
    from .migration_runner import run_migration

    return run_migration(conn, target_version=int(target_version), logger=logger)
