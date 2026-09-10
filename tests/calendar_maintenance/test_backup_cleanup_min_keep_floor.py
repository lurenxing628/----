"""合同测试：备份轮换修剪的数量保底与失败跳过（B01，2026-07-19 盲区扫描）——
(1) 两条修剪路径（BackupManager.cleanup_old_backups 手动按钮路径 / cleanup_backups_with_limit 自动路径）
无论天龄都至少保留最新 MIN_KEEP_BACKUPS 份，长期停机后所有备份全部过期时不得剪光（before_restore
等安全快照同前缀、同受保底保护）；(2) run_if_due 在当轮自动备份失败（due=True 且 ran=False）时必须
跳过本轮自动清理并留 warning 痕，不写 cleanup job_state；备份成功时清理照常执行且保底生效。"""

from __future__ import annotations

import os
import time
from datetime import datetime

import core.services.system.maintenance.backup_task as backup_task_mod
from core.infrastructure.backup import MIN_KEEP_BACKUPS, BackupManager
from core.infrastructure.database import get_connection
from core.services.system import SystemMaintenanceService
from core.services.system.maintenance.cleanup_task import cleanup_backups_with_limit


class _CollectingLogger:
    def __init__(self) -> None:
        self.warnings = []
        self.errors = []
        self.infos = []

    def warning(self, message) -> None:
        self.warnings.append(str(message))

    def error(self, message) -> None:
        self.errors.append(str(message))

    def info(self, message) -> None:
        self.infos.append(str(message))


def _fmt_db_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _seed_expired_backups(backup_dir: str, names) -> list:
    """按传入顺序生成过期备份文件，越靠后 mtime 越新（全部早于默认 keep_days=7 的 cutoff）。"""
    paths = []
    base = time.time() - 60 * 24 * 3600
    for index, name in enumerate(names):
        path = os.path.join(backup_dir, name)
        with open(path, "wb") as f:
            f.write(b"seed")
        mtime = base + index * 3600
        os.utime(path, (mtime, mtime))
        paths.append(path)
    return paths


