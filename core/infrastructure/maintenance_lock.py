"""数据库维护窗互斥锁（自 core/infrastructure/backup.py 拆出，公共 API 经 backup.py 原样再导出）。

职责：维护窗锁文件的创建/读取/自愈判定、进程内互斥、线程维护上下文。
安全方向保持 fail-closed：锁状态读取异常一律按『窗口活跃』处理并抛 MaintenanceWindowError。

自愈死区修复（B04，2026-07-19 盲区扫描）：
- ts 缺失/损坏/内容不可解码 → 用锁文件 mtime 兜底计算 age，不再永不自愈；
- 超龄锁的 pid 缺失/不可解析 → 按可疑处理（允许自愈），不再恒按存活；
- 超龄锁因 pid 判定存活而不自愈时（Windows 无法核对进程身份，PID 可能被复用）→
  记录 warning 留痕（锁路径 + 锁内容 + 判定依据），给现场人工处置提供线索。
"""

from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional

from core.infrastructure.migration_common import fallback_log
from core.infrastructure.safe_files import (
    create_fixed_file_exclusive,
    read_fixed_bytes,
    remove_fixed_file,
)

_MAINT_MUTEX = threading.RLock()
_MAINT_CONTEXT = threading.local()
_MAINT_LOCK_STALE_SECONDS = 300


class MaintenanceWindowError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = str(code or "").strip() or "maintenance_error"
        self.message = str(message or "数据库正在维护/恢复中，请稍后重试。")
        super().__init__(self.message)


def _maintenance_lock_path(db_path: str) -> str:
    return os.path.abspath(db_path) + ".maintenance.lock"


def _current_maintenance_state() -> Optional[dict]:
    state = getattr(_MAINT_CONTEXT, "state", None)
    if isinstance(state, dict):
        return state
    return None


def current_thread_holds_maintenance_window(db_path: str) -> bool:
    state = _current_maintenance_state()
    return bool(state and state.get("db_path") == os.path.abspath(db_path) and int(state.get("depth") or 0) > 0)


