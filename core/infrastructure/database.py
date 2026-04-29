from __future__ import annotations

import gc
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
from typing import List, Optional

from .migrations.common import MigrationOutcome, fallback_log

CURRENT_SCHEMA_VERSION = 7
_CREATE_TABLE_RE = re.compile(r"(?ims)^\s*(CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(.*?\);)")
_CREATE_INDEX_RE = re.compile(
    r"(?im)^\s*(CREATE\s+(?:UNIQUE\s+)?INDEX\s+IF\s+NOT\s+EXISTS\s+[A-Za-z_][A-Za-z0-9_]*\s+ON\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(.*?\);)"
)


class MigrationContractError(RuntimeError):
    """迁移契约不满足：允许补缺失整表，但不允许静默吞掉复杂残缺库。"""


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
                fallback_log(logger, "warning", f"清理 SQLite sidecar 失败：{e}（path={p}）")


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


def _load_schema_sql(schema_path: str) -> str:
    with open(schema_path, encoding="utf-8") as f:
        return f.read()


def _build_schema_exec_script(sql: str) -> str:
    script = str(sql or "")
    try:
        # 只有在没有显式 BEGIN 时才包裹
        if not re.search(r"(?im)^\s*BEGIN\b", script):
            # 移除 PRAGMA foreign_keys = ON; 因为它不能在事务中执行
            clean_sql = re.sub(r"(?im)^\s*PRAGMA\s+foreign_keys\s*=\s*\w+;?", "", script)
            return "BEGIN;\n" + clean_sql + "\nCOMMIT;\n"
    except Exception:
        return script
    return script


def _declared_schema_tables(schema_sql: str) -> List[str]:
    tables: List[str] = []
    for match in _CREATE_TABLE_RE.finditer(str(schema_sql or "")):
        name = str(match.group(2) or "").strip()
        if not name or name == "SchemaVersion" or name in tables:
            continue
        tables.append(name)
    return tables


def _schema_create_table_statements(schema_sql: str) -> dict:
    statements = {}
    for match in _CREATE_TABLE_RE.finditer(str(schema_sql or "")):
        stmt = str(match.group(1) or "").strip()
        name = str(match.group(2) or "").strip()
        if not stmt or not name or name == "SchemaVersion":
            continue
        statements[name] = stmt
    return statements


def _schema_index_statements(schema_sql: str) -> List[tuple]:
    statements = []
    for match in _CREATE_INDEX_RE.finditer(str(schema_sql or "")):
        stmt = str(match.group(1) or "").strip()
        table = str(match.group(2) or "").strip()
        if not stmt or not table:
            continue
        statements.append((table, stmt))
    return statements


def _build_statement_script(statements: List[str]) -> str:
    clean = [str(stmt or "").strip() for stmt in statements if str(stmt or "").strip()]
    if not clean:
        return ""
    return "BEGIN;\n" + "\n".join(clean) + "\nCOMMIT;\n"


def _missing_schema_tables(conn: sqlite3.Connection, schema_sql: str) -> List[str]:
    existing = set(_list_user_tables(conn))
    return [name for name in _declared_schema_tables(schema_sql) if name not in existing]


def _bootstrap_missing_tables_from_schema(conn: sqlite3.Connection, schema_sql: str, logger=None) -> List[str]:
    missing_tables = _missing_schema_tables(conn, schema_sql)
    if not missing_tables:
        return []
    table_statements = _schema_create_table_statements(schema_sql)
    index_statements = _schema_index_statements(schema_sql)
    selected_statements: List[str] = []
    for table in missing_tables:
        stmt = table_statements.get(table)
        if stmt:
            selected_statements.append(stmt)
    for table, stmt in index_statements:
        if table in missing_tables:
            selected_statements.append(stmt)
    script = _build_statement_script(selected_statements)
    if not script:
        return []
    conn.executescript(script)
    try:
        conn.commit()
    except Exception:
        pass
    if logger:
        fallback_log(
            logger, "warning", f"检测到非空数据库缺失整表，已按 schema.sql 补齐：{', '.join(missing_tables)}。"
        )
    return missing_tables


