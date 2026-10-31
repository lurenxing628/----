"""回归测试：当维护窗口（maintenance_window）正被其他线程持有时，退出备份 factory._run_exit_backup() 必须 fail-fast 跳过——返回 False、耗时不到 1 秒、且不在 backup_dir 生成任何 *_exit.db。"""

from __future__ import annotations

import os
import threading
import time

import pytest

_NOT_JSON = "Out of range float values are not JSON compliant"


def _strict(text):
    from core.shared.strict_json import load_strict_json

    def malformed():
        raise AssertionError(f"stored text is not strict JSON: {text!r}")

    return load_strict_json(text, on_malformed=malformed)


def _list_exit_backups(backup_dir: str) -> list:
    if not os.path.exists(backup_dir):
        return []
    return sorted([f for f in os.listdir(backup_dir) if f.startswith("aps_backup_") and f.endswith("_exit.db")])


def test_exit_backup_maintenance(db_path, tmp_path, monkeypatch) -> None:

    from flask import Flask

    from core.infrastructure.backup import maintenance_window
    from core.infrastructure.database import get_connection
    from data.repositories.system_config_repo import SystemConfigRepository
    from web.bootstrap import factory as factory_mod
    from web.bootstrap.launcher_shutdown import RuntimeExitBackupManager
    from web.bootstrap.workbench_system_restore_recovery import system_journal_directory

    backup_dir = os.path.join(str(tmp_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)


    conn = get_connection(db_path)
    try:
        with conn:
            SystemConfigRepository(conn).set(
                "auto_backup_enabled",
                "yes",
                description="自动备份（按请求触发；正常退出时也受此开关控制）是否启用：yes/no",
            )
    finally:
        conn.close()

    app = Flask(__name__)
    app.config.update(DATABASE_PATH=db_path, BACKUP_DIR=backup_dir, BACKUP_KEEP_DAYS=7,
                      WORKBENCH_SYSTEM_JOURNAL_DIR=system_journal_directory(db_path))
    monkeypatch.setattr(factory_mod, "_EXIT_BACKUP_MANAGER", RuntimeExitBackupManager(app))

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
    ran = factory_mod._run_exit_backup()
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


def test_unconfirmed_config_connection_close_skips_exit_backup_with_its_own_reason(db_path, tmp_path, monkeypatch, caplog) -> None:
    import logging
    import sqlite3

    from flask import Flask

    from core.infrastructure.database import get_connection
    from data.repositories.system_config_repo import SystemConfigRepository
    from web.bootstrap.launcher_shutdown import RuntimeExitBackupManager, read_exit_backup_enabled, run_exit_backup
    from web.bootstrap.workbench_system_restore_recovery import system_journal_directory

    conn = get_connection(db_path)
    try:
        with conn:
            SystemConfigRepository(conn).set("auto_backup_enabled", "yes")
    finally:
        conn.close()
    app = Flask(__name__)
    app.config.update(DATABASE_PATH=db_path, BACKUP_DIR=os.path.join(str(tmp_path), "backups"), BACKUP_KEEP_DAYS=7,
                      WORKBENCH_SYSTEM_JOURNAL_DIR=system_journal_directory(db_path))
    manager = RuntimeExitBackupManager(app)
    backups = []
    monkeypatch.setattr(manager, "backup", lambda **kwargs: backups.append(kwargs))
    opened = []

    class CloseUnconfirmed:
        def __init__(self, path):
            self.conn = get_connection(path)
            opened.append(self.conn)

        def __getattr__(self, name):
            return getattr(self.conn, name)

        def close(self):
            raise sqlite3.OperationalError("config connection close unconfirmed")

    def read_enabled(target):
        return read_exit_backup_enabled(target, CloseUnconfirmed)

    try:
        with caplog.at_level(logging.INFO):
            assert read_enabled(manager) is None
            caplog.clear()
            assert run_exit_backup(manager, read_enabled) is False
    finally:
        for item in opened:
            item.close()
    assert backups == []
    assert "关闭退出自动备份配置连接失败，本次不做退出备份：config connection close unconfirmed" in caplog.text
    assert "退出自动备份已跳过：读取配置失败。" in caplog.text
    assert "维护状态或停止屏障未核实" not in caplog.text


def test_operation_log_cleanup_uses_utc_boundary_and_keeps_limits(schema_conn, tmp_path, monkeypatch):
    from datetime import datetime

    from core.services.system.maintenance import cleanup_task
    from core.services.system.system_maintenance_service import _fmt_db_dt

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 16, 0, 30)

        @classmethod
        def utcnow(cls):
            return cls(2026, 10, 15, 16, 30)

    monkeypatch.setattr(cleanup_task, "datetime", Clock)
    times = ("2026-10-14 16:29:58", "2026-10-14 16:29:59", "2026-10-14 16:30:00",
             "2026-10-14 16:30:01", "2026-10-14 23:59:59", "2026-10-15 16:30:00")
    schema_conn.executemany("INSERT INTO OperationLogs(log_time,log_level,module,action) VALUES (?,'INFO','system','test')",
                            [(value,) for value in times])
    deleted, meta = cleanup_task.cleanup_operation_logs_with_limit(schema_conn, keep_days=1,
        min_keep_logs=4, max_delete=1, fmt_db_dt_fn=_fmt_db_dt)
    assert deleted == 1 and meta["cutoff"] == "2026-10-14 16:30:00" and meta["candidates"] == 2
    assert [row[0] for row in schema_conn.execute("SELECT log_time FROM OperationLogs ORDER BY id")] == list(times[1:])
    deleted, meta = cleanup_task.cleanup_operation_logs_with_limit(schema_conn, keep_days=1,
        min_keep_logs=4, max_delete=10, fmt_db_dt_fn=_fmt_db_dt)
    assert deleted == 1 and meta["allow"] == 1
    assert [row[0] for row in schema_conn.execute("SELECT log_time FROM OperationLogs ORDER BY id")] == list(times[2:])
    deleted, meta = cleanup_task.cleanup_operation_logs_with_limit(schema_conn, keep_days=1,
        min_keep_logs=4, max_delete=10, fmt_db_dt_fn=_fmt_db_dt)
    assert deleted == 0 and meta["reason"] == "total_le_min_keep"
    _, backup_meta = cleanup_task.cleanup_backups_with_limit(str(tmp_path / "missing-backups"),
        keep_days=1, max_delete=10, fmt_db_dt_fn=_fmt_db_dt)
    assert backup_meta["cutoff"] == "2026-10-15 00:30:00"


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_operation_log_detail_is_strict_json_and_rejects_non_finite_numbers(schema_conn, caplog, number):
    import logging

    from core.infrastructure.logging import OperationLogger
    from core.shared.strict_json import canonical_json

    logger = logging.getLogger("tests.operation_log_detail")
    op_logger = OperationLogger(schema_conn, logger=logger)
    # 普通审计按既有契约只记文件日志并返回 False；要求落库的调用方用 raise_on_fail 拿到原异常。
    with caplog.at_level(logging.ERROR, logger=logger.name):
        assert op_logger.info("system", "probe", detail={"value": number}) is False
    assert "写入操作日志失败：" + _NOT_JSON in caplog.text
    with pytest.raises(ValueError, match=_NOT_JSON):
        op_logger.info("system", "probe", detail={"value": number}, raise_on_fail=True)
    assert not schema_conn.in_transaction
    assert op_logger.info("system", "probe", detail={"value": 1.5, "名称": "设备"}) is True
    stored = [row[0] for row in schema_conn.execute("SELECT detail FROM OperationLogs")]
    assert stored == [canonical_json({"value": 1.5, "名称": "设备"})]
    assert _strict(stored[0]) == {"value": 1.5, "名称": "设备"}


