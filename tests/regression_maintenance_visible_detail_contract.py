from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


class _CollectingLogger:
    def __init__(self) -> None:
        self.warnings = []

    def warning(self, message: str) -> None:
        self.warnings.append(str(message))
        raise RuntimeError("logger unavailable")


class _FakeBackupManager:
    def __init__(self, *, db_path: str, backup_dir: str, keep_days: int, logger=None) -> None:
        self.backup_dir = backup_dir

    def backup(self, *, suffix: str) -> str:
        path = Path(self.backup_dir) / f"aps_backup_fake_{suffix}.db"
        path.write_bytes(b"backup")
        return str(path)


class _FakeJobRepo:
    def __init__(self) -> None:
        self.runs = []

    def set_last_run(self, *args, **kwargs) -> None:
        self.runs.append((args, kwargs))
        return None


class _FakeOpLogger:
    def __init__(self) -> None:
        self.info_calls = []
        self.error_calls = []

    def info(self, **kwargs) -> bool:
        self.info_calls.append(dict(kwargs))
        return True

    def error(self, **kwargs) -> bool:
        self.error_calls.append(dict(kwargs))
        return True


def _due(*_args, **_kwargs):
    return True, None


def _fmt_db_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def test_auto_backup_reports_size_stat_failure(monkeypatch, tmp_path: Path) -> None:
    import core.services.system.maintenance.backup_task as backup_task

    monkeypatch.setattr(backup_task, "BackupManager", _FakeBackupManager)

    def _boom_stat(_path):
        raise OSError("stat denied")

    monkeypatch.setattr(backup_task.os, "stat", _boom_stat)

    conn = sqlite3.connect(":memory:")
    job_repo = _FakeJobRepo()
    op_logger = _FakeOpLogger()
    ran, detail = backup_task.maybe_run_auto_backup(
        conn,
        job_repo=job_repo,
        now=datetime(2026, 1, 1, 8, 0, 0),
        interval_minutes=1,
        db_path=str(tmp_path / "aps.db"),
        backup_dir=str(tmp_path),
        keep_days=7,
        job_key="visible_size_failure",
        logger=None,
        op_logger=op_logger,
        is_due_fn=_due,
        fmt_db_dt_fn=_fmt_db_dt,
    )
    conn.close()

    assert ran is True
    assert detail["size_mb"] is None
    assert detail["size_mb_status"] == "stat_failed"
    assert "stat denied" in str(detail["size_mb_error"])
    assert op_logger.info_calls, "自动备份应把 size stat 失败写进 OperationLogs detail"
    op_detail = op_logger.info_calls[0]["detail"]
    assert op_detail["size_mb_status"] == "stat_failed"
    assert "stat denied" in str(op_detail["size_mb_error"])
    job_detail = json.loads(job_repo.runs[0][1]["last_run_detail"])
    assert job_detail["size_mb_status"] == "stat_failed"
    assert "stat denied" in str(job_detail["size_mb_error"])


def test_backup_cleanup_reports_mtime_and_delete_failures(monkeypatch, tmp_path: Path) -> None:
    import core.services.system.maintenance.cleanup_task as cleanup_task

    old_ok = tmp_path / "aps_backup_20000101_000000_auto.db"
    old_bad_mtime = tmp_path / "aps_backup_20000101_000001_auto.db"
    old_bad_delete = tmp_path / "aps_backup_20000101_000002_auto.db"
    for path in (old_ok, old_bad_mtime, old_bad_delete):
        path.write_bytes(b"old")

    old_ts = (datetime.now() - timedelta(days=30)).timestamp()
    old_ok.touch()
    cleanup_task.os.utime(old_ok, (old_ts, old_ts))
    original_getmtime = cleanup_task.os.path.getmtime
    original_remove = cleanup_task.os.remove

    def _getmtime(path):
        if str(path).endswith(old_bad_mtime.name):
            raise OSError("mtime denied")
        return original_getmtime(path) if not str(path).endswith(old_bad_delete.name) else old_ts

    def _remove(path):
        if str(path).endswith(old_bad_delete.name):
            raise OSError("delete denied")
        return original_remove(path)

    monkeypatch.setattr(cleanup_task.os.path, "getmtime", _getmtime)
    monkeypatch.setattr(cleanup_task.os, "remove", _remove)

    removed, meta = cleanup_task.cleanup_backups_with_limit(
        str(tmp_path),
        keep_days=7,
        max_delete=10,
        fmt_db_dt_fn=_fmt_db_dt,
    )

    assert removed == 1
    assert meta["mtime_error_count"] == 1
    assert meta["mtime_error_sample"][0]["filename"] == old_bad_mtime.name
    assert meta["delete_error_count"] == 1
    assert meta["delete_error_sample"][0]["filename"] == old_bad_delete.name
    assert old_bad_delete.exists(), "删除失败的文件必须仍在，且结果里要能看到失败原因"


