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
        ("OperatorMachine", "skill_level"),
        ("OperatorMachine", "is_primary"),
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
            except Exception:
                pass
    except Exception:
        # 回滚：用备份文件恢复 db_path
        if backup_path and os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, db_path)
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

    # OperatorMachine.skill_level/is_primary（人机关联：技能等级/主操设备）
    if not _column_exists(conn, "OperatorMachine", "skill_level"):
        conn.execute("ALTER TABLE OperatorMachine ADD COLUMN skill_level TEXT DEFAULT 'normal'")
    if not _column_exists(conn, "OperatorMachine", "is_primary"):
        conn.execute("ALTER TABLE OperatorMachine ADD COLUMN is_primary TEXT DEFAULT 'no'")

    # 旧数据回填：将 NULL/空串统一为默认值（避免导出/排序出现空值）
    try:
        conn.execute(
            "UPDATE OperatorMachine SET skill_level = 'normal' "
            "WHERE skill_level IS NULL OR TRIM(CAST(skill_level AS TEXT)) = ''"
        )
    except Exception:
        pass
    try:
        conn.execute(
            "UPDATE OperatorMachine SET is_primary = 'no' "
            "WHERE is_primary IS NULL OR TRIM(CAST(is_primary AS TEXT)) = ''"
        )
    except Exception:
        pass


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

    from datetime import date, datetime
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
        # 仅接受 YYYY-M-D / YYYY-MM-DD（显式组装，避免依赖 strptime 的宽松/严格差异）
        m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
        if not m:
            return None
        try:
            y = int(m.group(1))
            mo = int(m.group(2))
            d = int(m.group(3))
            return date(y, mo, d).isoformat()
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
