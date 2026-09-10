"""合同测试：维护窗锁自愈三死区闭合（B04，2026-07-19 盲区扫描）——
(a) 锁文件 ts 缺失/损坏/内容不可解码（断电半写典型形态）时用锁文件 mtime 兜底计算 age，超龄仍可自愈，
不再『age=None 永不自愈』；(b) 超龄锁的 pid 缺失/不可解析按可疑处理（允许自愈），不再恒按存活；
(c) 超龄锁因 pid 判定存活（PID 可能被复用、无法核对进程身份）而不自愈时，必须留 warning 痕
（含锁路径、锁内容、判定依据），给现场人工删锁提供线索；未超龄的锁（含刚半写的空锁）一律不自愈，
锁 API 经 core.infrastructure.backup 再导出路径保持可用。"""

from __future__ import annotations

import os
import time

from core.infrastructure.backup import is_maintenance_window_active, read_maintenance_lock_state

# 与既有 test_maintenance_window_mutex.py 一致：本机不可能存活的 pid。
_DEAD_PID = 999999
_OVER_AGE_SECONDS = 600  # 大于 _MAINT_LOCK_STALE_SECONDS=300


class _CollectingLogger:
    def __init__(self) -> None:
        self.warnings = []
        self.infos = []

    def warning(self, message) -> None:
        self.warnings.append(str(message))

    def info(self, message) -> None:
        self.infos.append(str(message))

    def error(self, message) -> None:
        self.warnings.append(str(message))


def _write_lock(db_path: str, content: bytes, *, age_seconds: float) -> str:
    lock_path = db_path + ".maintenance.lock"
    with open(lock_path, "wb") as f:
        f.write(content)
    stamp = time.time() - float(age_seconds)
    os.utime(lock_path, (stamp, stamp))
    return lock_path


def test_empty_lock_file_heals_by_mtime_when_over_age(tmp_path) -> None:
    """死区(a)+(b)：断电半写出的空锁文件（无 ts 无 pid），超龄后按 mtime 兜底自愈。"""
    db_path = os.path.join(str(tmp_path), "aps.db")
    lock_path = _write_lock(db_path, b"", age_seconds=_OVER_AGE_SECONDS)

    state = read_maintenance_lock_state(db_path)
    assert state is not None and state.get("age_source") == "mtime", state
    assert float(state.get("age_seconds") or 0) >= 300, state

    assert is_maintenance_window_active(db_path, logger=_CollectingLogger()) is False
    assert not os.path.exists(lock_path), "超龄空锁应被自愈清理"


def test_corrupt_ts_lock_heals_by_mtime_when_pid_dead(tmp_path) -> None:
    """死区(a)：ts token 损坏 → age 用 mtime 兜底；pid 已死 → 超龄自愈。"""
    db_path = os.path.join(str(tmp_path), "aps.db")
    lock_path = _write_lock(
        db_path, f"pid={_DEAD_PID} action=restore ts=not-a-timestamp".encode(), age_seconds=_OVER_AGE_SECONDS
    )

    state = read_maintenance_lock_state(db_path)
    assert state is not None and state.get("ts") is None and state.get("age_source") == "mtime", state

    assert is_maintenance_window_active(db_path, logger=_CollectingLogger()) is False
    assert not os.path.exists(lock_path)


def test_undecodable_lock_content_heals_by_mtime_when_over_age(tmp_path) -> None:
    """死区(a)：锁内容不可解码（断电垃圾字节）→ read_error 不再卡死，mtime 超龄自愈。"""
    db_path = os.path.join(str(tmp_path), "aps.db")
    lock_path = _write_lock(db_path, b"\xff\xfe\xfd\x00", age_seconds=_OVER_AGE_SECONDS)

    assert is_maintenance_window_active(db_path, logger=_CollectingLogger()) is False
    assert not os.path.exists(lock_path)


def test_missing_pid_lock_heals_when_over_age(tmp_path) -> None:
    """死区(b)：pid token 缺失、ts 完好且超龄 → 按可疑处理允许自愈（此前恒按存活永不自愈）。"""
    db_path = os.path.join(str(tmp_path), "aps.db")
    lock_path = _write_lock(
        db_path, b"action=migrate ts=2000-01-01T00:00:00", age_seconds=_OVER_AGE_SECONDS
    )

    state = read_maintenance_lock_state(db_path)
    assert state is not None and state.get("pid") is None and state.get("age_source") == "ts", state

    assert is_maintenance_window_active(db_path, logger=_CollectingLogger()) is False
    assert not os.path.exists(lock_path)


def test_over_age_lock_with_live_pid_stays_active_and_leaves_trace(tmp_path) -> None:
    """死区(c)：超龄但 pid 判定存活（可能是 PID 复用）→ 保守不自愈，但必须留 warning 痕
    （锁路径 + 锁内容 + 判定依据），不得再无声卡死。"""
    db_path = os.path.join(str(tmp_path), "aps.db")
    live_pid = os.getpid()
    raw = f"pid={live_pid} action=restore ts=2000-01-01T00:00:00"
    lock_path = _write_lock(db_path, raw.encode("utf-8"), age_seconds=_OVER_AGE_SECONDS)

    logger = _CollectingLogger()
    assert is_maintenance_window_active(db_path, logger=logger) is True
    assert os.path.exists(lock_path), "pid 存活时不得自愈删除锁"
    traces = [m for m in logger.warnings if "维护锁已超过陈旧阈值" in m]
    assert traces, f"超龄未自愈必须留 warning 痕，实际日志：{logger.warnings}"
    assert lock_path in traces[0] and str(live_pid) in traces[0] and raw in traces[0], traces[0]


def test_fresh_torn_lock_stays_active_without_heal(tmp_path) -> None:
    """安全边界：刚写坏的新鲜锁（mtime 未超龄）保持 fail-closed（窗口活跃），不得被 mtime 兜底误自愈。"""
    db_path = os.path.join(str(tmp_path), "aps.db")
    lock_path = _write_lock(db_path, b"", age_seconds=0)

    logger = _CollectingLogger()
    assert is_maintenance_window_active(db_path, logger=logger) is True
    assert os.path.exists(lock_path)
    assert not any("维护锁已超过陈旧阈值" in m for m in logger.warnings), logger.warnings
