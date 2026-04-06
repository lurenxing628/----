from __future__ import annotations

import os
import sys
import tempfile


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _list_exit_backups(backup_dir: str) -> list:
    if not os.path.exists(backup_dir):
        return []
    return sorted([f for f in os.listdir(backup_dir) if f.startswith("aps_backup_") and f.endswith("_exit.db")])


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.backup import BackupManager
    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.system import SystemConfigService
    from web.bootstrap import factory as factory_mod

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_exit_backup_cfg_")
    db_path = os.path.join(tmpdir, "aps_test.db")
    backup_dir = os.path.join(tmpdir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    ensure_schema(
        db_path,
        logger=None,
        schema_path=os.path.join(repo_root, "schema.sql"),
        backup_dir=backup_dir,
    )

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

    print("OK")


if __name__ == "__main__":
    main()
