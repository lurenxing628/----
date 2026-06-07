"""回归测试：factory._run_exit_backup 退出自动备份受 auto_backup_enabled 开关控制——缺省配置下不执行、不生成 *_exit.db、且只读检查不写入默认 SystemConfig；设为 yes 后执行并恰好生成 1 个 *_exit.db（不再产生 *_auto.db）。"""

from __future__ import annotations

import os


def _list_exit_backups(backup_dir: str) -> list:
    if not os.path.exists(backup_dir):
        return []
    return sorted([f for f in os.listdir(backup_dir) if f.startswith("aps_backup_") and f.endswith("_exit.db")])


def test_exit_backup_respects_config(db_path, tmp_path) -> None:

    from core.infrastructure.backup import BackupManager
    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.system import SystemConfigService
    from web.bootstrap import factory as factory_mod

    backup_dir = os.path.join(str(tmp_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)


    bm = BackupManager(db_path=db_path, backup_dir=backup_dir, keep_days=7, logger=None)

    ran_missing = factory_mod._run_exit_backup(bm)
    if ran_missing:
        raise RuntimeError("缺省配置下不应执行退出自动备份")
    if _list_exit_backups(backup_dir):
        raise RuntimeError("缺省配置下不应生成 *_exit.db")

    conn = get_connection(db_path)
    try:
        cfg_count = int(conn.execute("SELECT COUNT(*) FROM SystemConfig").fetchone()[0])
    finally:
        conn.close()
    if cfg_count != 0:
        raise RuntimeError(f"只读退出备份检查不应写入默认配置：SystemConfig.count={cfg_count}")

    conn = get_connection(db_path)
    try:
        SystemConfigService(conn, logger=None).set_value(
            "auto_backup_enabled",
            "yes",
            description="自动备份（按请求触发；正常退出时也受此开关控制）是否启用：yes/no",
        )
    finally:
        conn.close()

    ran_enabled = factory_mod._run_exit_backup(bm)
    if not ran_enabled:
        raise RuntimeError("auto_backup_enabled=yes 时应执行退出自动备份")

    exit_backups = _list_exit_backups(backup_dir)
    if len(exit_backups) != 1:
        raise RuntimeError(f"期望生成 1 个 *_exit.db，实际 {exit_backups!r}")
    if any(name.endswith("_auto.db") for name in os.listdir(backup_dir)):
        raise RuntimeError("退出自动备份不应再生成 *_auto.db")


