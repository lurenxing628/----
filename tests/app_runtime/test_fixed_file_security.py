"""回归测试：固定名运行文件和备份清理不跟随软链接。"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

import pytest


def _symlink_supported(tmp_path: Path) -> bool:
    try:
        target = tmp_path / "_target"
        target.write_text("x", encoding="utf-8")
        link = tmp_path / "_link"
        os.symlink(str(target), str(link))
        link.unlink()
        return True
    except (OSError, NotImplementedError):
        return False


def _skip_without_symlink(tmp_path: Path) -> None:
    if not _symlink_supported(tmp_path):
        pytest.skip("平台不支持创建软链接（如 Windows 无权限）")


def _skip_without_hardlink(tmp_path: Path) -> None:
    try:
        target = tmp_path / "_hardlink_target"
        target.write_text("x", encoding="utf-8")
        link = tmp_path / "_hardlink"
        os.link(str(target), str(link))
        link.unlink()
    except (OSError, NotImplementedError):
        pytest.skip("平台不支持创建硬链接")


def _sqlite_uri_database_path(database) -> str:
    text = os.fspath(database)
    if not text.startswith("file:"):
        return text
    return unquote(text[5:].split("?", 1)[0])


def _valid_runtime_contract_payload(runtime_dir: Path, *, log_dir: Path):
    return {
        "contract_version": 1,
        "pid": 123,
        "host": "127.0.0.1",
        "port": 5728,
        "shutdown_token": "token",
        "exe_path": sys.executable,
        "runtime_dir": str(runtime_dir),
        "chrome_profile_dir": str(runtime_dir / "chrome109_profile"),
        "data_dirs": {"log_dir": str(log_dir)},
    }


def test_runtime_contract_writes_refuse_symlinks_without_touching_targets(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    from core.infrastructure.safe_files import UnsafeFixedFileError
    from web.bootstrap import launcher_contracts as contracts

    runtime_dir = tmp_path / "runtime"
    state_dir = runtime_dir / "logs"
    state_dir.mkdir(parents=True)
    victim = tmp_path / "victim.txt"
    victim.write_text("VICTIM-UNTOUCHED", encoding="utf-8")

    for name in ("aps_host.txt", "aps_port.txt", "aps_db_path.txt", "aps_runtime.json"):
        os.symlink(str(victim), str(state_dir / name))

    with pytest.raises(UnsafeFixedFileError):
        contracts.write_runtime_host_port_files(
            runtime_dir=str(runtime_dir),
            cfg_log_dir=None,
            host="0.0.0.0",
            port=5728,
            db_path=str(tmp_path / "aps.db"),
        )

    assert victim.read_text(encoding="utf-8") == "VICTIM-UNTOUCHED"
    for name in ("aps_host.txt", "aps_port.txt", "aps_db_path.txt", "aps_runtime.json"):
        path = state_dir / name
        assert os.path.islink(str(path))


def test_runtime_contract_and_lock_readers_refuse_symlink(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    from web.bootstrap.launcher_contract_result import read_runtime_contract_result
    from web.bootstrap.launcher_lock_result import read_runtime_lock_result_from_path

    runtime_dir = tmp_path / "runtime"
    state_dir = runtime_dir / "logs"
    state_dir.mkdir(parents=True)
    contract_target = tmp_path / "contract-target.json"
    contract_target.write_text(
        json.dumps(
            {
                "contract_version": 1,
                "pid": 123,
                "host": "127.0.0.1",
                "port": 5728,
                "shutdown_token": "token",
                "exe_path": sys.executable,
                "runtime_dir": str(runtime_dir),
                "chrome_profile_dir": str(tmp_path / "chrome109_profile"),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    os.symlink(str(contract_target), str(state_dir / "aps_runtime.json"))

    contract_result = read_runtime_contract_result(str(runtime_dir))

    assert contract_result.status == "unreadable"
    assert not contract_result.ok

    lock_target = tmp_path / "lock-target.txt"
    lock_target.write_text("pid=123\nowner=test\n", encoding="utf-8")
    lock_path = state_dir / "aps_runtime.lock"
    os.symlink(str(lock_target), str(lock_path))

    lock_result = read_runtime_lock_result_from_path(str(lock_path), state_dir=str(state_dir))

    assert lock_result.status == "unreadable"
    assert not lock_result.ok


def test_runtime_readers_refuse_dangling_symlinks(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    from web.bootstrap.launcher_contract_result import read_runtime_contract_result
    from web.bootstrap.launcher_endpoint_result import read_runtime_endpoint_files_result
    from web.bootstrap.launcher_lock_result import read_runtime_lock_result_from_path
    from web.bootstrap.runtime_probe import read_runtime_host_port

    runtime_dir = tmp_path / "runtime"
    state_dir = runtime_dir / "logs"
    state_dir.mkdir(parents=True)
    missing_target = tmp_path / "missing-target"

    os.symlink(str(missing_target), str(state_dir / "aps_runtime.json"))
    os.symlink(str(missing_target), str(state_dir / "aps_runtime.lock"))
    os.symlink(str(missing_target), str(state_dir / "aps_host.txt"))
    (state_dir / "aps_port.txt").write_text("5728\n", encoding="utf-8")

    assert read_runtime_contract_result(str(runtime_dir)).status == "unreadable"
    assert read_runtime_lock_result_from_path(str(state_dir / "aps_runtime.lock"), state_dir=str(state_dir)).status == "unreadable"
    endpoint_result = read_runtime_endpoint_files_result(str(state_dir))
    assert endpoint_result.host_status == "unreadable"
    assert endpoint_result.uncertain
    assert read_runtime_host_port(str(runtime_dir)) is None


def test_read_fixed_bytes_refuses_symlink_replacement_after_initial_stat(tmp_path: Path, monkeypatch) -> None:
    _skip_without_symlink(tmp_path)
    import core.infrastructure.safe_files as safe_mod

    fixed_file = tmp_path / "fixed-runtime.txt"
    fixed_file.write_text("SAFE", encoding="utf-8")
    victim = tmp_path / "victim.txt"
    victim.write_text("SECRET", encoding="utf-8")
    original_stat_regular_file = safe_mod.stat_regular_file
    replaced = {"done": False}

    def replacing_stat(path):
        st = original_stat_regular_file(path)
        if Path(os.fspath(path)) == fixed_file and not replaced["done"]:
            replaced["done"] = True
            fixed_file.unlink()
            os.symlink(str(victim), str(fixed_file))
        return st

    monkeypatch.setattr(safe_mod, "stat_regular_file", replacing_stat)

    with pytest.raises(OSError):
        safe_mod.read_fixed_bytes(str(fixed_file))

    assert os.path.islink(str(fixed_file))
    assert victim.read_text(encoding="utf-8") == "SECRET"


def test_write_fixed_text_refuses_symlink_created_after_missing_check_even_without_no_follow(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _skip_without_symlink(tmp_path)
    import core.infrastructure.safe_files as safe_mod

    fixed_file = tmp_path / "aps_host.txt"
    victim = tmp_path / "victim.txt"
    victim.write_text("VICTIM-UNCHANGED", encoding="utf-8")
    original_check = safe_mod._raise_if_existing_path_unsafe

    def create_symlink_after_check(path_s, *, replace_symlink=False):
        result = original_check(path_s, replace_symlink=replace_symlink)
        if Path(os.fspath(path_s)) == fixed_file and not fixed_file.exists():
            os.symlink(str(victim), str(fixed_file))
        return result

    monkeypatch.setattr(safe_mod, "_O_NOFOLLOW", 0)
    monkeypatch.setattr(safe_mod, "_raise_if_existing_path_unsafe", create_symlink_after_check)

    with pytest.raises(safe_mod.UnsafeFixedFileError):
        safe_mod.write_fixed_text(str(fixed_file), "NEW-CONTENT")

    assert os.path.islink(str(fixed_file))
    assert victim.read_text(encoding="utf-8") == "VICTIM-UNCHANGED"


def test_write_fixed_text_refuses_hardlink_replacement_without_truncating_target(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _skip_without_hardlink(tmp_path)
    import core.infrastructure.safe_files as safe_mod

    fixed_file = tmp_path / "aps_port.txt"
    fixed_file.write_text("5728\n", encoding="utf-8")
    victim = tmp_path / "victim.txt"
    victim.write_text("VICTIM-UNCHANGED", encoding="utf-8")
    original_check = safe_mod._raise_if_existing_path_unsafe
    replaced = {"done": False}

    def replace_with_hardlink_after_check(path_s, *, replace_symlink=False):
        result = original_check(path_s, replace_symlink=replace_symlink)
        if Path(os.fspath(path_s)) == fixed_file and not replaced["done"]:
            replaced["done"] = True
            fixed_file.unlink()
            os.link(str(victim), str(fixed_file))
        return result

    monkeypatch.setattr(safe_mod, "_O_NOFOLLOW", 0)
    monkeypatch.setattr(safe_mod, "_raise_if_existing_path_unsafe", replace_with_hardlink_after_check)

    with pytest.raises(safe_mod.UnsafeFixedFileError):
        safe_mod.write_fixed_text(str(fixed_file), "NEW-CONTENT")

    assert victim.read_text(encoding="utf-8") == "VICTIM-UNCHANGED"


def test_write_fixed_text_refuses_preexisting_hardlink_without_truncating_target(tmp_path: Path) -> None:
    _skip_without_hardlink(tmp_path)
    import core.infrastructure.safe_files as safe_mod

    victim = tmp_path / "victim.txt"
    fixed_file = tmp_path / "aps_host.txt"
    victim.write_text("VICTIM-UNCHANGED", encoding="utf-8")
    os.link(str(victim), str(fixed_file))

    with pytest.raises(safe_mod.UnsafeFixedFileError):
        safe_mod.write_fixed_text(str(fixed_file), "NEW-CONTENT")

    assert victim.read_text(encoding="utf-8") == "VICTIM-UNCHANGED"


def test_fixed_file_helpers_refuse_preexisting_hardlink_for_read_and_json_write(tmp_path: Path) -> None:
    _skip_without_hardlink(tmp_path)
    import core.infrastructure.safe_files as safe_mod

    victim = tmp_path / "victim.txt"
    fixed_file = tmp_path / "aps_runtime.json"
    victim.write_text('{"secret": "VICTIM"}', encoding="utf-8")
    os.link(str(victim), str(fixed_file))

    with pytest.raises(safe_mod.UnsafeFixedFileError):
        safe_mod.read_fixed_text(str(fixed_file))
    with pytest.raises(safe_mod.UnsafeFixedFileError):
        with safe_mod.open_fixed_file_for_read_binary(str(fixed_file)):
            pass
    with pytest.raises(safe_mod.UnsafeFixedFileError):
        safe_mod.write_fixed_json(str(fixed_file), {"safe": True})

    assert victim.read_text(encoding="utf-8") == '{"secret": "VICTIM"}'


def test_remove_fixed_file_refuses_preexisting_hardlink_without_unlinking(tmp_path: Path) -> None:
    _skip_without_hardlink(tmp_path)
    import core.infrastructure.safe_files as safe_mod

    victim = tmp_path / "victim.txt"
    fixed_file = tmp_path / "launcher.log"
    victim.write_text("VICTIM-UNCHANGED", encoding="utf-8")
    os.link(str(victim), str(fixed_file))

    with pytest.raises(safe_mod.UnsafeFixedFileError):
        safe_mod.remove_fixed_file(str(fixed_file))

    assert fixed_file.exists()
    assert victim.read_text(encoding="utf-8") == "VICTIM-UNCHANGED"


def test_runtime_artifact_detection_counts_dangling_symlinks(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    from web.bootstrap.launcher_paths import resolve_runtime_state_dir_for_read, resolve_runtime_state_paths
    from web.bootstrap.launcher_stop import _has_runtime_artifacts

    runtime_dir = tmp_path / "runtime"
    state_dir = runtime_dir / "logs"
    state_dir.mkdir(parents=True)
    os.symlink(str(tmp_path / "missing-host-target"), str(state_dir / "aps_host.txt"))

    assert _has_runtime_artifacts(resolve_runtime_state_paths(str(state_dir)))

    direct_state_dir = tmp_path / "direct-state"
    direct_state_dir.mkdir()
    os.symlink(str(tmp_path / "missing-direct-host-target"), str(direct_state_dir / "aps_host.txt"))

    assert resolve_runtime_state_dir_for_read(str(direct_state_dir)) == str(direct_state_dir)


def test_launcher_log_warning_refuses_symlink_logs_without_touching_targets(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    from web.bootstrap.launcher_observability import launcher_log_warning

    state_dir = tmp_path / "logs"
    state_dir.mkdir()
    log_victim = tmp_path / "launcher-victim.txt"
    error_victim = tmp_path / "error-victim.txt"
    log_victim.write_text("LOG-VICTIM", encoding="utf-8")
    error_victim.write_text("ERROR-VICTIM", encoding="utf-8")
    os.symlink(str(log_victim), str(state_dir / "launcher.log"))
    os.symlink(str(error_victim), str(state_dir / "aps_launch_error.txt"))

    result = launcher_log_warning(None, "hello fixed file", state_dir=str(state_dir), write_launch_error=True)

    assert not result.file_ok
    assert not result.error_file_ok
    assert result.stderr_ok
    assert log_victim.read_text(encoding="utf-8") == "LOG-VICTIM"
    assert error_victim.read_text(encoding="utf-8") == "ERROR-VICTIM"
    assert os.path.islink(str(state_dir / "launcher.log"))
    assert os.path.islink(str(state_dir / "aps_launch_error.txt"))
    assert "拒绝覆盖软链接固定文件" in "\n".join(result.errors)


def test_launcher_log_warning_refuses_symlink_parent_dir_without_writing_outside(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    from web.bootstrap.launcher_observability import launcher_log_warning

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(str(outside), str(runtime_dir / "logs"))

    result = launcher_log_warning(None, "hello outside", runtime_dir=str(runtime_dir), write_launch_error=True)

    assert not result.file_ok
    assert not result.error_file_ok
    assert result.stderr_ok
    assert not (outside / "launcher.log").exists()
    assert not (outside / "aps_launch_error.txt").exists()
    assert "软链接目录" in "\n".join(result.errors)


def test_runtime_cleanup_removes_launcher_log(tmp_path: Path) -> None:
    from web.bootstrap.launcher_cleanup_result import delete_runtime_contract_files_result

    runtime_dir = tmp_path / "runtime"
    state_dir = runtime_dir / "logs"
    state_dir.mkdir(parents=True)
    launcher_log = state_dir / "launcher.log"
    launcher_log.write_text("old launcher log", encoding="utf-8")

    result = delete_runtime_contract_files_result(str(runtime_dir))

    assert result.ok
    assert str(launcher_log) in result.removed_paths
    assert not launcher_log.exists()


def test_runtime_cleanup_refuses_symlink_launcher_log(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    from web.bootstrap.launcher_cleanup_result import delete_runtime_contract_files_result

    runtime_dir = tmp_path / "runtime"
    state_dir = runtime_dir / "logs"
    state_dir.mkdir(parents=True)
    victim = tmp_path / "launcher-victim.txt"
    victim.write_text("VICTIM-UNTOUCHED", encoding="utf-8")
    launcher_log = state_dir / "launcher.log"
    os.symlink(str(victim), str(launcher_log))

    result = delete_runtime_contract_files_result(str(runtime_dir))

    assert not result.ok
    assert str(launcher_log) in result.attempted_paths
    assert str(launcher_log) not in result.removed_paths
    assert os.path.islink(str(launcher_log))
    assert victim.read_text(encoding="utf-8") == "VICTIM-UNTOUCHED"
    assert any(f.path == str(launcher_log) and f.reason == "remove_failed" for f in result.failures)


def test_runtime_cleanup_refuses_symlink_parent_dir_without_removing_outside(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    from web.bootstrap.launcher_cleanup_result import delete_runtime_contract_files_result

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_log = outside / "launcher.log"
    outside_log.write_text("OUTSIDE-UNCHANGED", encoding="utf-8")
    os.symlink(str(outside), str(runtime_dir / "logs"))

    result = delete_runtime_contract_files_result(str(runtime_dir))

    assert not result.ok
    assert outside_log.read_text(encoding="utf-8") == "OUTSIDE-UNCHANGED"
    assert os.path.islink(str(runtime_dir / "logs"))
    assert any("软链接目录" in failure.error for failure in result.failures)


def test_runtime_cleanup_does_not_trust_invalid_contract_mirror_log_dir(tmp_path: Path) -> None:
    from web.bootstrap.launcher_cleanup_result import delete_runtime_contract_files_result

    runtime_dir = tmp_path / "runtime"
    state_dir = runtime_dir / "logs"
    state_dir.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_log = outside / "launcher.log"
    outside_log.write_text("OUTSIDE-UNCHANGED", encoding="utf-8")
    (state_dir / "aps_runtime.json").write_text(
        json.dumps({"data_dirs": {"log_dir": str(outside)}}, ensure_ascii=False),
        encoding="utf-8",
    )

    result = delete_runtime_contract_files_result(str(runtime_dir))

    assert not result.ok
    assert str(outside) not in result.target_dirs
    assert outside_log.read_text(encoding="utf-8") == "OUTSIDE-UNCHANGED"
    assert any(f.reason == "mirror_dirs_invalid" for f in result.failures)


def test_runtime_cleanup_does_not_trust_valid_contract_with_unverified_external_log_dir(tmp_path: Path) -> None:
    from web.bootstrap.launcher_cleanup_result import delete_runtime_contract_files_result

    runtime_dir = tmp_path / "runtime"
    state_dir = runtime_dir / "logs"
    state_dir.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_log = outside / "launcher.log"
    outside_log.write_text("OUTSIDE-UNCHANGED", encoding="utf-8")
    (state_dir / "aps_runtime.json").write_text(
        json.dumps(_valid_runtime_contract_payload(runtime_dir, log_dir=outside), ensure_ascii=False),
        encoding="utf-8",
    )

    result = delete_runtime_contract_files_result(str(runtime_dir))

    assert not result.ok
    assert str(outside) not in result.target_dirs
    assert outside_log.read_text(encoding="utf-8") == "OUTSIDE-UNCHANGED"
    assert any(f.reason == "mirror_dirs_invalid" and "matching_contract" in f.error for f in result.failures)


def test_backup_list_and_cleanup_skip_symlink_backups(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    from core.infrastructure.backup import BackupManager

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    db_path = tmp_path / "aps.db"
    db_path.write_bytes(b"db")
    old_regular = backup_dir / "aps_backup_20000101_000000_auto.db"
    old_regular.write_bytes(b"old")
    old_ts = (datetime.now() - timedelta(days=30)).timestamp()
    os.utime(str(old_regular), (old_ts, old_ts))
    victim = tmp_path / "backup-victim.db"
    victim.write_text("VICTIM-UNTOUCHED", encoding="utf-8")
    link = backup_dir / "aps_backup_20000101_000001_auto.db"
    os.symlink(str(victim), str(link))

    manager = BackupManager(db_path=str(db_path), backup_dir=str(backup_dir), keep_days=7, logger=None)

    listed = manager.list_backups()
    cleanup_result = manager.cleanup_old_backups()

    assert all(item["filename"] != link.name for item in listed)
    assert manager.last_list_unsafe_count == 1
    assert manager.last_list_unsafe_sample[0]["filename"] == link.name
    assert not old_regular.exists()
    assert cleanup_result["unsafe_count"] == 1
    assert cleanup_result["unsafe_sample"][0]["filename"] == link.name
    assert os.path.islink(str(link))
    assert victim.read_text(encoding="utf-8") == "VICTIM-UNTOUCHED"


def test_maintenance_lock_bad_utf8_is_reported_and_blocks_backup(tmp_path: Path) -> None:
    from core.infrastructure.backup import (
        MaintenanceWindowError,
        ensure_backup_allowed,
        read_maintenance_lock_state,
    )

    db_path = tmp_path / "aps.db"
    db_path.write_bytes(b"db")
    lock_path = Path(str(db_path) + ".maintenance.lock")
    lock_path.write_bytes(b"pid=123 ts=\xff\xfe\n")

    state = read_maintenance_lock_state(str(db_path))

    assert state is not None
    assert state.get("read_error") is not None
    assert state.get("raw") == ""
    with pytest.raises(MaintenanceWindowError, match="数据库正在维护"):
        ensure_backup_allowed(str(db_path))
    assert lock_path.exists()


def test_missing_maintenance_lock_under_symlink_parent_is_not_treated_as_active(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    from core.infrastructure.backup import MaintenanceWindowError, ensure_backup_allowed, read_maintenance_lock_state

    real_dir = tmp_path / "real-db-dir"
    real_dir.mkdir()
    alias_dir = tmp_path / "alias-db-dir"
    os.symlink(str(real_dir), str(alias_dir))
    db_path = alias_dir / "aps.db"

    assert read_maintenance_lock_state(str(db_path)) is None
    ensure_backup_allowed(str(db_path))

    lock_path = real_dir / "aps.db.maintenance.lock"
    lock_path.write_text("pid=123 action=test\n", encoding="utf-8")

    state = read_maintenance_lock_state(str(db_path))

    assert state is not None
    assert state.get("read_error") is not None
    with pytest.raises(MaintenanceWindowError, match="数据库正在维护"):
        ensure_backup_allowed(str(db_path))


def test_backup_restore_refuses_symlink_backup_file(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    import sqlite3

    from core.infrastructure.backup import BackupManager

    db_path = tmp_path / "aps.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t(name) VALUES ('original')")
        conn.commit()
    finally:
        conn.close()

    target_db = tmp_path / "target.db"
    conn = sqlite3.connect(str(target_db))
    try:
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t(name) VALUES ('target')")
        conn.commit()
    finally:
        conn.close()

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_link = backup_dir / "aps_backup_20990101_000000_manual.db"
    os.symlink(str(target_db), str(backup_link))
    manager = BackupManager(db_path=str(db_path), backup_dir=str(backup_dir), keep_days=7, logger=None)

    result = manager.restore(str(backup_link))

    assert not result.ok
    assert result.code == "backup_unreadable"
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT name FROM t").fetchone()
    finally:
        conn.close()
    assert row == ("original",)


def test_backup_restore_refuses_non_regular_backup_file(tmp_path: Path) -> None:
    import sqlite3

    from core.infrastructure.backup import BackupManager

    db_path = tmp_path / "aps.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t(name) VALUES ('original')")
        conn.commit()
    finally:
        conn.close()

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_dir_entry = backup_dir / "aps_backup_20990101_000001_manual.db"
    backup_dir_entry.mkdir()
    manager = BackupManager(db_path=str(db_path), backup_dir=str(backup_dir), keep_days=7, logger=None)

    result = manager.restore(str(backup_dir_entry))

    assert not result.ok
    assert result.code == "backup_unreadable"
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT name FROM t").fetchone()
    finally:
        conn.close()
    assert row == ("original",)


def test_backup_restore_refuses_symlink_database_target_without_touching_target(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    import sqlite3

    from core.infrastructure.backup import BackupManager

    victim_db = tmp_path / "victim.db"
    real_connect = sqlite3.connect
    conn = real_connect(str(victim_db))
    try:
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t(name) VALUES ('victim')")
        conn.commit()
    finally:
        conn.close()

    db_link = tmp_path / "aps.db"
    os.symlink(str(victim_db), str(db_link))

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_path = backup_dir / "aps_backup_20990101_000010_manual.db"
    conn = real_connect(str(backup_path))
    try:
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t(name) VALUES ('restore-source')")
        conn.commit()
    finally:
        conn.close()

    manager = BackupManager(db_path=str(db_link), backup_dir=str(backup_dir), keep_days=7, logger=None)

    result = manager.restore(str(backup_path))

    assert not result.ok
    assert result.code == "db_target_unreadable"
    assert os.path.islink(str(db_link))
    conn = real_connect(str(victim_db))
    try:
        row = conn.execute("SELECT name FROM t").fetchone()
    finally:
        conn.close()
    assert row == ("victim",)


def test_backup_restore_refuses_hardlink_database_target_without_touching_peer(tmp_path: Path) -> None:
    _skip_without_hardlink(tmp_path)
    import sqlite3

    from core.infrastructure.backup import BackupManager

    peer_db = tmp_path / "peer.db"
    real_connect = sqlite3.connect
    conn = real_connect(str(peer_db))
    try:
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t(name) VALUES ('peer')")
        conn.commit()
    finally:
        conn.close()

    db_path = tmp_path / "aps.db"
    os.link(str(peer_db), str(db_path))

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_path = backup_dir / "aps_backup_20990101_000011_manual.db"
    conn = real_connect(str(backup_path))
    try:
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t(name) VALUES ('restore-source')")
        conn.commit()
    finally:
        conn.close()

    manager = BackupManager(db_path=str(db_path), backup_dir=str(backup_dir), keep_days=7, logger=None)

    result = manager.restore(str(backup_path))

    assert not result.ok
    assert result.code == "db_target_unreadable"
    conn = real_connect(str(peer_db))
    try:
        row = conn.execute("SELECT name FROM t").fetchone()
    finally:
        conn.close()
    assert row == ("peer",)


def _create_operation_logs_db(path: Path) -> None:
    import sqlite3

    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            """
            CREATE TABLE OperationLogs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_level TEXT,
                module TEXT,
                action TEXT,
                target_type TEXT,
                target_id TEXT,
                operator TEXT,
                detail TEXT,
                created_at TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _operation_log_count(path: Path) -> int:
    import sqlite3

    conn = sqlite3.connect(str(path))
    try:
        return int(conn.execute("SELECT COUNT(1) FROM OperationLogs").fetchone()[0])
    finally:
        conn.close()