def test_auto_backup_cleanup_persists_mtime_and_delete_failures(monkeypatch, tmp_path: Path) -> None:
    import core.services.system.maintenance.cleanup_task as cleanup_task

    old_ok = tmp_path / "aps_backup_20000101_000000_auto.db"
    old_bad_mtime = tmp_path / "aps_backup_20000101_000001_auto.db"
    old_bad_delete = tmp_path / "aps_backup_20000101_000002_auto.db"
    for path in (old_ok, old_bad_mtime, old_bad_delete):
        path.write_bytes(b"old")

    old_ts = (datetime.now() - timedelta(days=30)).timestamp()
    cleanup_task.os.utime(old_ok, (old_ts, old_ts))
    original_getmtime = cleanup_task.os.path.getmtime
    original_remove = cleanup_task.os.remove

    def _getmtime(path):
        if str(path).endswith(old_bad_mtime.name):
            raise OSError("mtime denied")
        return original_getmtime(path) if not str(path).endswith(old_bad_delete.name) else old_ts

    def _remove(path):
        if str(path).endswith(old_bad_delete.name):
            raise OSError("delete denied")
        return original_remove(path)

    monkeypatch.setattr(cleanup_task.os.path, "getmtime", _getmtime)
    monkeypatch.setattr(cleanup_task.os, "remove", _remove)

    conn = sqlite3.connect(":memory:")
    job_repo = _FakeJobRepo()
    op_logger = _FakeOpLogger()
    ran, detail = cleanup_task.maybe_run_auto_backup_cleanup(
        conn,
        job_repo=job_repo,
        now=datetime(2026, 1, 1, 8, 0, 0),
        interval_minutes=1,
        backup_dir=str(tmp_path),
        keep_days=7,
        max_backup_delete_per_run=10,
        job_key="visible_cleanup_failure",
        logger=None,
        op_logger=op_logger,
        is_due_fn=_due,
        fmt_db_dt_fn=_fmt_db_dt,
    )
    conn.close()

    assert ran is True
    assert detail["mtime_error_count"] == 1
    assert detail["delete_error_count"] == 1
    op_detail = op_logger.info_calls[0]["detail"]
    assert op_detail["mtime_error_sample"][0]["filename"] == old_bad_mtime.name
    assert op_detail["delete_error_sample"][0]["filename"] == old_bad_delete.name
    job_detail = json.loads(job_repo.runs[0][1]["last_run_detail"])
    assert job_detail["mtime_error_count"] == 1
    assert job_detail["delete_error_count"] == 1
    assert job_detail["mtime_error_sample"][0]["filename"] == old_bad_mtime.name
    assert job_detail["delete_error_sample"][0]["filename"] == old_bad_delete.name


def test_maintenance_safe_logger_falls_back_to_stderr(capsys) -> None:
    from core.services.system.maintenance.backup_task import _safe_logger_emit as backup_emit
    from core.services.system.maintenance.cleanup_task import _safe_logger_emit as cleanup_emit

    backup_emit(_CollectingLogger(), "warning", "backup warning visible")
    cleanup_emit(_CollectingLogger(), "warning", "cleanup warning visible")

    stderr = capsys.readouterr().err
    assert "backup warning visible" in stderr
    assert "cleanup warning visible" in stderr