def _pid_exists(pid: Optional[int]) -> bool:
    try:
        pid_int = int(pid or 0)
    except Exception:
        return True
    if pid_int <= 0:
        return True
    if os.name == "nt":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid_int)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            err = int(ctypes.windll.kernel32.GetLastError() or 0)
            if err == 5:
                return True
            return False
        except Exception:
            return True
    try:
        os.kill(pid_int, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return True
    return True


def _empty_maintenance_lock_state(lock_path: str) -> dict:
    state = {
        "path": lock_path,
        "pid": None,
        "action": None,
        "ts": None,
        "age_seconds": None,
        "age_source": None,
        "raw": "",
    }
    return state


def _read_lock_file_text(lock_path: str, state: dict) -> Optional[str]:
    if not os.path.lexists(lock_path):
        raise FileNotFoundError(lock_path)
    try:
        raw = read_fixed_bytes(lock_path).decode("utf-8").strip()
    except FileNotFoundError:
        raise
    except Exception as e:
        state["read_error"] = e
        return None
    return raw


def _apply_maintenance_lock_token(state: dict, token: str) -> None:
    if "=" not in token:
        return
    key, value = token.split("=", 1)
    key = str(key or "").strip().lower()
    value = str(value or "").strip()
    if key == "pid":
        try:
            state["pid"] = int(value)
        except Exception:
            state["pid"] = None
    elif key == "action":
        state["action"] = value or None
    elif key == "ts":
        state["ts_text"] = value or None
        try:
            state["ts"] = datetime.fromisoformat(value)
        except Exception:
            state["ts"] = None


def _apply_maintenance_lock_age(state: dict) -> None:
    ts = state.get("ts")
    if isinstance(ts, datetime):
        try:
            state["age_seconds"] = max(0.0, (datetime.now() - ts).total_seconds())
            state["age_source"] = "ts"
            return
        except Exception:
            state["age_seconds"] = None
    # B04(a)：ts 缺失/损坏（含断电半写、内容不可解码）时用锁文件 mtime 兜底计算 age，
    # 否则 age 永远为 None、陈旧锁永不自愈。mtime 也拿不到时维持 fail-closed（按窗口活跃）。
    try:
        lock_mtime = os.lstat(str(state.get("path") or "")).st_mtime
        state["age_seconds"] = max(0.0, time.time() - float(lock_mtime))
        state["age_source"] = "mtime"
    except Exception:
        state["age_seconds"] = None
        state["age_source"] = None


def read_maintenance_lock_state(db_path: str) -> Optional[dict]:
    lock_path = _maintenance_lock_path(db_path)
    state = _empty_maintenance_lock_state(lock_path)
    try:
        raw = _read_lock_file_text(lock_path, state)
    except FileNotFoundError:
        return None
    if raw is not None:
        state["raw"] = raw
        for token in raw.split():
            _apply_maintenance_lock_token(state, token)
    _apply_maintenance_lock_age(state)
    return state


def _lock_age_value(state: dict) -> Optional[float]:
    age_seconds = state.get("age_seconds")
    if age_seconds is None:
        return None
    try:
        return float(age_seconds)
    except Exception:
        return None


def _should_auto_heal_lock(state: Optional[dict]) -> bool:
    if not isinstance(state, dict):
        return False
    age_value = _lock_age_value(state)
    if age_value is None:
        return False
    if age_value < float(_MAINT_LOCK_STALE_SECONDS):
        return False
    try:
        pid_int = int(state.get("pid"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        pid_int = 0
    if pid_int <= 0:
        # B04(b)：超龄锁的 pid 缺失/不可解析按可疑处理，允许自愈。
        # 此前 _pid_exists(None) 恒按存活，导致半写锁永久卡死维护窗。
        return True
    return not _pid_exists(pid_int)


def _log_stale_lock_kept_alive(state: dict, logger) -> None:
    """B04(c)：超龄锁因 pid 判定存活而不自愈时留痕（Windows 无法核对进程身份，PID 可能被复用）。"""
    age_value = _lock_age_value(state)
    if age_value is None or age_value < float(_MAINT_LOCK_STALE_SECONDS):
        return
    fallback_log(
        logger,
        "warning",
        "维护锁已超过陈旧阈值，但锁内 pid 判定为存活，继续按维护中处理："
        f"path={state.get('path')} pid={state.get('pid')} age_s={int(age_value)} "
        f"age_source={state.get('age_source')} raw={str(state.get('raw') or '')!r}；"
        "判定依据仅为 PID 存活（无法核对进程身份，PID 可能已被其它进程复用）。"
        "若确认维护进程已不存在，可手动删除该锁文件后重试。",
    )


def is_maintenance_window_active(db_path: str, *, logger=None) -> bool:
    if current_thread_holds_maintenance_window(db_path):
        return True
    try:
        state = read_maintenance_lock_state(db_path)
        if state is None:
            return False
        if _should_auto_heal_lock(state):
            lock_path = str(state.get("path") or _maintenance_lock_path(db_path))
            try:
                remove_fixed_file(lock_path)
                fallback_log(
                    logger,
                    "warning",
                    f"检测到陈旧维护锁，已自动清理：{lock_path}（pid={state.get('pid')} "
                    f"age_s={int(state.get('age_seconds') or 0)} age_source={state.get('age_source')} "
                    f"raw={str(state.get('raw') or '')!r}）",
                )
                return False
            except Exception as e:
                fallback_log(logger, "warning", f"陈旧维护锁自动清理失败：{e}（path={lock_path}）")
        else:
            _log_stale_lock_kept_alive(state, logger)
        return True
    except Exception as exc:
        fallback_log(logger, "warning", f"维护锁状态检测失败，已按不可确认处理并阻止继续：{exc}")
        raise MaintenanceWindowError("lock_state_unavailable", "系统维护锁状态检测失败，请稍后重试。") from exc


def ensure_backup_allowed(db_path: str, *, logger=None) -> None:
    if current_thread_holds_maintenance_window(db_path):
        return
    if is_maintenance_window_active(db_path, logger=logger):
        raise MaintenanceWindowError("busy", "数据库正在维护/恢复中，请稍后重试。")


def _enter_nested_maintenance_window(state: dict, db_abs: str) -> None:
    if state.get("db_path") != db_abs:
        raise MaintenanceWindowError("busy", "当前线程已有其他维护任务在执行，暂不支持跨数据库嵌套维护。")
    state["depth"] = int(state.get("depth") or 0) + 1


def _exit_nested_maintenance_window(state: dict) -> None:
    state["depth"] = max(0, int(state.get("depth") or 1) - 1)


def _acquire_maintenance_mutex() -> None:
    if not _MAINT_MUTEX.acquire(blocking=False):
        raise MaintenanceWindowError("busy", "数据库正在维护/恢复中，请稍后重试。")


def _write_maintenance_lock_metadata(lock_fd: int, payload: str) -> None:
    data = str(payload or "").encode("utf-8")
    written_total = 0
    while written_total < len(data):
        written = os.write(lock_fd, data[written_total:])
        if int(written or 0) <= 0:
            raise OSError("维护锁文件 metadata 写入不完整。")
        written_total += int(written)


def _cleanup_failed_maintenance_lock(lock_fd: Optional[int], lock_path: str, *, logger=None) -> None:
    if lock_fd is not None:
        try:
            os.close(lock_fd)
        except Exception as e:
            fallback_log(logger, "warning", f"维护锁创建失败后的句柄关闭失败：{e}")
    try:
        remove_fixed_file(lock_path)
    except Exception as e:
        fallback_log(logger, "warning", f"维护锁创建失败后的锁文件清理失败：{e}")


@contextmanager
def maintenance_window(db_path: str, *, logger=None, action: str = "maintenance") -> Iterator[None]:
    db_abs = os.path.abspath(db_path)
    state = _current_maintenance_state()
    if state is not None:
        _enter_nested_maintenance_window(state, db_abs)
        try:
            yield
        finally:
            _exit_nested_maintenance_window(state)
        return

    _acquire_maintenance_mutex()

    lock_path = _maintenance_lock_path(db_abs)
    lock_fd = None
    entered_root = False
    try:
        if is_maintenance_window_active(db_abs, logger=logger):
            raise MaintenanceWindowError("busy", "数据库正在维护/恢复中，请稍后重试。")
        try:
            lock_fd = create_fixed_file_exclusive(lock_path)
            try:
                _write_maintenance_lock_metadata(lock_fd, f"pid={os.getpid()} action={action} ts={datetime.now().isoformat()}")
            except Exception as e:
                _cleanup_failed_maintenance_lock(lock_fd, lock_path, logger=logger)
                lock_fd = None
                raise MaintenanceWindowError("lock_metadata_write_failed", f"维护锁文件写入失败：{e}") from e
        except FileExistsError as e:
            raise MaintenanceWindowError("busy", "数据库正在维护/恢复中，请稍后重试。") from e
        except MaintenanceWindowError:
            raise
        except Exception as e:
            raise MaintenanceWindowError("lock_failed", f"维护锁文件创建失败：{e}") from e

        _MAINT_CONTEXT.state = {"db_path": db_abs, "depth": 1, "lock_path": lock_path, "lock_fd": lock_fd}
        entered_root = True
        yield
    finally:
        if entered_root:
            try:
                delattr(_MAINT_CONTEXT, "state")
            except Exception as e:
                fallback_log(logger, "warning", f"维护线程上下文清理失败：{e}")
                try:
                    _MAINT_CONTEXT.state = None
                except Exception as cleanup_exc:
                    fallback_log(logger, "warning", f"维护线程上下文重置失败：{cleanup_exc}")
            if lock_fd is not None:
                try:
                    os.close(lock_fd)
                except Exception as e:
                    fallback_log(logger, "warning", f"维护锁文件句柄关闭失败：{e}")
            try:
                remove_fixed_file(lock_path)
            except Exception as e:
                fallback_log(logger, "warning", f"维护锁文件删除失败：{e}")
        try:
            _MAINT_MUTEX.release()
        except Exception as e:
            fallback_log(logger, "warning", f"维护互斥锁释放失败：{e}")