def test_unreadable_stale_maintenance_lock_fails_closed_without_deleting_lock(tmp_path, monkeypatch):
    import os
    import time

    from core.infrastructure import maintenance_lock

    db_path = tmp_path / "aps.db"
    lock_path = tmp_path / "aps.db.maintenance.lock"
    lock_path.write_text(f"pid={os.getpid()} action=backup ts=2026-10-01T00:00:00", encoding="utf-8")
    stale_time = time.time() - 600
    os.utime(lock_path, (stale_time, stale_time))

    def deny_read(_path):
        raise PermissionError("permission denied reading lock file")

    monkeypatch.setattr(maintenance_lock, "read_fixed_bytes", deny_read)
    with pytest.raises(maintenance_lock.MaintenanceWindowError) as exc:
        maintenance_lock.is_maintenance_window_active(str(db_path))
    assert exc.value.code == "lock_state_unavailable"
    assert lock_path.exists()


def test_maintenance_tasks_overview_and_records_share_one_result_classification(
    schema_conn,
    tmp_path,
    monkeypatch,
) -> None:
    import logging
    from datetime import datetime

    from core.infrastructure.logging import OperationLogger
    from core.services.system.maintenance import backup_task, cleanup_task
    from core.services.system.system_maintenance_service import _fmt_db_dt
    from core.services.system.workbench_overview import build_system_overview
    from core.services.workbench.system.maintenance_records import maintenance_records
    from data.repositories.system_job_state_repo import SystemJobStateRepository

    logger = logging.getLogger("tests.maintenance_unified_status")
    op_logger = OperationLogger(schema_conn, logger=logger)
    job_repo = SystemJobStateRepository(schema_conn, logger=logger)
    now = datetime(2026, 10, 16, 8, 0, 0)
    db_file = tmp_path / "aps.db"
    db_file.write_bytes(b"sqlite-placeholder")
    backup_dir = tmp_path / "backups"
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # 1) 备份目录不存在 + 日志条数未超保底：两项清理均为 skipped，overview 与 maintenance_records 一致
    assert cleanup_task.maybe_run_auto_backup_cleanup(
        schema_conn,
        job_repo=job_repo,
        now=now,
        interval_minutes=60,
        backup_dir=str(backup_dir),
        keep_days=7,
        max_backup_delete_per_run=10,
        job_key="auto_backup_cleanup",
        logger=logger,
        op_logger=op_logger,
        is_due_fn=lambda *_args: True,
        fmt_db_dt_fn=_fmt_db_dt,
    ) is True
    assert cleanup_task.maybe_run_auto_log_cleanup(
        schema_conn,
        job_repo=job_repo,
        now=now,
        interval_minutes=60,
        keep_days=7,
        min_keep_logs=50,
        max_log_delete_per_run=10,
        job_key="auto_log_cleanup",
        logger=logger,
        op_logger=op_logger,
        is_due_fn=lambda *_args: True,
        fmt_db_dt_fn=_fmt_db_dt,
    ) is True

    overview = build_system_overview(
        schema_conn,
        db_path=str(db_file),
        backup_dir=str(backup_dir),
        log_dir=str(log_dir),
    )
    jobs_by_kind = {job["kind"]: job for job in overview["maintenance"]["jobs"]}
    assert jobs_by_kind["auto_backup_cleanup"]["result"]["status"] == "skipped"
    assert jobs_by_kind["auto_log_cleanup"]["result"]["status"] == "skipped"

    rows, _sources = maintenance_records(schema_conn, str(backup_dir), None, journal_records=[])
    cleanup_events = [row for row in rows if row["record_kind"] == "cleanup_event"]
    assert [(row["event_source"], row["status"]) for row in cleanup_events] == [
        ("operation_audit", "skipped"),
        ("operation_audit", "skipped"),
    ]

    # 清空 OperationLogs 后走 latest_job_state_only 回退链，仍统一判为 skipped
    schema_conn.execute("DELETE FROM OperationLogs")
    schema_conn.commit()
    fallback_rows, _ = maintenance_records(schema_conn, str(backup_dir), None, journal_records=[])
    fallback_events = [row for row in fallback_rows if row["record_kind"] == "cleanup_event"]
    assert {row["event_source"] for row in fallback_events} == {"latest_job_state_only"}
    assert {row["status"] for row in fallback_events} == {"skipped"}

    # 2) 局部异常：backup stat_failed 与 backup_cleanup delete_error_count > 0 均写 WARNING 且三处统一判为 partial
    backup_dir.mkdir(parents=True, exist_ok=True)
    fake_backup = backup_dir / "aps_backup_20261016_080000_auto.db"
    fake_backup.write_bytes(b"backup-bytes")
    monkeypatch.setattr(backup_task.BackupManager, "backup", lambda self, suffix="auto": str(fake_backup))

    orig_stat = backup_task.os.stat

    def fail_stat(path, *args, **kwargs):
        if str(path) == str(fake_backup):
            raise OSError("simulated stat failure")
        return orig_stat(path, *args, **kwargs)

    monkeypatch.setattr(backup_task.os, "stat", fail_stat)
    due, ok = backup_task.maybe_run_auto_backup(
        schema_conn,
        job_repo=job_repo,
        now=now,
        interval_minutes=60,
        db_path=str(db_file),
        backup_dir=str(backup_dir),
        keep_days=7,
        job_key="auto_backup",
        logger=logger,
        op_logger=op_logger,
        is_due_fn=lambda *_args: True,
        fmt_db_dt_fn=_fmt_db_dt,
    )
    assert (due, ok) == (True, True)

    monkeypatch.setattr(
        cleanup_task,
        "cleanup_backups_with_limit",
        lambda **_kwargs: (
            1,
            {
                "cutoff": "2026-10-09 08:00:00",
                "candidates": 2,
                "min_keep": 3,
                "kept_recent_count": 0,
                "removed_sample": ["aps_backup_old.db"],
                "mtime_error_count": 0,
                "mtime_error_sample": [],
                "unsafe_backup_count": 0,
                "unsafe_backup_sample": [],
                "delete_error_count": 1,
                "delete_error_sample": [{"filename": "aps_backup_locked.db", "error": "locked"}],
            },
        ),
    )
    assert cleanup_task.maybe_run_auto_backup_cleanup(
        schema_conn,
        job_repo=job_repo,
        now=now,
        interval_minutes=60,
        backup_dir=str(backup_dir),
        keep_days=7,
        max_backup_delete_per_run=10,
        job_key="auto_backup_cleanup",
        logger=logger,
        op_logger=op_logger,
        is_due_fn=lambda *_args: True,
        fmt_db_dt_fn=_fmt_db_dt,
    ) is True

    logged = schema_conn.execute(
        "SELECT action, log_level, detail FROM OperationLogs ORDER BY id ASC"
    ).fetchall()
    assert [(row[0], row[1], _strict(row[2])["status"]) for row in logged] == [
        ("backup", "WARNING", "partial"),
        ("cleanup", "WARNING", "partial"),
    ]

    overview_after = build_system_overview(
        schema_conn,
        db_path=str(db_file),
        backup_dir=str(backup_dir),
        log_dir=str(log_dir),
    )
    jobs_after = {job["kind"]: job for job in overview_after["maintenance"]["jobs"]}
    assert jobs_after["auto_backup"]["result"]["status"] == "partial"
    assert jobs_after["auto_backup_cleanup"]["result"]["status"] == "partial"

    audit_rows, _ = maintenance_records(schema_conn, str(backup_dir), None, journal_records=[])
    audit_cleanup = [row for row in audit_rows if row["record_kind"] == "cleanup_event" and row["event_source"] == "operation_audit"]
    assert len(audit_cleanup) == 1 and audit_cleanup[0]["status"] == "partial"

    schema_conn.execute("DELETE FROM OperationLogs")
    schema_conn.commit()
    latest_rows, _ = maintenance_records(schema_conn, str(backup_dir), None, journal_records=[])
    latest_by_ref = {
        row["event_ref"]: row["status"]
        for row in latest_rows
        if row["record_kind"] == "cleanup_event"
    }
    assert latest_by_ref == {
        "auto_backup_cleanup": "partial",
        "auto_log_cleanup": "skipped",
    }

    # 3) 计数字段类型损坏（如 mtime_error_count 为字符串 "1"、removed_count 为 null 或其他计数字段非法）：
    # 系统概况与维护历史记录（含 OperationLogs 与 SystemJobState）均归为异常/未知，绝不报为 succeeded/completed
    for bad_detail in (
        '{"removed_count": 0, "mtime_error_count": "1"}',
        '{"removed_count": null}',
        '{"removed_count": null, "skipped": true}',
        '{"removed_count": 0, "total": "bad"}',
        '{"removed_count": 0, "kept_count": -1}',
        '{"removed_count": 0, "time_cost_ms": null}',
    ):
        with schema_conn:
            schema_conn.execute("DELETE FROM OperationLogs")
            job_repo.set_last_run(
                "auto_backup_cleanup",
                last_run_time="2026-10-16 08:00:00",
                last_run_detail=bad_detail,
            )
        overview_corrupt = build_system_overview(
            schema_conn,
            db_path=str(db_file),
            backup_dir=str(backup_dir),
            log_dir=str(log_dir),
        )
        jobs_corrupt = {job["kind"]: job for job in overview_corrupt["maintenance"]["jobs"]}
        assert jobs_corrupt["auto_backup_cleanup"]["status"] == "partial"
        assert jobs_corrupt["auto_backup_cleanup"]["result"]["status"] == "invalid"

        corrupt_rows, corrupt_sources = maintenance_records(schema_conn, str(backup_dir), None, journal_records=[])
        corrupt_by_ref = {
            row["event_ref"]: row["status"]
            for row in corrupt_rows
            if row["record_kind"] == "cleanup_event"
        }
        assert corrupt_by_ref["auto_backup_cleanup"] == "unknown"
        assert any(
            item.get("code") == "maintenance_last_detail_invalid"
            and item.get("job_key") == "auto_backup_cleanup"
            for item in corrupt_sources
        )

        with schema_conn:
            schema_conn.execute(
                "INSERT INTO OperationLogs(log_time, log_level, module, action, detail) VALUES (?, 'INFO', 'system', 'cleanup', ?)",
                ("2026-10-16 08:00:00", bad_detail),
            )
        audit_corrupt_rows, _ = maintenance_records(schema_conn, str(backup_dir), None, journal_records=[])
        audit_corrupt_events = [
            row for row in audit_corrupt_rows
            if row["record_kind"] == "cleanup_event" and row["event_source"] == "operation_audit"
        ]
        assert len(audit_corrupt_events) == 1
        assert audit_corrupt_events[0]["status"] == "unknown"

    # 4) 展示裁剪不影响分类：error 前 1000 字符为空白、后续带错误正文时，
    # 系统概况与维护历史记录（SystemJobState 与 OperationLogs）均判为 failed，且展示值保持 1000 字符裁剪
    long_error_detail = f'{{"removed_count": 0, "error": "{" " * 1000}disk full"}}'
    with schema_conn:
        schema_conn.execute("DELETE FROM OperationLogs")
        job_repo.set_last_run(
            "auto_backup_cleanup",
            last_run_time="2026-10-16 08:00:00",
            last_run_detail=long_error_detail,
        )
    overview_long_error = build_system_overview(
        schema_conn,
        db_path=str(db_file),
        backup_dir=str(backup_dir),
        log_dir=str(log_dir),
    )
    jobs_long_error = {job["kind"]: job for job in overview_long_error["maintenance"]["jobs"]}
    assert jobs_long_error["auto_backup_cleanup"]["result"]["status"] == "failed"
    assert jobs_long_error["auto_backup_cleanup"]["result"]["values"]["error"] == " " * 1000

    long_error_rows, _ = maintenance_records(schema_conn, str(backup_dir), None, journal_records=[])
    long_error_by_ref = {
        row["event_ref"]: row["status"]
        for row in long_error_rows
        if row["record_kind"] == "cleanup_event"
    }
    assert long_error_by_ref["auto_backup_cleanup"] == "failed"

    with schema_conn:
        schema_conn.execute(
            "INSERT INTO OperationLogs(log_time, log_level, module, action, detail) VALUES (?, 'ERROR', 'system', 'cleanup', ?)",
            ("2026-10-16 08:00:00", long_error_detail),
        )
    audit_long_error_rows, _ = maintenance_records(schema_conn, str(backup_dir), None, journal_records=[])
    audit_long_error_events = [
        row for row in audit_long_error_rows
        if row["record_kind"] == "cleanup_event" and row["event_source"] == "operation_audit"
    ]
    assert len(audit_long_error_events) == 1
    assert audit_long_error_events[0]["status"] == "failed"
