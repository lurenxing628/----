from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import threading
from unittest import mock


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _set_schema_version(db_path: str, version: int) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE SchemaVersion SET version=? WHERE id=1", (int(version),))
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure import backup as backup_mod
    from core.infrastructure import database as database_mod
    from core.infrastructure.backup import (
        BackupManager,
        MaintenanceWindowError,
        current_thread_holds_maintenance_window,
        is_maintenance_window_active,
        maintenance_window,
    )
    from core.infrastructure.database import ensure_schema

    schema_path = os.path.join(repo_root, "schema.sql")
    tmpdir = tempfile.mkdtemp(prefix="aps_reg_maint_window_")
    db_path = os.path.join(tmpdir, "aps_test.db")
    backup_dir = os.path.join(tmpdir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    ensure_schema(db_path, logger=None, schema_path=schema_path, backup_dir=backup_dir)
    _set_schema_version(db_path, 4)

    mgr = BackupManager(db_path=db_path, backup_dir=backup_dir, keep_days=7, logger=None)
    backup_path = mgr.backup(suffix="seed_v4")

    hold_started = threading.Event()
    hold_release = threading.Event()

    def _hold_window() -> None:
        with maintenance_window(db_path, logger=None, action="test_hold"):
            hold_started.set()
            if not hold_release.wait(5):
                raise RuntimeError("维护窗口测试线程等待超时")

    holder = threading.Thread(target=_hold_window, daemon=True)
    holder.start()
    if not hold_started.wait(3):
        raise RuntimeError("维护窗口未按预期建立")
    if not is_maintenance_window_active(db_path):
        raise RuntimeError("维护窗口建立后未看到锁文件")

    try:
        mgr.backup(suffix="manual")
    except MaintenanceWindowError as e:
        if e.code != "busy":
            raise RuntimeError(f"外部 backup() 预期 busy，实际 {e.code}/{e}")
    else:
        raise RuntimeError("预期 maintenance window 期间外部 backup() 被阻止，但实际成功了")

    try:
        with maintenance_window(db_path, logger=None, action="second"):
            raise RuntimeError("第二个维护操作不应成功进入 maintenance window")
    except MaintenanceWindowError as e:
        if e.code != "busy":
            raise RuntimeError(f"第二个维护操作预期 busy，实际 {e.code}/{e}")

    hold_release.set()
    holder.join(timeout=3)
    if holder.is_alive():
        raise RuntimeError("维护窗口测试线程未正常退出")

    stale_lock = db_path + ".maintenance.lock"
    with open(stale_lock, "w", encoding="utf-8") as f:
        f.write("pid=999999 action=stale ts=2000-01-01T00:00:00")
    if is_maintenance_window_active(db_path, logger=None):
        raise RuntimeError("陈旧维护锁应被保守自愈并清理，而不是继续视为 active")
    if os.path.exists(stale_lock):
        raise RuntimeError("陈旧维护锁自愈后应被删除")

    lock_warnings = []

    class _ListLogger:
        def warning(self, message):
            lock_warnings.append(str(message))

    with mock.patch.object(backup_mod, "read_maintenance_lock_state", side_effect=RuntimeError("lock read boom")):
        try:
            is_maintenance_window_active(db_path, logger=_ListLogger())
        except MaintenanceWindowError as e:
            if e.code != "lock_state_unavailable":
                raise RuntimeError(f"维护锁读取失败预期 lock_state_unavailable，实际 {e.code}/{e}")
        else:
            raise RuntimeError("维护锁读取失败时不应按无维护窗口放行")

        try:
            backup_mod.ensure_backup_allowed(db_path, logger=_ListLogger())
        except MaintenanceWindowError as e:
            if e.code != "lock_state_unavailable":
                raise RuntimeError(f"backup 放行检查预期 lock_state_unavailable，实际 {e.code}/{e}")
        else:
            raise RuntimeError("维护锁读取失败时 ensure_backup_allowed 不应放行")

        try:
            mgr.backup(suffix="lock_read_failed")
        except MaintenanceWindowError as e:
            if e.code != "lock_state_unavailable":
                raise RuntimeError(f"backup() 预期 lock_state_unavailable，实际 {e.code}/{e}")
        else:
            raise RuntimeError("维护锁读取失败时 backup() 不应成功生成备份")

        restore_result = mgr.restore(backup_path)
        if restore_result.ok or restore_result.code != "lock_state_unavailable":
            raise RuntimeError(
                "维护锁读取失败时 restore() 不应继续恢复，实际 "
                f"ok={restore_result.ok} code={restore_result.code} message={restore_result.message}"
            )

    if not any("维护锁状态检测失败" in message for message in lock_warnings):
        raise RuntimeError(f"维护锁读取失败应记录可诊断 warning，实际日志：{lock_warnings}")

    backup_entered = threading.Event()
    backup_release = threading.Event()

    class _ConnProxy:
        def __init__(self, inner, *, on_backup=None):
            self._inner = inner
            self._on_backup = on_backup

        def backup(self, dest):
            if self._on_backup is not None:
                self._on_backup()
            real_dest = getattr(dest, "_inner", dest)
            return self._inner.backup(real_dest)

        def close(self):
            return self._inner.close()

        def __getattr__(self, name):
            return getattr(self._inner, name)

    real_connect = backup_mod.sqlite3.connect

    def _patched_connect(path, *args, **kwargs):
        inner = real_connect(path, *args, **kwargs)
        path_abs = os.path.abspath(str(path))
        if path_abs == os.path.abspath(db_path):
            return _ConnProxy(
                inner,
                on_backup=lambda: (
                    backup_entered.set(),
                    backup_release.wait(5) or (_ for _ in ()).throw(RuntimeError("backup 持锁测试等待超时")),
                )[-1],
            )
        return _ConnProxy(inner)

    backup_done = {"path": None}

    def _run_manual_backup() -> None:
        backup_done["path"] = mgr.backup(suffix="manual_hold")

    with mock.patch.object(backup_mod.sqlite3, "connect", side_effect=_patched_connect):
        worker = threading.Thread(target=_run_manual_backup, daemon=True)
        worker.start()
        if not backup_entered.wait(3):
            raise RuntimeError("backup() 未按预期进入持锁区间")
        if not is_maintenance_window_active(db_path):
            raise RuntimeError("backup() 执行期间应激活维护窗口")
        try:
            mgr.backup(suffix="blocked_while_backup")
        except MaintenanceWindowError as e:
            if e.code != "busy":
                raise RuntimeError(f"backup() 并发阻止预期 busy，实际 {e.code}/{e}")
        else:
            raise RuntimeError("预期 backup() 持锁期间第二次 backup 被阻止，但实际成功了")
        backup_release.set()
        worker.join(timeout=3)
        if worker.is_alive():
            raise RuntimeError("backup() 持锁测试线程未正常退出")
    if not backup_done["path"] or not os.path.exists(str(backup_done["path"])):
        raise RuntimeError("持锁 backup() 完成后应生成备份文件")

    _set_schema_version(db_path, 6)
    _set_schema_version(backup_path, 4)

    observed = {"inside_window": False}
    orig_migrate = database_mod._migrate_with_backup

    def _wrapped_migrate(*args, **kwargs):
        observed["inside_window"] = current_thread_holds_maintenance_window(db_path)
        return orig_migrate(*args, **kwargs)

    with mock.patch.object(database_mod, "_migrate_with_backup", side_effect=_wrapped_migrate):
        with maintenance_window(db_path, logger=None, action="restore_flow"):
            result = mgr.restore(backup_path)
            if not result.ok:
                raise RuntimeError(f"restore() 预期成功，实际 {result.code}: {result.message}")
            if not is_maintenance_window_active(db_path):
                raise RuntimeError("restore_flow 持锁期间锁文件不应消失")
            ensure_schema(db_path, logger=None, schema_path=schema_path, backup_dir=backup_dir)

    if not observed["inside_window"]:
        raise RuntimeError("预期 ensure_schema() 进入 _migrate_with_backup 时仍处于同一 maintenance window")

    print("OK")


if __name__ == "__main__":
    main()