def test_restore_success_log_refuses_symlink_database_path_without_touching_target(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    from types import SimpleNamespace

    from flask import Flask

    from web.routes.system_backup import _write_restore_success_log

    victim_db = tmp_path / "victim.db"
    _create_operation_logs_db(victim_db)
    db_link = tmp_path / "aps.db"
    os.symlink(str(victim_db), str(db_link))

    app = Flask(__name__)
    app.config["DATABASE_PATH"] = str(db_link)
    with app.app_context():
        conn = _write_restore_success_log(
            "aps_backup_20990101_000000_manual.db",
            SimpleNamespace(code="verified", before_restore_path=None),
        )

    assert conn is None
    assert os.path.islink(str(db_link))
    assert _operation_log_count(victim_db) == 0


def test_restore_success_log_refuses_hardlink_database_path_without_touching_peer(tmp_path: Path) -> None:
    _skip_without_hardlink(tmp_path)
    from types import SimpleNamespace

    from flask import Flask

    from web.routes.system_backup import _write_restore_success_log

    peer_db = tmp_path / "peer.db"
    _create_operation_logs_db(peer_db)
    db_path = tmp_path / "aps.db"
    os.link(str(peer_db), str(db_path))

    app = Flask(__name__)
    app.config["DATABASE_PATH"] = str(db_path)
    with app.app_context():
        conn = _write_restore_success_log(
            "aps_backup_20990101_000000_manual.db",
            SimpleNamespace(code="verified", before_restore_path=None),
        )

    assert conn is None
    assert db_path.exists()
    assert _operation_log_count(peer_db) == 0


def test_backup_temp_symlink_is_refused_before_sqlite_writes(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    from core.infrastructure.backup import BackupManager

    db_path = tmp_path / "aps.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t(name) VALUES ('ok')")
        conn.commit()
    finally:
        conn.close()

    victim = tmp_path / "victim.db"
    victim.write_text("VICTIM-UNTOUCHED", encoding="utf-8")

    manager = BackupManager(db_path=str(db_path), backup_dir=str(backup_dir), keep_days=7, logger=None)
    backup_name = backup_dir / "aps_backup_20990101_000000_forced.db"
    tmp_link = backup_dir / "aps_backup_20990101_000000_forced.db.tmp"
    os.symlink(str(victim), str(tmp_link))
    original_now = __import__("core.infrastructure.backup", fromlist=["datetime"]).datetime

    class _FixedDatetime(original_now):
        @classmethod
        def now(cls):
            return cls(2099, 1, 1, 0, 0, 0)

    import core.infrastructure.backup as backup_mod

    old_datetime = backup_mod.datetime
    backup_mod.datetime = _FixedDatetime
    try:
        with pytest.raises(RuntimeError, match="清理备份临时文件失败"):
            manager.backup(suffix="forced")
    finally:
        backup_mod.datetime = old_datetime

    assert not backup_name.exists()
    assert victim.read_text(encoding="utf-8") == "VICTIM-UNTOUCHED"
    assert os.path.islink(str(tmp_link))


def test_backup_temp_replacement_before_sqlite_write_is_refused(tmp_path: Path, monkeypatch) -> None:
    _skip_without_symlink(tmp_path)
    import sqlite3

    import core.infrastructure.backup as backup_mod
    from core.infrastructure.backup import BackupManager
    from core.infrastructure.safe_files import UnsafeFixedFileError

    db_path = tmp_path / "aps.db"
    real_connect = sqlite3.connect
    conn = real_connect(str(db_path))
    try:
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t(name) VALUES ('source')")
        conn.commit()
    finally:
        conn.close()

    victim = tmp_path / "victim.db"
    conn = real_connect(str(victim))
    try:
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t(name) VALUES ('victim')")
        conn.commit()
    finally:
        conn.close()

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    manager = BackupManager(db_path=str(db_path), backup_dir=str(backup_dir), keep_days=7, logger=None)
    tmp_candidate = backup_dir / "aps_backup_20990101_000000_race.db.tmp"
    original_now = backup_mod.datetime

    class _FixedDatetime(original_now):
        @classmethod
        def now(cls):
            return cls(2099, 1, 1, 0, 0, 0)

    replaced = {"done": False}

    def replacing_connect(database, *args, **kwargs):
        if _sqlite_uri_database_path(database) == str(tmp_candidate) and not replaced["done"]:
            replaced["done"] = True
            tmp_candidate.unlink()
            os.symlink(str(victim), str(tmp_candidate))
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(backup_mod, "datetime", _FixedDatetime)
    monkeypatch.setattr(backup_mod.sqlite3, "connect", replacing_connect)

    with pytest.raises(UnsafeFixedFileError):
        manager.backup(suffix="race")

    conn = real_connect(str(victim))
    try:
        row = conn.execute("SELECT name FROM t").fetchone()
    finally:
        conn.close()
    assert row == ("victim",)
    assert os.path.islink(str(tmp_candidate))


def test_backup_temp_replacement_to_missing_symlink_does_not_create_target(tmp_path: Path, monkeypatch) -> None:
    _skip_without_symlink(tmp_path)
    import sqlite3

    import core.infrastructure.backup as backup_mod
    from core.infrastructure.backup import BackupManager

    db_path = tmp_path / "aps.db"
    real_connect = sqlite3.connect
    conn = real_connect(str(db_path))
    try:
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t(name) VALUES ('source')")
        conn.commit()
    finally:
        conn.close()

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    manager = BackupManager(db_path=str(db_path), backup_dir=str(backup_dir), keep_days=7, logger=None)
    tmp_candidate = backup_dir / "aps_backup_20990101_000000_missing.db.tmp"
    missing_target = tmp_path / "missing-victim.db"
    original_now = backup_mod.datetime

    class _FixedDatetime(original_now):
        @classmethod
        def now(cls):
            return cls(2099, 1, 1, 0, 0, 0)

    replaced = {"done": False}

    def replacing_connect(database, *args, **kwargs):
        if _sqlite_uri_database_path(database) == str(tmp_candidate) and not replaced["done"]:
            replaced["done"] = True
            tmp_candidate.unlink()
            os.symlink(str(missing_target), str(tmp_candidate))
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(backup_mod, "datetime", _FixedDatetime)
    monkeypatch.setattr(backup_mod.sqlite3, "connect", replacing_connect)

    with pytest.raises(sqlite3.OperationalError):
        manager.backup(suffix="missing")

    assert not missing_target.exists()
    assert os.path.islink(str(tmp_candidate))


def test_backup_restore_source_replacement_before_copy_is_refused_and_rolls_back(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _skip_without_symlink(tmp_path)
    import sqlite3

    import core.infrastructure.backup as backup_mod
    from core.infrastructure.backup import BackupManager

    real_connect = sqlite3.connect
    db_path = tmp_path / "aps.db"
    conn = real_connect(str(db_path))
    try:
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t(name) VALUES ('original')")
        conn.commit()
    finally:
        conn.close()

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_path = backup_dir / "aps_backup_20990101_000000_manual.db"
    conn = real_connect(str(backup_path))
    try:
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t(name) VALUES ('backup')")
        conn.commit()
    finally:
        conn.close()

    victim = tmp_path / "victim.db"
    conn = real_connect(str(victim))
    try:
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t(name) VALUES ('victim')")
        conn.commit()
    finally:
        conn.close()

    replaced = {"done": False}

    def replacing_connect(database, *args, **kwargs):
        if _sqlite_uri_database_path(database) == str(backup_path) and not replaced["done"]:
            replaced["done"] = True
            backup_path.unlink()
            os.symlink(str(victim), str(backup_path))
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(backup_mod.sqlite3, "connect", replacing_connect)
    manager = BackupManager(db_path=str(db_path), backup_dir=str(backup_dir), keep_days=7, logger=None)

    result = manager.restore(str(backup_path))

    assert not result.ok
    assert result.code in {"restore_failed_rolled_back", "restore_failed"}
    conn = real_connect(str(db_path))
    try:
        row = conn.execute("SELECT name FROM t").fetchone()
    finally:
        conn.close()
    assert row == ("original",)
    assert os.path.islink(str(backup_path))


def test_maintenance_cleanup_skips_symlink_backups(tmp_path: Path) -> None:
    _skip_without_symlink(tmp_path)
    from core.services.system.maintenance.cleanup_task import cleanup_backups_with_limit

    old_regular = tmp_path / "aps_backup_20000101_000000_auto.db"
    old_regular.write_bytes(b"old")
    old_ts = (datetime.now() - timedelta(days=30)).timestamp()
    os.utime(str(old_regular), (old_ts, old_ts))
    victim = tmp_path / "maintenance-victim.db"
    victim.write_text("VICTIM-UNTOUCHED", encoding="utf-8")
    link = tmp_path / "aps_backup_20000101_000001_auto.db"
    os.symlink(str(victim), str(link))

    removed, meta = cleanup_backups_with_limit(
        str(tmp_path),
        keep_days=7,
        max_delete=10,
        fmt_db_dt_fn=lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S"),
    )

    assert removed == 1
    assert meta["candidates"] == 1
    assert not old_regular.exists()
    assert os.path.islink(str(link))
    assert victim.read_text(encoding="utf-8") == "VICTIM-UNTOUCHED"