def _cleanup_probe_db(db_path: str) -> None:
    for suf in ("", "-wal", "-shm", "-journal"):
        path = f"{db_path}{suf}"
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


def _build_contract_error(
    *,
    missing_tables: Optional[List[str]] = None,
    blocked_version: Optional[int] = None,
    blocked_outcome: Optional[MigrationOutcome] = None,
    bootstrap_error: Optional[Exception] = None,
) -> MigrationContractError:
    parts = ["检测到非空数据库存在不受支持的残缺结构。"]
    if missing_tables:
        parts.append(f"已识别缺失整表：{', '.join(missing_tables)}。")
    parts.append("系统只会自动补齐缺失整表；现有表结构残缺请先人工修复或恢复到完整备份后再重试。")
    if bootstrap_error is not None:
        parts.append(f"缺失整表预补齐失败：{bootstrap_error}")
    elif blocked_version is not None and blocked_outcome is not None:
        parts.append(f"迁移预检在 v{blocked_version} 返回 {blocked_outcome.value}。")
    return MigrationContractError(" ".join(parts))


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


def _ensure_schema_version(conn: sqlite3.Connection, logger=None) -> None:
    """
    确保 SchemaVersion 表存在，并写入/修正版本号。

    兼容策略：
    - 老库可能没有 SchemaVersion：插入 version=0
    - 新库可能由 schema.sql 初始化为 version=0：若检测到结构已满足当前版本且库中仍无业务数据，则直接将版本提升到 CURRENT_SCHEMA_VERSION（避免无谓迁移/备份）
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
    if v <= 0 and _detect_schema_is_current(conn) and _is_truly_empty_db(conn):
        _set_schema_version(conn, CURRENT_SCHEMA_VERSION)
        if logger:
            fallback_log(
                logger, "info", f"检测到新库结构已满足当前版本，SchemaVersion 已设为 {CURRENT_SCHEMA_VERSION}。"
            )


def _is_truly_empty_db(conn: sqlite3.Connection) -> bool:
    for name in _list_user_tables(conn):
        quoted_name = '"' + str(name).replace('"', '""') + '"'
        row = conn.execute(f"SELECT 1 FROM {quoted_name} LIMIT 1").fetchone()
        if row is not None:
            return False
    return True


def _list_user_tables(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
          AND name <> 'SchemaVersion'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [r["name"] if isinstance(r, sqlite3.Row) else r[0] for r in rows]


def _has_no_user_tables(conn: sqlite3.Connection) -> bool:
    return len(_list_user_tables(conn)) == 0


def _detect_schema_is_current(conn: sqlite3.Connection) -> bool:
    """
    用“结构特征”判断当前 DB 是否已经包含当前 schema.sql 的关键字段，
    用于 brand-new 空库初始化后的版本快进。

    注意：
    - 这是“可快进”的结构特征检查，不等于对所有迁移副作用的完整等价证明
    - 如未来新增迁移版本，需要同步审视这里的特征集合是否仍能代表当前结构
    """
    # 这些字段/表是 V1.1 之后补齐的代表性特征
    needed = [
        ("ResourceTeams", "team_id"),
        ("Operators", "team_id"),
        ("Machines", "category"),
        ("Machines", "team_id"),
        ("Batches", "ready_date"),
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
        if not ("SystemConfig" in names and "SystemJobState" in names):
            return False
        index_row = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='index'
              AND name='idx_schedule_version_op_unique'
              AND tbl_name='Schedule'
            LIMIT 1
            """
        ).fetchone()
        return index_row is not None
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


def _run_migration(conn: sqlite3.Connection, target_version: int, logger=None) -> MigrationOutcome:
    # 迁移实现按版本拆到 core/infrastructure/migrations/*
    from .migrations import run_migration

    return run_migration(conn, target_version=int(target_version), logger=logger)