def _upsert_system_config(conn, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO SystemConfig (config_key, config_value, description, updated_at)
        VALUES (?, ?, '', CURRENT_TIMESTAMP)
        ON CONFLICT(config_key) DO UPDATE SET
          config_value = excluded.config_value,
          updated_at = CURRENT_TIMESTAMP
        """,
        (str(key), str(value)),
    )


def test_cleanup_backups_with_limit_keeps_newest_min_keep_even_all_expired(tmp_path) -> None:
    names = [f"aps_backup_2000010{i}_000000_auto.db" for i in range(1, 6)]
    paths = _seed_expired_backups(str(tmp_path), names)

    removed, meta = cleanup_backups_with_limit(
        str(tmp_path),
        keep_days=7,
        max_delete=200,
        fmt_db_dt_fn=_fmt_db_dt,
    )

    assert meta["min_keep"] == MIN_KEEP_BACKUPS == 3
    assert removed == 2, f"5 份全过期时只允许删到保底线（删 2 留 3），实际 removed={removed} meta={meta}"
    assert meta["kept_recent_count"] == 3
    assert meta["candidates"] == 2
    survivors = [p for p in paths if os.path.exists(p)]
    assert survivors == paths[2:], f"应保留 mtime 最新的 3 份，实际存活：{[os.path.basename(p) for p in survivors]}"


def test_cleanup_backups_with_limit_fresh_files_do_not_consume_floor(tmp_path) -> None:
    expired_names = [f"aps_backup_2000010{i}_000000_auto.db" for i in range(1, 5)]
    expired_paths = _seed_expired_backups(str(tmp_path), expired_names)
    fresh_paths = []
    for name in ("aps_backup_20990101_000000_auto.db", "aps_backup_20990102_000000_auto.db"):
        path = os.path.join(str(tmp_path), name)
        with open(path, "wb") as f:
            f.write(b"fresh")
        fresh_paths.append(path)

    removed, meta = cleanup_backups_with_limit(
        str(tmp_path),
        keep_days=7,
        max_delete=200,
        fmt_db_dt_fn=_fmt_db_dt,
    )

    # 保底集合 = 全部备份里 mtime 最新的 3 份 = 2 份新鲜 + 1 份最新过期 → 过期候选剩 3 份。
    assert removed == 3, f"实际 removed={removed} meta={meta}"
    assert meta["kept_recent_count"] == 1
    assert all(os.path.exists(p) for p in fresh_paths)
    assert os.path.exists(expired_paths[3]) and not any(os.path.exists(p) for p in expired_paths[:3])


def test_cleanup_old_backups_keeps_newest_min_keep_including_safety_snapshots(tmp_path) -> None:
    backup_dir = os.path.join(str(tmp_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    db_path = os.path.join(str(tmp_path), "aps.db")
    with open(db_path, "wb") as f:
        f.write(b"db")
    # 最新一份是 before_restore 安全快照：保底按数量下限保护，同前缀一并覆盖。
    names = [
        "aps_backup_20000101_000000_auto.db",
        "aps_backup_20000102_000000_auto.db",
        "aps_backup_20000103_000000_auto.db",
        "aps_backup_20000104_000000_before_restore.db",
    ]
    paths = _seed_expired_backups(backup_dir, names)

    mgr = BackupManager(db_path=db_path, backup_dir=backup_dir, keep_days=7, logger=None)
    result = mgr.cleanup_old_backups()

    assert result["min_keep"] == MIN_KEEP_BACKUPS == 3
    assert result["removed_count"] == 1, f"4 份全过期时只允许删到保底线（删 1 留 3），实际：{result}"
    assert result["kept_recent_count"] == 3
    assert not os.path.exists(paths[0])
    assert all(os.path.exists(p) for p in paths[1:]), "最新 3 份（含 before_restore 快照）必须存活"


def test_run_if_due_skips_backup_cleanup_when_auto_backup_fails(db_path, tmp_path, monkeypatch) -> None:
    backup_dir = os.path.join(str(tmp_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    seeded = _seed_expired_backups(
        backup_dir, [f"aps_backup_2000010{i}_000000_auto.db" for i in range(1, 6)]
    )

    class _BoomBackupManager:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def backup(self, suffix=None):
            raise RuntimeError("backup boom for skip contract")

    monkeypatch.setattr(backup_task_mod, "BackupManager", _BoomBackupManager)

    conn = get_connection(db_path)
    logger = _CollectingLogger()
    try:
        _upsert_system_config(conn, "auto_backup_enabled", "yes")
        _upsert_system_config(conn, "auto_backup_cleanup_enabled", "yes")
        conn.commit()

        SystemMaintenanceService.reset_throttle_for_tests()
        result = SystemMaintenanceService.run_if_due(
            conn,
            db_path=db_path,
            backup_dir=backup_dir,
            backup_keep_days_default=7,
            logger=logger,
            op_logger=None,
        )

        backup_detail = result.details.get("auto_backup") or {}
        assert backup_detail.get("due") is True and "backup boom" in str(backup_detail.get("error")), backup_detail
        cleanup_detail = result.details.get("auto_backup_cleanup") or {}
        assert cleanup_detail.get("skipped") is True, f"当轮备份失败必须跳过清理：{result.details}"
        assert cleanup_detail.get("reason") == "auto_backup_failed_this_round", cleanup_detail
        assert all(os.path.exists(p) for p in seeded), "跳过清理的当轮不得删除任何历史备份"
        assert any("已跳过本轮自动清理备份" in message for message in logger.warnings), logger.warnings

        row = conn.execute(
            "SELECT 1 FROM SystemJobState WHERE job_key = ?",
            (SystemMaintenanceService.JOB_AUTO_BACKUP_CLEANUP,),
        ).fetchone()
        assert row is None, "跳过的清理不得写 job_state（下一轮备份成功后清理应照常恢复）"
    finally:
        SystemMaintenanceService.reset_throttle_for_tests()
        try:
            conn.close()
        except Exception:
            pass


def test_run_if_due_cleanup_runs_with_floor_when_auto_backup_succeeds(db_path, tmp_path) -> None:
    backup_dir = os.path.join(str(tmp_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    seeded = _seed_expired_backups(
        backup_dir, [f"aps_backup_2000010{i}_000000_auto.db" for i in range(1, 6)]
    )

    conn = get_connection(db_path)
    try:
        _upsert_system_config(conn, "auto_backup_enabled", "yes")
        _upsert_system_config(conn, "auto_backup_cleanup_enabled", "yes")
        conn.commit()

        SystemMaintenanceService.reset_throttle_for_tests()
        result = SystemMaintenanceService.run_if_due(
            conn,
            db_path=db_path,
            backup_dir=backup_dir,
            backup_keep_days_default=7,
            logger=None,
            op_logger=None,
        )

        backup_detail = result.details.get("auto_backup") or {}
        assert backup_detail.get("created"), f"真实库自动备份应成功：{result.details}"
        cleanup_detail = result.details.get("auto_backup_cleanup") or {}
        assert cleanup_detail.get("skipped") is not True, cleanup_detail
        # 保底集合 = 新自动备份 + 最新 2 份过期 → 5 份过期删 3 留 2。
        assert cleanup_detail.get("removed_count") == 3, cleanup_detail
        assert cleanup_detail.get("kept_recent_count") == 2, cleanup_detail
        assert not any(os.path.exists(p) for p in seeded[:3])
        assert all(os.path.exists(p) for p in seeded[3:])
    finally:
        SystemMaintenanceService.reset_throttle_for_tests()
        try:
            conn.close()
        except Exception:
            pass
