from __future__ import annotations

import os
import sys
import tempfile
import threading
import time


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

    from core.infrastructure.backup import BackupManager, maintenance_window
    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.system import SystemConfigService
    from web.bootstrap import factory as factory_mod

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_exit_backup_maint_")
    db_path = os.path.join(tmpdir, "aps_test.db")
    backup_dir = os.path.join(tmpdir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    ensure_schema(
        db_path,
        logger=None,
        schema_path=os.path.join(repo_root, "schema.sql"),
        backup_dir=backup_dir,
    )

    conn = get_connection(db_path)
    try:
        SystemConfigService(conn, logger=None).set_value(
            "auto_backup_enabled",
            "yes",
            description="自动备份（按请求触发；正常退出时也受此开关控制）是否启用：yes/no",
        )
    finally:
        conn.close()

    bm = BackupManager(db_path=db_path, backup_dir=backup_dir, keep_days=7, logger=None)

    hold_started = threading.Event()
    hold_release = threading.Event()

    def _hold_window() -> None:
        with maintenance_window(db_path, logger=None, action="test_exit_guard"):
            hold_started.set()
            if not hold_release.wait(5):
                raise RuntimeError("维护窗口测试线程等待超时")

    holder = threading.Thread(target=_hold_window, daemon=True)
    holder.start()
    if not hold_started.wait(3):
        raise RuntimeError("未能建立维护窗口，无法执行退出备份回归")

    t0 = time.perf_counter()
    ran = factory_mod._run_exit_backup(bm)
    elapsed = time.perf_counter() - t0

    hold_release.set()
    holder.join(timeout=3)
    if holder.is_alive():
        raise RuntimeError("维护窗口测试线程未正常退出")

    if ran:
        raise RuntimeError("维护窗口期间 _run_exit_backup 应跳过，不应执行实际备份")
    if elapsed >= 1.0:
        raise RuntimeError(f"_run_exit_backup 预期 fail-fast，不应长时间等待；实际耗时 {elapsed:.3f}s")
    if _list_exit_backups(backup_dir):
        raise RuntimeError("维护窗口期间不应生成 *_exit.db")

    print("OK")


if __name__ == "__main__":
    main()
